from __future__ import annotations

from typing import Any


FRAME_SIZE = 41

def _quantize(value: float) -> int:
    """按课程规范执行Q(y)=floor(y+0.5)。"""
    return int(value + 0.5)

def parse_state_vector(vector: list[Any]) -> dict[str, Any]:
    """将OpenSky状态向量转换为发送方内部结构化记录。"""
    if len(vector) < 17:
        raise ValueError("OpenSky状态向量长度不足17")

    target_id = vector[0]
    if not isinstance(target_id, str):
        raise TypeError("icao24必须是字符串")
    target_id = target_id.lower()
    if len(target_id) != 6:
        raise ValueError("icao24必须正好为6位十六进制字符")
    try:
        int(target_id, 16)
    except ValueError as exc:
        raise ValueError("icao24包含非十六进制字符") from exc

    time_position = vector[3]
    last_contact = vector[4]
    if time_position is not None:
        timestamp = time_position
        time_source = "position_time"
    elif last_contact is not None:
        timestamp = last_contact
        time_source = "last_contact_fallback"
    else:
        raise ValueError("time_position和last_contact不能同时为空")

    if not isinstance(timestamp, int) or isinstance(timestamp, bool):
        raise TypeError("timestamp必须是整数")
    if not 0 <= timestamp <= 0xFFFFFFFF:
        raise ValueError("timestamp超出uint32范围")

    on_ground = vector[8]
    if not isinstance(on_ground, bool):
        raise TypeError("on_ground必须是布尔值")

    callsign = vector[1]
    if callsign is not None:
        if not isinstance(callsign, str):
            raise TypeError("callsign必须是字符串或None")
        callsign = callsign.strip()
        if callsign == "":
            callsign = None
        else:
            try:
                callsign.encode("ascii")
            except UnicodeEncodeError as exc:
                raise ValueError("callsign必须只包含ASCII字符") from exc
            if len(callsign) > 8:
                raise ValueError("callsign长度不能超过8个字符")

    altitude = vector[7]
    if altitude is not None:
        alt_type = "barometric"
    else:
        altitude = vector[13]
        alt_type = "geometric" if altitude is not None else "unknown"

    record = {
        "target_id": target_id,
        "callsign": callsign,
        "timestamp": timestamp,
        "time_source": time_source,
        "lat": vector[6],
        "lon": vector[5],
        "altitude": altitude,
        "alt_type": alt_type,
        "speed": vector[9],
        "heading": vector[10],
        "vertical_rate": vector[11],
        "on_ground": on_ground,
    }

    ranges = {
        "lat": (-90.0, 90.0),
        "lon": (-180.0, 180.0),
        "altitude": (-1000.0, 64535.0),
        "speed": (0.0, 6553.5),
        "heading": (0.0, 359.99),
        "vertical_rate": (-327.68, 327.67),
    }

    for field, (minimum, maximum) in ranges.items():
        value = record[field]
        if value is None:
            continue
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError(f"{field}必须是数值或None")
        if not minimum <= value <= maximum:
            raise ValueError(f"{field}超出范围[{minimum}, {maximum}]")

    return record


def calculate_checksum(data_without_checksum: bytes) -> int:
    """计算前39字节无符号字节值之和模65536。"""
    if len(data_without_checksum) != 39:
        raise ValueError("校验和输入必须正好为39字节")
    return sum(data_without_checksum) % 65536


