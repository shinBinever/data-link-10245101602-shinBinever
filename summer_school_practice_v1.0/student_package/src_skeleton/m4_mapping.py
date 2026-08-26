from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


VERIFIED_RULES: dict[tuple[str, str], dict[str, str]] = {
    ("OpenSky", "target_id"): {
        "unified_field": "track_id",
        "mapping_rule": "转为六位小写十六进制字符串并保留前导0",
        "unit_conversion": "无",
        "null_strategy": "必需字段；缺失则拒绝记录",
        "evidence": "source_field_definitions.md: track_id",
    },
    ("OpenSky", "latest_time"): {
        "unified_field": "timestamp",
        "mapping_rule": "正整数Unix秒直接映射",
        "unit_conversion": "无",
        "null_strategy": "缺失或非正整数时time_valid=false",
        "evidence": "source_field_definitions.md: timestamp",
    },
    ("TeachingLink", "latitude_code+validity_flags.bit0"): {
        "unified_field": "position.lat",
        "mapping_rule": "bit0有效时按22位纬度公式恢复",
        "unit_conversion": "code/(2^22-1)*180-90 degree",
        "null_strategy": "bit0=0时为null",
        "evidence": "source_field_definitions.md: position.lat",
    },
    ("TeachingLink", "longitude_code+validity_flags.bit1"): {
        "unified_field": "position.lon",
        "mapping_rule": "bit1有效时按22位经度公式恢复",
        "unit_conversion": "code/(2^22-1)*360-180 degree",
        "null_strategy": "bit1=0时为null",
        "evidence": "source_field_definitions.md: position.lon",
    },
    ("TeachingLink", "altitude_code+validity_flags.bit2"): {
        "unified_field": "position.alt",
        "mapping_rule": "bit2有效时恢复物理高度",
        "unit_conversion": "code-1000 meter",
        "null_strategy": "bit2=0时为null",
        "evidence": "source_field_definitions.md: position.alt",
    },
    ("TeachingLink", "callsign"): {
        "input_field": "callsign+validity_flags.bit6",
        "unified_field": "identity.callsign",
        "mapping_rule": "bit6有效时去除补0和首尾空白",
        "unit_conversion": "无",
        "null_strategy": "bit6=0或清理后为空时为null",
        "evidence": "source_field_definitions.md: identity.callsign",
    },
    ("TeachingLink", "status_flags.bit2"): {
        "unified_field": "quality.time_source",
        "mapping_rule": "0=position_time, 1=last_contact_fallback",
        "unit_conversion": "无",
        "null_strategy": "状态位缺失时不得推断",
        "evidence": "source_field_definitions.md: quality.time_source",
    },
    ("TeachingLink", "message_valid"): {
        "unified_field": "quality.message_valid",
        "mapping_rule": "仅表示完整帧接收判据是否通过",
        "unit_conversion": "转为boolean",
        "null_strategy": "缺失时为false",
        "evidence": "source_field_definitions.md: quality.message_valid",
    },
}


def verify_candidate_mapping(candidate_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """依据课程权威字段定义，将候选行改写为正式、可追溯的映射。"""
    verified: list[dict[str, Any]] = []
    for candidate in candidate_rows:
        key = (str(candidate["source_format"]), str(candidate["input_field"]))
        if key not in VERIFIED_RULES:
            raise ValueError(f"没有权威依据的候选映射：{key}")
        verified.append({"source_format": key[0], "input_field": key[1], **VERIFIED_RULES[key], "verified": "true"})
    return verified


def _int(value: Any, default: int = 0) -> int:
    return default if value in (None, "") else int(value)


def _bool(value: Any) -> bool:
    return value if isinstance(value, bool) else str(value).strip().lower() in {"1", "true", "yes"}


def _nullable_float(value: Any) -> float | None:
    return None if value in (None, "") else float(value)


def map_to_unified(record: dict[str, Any], source_format: str) -> dict[str, Any]:
    """使用人工核验规则，将OpenSky或TeachingLink记录转换为统一态势。"""
    source = source_format.strip().lower()
    timestamp_value = (
        record.get("latest_time")
        if source == "opensky"
        else record.get("timestamp", record.get("latest_time"))
    )
    timestamp = _int(timestamp_value)

    if source == "teachinglink":
        validity = _int(record.get("validity_flags"))
        status = _int(record.get("status_flags"))
        lat = _int(record.get("latitude_code")) / (2**22 - 1) * 180 - 90 if validity & 1 else None
        lon = _int(record.get("longitude_code")) / (2**22 - 1) * 360 - 180 if validity & 2 else None
        altitude = float(_int(record.get("altitude_code")) - 1000) if validity & 4 else None
        speed = _int(record.get("speed_code")) * 0.1 if validity & 8 else None
        heading = _int(record.get("heading_code")) * 0.01 if validity & 16 else None
        vertical_rate = _int(record.get("vertical_rate_code")) * 0.01 - 327.68 if validity & 32 else None
        raw_callsign = str(record.get("callsign") or "").rstrip("\x00").strip()
        callsign = (raw_callsign or None) if validity & 64 else None
        alt_type = ("geometric" if status & 2 else "barometric") if altitude is not None else "unknown"
        time_source = "last_contact_fallback" if status & 4 else "position_time"
        on_ground = bool(status & 1)
        message_valid = _bool(record.get("message_valid"))
    elif source == "opensky":
        lat, lon = _nullable_float(record.get("lat")), _nullable_float(record.get("lon"))
        altitude = _nullable_float(record.get("altitude"))
        speed, heading = _nullable_float(record.get("speed")), _nullable_float(record.get("heading"))
        vertical_rate = _nullable_float(record.get("vertical_rate"))
        callsign = str(record.get("callsign") or "").strip() or None
        alt_type = str(record.get("alt_type") or "unknown") if altitude is not None else "unknown"
        time_source = str(record.get("time_source") or "position_time")
        on_ground = _bool(record.get("on_ground"))
        message_valid = _bool(record.get("message_valid"))
    else:
        raise ValueError(f"不支持的来源格式：{source_format}")

    position_valid = lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180
    return {
        "track_id": str(record.get("target_id") or "").strip().lower().zfill(6),
        "source": source,
        "timestamp": timestamp,
        "identity": {"callsign": callsign},
        "position": {"lat": lat, "lon": lon, "alt": altitude, "alt_type": alt_type},
        "motion": {"speed": speed, "heading": heading, "vertical_rate": vertical_rate},
        "status": {"on_ground": on_ground},
        "quality": {"position_valid": position_valid, "time_valid": timestamp > 0, "message_valid": message_valid, "time_source": time_source, "anomaly_flags": []},
    }


def main() -> int:
    output_dir = ROOT / "output"
    with (output_dir / "llm_mapping_candidate.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        verified = verify_candidate_mapping(list(csv.DictReader(handle)))
    with (output_dir / "verified_mapping_table.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(verified[0]))
        writer.writeheader()
        writer.writerows(verified)

    with (ROOT / "data" / "m4" / "partner_current_situation.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        unified = [map_to_unified(row, "TeachingLink") for row in csv.DictReader(handle)]
    with (output_dir / "unified_situation.ndjson").open("w", encoding="utf-8") as handle:
        for row in unified:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"M4完成：核验映射{len(verified)}条，统一态势{len(unified)}条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
