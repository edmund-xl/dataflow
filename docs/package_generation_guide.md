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

合并时，同主键完全相同的记录会自动去重；同主键但内容不同的记录会进入合并报告和字段级 `conflict_diff.xlsx`。默认存在冲突时不会生成最终交付包。若需要评审草稿，可使用底层命令追加 `--allow-conflicts`；草稿包采用 first-kept 值，`DRAFT_CONFLICTS.md` 会列出冲突主键、字段和值，草稿包不能用于最终验收。

## 三、交付内容

交付包包含归一化数据、图模型、丢弃关系审计、分层图、验证报告、风险台账、验收清单、元数据和压缩归档。

## 四、服务端口查询

如需单独查看服务端口、上下游依赖、防火墙和监控覆盖，可运行：

```bash
scripts/query_service_ports.sh path/to/DCP_v0.1 svc-rpc-api
```

如需指定输出文件：

```bash
scripts/query_service_ports.sh path/to/DCP_v0.1 svc-rpc-api --output /tmp/service_ports.json
```

服务下钻图支持更细粒度的审查参数：

```bash
scripts/build_service_drilldown.sh path/to/DCP_v0.1 svc-rpc-api --depth 2 --direction downstream --theme dark --risk-focus
```

## 五、后续路线图

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

Rows with the same primary key and identical content are de-duplicated automatically. Rows with the same primary key but different content are recorded in the merge report and field-level `conflict_diff.xlsx`; they must be resolved before final acceptance.

By default, conflicts prevent final package generation. To create a review draft, use the lower-level command with `--allow-conflicts`; the draft package uses first-kept values, `DRAFT_CONFLICTS.md` lists the conflicting keys, fields, and values, and draft packages must not be used for final acceptance.

## 3. Delivery Content

The package contains normalized data, graph models, dropped-edge audit data, layered diagrams, validation reports, risk registers, acceptance checklists, metadata, and a compressed archive.

## 4. Service Port Query

To inspect one service's ports, upstream/downstream dependencies, firewall rules, and monitoring coverage, run:

```bash
scripts/query_service_ports.sh path/to/DCP_v0.1 svc-rpc-api
```

To specify the output file:

```bash
scripts/query_service_ports.sh path/to/DCP_v0.1 svc-rpc-api --output /tmp/service_ports.json
```

Service drilldown diagrams support more granular review options:

```bash
scripts/build_service_drilldown.sh path/to/DCP_v0.1 svc-rpc-api --depth 2 --direction downstream --theme dark --risk-focus
```

## 5. Roadmap

Meegle synchronization, GCP read-only collection, and version diff are later-stage capabilities. The current default workflow does not connect to external systems or handle credentials.
