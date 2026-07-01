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

当前版本是规则驱动确定性 Agent。事实来源仅限 DevOps 或信息采集人员提交的 DCP 工作簿和证据目录；Agent 自动完成校验、归一化、建图、风险检查、出图、报告和打包。Agent 不凭空补依赖，不自动接受安全例外，不修改生产环境。后续外部系统同步、只读采集和版本 Diff 只作为路线图能力，不属于当前默认流程。

分层图采用内置专业渲染器生成：总览图和服务依赖图使用编号拓扑图，其他分层图使用统一的浅色 C4 架构配色。渲染不依赖外部图形命令，能够稳定生成 SVG、PNG、PDF、Mermaid 调试文件、draw.io 可编辑源图和 GraphML 工具交换文件。draw.io / GraphML 只用于展示和二次编辑，架构事实仍以源工作簿为准；如果关系需要变更，应修改 Excel/DCP 后重新生成。

总览图和服务依赖图采用主数据流编号视图：只展示真实数据流关系，图上线条以编号标识，右侧 `Edge ledger` 记录来源工作簿记录、关系类型、端口和源/目标对象，避免长标签压在线路上导致不可读。其他图层回到原始表现方式，优先保证整体视觉稳定和可交付。

## 四、脚本化使用流程

### 环境自检

首次使用或换机器后，先安装本地环境并执行自检：

```bash
scripts/setup_env.sh
export DATAFLOW_PYTHON="$(pwd)/.venv/bin/python"
scripts/doctor.sh
```

如需检查指定 DCP：

```bash
scripts/doctor.sh path/to/DCP_v0.1
```

Doctor 会检查 Python 版本、必要依赖、工作簿识别、工作簿读取、图构建和脚本可执行状态，并按 `READY / WARN / MISSING` 输出结果。

### 信息采集自检

信息采集人员填写或更新工作簿后执行：

```bash
scripts/check_dcp.sh samples/DCP_clean_v0.1
```

默认输出位置：

```text
samples/DCP_clean_v0.1/agent_check/
```

先阅读 `check_summary.md`。如果状态为 `NEEDS_FIX`，继续阅读 `fix_list.md`，修正源工作簿后再次执行脚本。需要从内容本身综合判断服务、依赖、数据资产、外部系统、网络、安全、监控、IAM、CI/CD 和证据问题时，阅读 `architecture_findings.md`；该报告直接分析 Excel/DCP 生成的 graph model，不依赖人工看图，并区分总览图就绪度、自动化问题和需要人工复核的审查观察项。

如需指定输出目录：

```bash
scripts/check_dcp.sh samples/DCP_clean_v0.1 --output /tmp/agent_check
```

### 单个采集包完整出包

当一个采集包已经准备好时执行：

```bash
scripts/build_dataflow_package.sh samples/DCP_clean_v0.1
```

默认输出位置：

```text
samples/DCP_clean_v0.1/dist/
```

如需指定输出目录：

```bash
scripts/build_dataflow_package.sh samples/DCP_clean_v0.1 --output /tmp/dataflow_dist
```

### 多个采集包汇总出包

数据汇总负责人收集多份 DCP 后执行：

```bash
scripts/merge_dcp.sh DCP_source_a DCP_source_b DCP_source_c
```

系统会生成合并工作簿、合并报告、完整数据流图交付包和压缩归档。

如需指定输出目录或生成冲突评审草稿：

```bash
scripts/merge_dcp.sh DCP_source_a DCP_source_b --output /tmp/dataflow_merge --allow-conflicts
```

### 单服务下钻图

需要查看单个服务上下游、运行实例、数据资产、安全控制和监控覆盖时执行：

```bash
scripts/build_service_drilldown.sh samples/DCP_clean_v0.1 svc-rpc-api
```

可选参数支持 `--depth`、`--direction upstream|downstream|both`、`--theme auto|light|dark|security` 和 `--risk-focus`，用于更精细的审查视图。

### 单服务端口查询

需要快速查看单个服务的监听端口、上下游依赖、防火墙规则和监控覆盖时执行：