def encode_position_message(record: dict[str, Any], message_seq: int) -> bytes:
    """按41字节TeachingLink格式封装一条位置状态消息。"""
    if not isinstance(message_seq, int) or isinstance(message_seq, bool):
        raise TypeError("message_seq必须是整数")

    timestamp = record.get("timestamp")
    if not isinstance(timestamp, int) or isinstance(timestamp, bool):
        raise TypeError("timestamp必须是整数")
    if not 0 <= timestamp <= 0xFFFFFFFF:
        raise ValueError("timestamp超出uint32范围")

    target_id = record.get("target_id")
    if not isinstance(target_id, str) or len(target_id) != 6:
        raise ValueError("target_id必须是6位十六进制字符串")
    try:
        target_code = int(target_id, 16)
    except ValueError as exc:
        raise ValueError("target_id包含非十六进制字符") from exc

    on_ground = record.get("on_ground")
    if not isinstance(on_ground, bool):
        raise TypeError("on_ground必须是布尔值")

    alt_type = record.get("alt_type")
    if alt_type not in {"barometric", "geometric", "unknown"}:
        raise ValueError("alt_type取值无效")

    time_source = record.get("time_source")
    if time_source not in {"position_time", "last_contact_fallback"}:
        raise ValueError("time_source取值无效")

    frame = bytearray(FRAME_SIZE)

    frame[0:2] = (0x4453).to_bytes(2, "big")
    frame[2] = 1
    frame[3] = 1
    frame[4:6] = FRAME_SIZE.to_bytes(2, "big")
    frame[6:8] = (message_seq % 65536).to_bytes(2, "big")
    frame[8:12] = timestamp.to_bytes(4, "big")
    frame[12:15] = target_code.to_bytes(3, "big")

    validity_flags = 0

    callsign = record.get("callsign")
    if callsign is not None:
        if not isinstance(callsign, str):
            raise TypeError("callsign必须是字符串或None")
        callsign_bytes = callsign.encode("ascii")
        if not 1 <= len(callsign_bytes) <= 8:
            raise ValueError("有效callsign长度必须为1到8字节")
        frame[15:23] = callsign_bytes.ljust(8, b"\x00")
        validity_flags |= 1 << 6

    def put_optional(
        field: str,
        offset: int,
        length: int,
        flag_bit: int,
        minimum: float,
        maximum: float,
        transform,
    ) -> None:
        nonlocal validity_flags

        value = record.get(field)
        if value is None:
            return
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError(f"{field}必须是数值或None")
        if not minimum <= value <= maximum:
            raise ValueError(f"{field}超出范围[{minimum}, {maximum}]")

        code = _quantize(transform(float(value)))
        if not 0 <= code < (1 << (8 * length)):
            raise ValueError(f"{field}量化结果无法装入{length}字节")

        frame[offset : offset + length] = code.to_bytes(length, "big")
        validity_flags |= 1 << flag_bit

    put_optional(
        "lat", 23, 3, 0, -90.0, 90.0,
        lambda value: (value + 90.0) / 180.0 * ((1 << 22) - 1),
    )
    put_optional(
        "lon", 26, 3, 1, -180.0, 180.0,
        lambda value: (value + 180.0) / 360.0 * ((1 << 22) - 1),
    )
    put_optional(
        "altitude", 29, 2, 2, -1000.0, 64535.0,
        lambda value: value + 1000.0,
    )
    put_optional(
        "speed", 31, 2, 3, 0.0, 6553.5,
        lambda value: value / 0.1,
    )
    put_optional(
        "heading", 33, 2, 4, 0.0, 359.99,
        lambda value: value / 0.01,
    )
    put_optional(
        "vertical_rate", 35, 2, 5, -327.68, 327.67,
        lambda value: (value + 327.68) / 0.01,
    )

    status_flags = 0
    if on_ground:
        status_flags |= 1 << 0
    if alt_type == "geometric":
        status_flags |= 1 << 1
    if time_source == "last_contact_fallback":
        status_flags |= 1 << 2

    frame[37] = status_flags
    frame[38] = validity_flags

    checksum = calculate_checksum(bytes(frame[:39]))
    frame[39:41] = checksum.to_bytes(2, "big")

    return bytes(frame)


