# Dataflow Project 数据流图项目最终方案完整包 v1.0（中文翻译版）

本压缩包为中文翻译版，仅翻译原方案中的文字、字段和文件名，不改变方案内容。

## 文件清单

- `dataflow_project_final_plan_v1.0.docx`：完整方案总文档。
- `dataflow_collection_template_bundle_v1.0.zip`：数据采集模板包。
- `dataflow_main_collection_template_v1.0.xlsx`：DevOps 唯一需要填写的主采集表。
- `dataflow_task_collection_mapping_v1.0.xlsx`：Meegle 任务与采集工作表映射。
- `dataflow_data_dictionary_v1.0.xlsx`：字段、类型、必填、主外键、枚举和智能体用途。
- `dataflow_sample_input_v1.0.xlsx`：带演示数据的样例输入。
- `dataflow_collection_filling_guide_v1.0.docx`：DevOps 填写说明。
- `dataflow_agent_io_contract_v1.0.md`：智能体输入输出契约。
- `dataflow_overview_demo_v1.0.png`：总览图演示。
- `dataflow_service_dependency_drilldown_demo_v1.0.png`：服务依赖下钻演示。

## 使用方式

1. DevOps 只填写 `dataflow_main_collection_template_v1.0.xlsx`。
2. DevOps 同时提交原始导出、证据和说明文件。
3. 智能体读取主采集表和证据包，完成校验、建模、出图、报告和打包。
4. 如果图或报告有误，回到主采集表修正数据后重新生成，不手工修改图或报告。
