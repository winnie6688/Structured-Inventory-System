from __future__ import annotations

from collections import Counter

from app.schemas import ErrorType, InventoryRecord, ParsedRawRecord, ReviewRecord

SIZE_EXPAND_MAP = {
    "6": "36",
    "7": "37",
    "8": "38",
    "9": "39",
    "0": "40",
}

COLOR_NORMALIZE_MAP = {
    "米": "米色",
    "黑": "黑色",
    "棕": "棕色",
    "卡": "卡其",
    "杏": "杏色",
}

SIZE_RANGE = {
    "男": (38, 48),
    "女": (35, 43),
}


def normalize_color(color: str | None) -> str | None:
    if not color:
        return color
    return COLOR_NORMALIZE_MAP.get(color, color)


def expand_size_token(size: str | None) -> str | None:
    if not size:
        return size
    return SIZE_EXPAND_MAP.get(size, size)


def infer_gender_from_category(category: str | None) -> str | None:
    if not category:
        return None
    if "男" in category:
        return "男"
    if "女" in category:
        return "女"
    return None


def validate_and_transform(raw_records: list[ParsedRawRecord], skip_striked: bool = True):
    valid_records: list[InventoryRecord] = []
    review_records: list[ReviewRecord] = []
    error_counter: Counter[ErrorType] = Counter()

    for raw in raw_records:
        category = (raw.品类 or "").strip()
        model = (raw.型号 or "").strip()
        color = normalize_color((raw.颜色 or "").strip())
        size = expand_size_token((raw.尺码 or "").strip())
        qty = raw.数量 if raw.数量 is not None else 1

        if raw.作废:
            error_counter[ErrorType.STRIKED_OUT] += 1
            review_records.append(
                ReviewRecord(
                    品类=category or "未知",
                    型号=model or "未知",
                    颜色=color or "未知",
                    尺码=size or "未知",
                    数量=max(qty, 1),
                    异常原因="尺码被划掉(X/斜杠)",
                )
            )
            continue

        missing_fields = []
        if not category:
            missing_fields.append("品类")
        if not model:
            missing_fields.append("型号")
        if not color:
            missing_fields.append("颜色")
        if not size:
            missing_fields.append("尺码")

        if missing_fields:
            error_counter[ErrorType.FIELD_MISSING] += 1
            review_records.append(
                ReviewRecord(
                    品类=category or "未知",
                    型号=model or "未知",
                    颜色=color or "未知",
                    尺码=size or "未知",
                    数量=max(qty, 1),
                    异常原因=f"字段缺失: {','.join(missing_fields)}",
                )
            )
            continue

        if qty < 1:
            error_counter[ErrorType.INVALID_QTY] += 1
            review_records.append(
                ReviewRecord(
                    品类=category,
                    型号=model,
                    颜色=color,
                    尺码=size,
                    数量=1,
                    异常原因="数量必须>=1",
                )
            )
            continue

        gender = raw.性别 or infer_gender_from_category(category)
        if gender in SIZE_RANGE and size.isdigit():
            min_size, max_size = SIZE_RANGE[gender]
            size_int = int(size)
            if size_int < min_size or size_int > max_size:
                error_counter[ErrorType.SIZE_OUT_OF_RANGE] += 1
                review_records.append(
                    ReviewRecord(
                        品类=category,
                        型号=model,
                        颜色=color,
                        尺码=size,
                        数量=qty,
                        异常原因=f"{gender}鞋尺码超范围({min_size}-{max_size})",
                    )
                )
                continue

        valid_records.append(
            InventoryRecord(
                品类=category,
                型号=model,
                颜色=color,
                尺码=size,
                数量=qty,
            )
        )

    return valid_records, review_records, error_counter
