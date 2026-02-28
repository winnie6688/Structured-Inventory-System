from __future__ import annotations

import json

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.schemas import ParsedRawRecord, ProcessResult
from app.services.feishu_client import FeishuClient
from app.services.multimodal_client import MockMultimodalClient, get_multimodal_client
from app.services.pipeline import InventoryPipeline

router = APIRouter(prefix="/api/v1/inventory", tags=["inventory"])


@router.post("/parse-sync", response_model=ProcessResult)
async def parse_and_sync(
    files: list[UploadFile] = File(default=[]),
    dry_run: bool = Form(default=False),
    manual_records_json: str | None = Form(default=None),
):
    """
    处理图片解析并同步到飞书。
    - 支持多文件上传
    - 支持 dry_run 仅解析不写入
    - 支持 manual_records_json 用于调试输入
    """
    if not files and not manual_records_json:
        raise HTTPException(status_code=400, detail="请至少上传1张图片，或提供手动输入记录")

    manual_records = None
    if manual_records_json:
        try:
            raw_data = json.loads(manual_records_json)
            # Pydantic validation
            if isinstance(raw_data, list):
                manual_records = [ParsedRawRecord(**item) for item in raw_data]
            else:
                raise ValueError("必须是 JSON 数组")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"手动输入记录格式错误: {exc}") from exc

    if files:
        try:
            parser_client = get_multimodal_client()
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    else:
        # manual_records_json-only mode does not require model provider config
        parser_client = MockMultimodalClient()

    pipeline = InventoryPipeline(
        parser_client=parser_client,
        feishu_client=FeishuClient(),
    )

    result = await pipeline.run(files=files, dry_run=dry_run, manual_records=manual_records)
    return result


@router.get("/health")
async def health_check():
    return {"status": "ok"}