```bash
scripts/query_service_ports.sh samples/DCP_clean_v0.1 svc-rpc-api
```

如需指定输出文件：

```bash
scripts/query_service_ports.sh samples/DCP_clean_v0.1 svc-rpc-api --output /tmp/service_ports.json
```

## 五、工程接口

脚本是日常使用入口。底层命令仍保留给开发和排错使用，包括 `check`、`quick-build`、`merge`、`drilldown`、`query-port`、`validate`、`normalize`、`build`、`risk`、`render`、`report`、`package` 和 `run`。

如需指定 Python 解释器，可使用环境变量：

```bash
DATAFLOW_PYTHON=/path/to/python scripts/check_dcp.sh samples/DCP_clean_v0.1
```

日常脚本会把已支持的 CLI 参数继续传给底层命令，例如 `--output`、`--env`、`--version`、`--allow-conflicts`、`--depth`、`--direction`、`--theme` 和 `--risk-focus`。

## 六、通用模板资料包

仓库提供通用数据流图模板资料包，位置为 `templates/dataflow_v1.0/`。该目录保存 v1.0 方案总文档、主数据采集模板、任务采集映射表、数据字典、样例输入、填写说明、智能体输入输出契约、演示图和嵌套模板包。

主要文件如下：

```text
templates/dataflow_v1.0/
  dataflow_project_final_plan_v1.0.docx
  dataflow_collection_template_bundle_v1.0.zip
  dataflow_main_collection_template_v1.0.xlsx
  dataflow_task_collection_mapping_v1.0.xlsx
  dataflow_data_dictionary_v1.0.xlsx
  dataflow_sample_input_v1.0.xlsx
  dataflow_collection_filling_guide_v1.0.docx
  dataflow_agent_io_contract_v1.0.md
  dataflow_overview_demo_v1.0.png
  dataflow_service_dependency_drilldown_demo_v1.0.png
  README.md
```

面向日常操作的短文档：

```text
CHANGELOG.md
docs/devops_dcp_collection_manual.md
docs/devops_collection_filling_guide.md
docs/dcp_self_check_guide.md
docs/package_generation_guide.md
```

当前默认可直接运行的干净样例位于 `samples/DCP_clean_v0.1/`，用于验证首次安装、自检、出包和合并的成功路径。`samples/DCP_v0.1/` 保留为风险演示样例，用于查看 `fix_list.md` 和风险报告效果。两份样例工作簿都已经预留 runtime 字段和显式依赖目标字段，包括 `Runtime_Type`、`Runtime_ID`、`Runtime_Name`、`Runtime_Namespace`、`Runtime_Cluster`、`Runtime_Region`、`Target_Type`、`Target_ID` 和 `Interaction_Mode`。

Schema 与模板兼容关系：

| 项目 | 当前值 | 说明 |
| --- | --- | --- |
| Python 包版本 | `0.1.1` | 当前代码版本，见 `pyproject.toml`。 |
| Workbook schema | `workbook_schema.v0.1` | Agent 校验和建图使用的结构化字段契约。 |
| Template package | `dataflow_template.v1.0` | `templates/dataflow_v1.0/` 中的通用模板资料包。 |

最终交付包的 `metadata.json` 会写入 `version`、`schema_version` 和 `template_version`，用于追踪代码、工作簿结构和模板资料的对应关系。

## 七、验证方法

项目通过自动化测试验证读取、校验、建图、渲染、报告、打包、自检脚本、构建脚本和合并脚本。验证命令如下：

```bash
python -m pytest -q
```

## 八、开源授权

本项目采用 MIT License 开源授权。版权归属 edmund-xl；使用者可以在遵守许可证条款的前提下复制、使用、修改、合并、发布、分发、再授权和销售本软件副本。完整授权文本见仓库根目录 `LICENSE` 文件。

## 九、结论

该智能体将 Dataflow Project 数据流图交付过程收敛为脚本化、结构化、可重复的工程流程。工作簿填写完成后能够即时反馈数据质量，汇总阶段能够自动合并与产出交付包，从而减少手工整理和手工画图带来的偏差。

