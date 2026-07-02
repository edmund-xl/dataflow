# 中文版本

# Dataflow Project 数据流图智能体

## 快速入口

日常只需要执行脚本。信息采集人员填写 DCP 工作簿后运行自检；数据汇总负责人收集多份 DCP 后运行合并或出包脚本。所有图、报告和压缩包都从同一份 Excel/DCP 生成。

```bash
scripts/setup_env.sh
export DATAFLOW_PYTHON="$(pwd)/.venv/bin/python"
scripts/check_dcp.sh samples/DCP_clean_v0.1
scripts/build_dataflow_package.sh samples/DCP_clean_v0.1
```

先看 `check_summary.md`。如果状态是 `NEEDS_FIX`，按 `fix_list.md` 回到源工作簿修正；如果需要判断服务、依赖、数据资产、外部系统、网络、安全、监控、IAM、CI/CD 和证据是否完整，读 `architecture_findings.md`。

## 核心原则

当前版本是规则驱动确定性 Agent。事实来源只包括 DCP 工作簿和证据目录；Agent 负责校验、归一化、建图、风险检查、出图、报告和打包。Agent 不凭空补依赖，不自动接受安全例外，不修改生产环境。后续外部系统同步、只读采集和版本 Diff 只作为路线图能力，不属于当前默认流程。

分层图采用专业渲染器生成：总览图、服务依赖图和安全/监控图使用“入口上下文 + 主数据流 + 控制摘要 / 覆盖矩阵 + edge ledger”的信息丰富视图，并优先通过 ELK layered orthogonal layout 进行主数据流排版；其他分层图使用统一的浅色 C4 架构配色。安全/监控图不把 Firewall、IAM、Monitoring 画成长穿越线，而是用节点覆盖标记、Security / Monitoring Ledger 和 Coverage Matrix 展示覆盖与风险。若 Node.js / elkjs 不可用，重点图层会回退到内置确定性布局。系统能够稳定生成 SVG、PNG、PDF、Mermaid 调试文件、draw.io 可编辑源图和 GraphML 工具交换文件。draw.io / GraphML 只用于展示和二次编辑，架构事实仍以源工作簿为准；如果关系需要变更，应修改 Excel/DCP 后重新生成。

总览图和服务依赖图只展示真实数据流主线，runtime、Firewall、IAM、Monitoring 作为上下文摘要展示，不伪装成主数据流。图上线条使用 ELK 正交路由和浅色 halo；端口、协议、状态、来源工作簿记录、关系类型和源/目标对象以碰撞避让的 inline edge detail 卡片展示，并同步保留在右侧 `Edge ledger` 中回溯，避免局部标签和线条堆叠。

## 脚本化使用流程

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

## 工程接口

脚本是日常使用入口。底层命令仍保留给开发和排错使用，包括 `check`、`quick-build`、`merge`、`drilldown`、`query-port`、`validate`、`normalize`、`build`、`risk`、`render`、`report`、`package` 和 `run`。

如需指定 Python 解释器，可使用环境变量：

```bash
DATAFLOW_PYTHON=/path/to/python scripts/check_dcp.sh samples/DCP_clean_v0.1
```

日常脚本会把已支持的 CLI 参数继续传给底层命令，例如 `--output`、`--env`、`--version`、`--allow-conflicts`、`--depth`、`--direction`、`--theme` 和 `--risk-focus`。

## 通用模板资料包

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

## 验证方法

项目通过自动化测试验证读取、校验、建图、渲染、报告、打包、自检脚本、构建脚本和合并脚本。验证命令如下：

```bash
python -m pytest -q
```

## 开源授权

本项目采用 MIT License 开源授权。版权归属 edmund-xl；使用者可以在遵守许可证条款的前提下复制、使用、修改、合并、发布、分发、再授权和销售本软件副本。完整授权文本见仓库根目录 `LICENSE` 文件。

## 不可变规则

