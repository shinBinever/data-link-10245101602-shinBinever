from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from m5_quality import (
    check_duplicates,
    check_record,
    build_quality_situation,
)


PACKAGE_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = PACKAGE_DIR / "data" / "m5" / "anomaly_cases.csv"
TEMPLATE_DIR = PACKAGE_DIR / "templates"
OUTPUT_DIR = PACKAGE_DIR / "output"


def read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        return list(csv.DictReader(file))


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
    with path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    records = read_csv(INPUT_FILE)

    alerts: list[dict[str, Any]] = []
    for record in records:
        alerts.extend(check_record(record))

    alerts.extend(check_duplicates(records))

    situations = build_quality_situation(records, alerts)

    write_csv(
        OUTPUT_DIR / "alert_log.csv",
        read_header("alert_log.csv"),
        alerts,
    )
    write_csv(
        OUTPUT_DIR / "quality_situation.csv",
        read_header("quality_situation.csv"),
        situations,
    )

    type_counts: dict[str, int] = {}
    for alert in alerts:
        alert_type = str(alert["alert_type"])
        type_counts[alert_type] = (
            type_counts.get(alert_type, 0) + 1
        )

    high_count = sum(
        alert["severity"] == "HIGH"
        for alert in alerts
    )
    medium_count = sum(
        alert["severity"] == "MEDIUM"
        for alert in alerts
    )

    print(f"输入记录数: {len(records)}")
    print(f"告警总数: {len(alerts)}")
    print(f"按类型统计: {type_counts}")
    print(f"HIGH告警数: {high_count}")
    print(f"MEDIUM告警数: {medium_count}")
    print(f"质量态势记录数: {len(situations)}")


if __name__ == "__main__":
    main()