## 十、不可变规则

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

The current version is a rule-driven deterministic agent. Its factual inputs are limited to DCP workbooks and evidence folders submitted by DevOps or information collection personnel; it automates validation, normalization, graph construction, risk checks, diagrams, reports, and packaging. The agent does not invent missing dependencies, does not automatically accept security exceptions, and does not modify production environments. External-system synchronization, read-only collection, and version diff are roadmap capabilities, not part of the default workflow.

Layered diagrams are generated by the built-in professional renderer: the overview and service dependency diagrams use numbered topology diagrams, while the other layered diagrams use the same light C4 architecture palette. Rendering does not depend on external graph commands and consistently produces SVG, PNG, PDF, Mermaid debug files, draw.io editable source files, and GraphML exchange files. draw.io and GraphML outputs are for presentation editing and tool import; the source workbook remains the factual source of truth. If a relationship changes, update the Excel/DCP and regenerate the package.

The overview and service dependency layers use numbered main-dataflow views: only real dataflow relationships are rendered, line labels are reduced to edge numbers, and the right-side `Edge ledger` records the source workbook row, relationship type, port, source object, and target object. Other layers return to the original rendering style to preserve a stable delivery appearance.

## 4. Script-First Workflow

### Environment Doctor

Before first use or after moving to another machine, set up the local environment and run the doctor:

```bash
scripts/setup_env.sh
export DATAFLOW_PYTHON="$(pwd)/.venv/bin/python"
scripts/doctor.sh
```

To check a specific DCP:

```bash
scripts/doctor.sh path/to/DCP_v0.1
```

The doctor checks the Python version, required dependencies, workbook detection, workbook reading, graph construction, and script executability, then reports `READY / WARN / MISSING`.

### Information Collection Self-Check

After filling in or updating the workbook, information collection personnel run:

```bash
scripts/check_dcp.sh samples/DCP_clean_v0.1
```

Default output path:

```text
samples/DCP_clean_v0.1/agent_check/
```

Read `check_summary.md` first. If the status is `NEEDS_FIX`, read `fix_list.md`, correct the source workbook, and run the script again. To review service, dependency, data asset, external system, network, security, monitoring, IAM, CI/CD, and evidence issues from the data itself, read `architecture_findings.md`; it directly analyzes the graph model generated from the Excel/DCP source, does not depend on manually reading diagrams, and separates executive overview readiness, automated findings, and human-review observations.

To specify the output directory:

```bash
scripts/check_dcp.sh samples/DCP_clean_v0.1 --output /tmp/agent_check
```

### Build One Complete Package

When one collection package is ready, run:

```bash
scripts/build_dataflow_package.sh samples/DCP_clean_v0.1
```

Default output path:

```text
samples/DCP_clean_v0.1/dist/
```

To specify the output directory:

```bash
scripts/build_dataflow_package.sh samples/DCP_clean_v0.1 --output /tmp/dataflow_dist
```

### Merge Multiple Collection Packages

After collecting multiple DCPs, the data aggregation owner runs:

```bash
scripts/merge_dcp.sh DCP_source_a DCP_source_b DCP_source_c
```

The system generates a merged workbook, a merge report, a complete data-flow package, and a compressed archive.

To specify the output directory or create a conflict-review draft:

```bash
scripts/merge_dcp.sh DCP_source_a DCP_source_b --output /tmp/dataflow_merge --allow-conflicts
```

### Single-Service Drilldown

To inspect one service's upstream and downstream relationships, runtime instance, data assets, security controls, and monitoring coverage, run:

```bash
scripts/build_service_drilldown.sh samples/DCP_clean_v0.1 svc-rpc-api
```

Optional arguments include `--depth`, `--direction upstream|downstream|both`, `--theme auto|light|dark|security`, and `--risk-focus` for more focused review views.

### Single-Service Port Query

To quickly inspect one service's listen ports, dependencies, firewall rules, and monitoring coverage, run:

```bash
scripts/query_service_ports.sh samples/DCP_clean_v0.1 svc-rpc-api
```

To specify the output file:

```bash
scripts/query_service_ports.sh samples/DCP_clean_v0.1 svc-rpc-api --output /tmp/service_ports.json
```

## 5. Engineering Interface

Scripts are the daily operation interface. Lower-level commands remain available for development and troubleshooting, including `check`, `quick-build`, `merge`, `drilldown`, `query-port`, `validate`, `normalize`, `build`, `risk`, `render`, `report`, `package`, and `run`.

To use a specific Python interpreter, set the environment variable:

```bash
DATAFLOW_PYTHON=/path/to/python scripts/check_dcp.sh samples/DCP_clean_v0.1
```

Daily scripts forward supported CLI arguments to the lower-level commands, including `--output`, `--env`, `--version`, `--allow-conflicts`, `--depth`, `--direction`, `--theme`, and `--risk-focus`.

## 6. Generic Template Package

The repository includes a generic data-flow template package at `templates/dataflow_v1.0/`. The directory contains the v1.0 final plan document, main collection template, task collection mapping, data dictionary, sample input, filling guide, agent input/output contract, demo diagrams, and nested template bundle.

Main files:

```text
templates/dataflow_v1.0/
  dataflow_project_final_plan_v1.0.docx
  dataflow_collection_template_bundle_v1.0.zip
  dataflow_main_collection_template_v1.0.xlsx
  dataflow_task_collection_mapping_v1.0.xlsx
  dataflow_data_dictionary_v1.0.xlsx
  dataflow_sample_input_v1.0.xlsx
  dataflow_collection_filling_guide_v1.0.docx
  dataflow_agent_io_contract_v1.0.md
  dataflow_overview_demo_v1.0.png
  dataflow_service_dependency_drilldown_demo_v1.0.png
  README.md
```

Short daily-operation documents:

```text
CHANGELOG.md
docs/devops_dcp_collection_manual.md
docs/devops_collection_filling_guide.md
docs/dcp_self_check_guide.md
docs/package_generation_guide.md
```

The default clean runnable sample is under `samples/DCP_clean_v0.1/` and is used to validate the successful first-run, self-check, package, and merge paths. `samples/DCP_v0.1/` remains as the risk-demo sample for reviewing `fix_list.md` and risk-report behavior. Both workbooks expose runtime fields and explicit dependency target fields, including `Runtime_Type`, `Runtime_ID`, `Runtime_Name`, `Runtime_Namespace`, `Runtime_Cluster`, `Runtime_Region`, `Target_Type`, `Target_ID`, and `Interaction_Mode`.

Schema and template compatibility:

| Item | Current value | Notes |
| --- | --- | --- |
| Python package version | `0.1.1` | Current code version in `pyproject.toml`. |
| Workbook schema | `workbook_schema.v0.1` | Structured field contract used by validation and graph generation. |
| Template package | `dataflow_template.v1.0` | Generic template package under `templates/dataflow_v1.0/`. |

The final package `metadata.json` records `version`, `schema_version`, and `template_version` so code, workbook structure, and template materials remain traceable.

## 7. Validation Method

Automated tests validate reading, validation, graph construction, rendering, reporting, packaging, self-check scripts, build scripts, and merge scripts. The validation command is:

```bash
python -m pytest -q
```

## 8. Open-Source License

This project is released under the MIT License. Copyright remains with edmund-xl, and users may copy, use, modify, merge, publish, distribute, sublicense, and sell copies of the software subject to the license terms. The full license text is available in the repository root `LICENSE` file.

## 9. Conclusion

The agent turns Dataflow Project data-flow delivery into a scripted, structured, and reproducible engineering workflow. The collection stage receives immediate quality feedback, and the aggregation stage automatically merges data and produces the final delivery package, reducing errors caused by manual assembly and manual diagramming.

## 10. Invariant Rule

The workbook is the only structured source of truth. If a diagram or report is wrong, correct the workbook and rerun the script. Do not manually edit generated artifacts.