工作簿是唯一结构化事实源。如果图或报告存在错误，必须修改工作簿并重新运行脚本，不允许手工修改生成产物。

---

# English Version

# Dataflow Project Dataflow Agent

## Quick Start

Daily use starts with scripts. Information collection personnel fill in the DCP workbook and run the self-check. The data aggregation owner collects multiple DCPs and runs build or merge scripts. Every diagram, report, and archive is generated from the same Excel/DCP source.

```bash
scripts/setup_env.sh
export DATAFLOW_PYTHON="$(pwd)/.venv/bin/python"
scripts/check_dcp.sh samples/DCP_clean_v0.1
scripts/build_dataflow_package.sh samples/DCP_clean_v0.1
```

Read `check_summary.md` first. If the status is `NEEDS_FIX`, correct the source workbook using `fix_list.md`. To review service, dependency, data asset, external system, network, security, monitoring, IAM, CI/CD, and evidence completeness, read `architecture_findings.md`.

## Core Rules

The current version is a rule-driven deterministic agent. Its factual inputs are limited to DCP workbooks and evidence folders. The agent validates, normalizes, builds graphs, checks risks, renders diagrams, writes reports, and packages outputs. It does not invent missing dependencies, does not automatically accept security exceptions, and does not modify production environments. External-system synchronization, read-only collection, and version diff remain roadmap capabilities.

Layered diagrams are generated by the professional renderer: the overview, service dependency, and security / monitoring diagrams use the information-rich "entry context + primary dataflow + control summary or coverage matrix + edge ledger" view and prefer ELK layered orthogonal layout for primary dataflow routing, while the other layered diagrams use the same light C4 architecture palette. The security / monitoring diagram does not draw Firewall, IAM, or Monitoring as long crossing dataflow lines; it shows them through node overlays, the Security / Monitoring Ledger, and the Coverage Matrix. If Node.js / elkjs is unavailable, the key diagrams fall back to the built-in deterministic layout. The system consistently produces SVG, PNG, PDF, Mermaid debug files, draw.io editable source files, and GraphML exchange files. draw.io and GraphML outputs are for presentation editing and tool import; the source workbook remains the factual source of truth. If a relationship changes, update the Excel/DCP and regenerate the package.

The overview and service dependency layers render only real primary dataflow lines. Runtime, Firewall, IAM, and Monitoring relationships stay as context summaries rather than primary dataflow. Lines use ELK orthogonal routing and a light halo; ports, protocols, status, source workbook rows, relationship types, source objects, and target objects are shown in collision-aware inline edge detail cards and also traced in the right-side `Edge ledger` to avoid local label and line stacking.

## Script-First Workflow

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

## Engineering Interface

Scripts are the daily operation interface. Lower-level commands remain available for development and troubleshooting, including `check`, `quick-build`, `merge`, `drilldown`, `query-port`, `validate`, `normalize`, `build`, `risk`, `render`, `report`, `package`, and `run`.

To use a specific Python interpreter, set the environment variable:

```bash
DATAFLOW_PYTHON=/path/to/python scripts/check_dcp.sh samples/DCP_clean_v0.1
```

Daily scripts forward supported CLI arguments to the lower-level commands, including `--output`, `--env`, `--version`, `--allow-conflicts`, `--depth`, `--direction`, `--theme`, and `--risk-focus`.

## Generic Template Package

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

## Validation Method

Automated tests validate reading, validation, graph construction, rendering, reporting, packaging, self-check scripts, build scripts, and merge scripts. The validation command is:

```bash
python -m pytest -q
```

## Open-Source License

This project is released under the MIT License. Copyright remains with edmund-xl, and users may copy, use, modify, merge, publish, distribute, sublicense, and sell copies of the software subject to the license terms. The full license text is available in the repository root `LICENSE` file.

## Invariant Rule

The workbook is the only structured source of truth. If a diagram or report is wrong, correct the workbook and rerun the script. Do not manually edit generated artifacts.
