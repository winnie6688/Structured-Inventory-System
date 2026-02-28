from __future__ import annotations

import base64
import json
import re
from abc import ABC, abstractmethod
from typing import Any

import httpx
from fastapi import UploadFile
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings
from app.schemas import ParsedRawRecord


class BaseMultimodalClient(ABC):
    @abstractmethod
    async def parse_image(self, file: UploadFile) -> list[ParsedRawRecord]:
        raise NotImplementedError


class MockMultimodalClient(BaseMultimodalClient):
    """Mock parser for local development.

    Strategy:
    1) If uploaded file body itself is JSON array, use it directly.
    2) Otherwise return one placeholder record.
    """

    async def parse_image(self, file: UploadFile) -> list[ParsedRawRecord]:
        raw_bytes = await file.read()
        await file.seek(0)

        try:
            payload = json.loads(raw_bytes.decode("utf-8"))
            if isinstance(payload, list):
                return [ParsedRawRecord(**item) for item in payload]
        except Exception:
            pass

        return [
            ParsedRawRecord(
                品类="",
                型号="",
                颜色="",
                尺码="",
                数量=1,
                作废=False,
                性别=None,
            )
        ]


class VolcengineMultimodalClient(BaseMultimodalClient):
    """Volcano Engine Ark multimodal parser.

    Expects OpenAI-compatible chat/completions format.
    """

    def __init__(self) -> None:
        if not settings.volcengine_api_key:
            raise ValueError("Missing VOLCENGINE_API_KEY")
        if not settings.volcengine_model:
            raise ValueError("Missing VOLCENGINE_MODEL")

        self.api_key = settings.volcengine_api_key
        self.model = settings.volcengine_model
        self.base_url = settings.volcengine_base_url.rstrip("/")
        self.timeout = settings.volcengine_timeout_seconds

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        reraise=True,
    )
    async def parse_image(self, file: UploadFile) -> list[ParsedRawRecord]:
        file_bytes = await file.read()
        await file.seek(0)

        mime_type = file.content_type or "image/jpeg"
        image_data_uri = self._to_data_uri(file_bytes, mime_type)

        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt()
        body = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {"type": "image_url", "image_url": {"url": image_data_uri}},
                    ],
                }
            ],
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        url = f"{self.base_url}/chat/completions"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()

        content_text = self._extract_content_text(data)
        payload = self._extract_json_array(content_text)
        records: list[ParsedRawRecord] = [ParsedRawRecord(**item) for item in payload]
        return records

    def _build_system_prompt(self) -> str:
        return (
            "你是鞋店库存单结构化提取助手。"
            "你的输出必须严格遵守: 只输出 JSON 数组，不要输出任何额外文本、注释或Markdown。"
            "抽取单位是“单个尺码记录”，同一型号若出现多个尺码，必须拆成多条记录。"
            "字段含义和规则如下:"
            "1) 字段固定: 品类, 型号, 颜色, 尺码, 数量, 作废, 性别。"
            "2) 下角标表示数量; 若尺码后无下角标，则数量=1。"
            "3) 尺码简写6/7/8/9/0，保持原样输出为字符串，不要在模型阶段展开。"
            "4) 若数字被X或斜杠划掉，则作废=true，否则false。"
            "5) 性别仅允许: 男/女/null。"
            "6) 无法识别的文本字段填空字符串，数量缺失时填1。"
            "7) 不要自行编造不存在的记录。"
        )

    def _build_user_prompt(self) -> str:
        return (
            "请解析这张库存图片并返回 JSON 数组，格式必须满足下方 JSON Schema。\\n"
            "JSON Schema:\\n"
            "{\\n"
            "  \\\"type\\\": \\\"array\\\",\\n"
            "  \\\"items\\\": {\\n"
            "    \\\"type\\\": \\\"object\\\",\\n"
            "    \\\"additionalProperties\\\": false,\\n"
            "    \\\"required\\\": [\\\"品类\\\", \\\"型号\\\", \\\"颜色\\\", \\\"尺码\\\", \\\"数量\\\", \\\"作废\\\", \\\"性别\\\"],\\n"
            "    \\\"properties\\\": {\\n"
            "      \\\"品类\\\": {\\\"type\\\": \\\"string\\\"},\\n"
            "      \\\"型号\\\": {\\\"type\\\": \\\"string\\\"},\\n"
            "      \\\"颜色\\\": {\\\"type\\\": \\\"string\\\"},\\n"
            "      \\\"尺码\\\": {\\\"type\\\": \\\"string\\\"},\\n"
            "      \\\"数量\\\": {\\\"type\\\": \\\"integer\\\", \\\"minimum\\\": 1},\\n"
            "      \\\"作废\\\": {\\\"type\\\": \\\"boolean\\\"},\\n"
            "      \\\"性别\\\": {\\\"type\\\": [\\\"string\\\", \\\"null\\\"], \\\"enum\\\": [\\\"男\\\", \\\"女\\\", null]}\\n"
            "    }\\n"
            "  }\\n"
            "}\\n"
            "仅返回 JSON 数组本体。"
        )

    @staticmethod
    def _to_data_uri(file_bytes: bytes, mime_type: str) -> str:
        encoded = base64.b64encode(file_bytes).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    @staticmethod
    def _extract_content_text(response: dict[str, Any]) -> str:
        choices = response.get("choices", [])
        if not choices:
            raise ValueError(f"Model response has no choices: {response}")

        message = choices[0].get("message", {})
        content = message.get("content")

        if isinstance(content, str):
            return content

        if isinstance(content, list):
            texts: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    texts.append(item.get("text", ""))
            return "\n".join(texts)

        raise ValueError(f"Unsupported model content format: {response}")

    @staticmethod
    def _extract_json_array(text: str) -> list[dict[str, Any]]:
        text = text.strip()

        # 1. Try simple json load
        try:
            payload = json.loads(text)
            if isinstance(payload, list):
                return payload
        except Exception:
            pass

        # 2. Try to find the outer-most brackets [ ... ]
        # This handles Markdown blocks, leading text, trailing text, etc.
        start = text.find("[")
        end = text.rfind("]")

        if start != -1 and end != -1 and end > start:
            candidate = text[start : end + 1]
            try:
                payload = json.loads(candidate)
                if isinstance(payload, list):
                    return payload
            except Exception:
                # 3. If that failed, maybe it has some simple syntax error?
                # For now, we just fail, but at least we tried to isolate the array.
                pass

        # 4. Fallback: try the old regex method just in case
        if text.startswith("```"):
            match = re.search(r"```(?:json)?\s*(\[.*\])\s*```", text, re.S)
            if match:
                try:
                    payload = json.loads(match.group(1))
                    if isinstance(payload, list):
                        return payload
                except Exception:
                    pass

        # 5. Last resort: raise error with snippet
        snippet = text[:200] + "..." if len(text) > 200 else text
        raise ValueError(f"Failed to extract JSON array from model output. Content start: {snippet}")


def get_multimodal_client() -> BaseMultimodalClient:
    provider = settings.multimodal_provider.strip().lower()
    if provider == "mock":
        return MockMultimodalClient()
    if provider == "volcengine":
        return VolcengineMultimodalClient()
    raise ValueError(f"Unsupported multimodal_provider: {settings.multimodal_provider}")
