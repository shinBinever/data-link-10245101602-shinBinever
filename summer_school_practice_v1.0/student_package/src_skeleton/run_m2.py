from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from m2_protocol import (
    encode_position_message,
    parse_state_vector,
    decode_position_message,
)


PACKAGE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = PACKAGE_DIR / "data" / "raw_states.json"
TEMPLATE_DIR = PACKAGE_DIR / "templates"
OUTPUT_DIR = PACKAGE_DIR / "output"


def read_header(filename: str) -> list[str]:
    with (TEMPLATE_DIR / filename).open(
        "r", encoding="utf-8-sig", newline=""
    ) as file:
        return next(csv.reader(file))


def write_csv(
    path: Path,
    fieldnames: list[str],
    rows: list[dict[str, Any]],
) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


def classify_parse_error(exc: Exception) -> tuple[str, str]:
    message = str(exc)

    if "同时为空" in message:
        return "timestamp", "REQUIRED_FIELD_MISSING"
    if "超出范围" in message:
        return message.split("超出范围", 1)[0], "OUT_OF_RANGE"
    if "icao24" in message:
        return "target_id", "ENCODING_ERROR"
    if isinstance(exc, TypeError):
        return "record", "TYPE_ERROR"

    return "record", "ENCODING_ERROR"


def make_roundtrip_rows(
    source: dict[str, Any],
    decoded: dict[str, Any],
) -> list[dict[str, Any]]:
    specifications = {
        "callsign": ("callsign_valid", None, 0.0, 6),
        "lat": ("lat_valid", "latitude_code", 180.0 / ((1 << 22) - 1), 0),
        "lon": ("lon_valid", "longitude_code", 360.0 / ((1 << 22) - 1), 1),
        "altitude": ("altitude_valid", "altitude_code", 1.0, 2),
        "speed": ("speed_valid", "speed_code", 0.1, 3),
        "heading": ("heading_valid", "heading_code", 0.01, 4),
        "vertical_rate": (
            "vertical_rate_valid",
            "vertical_rate_code",
            0.01,
            5,
        ),
    }

    rows: list[dict[str, Any]] = []

    for field, (valid_key, code_key, tolerance, flag_bit) in specifications.items():
        source_value = source[field]
        decoded_value = decoded[field]
        source_valid = source_value is not None
        decoded_valid = decoded[valid_key]

        if code_key is None:
            protocol_code: Any = (
                source_value.encode("ascii").hex()
                if source_value is not None
                else ""
            )
        else:
            protocol_code = decoded[code_key] if source_valid else ""

        if source_value is None and decoded_value is None:
            error = 0.0
            passed = not decoded_valid
        elif isinstance(source_value, (int, float)) and isinstance(
            decoded_value, (int, float)
        ):
            error = abs(float(source_value) - float(decoded_value))
            passed = decoded_valid and error <= tolerance + 1e-12
        else:
            error = 0.0 if source_value == decoded_value else float("inf")
            passed = decoded_valid and source_value == decoded_value

        rows.append(
            {
                "field": field,
                "source_value": source_value,
                "source_valid": source_valid,
                "protocol_code": protocol_code,
                "flag_bit": flag_bit,
                "decoded_value": decoded_value,
                "decoded_valid": decoded_valid,
                "absolute_error/tolerance": f"{error}/{tolerance}",
                "passed": passed,
            }
        )

    return rows


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with DATA_FILE.open("r", encoding="utf-8") as file:
        states = json.load(file)["states"]

    frames: list[bytes] = []
    decoded_rows: list[dict[str, Any]] = []
    validation_rows: list[dict[str, Any]] = []
    roundtrip_rows: list[dict[str, Any]] = []

    for record_no, vector in enumerate(states, start=1):
        target_id = vector[0] if vector else ""

        try:
            source = parse_state_vector(vector)
            frame = encode_position_message(source, record_no)
            decoded = decode_position_message(frame)

            frames.append(frame)
            decoded_rows.append(decoded)
            roundtrip_rows.extend(make_roundtrip_rows(source, decoded))

            if not decoded["message_valid"]:
                validation_rows.append(
                    {
                        "record_no": record_no,
                        "target_id": target_id,
                        "stage": "decode",
                        "field": "frame",
                        "problem_type": decoded["validation_errors"],
                        "value": "",
                        "description": "帧未通过TeachingLink接收验证",
                    }
                )

        except (TypeError, ValueError) as exc:
            field, problem_type = classify_parse_error(exc)
            validation_rows.append(
                {
                    "record_no": record_no,
                    "target_id": target_id,
                    "stage": "parse",
                    "field": field,
                    "problem_type": problem_type,
                    "value": "",
                    "description": str(exc),
                }
            )

    (OUTPUT_DIR / "encoded_messages.bin").write_bytes(b"".join(frames))

    write_csv(
        OUTPUT_DIR / "decoded_partner_states.csv",
        read_header("decoded_partner_states.csv"),
        decoded_rows,
    )
    write_csv(
        OUTPUT_DIR / "validation_log.csv",
        read_header("validation_log.csv"),
        validation_rows,
    )
    write_csv(
        OUTPUT_DIR / "roundtrip_report.csv",
        read_header("roundtrip_report.csv"),
        roundtrip_rows,
    )

    print(f"输入记录数: {len(states)}")
    print(f"成功编码帧数: {len(frames)}")
    print(f"二进制字节数: {sum(map(len, frames))}")
    print(f"验证日志数: {len(validation_rows)}")
    print(f"往返检查数: {len(roundtrip_rows)}")


if __name__ == "__main__":
    main()