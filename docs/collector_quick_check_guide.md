# 中文版本

# 信息采集自检流程工程白皮书

## 摘要

本文面向 DevOps 和信息采集人员，说明如何使用一个脚本完成采集包质量自检。自检流程的目标是让使用者在提交前发现缺失字段、引用错误、证据缺失、待确认关系和关键链路风险，从而减少汇总阶段的返工。

## 关键词

信息采集；数据采集包；自检；修复清单；质量门禁。

## 一、适用范围

本文适用于负责填写 Dataflow Project 数据采集工作簿的 DevOps 和信息采集人员。使用者不需要理解底层命令，也不需要手工生成图或报告，只需要维护源工作簿并执行自检脚本。

Agent 是规则驱动确定性工具，只读取 DCP 工作簿和证据目录，不凭空补依赖、不自动接受安全例外、不修改生产环境。

## 二、输入要求

采集包至少应包含主工作簿：

```text
DCP_v0.1/
  dataflow_collection_template_v0.1.xlsx
```

建议同时保留原始导出、截图、配置片段、命令输出和说明文件，用于证据追溯。

## 三、自检方法

在项目根目录执行：

```bash
scripts/check_dcp.sh path/to/DCP_v0.1
```

也可以直接传入工作簿路径：

```bash
scripts/check_dcp.sh path/to/dataflow_collection_template_v0.1.xlsx
```

## 四、输出结果

默认输出目录为：

```text
path/to/DCP_v0.1/agent_check/
```

主要文件包括：

```text
check_summary.md
fix_list.md
architecture_findings.md
reports/validation_report.xlsx
reports/issue_risk_register.xlsx
reports/logic_mapping_validation_report.docx
```

## 五、结果判读

首先阅读 `check_summary.md`。如果状态为 `PASS`，说明没有阻断级校验问题。如果状态为 `NEEDS_FIX`，应阅读 `fix_list.md`，逐项修正源工作簿，再重新执行自检脚本。需要综合判断服务、依赖、数据资产、外部系统、网络、安全、监控、IAM、CI/CD 和证据问题时，阅读 `architecture_findings.md`；它直接基于 Excel/DCP 生成的 graph model，不要求先看图，并会列出自动化问题和需要人工复核的审查观察项。

## 六、开源授权

本项目采用 MIT License 开源授权。版权归属 edmund-xl；使用者可以在遵守许可证条款的前提下复制、使用、修改、分发和商用本软件副本。完整授权文本见仓库根目录 `LICENSE` 文件。

## 七、结论

该流程把采集质量判断前移到工作簿填写阶段。信息采集人员不需要手工汇总，也不需要手工画图；只需要根据修复清单完善源工作簿。

## 八、不可变规则

不要修改生成报告或生成图。所有修正必须回到源工作簿完成。

---

# English Version

# Information Collection Self-Check Workflow Engineering White Paper

## Abstract

This document is for DevOps and information collection personnel and explains how to validate a collection package with one script. The goal is to help users identify missing fields, broken references, missing evidence, pending relationships, and key-path risks before submission, thereby reducing rework during aggregation.

## Keywords

Data collection; Data Collection Package; self-check; fix list; quality gate.

## 1. Scope

This document applies to DevOps and information collection personnel who fill in the Dataflow Project collection workbook. Users do not need to understand lower-level commands or manually generate diagrams and reports. They only need to maintain the source workbook and run the self-check script.

The agent is rule-driven and deterministic. It only reads the DCP workbook and evidence folder; it does not invent missing dependencies, automatically accept security exceptions, or modify production environments.

## 2. Input Requirements

The collection package must contain at least the main workbook:

```text
DCP_v0.1/
  dataflow_collection_template_v0.1.xlsx
```

Raw exports, screenshots, configuration snippets, command outputs, and notes are recommended for evidence traceability.

## 3. Self-Check Method

Run the following command from the project root:

```bash
scripts/check_dcp.sh path/to/DCP_v0.1
```

The workbook path can also be passed directly:

```bash
scripts/check_dcp.sh path/to/dataflow_collection_template_v0.1.xlsx
```

## 4. Output

The default output directory is:

```text
path/to/DCP_v0.1/agent_check/
```

Main files include:

```text
check_summary.md
fix_list.md
architecture_findings.md
reports/validation_report.xlsx
reports/issue_risk_register.xlsx
reports/logic_mapping_validation_report.docx
```

## 5. Result Interpretation

Read `check_summary.md` first. If the status is `PASS`, there is no blocking validation issue. If the status is `NEEDS_FIX`, read `fix_list.md`, correct the source workbook item by item, and run the self-check script again. To review service, dependency, data asset, external system, network, security, monitoring, IAM, CI/CD, and evidence issues, read `architecture_findings.md`; it is based directly on the graph model generated from the Excel/DCP source, does not require reading diagrams first, and lists both automated findings and human-review observations.

## 6. Open-Source License

This project is released under the MIT License. Copyright remains with edmund-xl, and users may copy, use, modify, distribute, and use the software commercially subject to the license terms. The full license text is available in the repository root `LICENSE` file.

## 7. Conclusion

This workflow moves data-quality assessment into the workbook filling stage. Information collection personnel do not need to manually aggregate data or draw diagrams. They only need to improve the source workbook according to the fix list.

## 8. Invariant Rule

Do not edit generated reports or generated diagrams. All corrections must be made in the source workbook.
