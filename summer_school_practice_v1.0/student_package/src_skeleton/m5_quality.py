from __future__ import annotations

from typing import Any


BATCH_TIME = 1710000120


def check_record(
    record: dict[str, Any],
    batch_time: int = BATCH_TIME,
) -> list[dict[str, Any]]:
    """检查位置缺失、时间延迟和航向越界。"""
    alerts: list[dict[str, Any]] = []

    target_id = record.get("target_id", "")
    lat = record.get("lat")
    lon = record.get("lon")
    heading = record.get("heading")

    record_time = record.get("latest_time")
    if record_time in (None, ""):
        record_time = record.get("timestamp")

    if lat in (None, "") or lon in (None, ""):
        alerts.append(
            {
                "alert_time": batch_time,
                "target_id": target_id,
                "alert_type": "POSITION_MISSING",
                "severity": "HIGH",
                "field": "lat/lon",
                "description": "纬度或经度缺失",
            }
        )

    if record_time not in (None, ""):
        delay = batch_time - int(record_time)
        if delay > 60:
            alerts.append(
                {
                    "alert_time": batch_time,
                    "target_id": target_id,
                    "alert_type": "DATA_DELAYED",
                    "severity": "MEDIUM",
                    "field": "timestamp",
                    "description": f"数据延迟{delay}秒，超过60秒",
                }
            )

    if heading not in (None, ""):
        heading_value = float(heading)
        if heading_value < 0 or heading_value >= 360:
            alerts.append(
                {
                    "alert_time": batch_time,
                    "target_id": target_id,
                    "alert_type": "HEADING_OUT_OF_RANGE",
                    "severity": "MEDIUM",
                    "field": "heading",
                    "description": f"航向值{heading_value}不在[0, 360)范围内",
                }
            )

    return alerts


def check_duplicates(
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """使用target_id+timestamp联合键检查重复。"""
    alerts: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()

    for record in records:
        target_id = str(record.get("target_id", ""))
        timestamp = int(record["timestamp"])
        key = (target_id, timestamp)

        if key in seen:
            alerts.append(
                {
                    "alert_time": BATCH_TIME,
                    "target_id": target_id,
                    "alert_type": "DUPLICATE_RECORD",
                    "severity": "MEDIUM",
                    "field": "target_id+timestamp",
                    "description": (
                        f"联合键重复：target_id={target_id}, "
                        f"timestamp={timestamp}"
                    ),
                }
            )
        else:
            seen.add(key)

    return alerts


def build_quality_situation(
    records: list[dict[str, Any]],
    alerts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """按HIGH > MEDIUM > NONE合成质量态势。"""
    situations: list[dict[str, Any]] = []

    key_counts: dict[tuple[str, int], int] = {}
    for record in records:
        key = (
            str(record.get("target_id", "")),
            int(record["timestamp"]),
        )
        key_counts[key] = key_counts.get(key, 0) + 1

    alerts_by_target: dict[str, list[dict[str, Any]]] = {}
    for alert in alerts:
        target_id = str(alert.get("target_id", ""))
        alerts_by_target.setdefault(target_id, []).append(alert)

    for record in records:
        target_id = str(record.get("target_id", ""))
        timestamp = int(record["timestamp"])
        lat = record.get("lat")
        lon = record.get("lon")
        heading = record.get("heading")

        target_alerts = alerts_by_target.get(target_id, [])
        alert_types = {
            str(alert.get("alert_type"))
            for alert in target_alerts
        }
        severities = {
            str(alert.get("severity"))
            for alert in target_alerts
        }

        duplicate_detected = (
            key_counts.get((target_id, timestamp), 0) > 1
        )

        position_valid = (
            lat not in (None, "")
            and lon not in (None, "")
        )
        delayed = "DATA_DELAYED" in alert_types
        heading_valid = (
            heading in (None, "")
            or 0 <= float(heading) < 360
        )

        if "HIGH" in severities:
            anomaly_level = "HIGH"
            display_status = "异常"
        elif "MEDIUM" in severities or duplicate_detected:
            anomaly_level = "MEDIUM"
            display_status = "关注"
        else:
            anomaly_level = "NONE"
            display_status = "正常"

        situations.append(
            {
                "target_id": target_id,
                "timestamp": timestamp,
                "position_valid": position_valid,
                "delayed": delayed,
                "duplicate_detected": duplicate_detected,
                "heading_valid": heading_valid,
                "message_valid": record.get(
                    "message_valid",
                    True,
                ),
                "anomaly_level": anomaly_level,
                "display_status": display_status,
            }
        )

    return situations
