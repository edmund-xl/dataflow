# 中文版本

# Dataflow Project 数据流图智能体工程白皮书

## 摘要

本文说明 Dataflow Project 数据流图智能体的建设目标、输入数据模型、自动化处理方法、脚本化使用流程和验证方式。该智能体面向生产环境数据流图交付场景，将信息采集、质量校验、关系建模、风险检查、图表生成、报告生成和交付包归档统一为一条可重复执行的工程流水线。日常使用以脚本为入口，信息采集人员填写工作簿并运行自检脚本，数据汇总负责人收集多份 DCP 并运行构建或合并脚本。

## 关键词

数据流图；结构化采集；自动校验；图模型；交付包；脚本化流程；可重复生成。

## 一、研究背景

Dataflow Project 生产环境涉及云项目、网络、服务器、服务、服务依赖、数据资产、防火墙、身份权限、监控和交付链路等多类对象。传统手工画图方式容易出现信息不完整、关系不可追溯、图表与事实源分离、报告修订不可重复等问题。为降低这些风险，本项目采用“采集表作为唯一结构化事实源，智能体自动生成产物”的方法。

## 二、系统目标

本系统的目标是把数据流图交付从人工整理转为自动化生产线。系统应当满足以下要求：信息采集人员能够快速自检工作簿质量；数据汇总负责人能够合并多份采集包；所有图、报告和归档包均由同一份结构化数据生成；任何产物错误都回到采集表修正，而不是手工修改生成文件。

## 三、方法设计

系统以数据采集包作为输入。采集包中的工作簿是唯一结构化输入，证据目录用于追溯和人工复核。智能体读取工作簿后执行模式校验、主键校验、外键校验、证据引用校验、核心链路检查、安全与监控检查，然后生成节点、边、图模型、分层图、验证报告、问题台账、验收清单和最终压缩包。

## 四、脚本化使用流程

### 信息采集自检

信息采集人员填写或更新工作簿后执行：

```bash
scripts/check_dcp.sh samples/DCP_v0.1
```

默认输出位置：

```text
samples/DCP_v0.1/agent_check/
```

先阅读 `check_summary.md`。如果状态为 `NEEDS_FIX`，继续阅读 `fix_list.md`，修正源工作簿后再次执行脚本。

### 单个采集包完整出包

当一个采集包已经准备好时执行：

```bash
scripts/build_dataflow_package.sh samples/DCP_v0.1
```

默认输出位置：

```text
samples/DCP_v0.1/dist/
```

### 多个采集包汇总出包

数据汇总负责人收集多份 DCP 后执行：

```bash
scripts/merge_dcp.sh DCP_source_a DCP_source_b DCP_source_c
```

系统会生成合并工作簿、合并报告、完整数据流图交付包和压缩归档。

## 五、工程接口

脚本是日常使用入口。底层命令仍保留给开发和排错使用，包括 `check`、`quick-build`、`merge`、`validate`、`normalize`、`build`、`risk`、`render`、`report`、`package` 和 `run`。

## 六、验证方法

项目通过自动化测试验证读取、校验、建图、渲染、报告、打包、自检脚本、构建脚本和合并脚本。验证命令如下：

```bash
python -m pytest -q
```

## 七、版权与授权

本项目版权归属 edmund-xl，并采用保留全部权利的私有授权。未经 edmund-xl 事先书面许可，不得复制、修改、合并、发布、分发、再授权、销售，或将本软件用于商业或生产目的。完整授权文本见仓库根目录 `LICENSE` 文件。

## 八、结论

该智能体将 Dataflow Project 数据流图交付过程收敛为脚本化、结构化、可重复的工程流程。工作簿填写完成后能够即时反馈数据质量，汇总阶段能够自动合并与产出交付包，从而减少手工整理和手工画图带来的偏差。

## 九、不可变规则

工作簿是唯一结构化事实源。如果图或报告存在错误，必须修改工作簿并重新运行脚本，不允许手工修改生成产物。