def decode_position_message(data: bytes) -> dict[str, Any]:
    """检查帧接收条件并恢复接收方结构化记录。"""
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("data必须是bytes或bytearray")

    errors: list[str] = []

    if len(data) != FRAME_SIZE:
        return {
            "message_valid": False,
            "validation_errors": "LENGTH_ERROR",
            "actual_length": len(data),
        }

    data = bytes(data)

    magic = int.from_bytes(data[0:2], "big")
    version = data[2]
    message_type = data[3]
    message_length = int.from_bytes(data[4:6], "big")
    message_seq = int.from_bytes(data[6:8], "big")
    timestamp = int.from_bytes(data[8:12], "big")
    target_code = int.from_bytes(data[12:15], "big")
    target_id = f"{target_code:06x}"

    callsign_bytes = data[15:23]
    latitude_raw = int.from_bytes(data[23:26], "big")
    longitude_raw = int.from_bytes(data[26:29], "big")
    altitude_code = int.from_bytes(data[29:31], "big")
    speed_code = int.from_bytes(data[31:33], "big")
    heading_code = int.from_bytes(data[33:35], "big")
    vertical_rate_code = int.from_bytes(data[35:37], "big")
    status_flags = data[37]
    validity_flags = data[38]
    checksum = int.from_bytes(data[39:41], "big")
    expected_checksum = calculate_checksum(data[:39])

    if magic != 0x4453:
        errors.append("MAGIC_ERROR")
    if version != 1:
        errors.append("VERSION_ERROR")
    if message_type != 1:
        errors.append("MESSAGE_TYPE_ERROR")
    if message_length != FRAME_SIZE:
        errors.append("LENGTH_ERROR")
    if checksum != expected_checksum:
        errors.append("CHECKSUM_ERROR")

    if latitude_raw & 0xC00000:
        errors.append("RESERVED_BITS_ERROR")
    if longitude_raw & 0xC00000:
        errors.append("RESERVED_BITS_ERROR")
    if status_flags & 0xF8:
        errors.append("RESERVED_BITS_ERROR")
    if validity_flags & 0x80:
        errors.append("RESERVED_BITS_ERROR")

    latitude_code = latitude_raw & 0x3FFFFF
    longitude_code = longitude_raw & 0x3FFFFF

    lat_valid = bool(validity_flags & (1 << 0))
    lon_valid = bool(validity_flags & (1 << 1))
    altitude_valid = bool(validity_flags & (1 << 2))
    speed_valid = bool(validity_flags & (1 << 3))
    heading_valid = bool(validity_flags & (1 << 4))
    vertical_rate_valid = bool(validity_flags & (1 << 5))
    callsign_valid = bool(validity_flags & (1 << 6))

    optional_values = (
        (lat_valid, latitude_raw),
        (lon_valid, longitude_raw),
        (altitude_valid, altitude_code),
        (speed_valid, speed_code),
        (heading_valid, heading_code),
        (vertical_rate_valid, vertical_rate_code),
        (callsign_valid, int.from_bytes(callsign_bytes, "big")),
    )
    for valid, raw_value in optional_values:
        if not valid and raw_value != 0:
            errors.append("FLAG_VALUE_INCONSISTENCY")

    callsign = None
    if callsign_valid:
        content = callsign_bytes.rstrip(b"\x00")
        padding = callsign_bytes[len(content):]

        if not content or b"\x00" in content:
            errors.append("ENCODING_ERROR")
        else:
            try:
                callsign = content.decode("ascii")
            except UnicodeDecodeError:
                errors.append("ENCODING_ERROR")

    scale_22 = (1 << 22) - 1

    lat = (
        latitude_code / scale_22 * 180.0 - 90.0
        if lat_valid else None
    )
    lon = (
        longitude_code / scale_22 * 360.0 - 180.0
        if lon_valid else None
    )
    altitude = altitude_code - 1000.0 if altitude_valid else None
    speed = speed_code * 0.1 if speed_valid else None
    heading = heading_code * 0.01 if heading_valid else None
    vertical_rate = (
        vertical_rate_code * 0.01 - 327.68
        if vertical_rate_valid else None
    )

    if heading_valid and not 0.0 <= heading < 360.0:
        errors.append("OUT_OF_RANGE")

    on_ground = bool(status_flags & (1 << 0))
    altitude_is_geometric = bool(status_flags & (1 << 1))
    timestamp_fallback = bool(status_flags & (1 << 2))

    if altitude_valid:
        alt_type = (
            "geometric" if altitude_is_geometric else "barometric"
        )
    else:
        alt_type = "unknown"

    time_source = (
        "last_contact_fallback"
        if timestamp_fallback else "position_time"
    )

    unique_errors = list(dict.fromkeys(errors))

    return {
        "target_id": target_id,
        "callsign": callsign,
        "timestamp": timestamp,
        "timestamp_source": time_source,
        "time_source": time_source,
        "message_seq": message_seq,
        "lat": lat,
        "lon": lon,
        "altitude": altitude,
        "alt_type": alt_type,
        "speed": speed,
        "heading": heading,
        "vertical_rate": vertical_rate,
        "on_ground": on_ground,
        "status_flags": status_flags,
        "validity_flags": validity_flags,
        "latitude_code": latitude_code,
        "longitude_code": longitude_code,
        "altitude_code": altitude_code,
        "speed_code": speed_code,
        "heading_code": heading_code,
        "vertical_rate_code": vertical_rate_code,
        "lat_valid": lat_valid,
        "lon_valid": lon_valid,
        "altitude_valid": altitude_valid,
        "speed_valid": speed_valid,
        "heading_valid": heading_valid,
        "vertical_rate_valid": vertical_rate_valid,
        "callsign_valid": callsign_valid,
        "checksum": checksum,
        "expected_checksum": expected_checksum,
        "message_valid": not unique_errors,
        "validation_errors": ";".join(unique_errors),
        "source": "TeachingLink",
    }
