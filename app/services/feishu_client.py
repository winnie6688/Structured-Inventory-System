from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings
from app.schemas import InventoryRecord


class FeishuClient:
    def __init__(self) -> None:
        self.base_url = settings.feishu_base_url.rstrip("/")
        self.app_id = settings.feishu_app_id
        self.app_secret = settings.feishu_app_secret
        self.app_token = settings.feishu_bitable_app_token
        self.table_id = settings.feishu_bitable_table_id

    @property
    def enabled(self) -> bool:
        return all([self.app_id, self.app_secret, self.app_token, self.table_id])

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        reraise=True,
    )
    async def _get_tenant_access_token(self) -> str:
        url = f"{self.base_url}/open-apis/auth/v3/tenant_access_token/internal"
        payload = {"app_id": self.app_id, "app_secret": self.app_secret}

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        if data.get("code") != 0:
            raise RuntimeError(f"Failed to get feishu token: {data}")

        return data["tenant_access_token"]

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        reraise=True,
    )
    async def _post_batch(self, client: httpx.AsyncClient, url: str, headers: dict, body: dict) -> dict:
        resp = await client.post(url, headers=headers, json=body)
        resp.raise_for_status()
        return resp.json()

    async def write_records(self, records: list[InventoryRecord], task_id: str) -> tuple[int, list[dict[str, Any]]]:
        if not records:
            return 0, []

        if not self.enabled:
            return 0, [
                {
                    "error": "Feishu config missing",
                    "detail": "请配置 FEISHU_APP_ID/FEISHU_APP_SECRET/FEISHU_BITABLE_APP_TOKEN/FEISHU_BITABLE_TABLE_ID",
                }
            ]

        try:
            token = await self._get_tenant_access_token()
        except Exception as e:
            return 0, [{"error": f"Feishu auth failed: {e}"}]

        url = f"{self.base_url}/open-apis/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records/batch_create"
        headers = {"Authorization": f"Bearer {token}"}

        # Transform records to payload format
        payload_records = [
            {
                "fields": {
                    "品类": r.品类,
                    "型号": r.型号,
                    "颜色": r.颜色,
                    "尺码": r.尺码,
                    "数量": r.数量,
                    "任务ID": task_id,
                }
            }
            for r in records
        ]

        # Batch write in chunks of 100
        BATCH_SIZE = 100
        total_created = 0
        errors = []

        async with httpx.AsyncClient(timeout=30) as client:
            for i in range(0, len(payload_records), BATCH_SIZE):
                chunk = payload_records[i : i + BATCH_SIZE]
                body = {"records": chunk}

                try:
                    data = await self._post_batch(client, url, headers, body)

                    if data.get("code") != 0:
                        errors.append({"batch_index": i, "error": "Feishu write failed", "detail": data})
                        continue

                    # The response structure for batch_create is usually:
                    # {"code": 0, "data": {"records": [...]}}
                    created = data.get("data", {}).get("records", [])
                    total_created += len(created)
                except Exception as e:
                    errors.append({"batch_index": i, "error": f"Request failed: {str(e)}"})

        return total_created, errors