---

# English Version

# Dataflow Project Dataflow Agent Engineering White Paper

## Abstract

This document describes the purpose, input model, automated processing method, script-first workflow, and validation approach of the Dataflow Project Dataflow Agent. The agent supports production data-flow deliverables by turning data collection, quality validation, relationship modeling, risk checks, diagram rendering, report generation, and package archiving into a repeatable engineering pipeline. Daily operation starts from scripts: information collection personnel fill in the workbook and run one self-check script, while the data aggregation owner collects multiple DCPs and runs one build or merge script.

## Keywords

Data flow diagram; structured collection; automated validation; graph model; delivery package; script-first workflow; reproducible generation.

## 1. Background

The Dataflow Project production environment contains cloud projects, networks, servers, services, dependencies, data assets, firewall rules, identity permissions, monitoring controls, and delivery paths. Manual diagramming is prone to missing data, untraceable relationships, separation between diagrams and source facts, and non-reproducible report revisions. This project therefore uses the workbook as the single structured source of truth and lets the agent generate all artifacts automatically.

## 2. Objectives

The objective is to turn data-flow delivery from manual assembly into an automated production line. Information collection personnel should be able to validate workbook quality quickly. The data aggregation owner should be able to merge multiple collection packages. Every diagram, report, and archive should be generated from the same structured data. Any artifact error must be corrected in the workbook and regenerated, not manually edited in the output.

## 3. Method

The system consumes a Data Collection Package. The workbook is the only structured input, while evidence folders are used for traceability and manual review. After reading the workbook, the agent performs schema validation, primary-key checks, foreign-key checks, evidence-reference checks, core-link checks, security and monitoring checks, and then generates nodes, edges, graph models, layered diagrams, validation reports, issue registers, acceptance checklists, and the final archive.

## 4. Script-First Workflow

### Information Collection Self-Check

After filling in or updating the workbook, information collection personnel run:

```bash
scripts/check_dcp.sh samples/DCP_v0.1
```

Default output path:

```text
samples/DCP_v0.1/agent_check/
```

Read `check_summary.md` first. If the status is `NEEDS_FIX`, read `fix_list.md`, correct the source workbook, and run the script again.

### Build One Complete Package

When one collection package is ready, run:

```bash
scripts/build_dataflow_package.sh samples/DCP_v0.1
```

Default output path:

```text
samples/DCP_v0.1/dist/
```

### Merge Multiple Collection Packages

After collecting multiple DCPs, the data aggregation owner runs:

```bash
scripts/merge_dcp.sh DCP_source_a DCP_source_b DCP_source_c
```

The system generates a merged workbook, a merge report, a complete data-flow package, and a compressed archive.

## 5. Engineering Interface

Scripts are the daily operation interface. Lower-level commands remain available for development and troubleshooting, including `check`, `quick-build`, `merge`, `validate`, `normalize`, `build`, `risk`, `render`, `report`, `package`, and `run`.

## 6. Validation Method

Automated tests validate reading, validation, graph construction, rendering, reporting, packaging, self-check scripts, build scripts, and merge scripts. The validation command is:

```bash
python -m pytest -q
```

## 7. Copyright And License

This project is proprietary to edmund-xl and all rights are reserved. No permission is granted to copy, modify, merge, publish, distribute, sublicense, sell, or use this software for commercial or production purposes without prior written permission from edmund-xl. The full license text is available in the repository root `LICENSE` file.

## 8. Conclusion

The agent turns Dataflow Project data-flow delivery into a scripted, structured, and reproducible engineering workflow. The collection stage receives immediate quality feedback, and the aggregation stage automatically merges data and produces the final delivery package, reducing errors caused by manual assembly and manual diagramming.

## 9. Invariant Rule

The workbook is the only structured source of truth. If a diagram or report is wrong, correct the workbook and rerun the script. Do not manually edit generated artifacts.
