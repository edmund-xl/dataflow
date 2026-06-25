# 中文版本

# DCP 自检说明

## 摘要

本文说明如何用一个脚本快速判断 DCP 是否可以提交。自检只读取工作簿和证据目录，不修改生产环境。

## 一、运行命令

首次使用前可以先检查本机环境：

```bash
scripts/doctor.sh
```

```bash
scripts/check_dcp.sh path/to/DCP_v0.1
```

如果需要指定 Python 解释器：

```bash
DATAFLOW_PYTHON=/path/to/python scripts/check_dcp.sh path/to/DCP_v0.1
```

如果需要指定输出目录：

```bash
scripts/check_dcp.sh path/to/DCP_v0.1 --output /tmp/agent_check
```

## 二、查看结果

默认输出目录：

```text
path/to/DCP_v0.1/agent_check/
```

先看 `check_summary.md`：

- `PASS`：没有阻断级校验问题。
- `NEEDS_FIX`：需要按 `fix_list.md` 修改源工作簿。
- `丢弃关系数量`：表示引用目标不存在或不完整导致未进入正式图的关系数量。

## 三、处理规则

不要直接修改生成报告或生成图。所有错误都应回到源工作簿修正，然后重新运行脚本。

---

# English Version

# DCP Self-Check Guide

## Abstract

This document explains how to quickly determine whether a DCP is ready for submission with one script. The self-check reads only the workbook and evidence folder and does not modify production environments.

## 1. Command

Before first use, check the local environment:

```bash
scripts/doctor.sh
```

```bash
scripts/check_dcp.sh path/to/DCP_v0.1
```

To use a specific Python interpreter:

```bash
DATAFLOW_PYTHON=/path/to/python scripts/check_dcp.sh path/to/DCP_v0.1
```

To specify the output directory:

```bash
scripts/check_dcp.sh path/to/DCP_v0.1 --output /tmp/agent_check
```

## 2. Review Results

Default output directory:

```text
path/to/DCP_v0.1/agent_check/
```

Read `check_summary.md` first:

- `PASS`: no blocking validation issue.
- `NEEDS_FIX`: correct the source workbook according to `fix_list.md`.
- `Dropped graph edges`: relationships that could not enter the formal graph because referenced endpoints are missing or incomplete.

## 3. Handling Rule

Do not edit generated reports or diagrams directly. Correct all errors in the source workbook and rerun the script.
