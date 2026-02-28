from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class TaskStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"


class ErrorType(str, Enum):
    SIZE_OUT_OF_RANGE = "尺码超范围"
    FIELD_MISSING = "字段缺失"
    INVALID_QTY = "数量无效"
    STRIKED_OUT = "尺码被划掉(X/斜杠)"
    WRITE_FAILED = "写入飞书失败"
    PARSE_FAILED = "文件解析失败"


class InventoryRecord(BaseModel):
    品类: str = Field(..., min_length=1)
    型号: str = Field(..., min_length=1)
    颜色: str = Field(..., min_length=1)
    尺码: str = Field(..., min_length=1)
    数量: int = Field(..., ge=1)


class ReviewRecord(InventoryRecord):
    异常原因: str


class ParsedRawRecord(BaseModel):
    品类: str | None = None
    型号: str | None = None
    颜色: str | None = None
    尺码: str | None = None
    数量: int | None = None
    作废: bool = False
    性别: str | None = None  # 男 / 女 / None

    class Config:
        populate_by_name = True
        extra = "ignore"


class ErrorSummary(BaseModel):
    type: ErrorType
    count: int


class TaskSummary(BaseModel):
    image_count: int
    parsed_total: int
    valid_total: int
    invalid_total: int
    write_success: int
    write_failed: int
    review_total: int
    status: TaskStatus


class ProcessResult(BaseModel):
    task_id: str
    summary: TaskSummary
    valid_records: list[InventoryRecord]
    review_records: list[ReviewRecord]
    error_summary: list[ErrorSummary]
    debug: dict[str, Any] = Field(default_factory=dict)


class ManualRawInput(BaseModel):
    records: list[ParsedRawRecord]

    @field_validator("records")
    @classmethod
    def validate_not_empty(cls, value: list[ParsedRawRecord]) -> list[ParsedRawRecord]:
        if not value:
            raise ValueError("records cannot be empty")
        return value
