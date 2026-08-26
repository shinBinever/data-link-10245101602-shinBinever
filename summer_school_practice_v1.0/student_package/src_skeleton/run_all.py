from __future__ import annotations

from pathlib import Path

import m2_protocol
import m4_mapping
import run_m2
import run_m3
import run_m5


STUDENT_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = STUDENT_PACKAGE_ROOT / "output"


def prepare_output_directory() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)


def parse() -> None:
    # 现有 run_m2.main() 会连续完成解析、编码、解码和验证。
    run_m2.main()


def encode() -> None:
    pass


def decode_validate() -> None:
    pass


def build_tracks() -> None:
    run_m3.main()


def map_unified() -> None:
    result = m4_mapping.main()
    if result != 0:
        raise RuntimeError(f"M4运行失败，退出码：{result}")


def check_quality() -> None:
    run_m5.main()


def export_results() -> None:
    required_outputs = [
        "encoded_messages.bin",
        "decoded_partner_states.csv",
        "validation_log.csv",
        "roundtrip_report.csv",
        "decoded_multitime.csv",
        "track_table.csv",
        "current_situation.csv",
        "verified_mapping_table.csv",
        "unified_situation.ndjson",
        "alert_log.csv",
        "quality_situation.csv",
    ]
    missing = [
        name
        for name in required_outputs
        if not (OUTPUT_ROOT / name).is_file()
        or (OUTPUT_ROOT / name).stat().st_size == 0
    ]
    if missing:
        raise FileNotFoundError(f"缺少或为空的输出：{', '.join(missing)}")
    print(f"M6端到端运行完成，共生成并验证{len(required_outputs)}项关键成果。")


def run_pipeline() -> None:
    prepare_output_directory()
    parse()
    encode()
    decode_validate()
    build_tracks()
    map_unified()
    check_quality()
    export_results()


def main() -> int:
    try:
        run_pipeline()
    except NotImplementedError as exc:
        print(exc)
        print("当前文件是学生骨架，模块实现完成后再进行端到端运行。")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
