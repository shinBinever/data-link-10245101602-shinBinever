from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from m3_tracks import (
    build_current_situation,
    build_tracks,
    decode_message_stream,
)


PACKAGE_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = PACKAGE_DIR / "data" / "partner_messages_multitime.bin"
TEMPLATE_DIR = PACKAGE_DIR / "templates"
OUTPUT_DIR = PACKAGE_DIR / "output"


def read_header(filename: str) -> list[str]:
    with (TEMPLATE_DIR / filename).open(
        "r",
        encoding="utf-8-sig",
        newline="",
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


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    records = decode_message_stream(INPUT_FILE.read_bytes())
    tracks = build_tracks(records)
    situations = build_current_situation(records)

    write_csv(
        OUTPUT_DIR / "decoded_multitime.csv",
        read_header("decoded_partner_states.csv"),
        records,
    )
    write_csv(
        OUTPUT_DIR / "track_table.csv",
        read_header("track_table.csv"),
        tracks,
    )
    write_csv(
        OUTPUT_DIR / "current_situation.csv",
        read_header("current_situation.csv"),
        situations,
    )

    valid_count = sum(
        record.get("message_valid") is True
        for record in records
    )

    print(f"解码记录数: {len(records)}")
    print(f"有效记录数: {valid_count}")
    print(f"航迹记录数: {len(tracks)}")
    print(f"当前态势目标数: {len(situations)}")


if __name__ == "__main__":
    main()