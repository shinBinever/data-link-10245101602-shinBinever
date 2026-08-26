from __future__ import annotations

from typing import Any

from m2_protocol import decode_position_message


def decode_message_stream(
    data: bytes,
    frame_size: int = 41,
) -> list[dict[str, Any]]:
    """按固定帧长批量解码；记录并忽略不完整尾帧。"""
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("data必须是bytes或bytearray")
    if not isinstance(frame_size, int) or isinstance(frame_size, bool):
        raise TypeError("frame_size必须是整数")
    if frame_size <= 0:
        raise ValueError("frame_size必须大于0")

    records: list[dict[str, Any]] = []

    for offset in range(0, len(data), frame_size):
        frame = bytes(data[offset : offset + frame_size])
        record = decode_position_message(frame)
        record["frame_no"] = offset // frame_size + 1
        records.append(record)

    return records


def save_records_to_sqlite(records: list[dict[str, Any]], db_path: str) -> None:
    """选做：保存接收记录，None必须写为NULL。"""
    raise NotImplementedError("M3选做：按optional_db_schema.sql实现写入、读取和简单查询。")


def build_tracks(
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """仅使用可接受记录，按target_id分组并按timestamp排序。"""
    acceptable_records = [
        record
        for record in records
        if record.get("message_valid") is True
        and isinstance(record.get("target_id"), str)
        and isinstance(record.get("timestamp"), int)
        and not isinstance(record.get("timestamp"), bool)
    ]

    acceptable_records.sort(
        key=lambda record: (
            record["target_id"],
            record["timestamp"],
        )
    )

    tracks: list[dict[str, Any]] = []
    sequence_by_target: dict[str, int] = {}

    for record in acceptable_records:
        target_id = record["target_id"]
        sequence_by_target[target_id] = (
            sequence_by_target.get(target_id, 0) + 1
        )

        track_record = dict(record)
        track_record["track_sequence_no"] = sequence_by_target[target_id]
        tracks.append(track_record)

    return tracks


def build_current_situation(
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """每个目标保留时间最新的可接受记录；可选字段缺失仍可入选。"""
    tracks = build_tracks(records)

    latest_by_target: dict[str, dict[str, Any]] = {}
    track_lengths: dict[str, int] = {}

    for record in tracks:
        target_id = record["target_id"]
        track_lengths[target_id] = track_lengths.get(target_id, 0) + 1

        current = latest_by_target.get(target_id)
        if (
            current is None
            or record["timestamp"] > current["timestamp"]
        ):
            latest_by_target[target_id] = record

    situations: list[dict[str, Any]] = []

    for target_id in sorted(latest_by_target):
        latest = dict(latest_by_target[target_id])
        latest["latest_time"] = latest["timestamp"]
        latest["track_length"] = track_lengths[target_id]
        situations.append(latest)

    return situations
