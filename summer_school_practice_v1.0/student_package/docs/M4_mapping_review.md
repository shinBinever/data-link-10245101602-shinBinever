# M4 AI辅助映射核验说明

- 候选来源：学校预生成候选。
- 使用的提示或候选文件：`reference/pre_generated_mapping_candidate.csv`，输出副本为 `output/llm_mapping_candidate.csv`。
- 发现的问题：候选将纬度和经度的统一字段写反；高度漏掉 `-1000 m` 偏置；呼号未检查 `validity_flags.bit6`；将 `status_flags.bit2` 错当成时间有效性，而该位实际表示时间来源。
- 人工修订依据：`schema/source_field_definitions.md`、`schema/partner_field_dictionary.csv`、`schema/teaching_message_spec.md` 和 `schema/unified_model.json`。正式映射逐条记录单位换算、空值策略、证据和 `verified=true`。
- 正常样例验证结果：`780abc` 解码为纬度约 `31.2503818°`、经度约 `121.4936689°`、高度 `9900 m`、速度 `231.5 m/s`，与输入表物理量一致。
- 真实零值验证：`000001` 的垂直速度编码 `32768` 经 `code*0.01-327.68` 恢复为 `0.0 m/s`，不会被误判为空值。
- 缺失值验证：`780def` 的纬度、经度、速度和呼号有效位为 0，统一态势中对应字段为 `null`，但有效的高度、航向和垂直速度仍保留。
- 语义边界：`message_valid` 仅表示帧结构、长度、校验和及标志一致性等接收判据通过，不代表来源可信或具备安全完整性。
- 不应由大模型自行决定的内容：协议位语义、比例因子和偏置、有效位、空值策略、质量字段含义均须由协议与字段定义确认。
