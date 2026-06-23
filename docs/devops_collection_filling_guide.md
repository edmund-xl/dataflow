# 中文版本

# DevOps 数据采集填写说明

## 摘要

本文给 DevOps 和信息采集人员使用，目标是把生产事实填写到标准 DCP 工作簿中，便于 Agent 自动校验、建图、报告和打包。

## 一、填写哪份文件

主工作簿必须使用标准文件名：

```text
dataflow_collection_template_v0.1.xlsx
```

不要把多个无标准名称的 Excel 放在同一个 DCP 目录中；如果确实需要使用其他文件名，请在脚本中直接传入工作簿路径。

## 二、填写原则

- 只填写已经确认或有证据支持的事实。
- 不确定的记录使用 `Pending_Confirmation`。
- 自动扫描得到但尚未人工确认的记录使用 `Auto_Detected`。
- 明确不适用的记录使用 `Not_Applicable`。
- 被拒绝的记录使用 `Rejected`，它不会进入正式图。
- 安全例外需要在问题或例外表中说明原因、责任人、到期时间和证据。

## 三、证据要求

每条关键记录都应能关联 `14_Evidence_Index` 中的证据 ID。证据可以是脱敏截图、配置片段、命令输出、审计记录或内部说明链接。

## 四、提交前检查

填写完成后运行：

```bash
scripts/check_dcp.sh path/to/DCP_v0.1
```

如果输出状态为 `NEEDS_FIX`，先修正源工作簿，再重新运行脚本。

---

# English Version

# DevOps Collection Filling Guide

## Abstract

This document is for DevOps and information collection personnel. Its purpose is to help users fill production facts into the standard DCP workbook so the agent can validate, model, render, report, and package the result automatically.

## 1. Workbook To Fill

The main workbook must use the standard file name:

```text
dataflow_collection_template_v0.1.xlsx
```

Do not place multiple non-standard Excel files in the same DCP directory. If another file name is required, pass the workbook path directly to the script.

## 2. Filling Rules

- Fill only facts that are confirmed or evidence-backed.
- Use `Pending_Confirmation` for uncertain records.
- Use `Auto_Detected` for automatically detected records that still need review.
- Use `Not_Applicable` for valid exclusions.
- Use `Rejected` for rejected records; they will not enter formal diagrams.
- Security exceptions must include reason, owner, due date, and evidence in the issue or exception sheet.

## 3. Evidence Requirements

Each key record should reference an evidence ID from `14_Evidence_Index`. Evidence may be a sanitized screenshot, configuration snippet, command output, audit record, or internal note link.

## 4. Pre-Submission Check

After filling the workbook, run:

```bash
scripts/check_dcp.sh path/to/DCP_v0.1
```

If the output status is `NEEDS_FIX`, correct the source workbook and rerun the script.
