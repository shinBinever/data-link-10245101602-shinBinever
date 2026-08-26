# M6综合运行说明

## 基本信息

- 姓名：吴博萱
- 学号：10245101602
- GitHub用户名：shinBinever
- Python版本：3.14.2
- 是否使用SQLite：否
- M4候选来源：学校预生成候选

## 安装与运行

先按课程包 `environment/README_environment.md` 建立独立 `.venv`。在课程包根目录清空 `student_package/output/` 后执行：

```powershell
.\.venv\Scripts\python.exe student_package\src_skeleton\run_all.py
```

## 程序入口

统一入口为 `student_package/src_skeleton/run_all.py`。程序依次调用：

1. `run_m2.main()`：完成 OpenSky 状态解析、TeachingLink 编码、解码和验证；
2. `run_m3.main()`：完成多时刻消息解码、航迹关联和当前态势生成；
3. `m4_mapping.main()`：核验候选映射并生成统一态势消息；
4. `run_m5.main()`：执行一致性规则并生成告警和质量态势；
5. `export_results()`：确认 11 项关键输出均已生成且非空。

## 输入文件

- M2：`data/raw_states.json`；
- M3：`data/partner_messages_multitime.bin`；
- M4：`output/llm_mapping_candidate.csv`、`data/m4/partner_current_situation.csv`；
- M5：`data/m5/anomaly_cases.csv`、`data/m5/anomaly_rules.csv`。

## 输出文件

- M2：`encoded_messages.bin`、`decoded_partner_states.csv`、`validation_log.csv`、`roundtrip_report.csv`；
- M3：`decoded_multitime.csv`、`track_table.csv`、`current_situation.csv`；
- M4：`llm_mapping_candidate.csv`、`verified_mapping_table.csv`、`unified_situation.ndjson`；
- M5：`alert_log.csv`、`quality_situation.csv`；
- M6 展示材料：`docs/M6_presentation.pptx`。

## 实验结果

M2 共读取 5 条原始记录，成功编码 3 帧，生成 123 字节二进制数据；3 帧均成功解码，另生成 2 条验证日志和 21 条字段级往返检查记录。M3 解码 9 条多时刻记录，9 条消息均有效，形成 9 条航迹记录和 3 个目标的当前态势。M4 核验 8 条候选映射并生成 8 条正式映射，将 3 条当前态势转换为统一 NDJSON。M5 处理 6 条异常案例，产生 4 条告警，其中 HIGH 1 条、MEDIUM 3 条，告警类型分别为位置缺失、数据延迟、航向越界和联合键重复。未启用 SQLite，因此未进行数据库入库。

## 已知限制

本实验使用离线教学数据和 TeachingLink 教学协议，结果不代表生产数据链性能。SQLite 为选做功能，本次未启用。M4 使用学校预生成候选，但正式映射由程序规则核验后输出。未使用助教检查点替代本人前序模块成果。

## 最终提交信息

- 仓库链接：https://github.com/shinBinever/data-link-10245101602-shinBinever
- 最终commit ID：提交并推送后填写
- 最后检查日期：2026-08-26
