from __future__ import annotations

import asyncio
from collections import Counter
from datetime import datetime
from uuid import uuid4

from fastapi import UploadFile

from app.schemas import (
    ErrorSummary,
    ErrorType,
    ParsedRawRecord,
    ProcessResult,
    TaskStatus,
    TaskSummary,
)
from app.services.feishu_client import FeishuClient
from app.services.multimodal_client import BaseMultimodalClient
from app.services.rules import validate_and_transform
from app.config import settings


class InventoryPipeline:
    def __init__(self, parser_client: BaseMultimodalClient, feishu_client: FeishuClient) -> None:
        self.parser_client = parser_client
        self.feishu_client = feishu_client

    async def run(
        self,
        files: list[UploadFile],
        dry_run: bool = False,
        manual_records: list[ParsedRawRecord] | None = None,
    ) -> ProcessResult:
        task_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid4().hex[:6]
        all_raw_records: list[ParsedRawRecord] = []
        error_counter: Counter[ErrorType] = Counter()
        parse_errors: list[dict] = []

        if manual_records:
            all_raw_records.extend(manual_records)
        else:
            semaphore = asyncio.Semaphore(max(settings.parse_max_concurrency, 1))

            async def process_one(f: UploadFile):
                try:
                    async with semaphore:
                        return await self.parser_client.parse_image(f)
                except Exception as exc:
                    return exc

            results = await asyncio.gather(*(process_one(f) for f in files))

            for i, res in enumerate(results):
                if isinstance(res, Exception):
                    error_counter[ErrorType.PARSE_FAILED] += 1
                    parse_errors.append({"filename": files[i].filename, "error": str(res)})
                else:
                    all_raw_records.extend(res)

        valid_records, review_records, rule_errors = validate_and_transform(all_raw_records)
        error_counter.update(rule_errors)

        write_success = 0
        write_failed = 0
        debug: dict = {}
        if parse_errors:
            debug["parse_errors"] = parse_errors

        if not dry_run:
            write_success, write_errors = await self.feishu_client.write_records(valid_records, task_id)
            write_failed = max(len(valid_records) - write_success, 0)
            if write_errors:
                error_counter[ErrorType.WRITE_FAILED] += len(write_errors)
                debug["write_errors"] = write_errors

        parsed_total = len(all_raw_records)
        valid_total = len(valid_records)
        invalid_total = len(review_records)
        review_total = len(review_records)

        if parsed_total == 0 or (valid_total == 0 and review_total == 0):
            status = TaskStatus.FAILED
        elif (write_failed > 0) or (review_total > 0):
            status = TaskStatus.PARTIAL_SUCCESS
        else:
            status = TaskStatus.SUCCESS

        summary = TaskSummary(
            image_count=len(files),
            parsed_total=parsed_total,
            valid_total=valid_total,
            invalid_total=invalid_total,
            write_success=write_success if not dry_run else valid_total,
            write_failed=write_failed if not dry_run else 0,
            review_total=review_total,
            status=status,
        )

        error_summary = [
            ErrorSummary(type=error_type, count=count)
            for error_type, count in sorted(error_counter.items(), key=lambda x: x[0].value)
        ]

        if dry_run:
            debug["dry_run"] = True

        return ProcessResult(
            task_id=task_id,
            summary=summary,
            valid_records=valid_records,
            review_records=review_records,
            error_summary=error_summary,
            debug=debug,
        )
