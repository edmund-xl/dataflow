# 中文版本

# 交付包生成说明

## 摘要

本文给数据汇总负责人使用，说明如何从一个或多个 DCP 生成完整数据流图交付包。

## 一、单个 DCP 出包

```bash
scripts/build_dataflow_package.sh path/to/DCP_v0.1
```

默认输出：

```text
path/to/DCP_v0.1/dist/
```

## 二、多个 DCP 合并出包

```bash
scripts/merge_dcp.sh path/to/DCP_A path/to/DCP_B
```

合并时，同主键完全相同的记录会自动去重；同主键但内容不同的记录会进入合并报告，必须在最终验收前处理。

## 三、交付内容

交付包包含归一化数据、图模型、分层图、验证报告、风险台账、验收清单、元数据和压缩归档。

## 四、后续路线图

Meegle 同步、GCP 只读采集和版本 Diff 是后续阶段能力；当前默认流程不连接外部系统，也不处理凭证。

---

# English Version

# Package Generation Guide

## Abstract

This document is for the data aggregation owner and explains how to generate a complete data-flow delivery package from one or more DCPs.

## 1. Build One DCP

```bash
scripts/build_dataflow_package.sh path/to/DCP_v0.1
```

Default output:

```text
path/to/DCP_v0.1/dist/
```

## 2. Merge Multiple DCPs

```bash
scripts/merge_dcp.sh path/to/DCP_A path/to/DCP_B
```

Rows with the same primary key and identical content are de-duplicated automatically. Rows with the same primary key but different content are recorded in the merge report and must be resolved before final acceptance.

## 3. Delivery Content

The package contains normalized data, graph models, layered diagrams, validation reports, risk registers, acceptance checklists, metadata, and a compressed archive.

## 4. Roadmap

Meegle synchronization, GCP read-only collection, and version diff are later-stage capabilities. The current default workflow does not connect to external systems or handle credentials.
