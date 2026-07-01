# 中文版本

# 版本变更记录

本文记录 Dataflow Agent 的用户可见变更。历史开发内容按日期和提交批次归档，不倒填虚构版本号。

## Unreleased

### Changed

- 总览图和服务依赖图统一为“入口上下文 + 主数据流 + 控制摘要 + edge ledger”的信息丰富视图，并增强主数据流的分 lane 正交路由、线条 halo、编号标签和 ledger 回溯能力。

## 0.1.1 - 2026-07-01

### Added

- 新增 `scripts/doctor.sh`，用于首次使用或换机器后的环境自检，输出 `READY / WARN / MISSING`。
- 新增 `scripts/setup_env.sh`，用于创建本地 `.venv` 并安装开发/运行依赖。
- 新增 `samples/DCP_clean_v0.1/` 干净通过样例，保留 `samples/DCP_v0.1/` 作为风险演示样例。
- 样例 DCP 工作簿补齐 runtime 字段和显式依赖目标字段，便于直接填写 `Runtime_Type`、`Runtime_ID`、`Runtime_Name`、`Runtime_Namespace`、`Runtime_Cluster`、`Runtime_Region`、`Target_Type`、`Target_ID` 和 `Interaction_Mode`。

### Changed

- `scripts/check_dcp.sh` 和 `scripts/build_dataflow_package.sh` 支持透传 `--env`、`--version`、`--output` 等底层 CLI 参数。
- 通用 v1.0 模板资料包同步补齐 runtime / target / interaction 字段、数据字典说明和嵌套模板包内容。
- README、DCP 自检说明、交付包生成说明和 DevOps manual 增加环境自检与脚本自定义输出示例。
- Overview 数据流图改为 graph-truthful 编号主链路布局：主线只展示真实数据流 edge，runtime / Firewall / IAM / Monitoring 不伪装成主数据流。
- 自检摘要和修复清单改为操作型输出，先展示提交判断、关键指标和按严重度 / Sheet 分组的修复项。
- `query-port` JSON 输出增加 source row、Evidence_ID 和 graph edge 追踪信息。
- `metadata.json` 增加 `schema_version` 和 `template_version`，README 增加 schema / template 兼容关系。
- Overview renderer 拆分为独立模块，降低后续图形优化的维护风险。
- 分层图新增 draw.io `.drawio` 可编辑源图和 GraphML `.graphml` 工具交换文件，便于拖拽调整和导入专业图形工具。
- 服务依赖图改为主数据流编号视图：图上线条只显示编号，右侧 `Edge ledger` 展示来源记录、关系类型、端口和源/目标对象，降低线条标签重叠。
- 总览图同步改为主数据流编号视图，安全与监控图改为逐行关系视图，避免控制类关系大量交叉堆叠。
- 主数据流编号渲染改为先画线、再画节点、最后画编号，并将编号锚定到水平线段上，避免数字被线条覆盖。
- 安全与监控图改为与其他普通分层图一致的浅色 C4 配色；编号拓扑仅保留在总览图和服务依赖图。
- 新增 completeness/risk rule matrix，并扩展 `architecture_findings.md` / `architecture_findings.json`，直接基于 Excel/DCP 生成的 graph model、校验结果、风险结果和可审查事实，综合列出服务、依赖、数据资产、外部系统、网络、CI/CD、安全、监控、IAM、证据、覆盖矩阵、缺失与风险清单、真实数据流链路、问题分组、审查观察项和源表修复位置。
- 新增总览图就绪度判断，明确当前数据是否足以支撑会议级 executive overview；信息不足时列出缺失的入口边界、核心数据流、数据资产、外部依赖、网络出口、安全控制、监控、IAM、CI/CD 或证据来源。

### Fixed

- 修复 dependency 级监控关系在 graph builder 中可能形成 dropped edge 的问题。

## 0.1.0 - 2026-06-24

### Added

- 新增规则驱动确定性 Dataflow Agent，支持读取 DCP workbook、执行校验、归一化、建图、风险检查、渲染、报告和打包。
- 新增脚本优先入口：`scripts/check_dcp.sh`、`scripts/build_dataflow_package.sh`、`scripts/merge_dcp.sh`、`scripts/build_service_drilldown.sh`、`scripts/query_service_ports.sh`。
- 新增 CLI 命令：`check`、`quick-build`、`merge`、`drilldown`、`query-port`、`validate`、`normalize`、`build`、`risk`、`render`、`report`、`package`、`run`。
- 新增 `Dropped graph edges` 审计输出，避免非法引用或缺失目标关系被静默丢弃。
- 新增 `GraphEdge.metadata`，记录来源 sheet、记录 ID、状态、证据、风险标签和 runtime context。
- 新增字段级 `field-level conflict diff`，合并冲突会生成 `conflict_diff.xlsx`、`conflict_diff.json` 和 `DRAFT_CONFLICTS.md`。
- 新增 runtime / target / interaction optional 字段支持，包括 `Runtime_Type`、`Runtime_ID`、`Target_Type`、`Target_ID`、`Interaction_Mode`。
- 新增 service drilldown 图，支持 depth、direction、theme 和 risk-focus 参数。
- 新增 `query-port` 服务端口查询能力，可输出服务监听端口、上下游依赖、防火墙和监控覆盖。
- 新增 DevOps DCP Collection Manual，提供 Step-by-Step 信息采集说明。
- 新增通用数据流图模板资料包 `templates/dataflow_v1.0/`。

### Changed

- 图形渲染升级为内置 C4-style / security audit 风格，输出 SVG、PNG、PDF 和 Mermaid。
- Overview 图增加降噪逻辑，优先展示入口、P0/P1 服务、关键数据资产、外部依赖、安全和监控控制点。
- `query_service_ports.sh` 支持透传 `--output`，可自定义 JSON 输出路径。
- 工作簿选择策略更严格：标准文件名优先；多个非标准 workbook 时要求显式指定。
- 合并策略明确：相同主键且完全一致自动去重；相同主键字段不同默认阻断最终包；`--allow-conflicts` 只能生成 Draft package。

### Fixed

- 修复缺失引用可能导致图边静默丢失的问题。
- 修复 merge 冲突包中 first-kept 语义不清的问题。
- 修复脚本中个人 Python runtime 路径耦合问题，改为 `DATAFLOW_PYTHON` 或 `python3`。

### Security

- 项目切换为 MIT License。
- 新增 `SECURITY.md`、`DATA_HANDLING.md` 和 `scripts/scan_sensitive.sh`。
- 明确真实 DCP、真实证据、真实导出文件和生成交付包不得提交 Git。
- CI 中加入敏感信息扫描。

### Docs

- README 同步脚本优先使用方式、MIT License、模板包位置和日常操作入口。
- 新增 DevOps 填写说明、自检说明、汇总说明、交付包生成说明和 Step-by-Step manual。
- 文档保持中文在前、英文在后。

### Validation

- 新增 GitHub Actions CI，覆盖安装、敏感信息扫描、pytest、样例自检、样例出包、样例合并、服务下钻和 artifact 上传。
- 测试覆盖 schema、foreign key、Rejected / Pending 状态、图生成、七类图渲染、merge 冲突、service drilldown、query-port、文档格式和命名约束。

## 历史开发记录 - 2026-06-23 至 2026-06-24

### 2026-06-23

- `9dadfab`：Initial dataflow agent。建立 Python CLI、schema、normalizer、graph builder、risk checker、diagram renderer、report generator、packager、sample DCP 和基础测试。
- `bc2b0e0`：Use neutral role wording in docs。调整文档角色措辞，避免绑定不必要的岗位表述。
- `de17391`：Add generic dataflow template bundle。导入并清洗通用数据流图模板资料包。
- `4061b2b`：Switch to MIT open source license。加入标准 MIT License 并移除私有授权残留。
- `2293e6c`：Improve diagram rendering style。提升 demo 图形表现，采用更专业的架构图视觉风格。
- `ddec35d`：Harden script python and workbook selection。移除个人 runtime 路径，支持 `DATAFLOW_PYTHON`，增强 workbook 选择策略。
- `19c68ec`：Add security data handling safeguards。新增安全与数据处理文档、样例说明和敏感信息扫描。
- `c0ff735`：Add CI sample package validation。新增 GitHub Actions，覆盖核心脚本流程和样例 artifact。
- `5cd3e55`：Document deterministic agent workflow。明确 Agent 是规则驱动确定性工具，不凭空补依赖、不自动接受安全例外、不修改生产环境。
- `bd3f51d`：Add service drilldown diagrams。新增单服务上下游、运行实例、数据资产、安全控制和监控覆盖下钻图。
- `9983860`：Enhance risk reporting rules。增强 Cloud Armor、NAT、PSC / Peering、Firewall、IAM 和监控覆盖风险规则。
- `ee336a5`：Gate merge conflicts and track lineage。默认阻断未解决 merge 冲突，新增 lineage 报告和 Draft package 标记。
- `32d50ab`：Implement dataflow roadmap enhancements。新增 dropped edges、edge metadata、runtime/target/interaction 支持、field-level conflict diff、query-port、SVG 可访问风险标记和端到端测试。
- `2c5ed49`：Enhance drilldown review controls。增强 drilldown depth、direction、theme 和 risk-focus 控制。
- `3ea9d76`：Add DevOps DCP collection manual。新增 DevOps DCP Collection Manual，提供 Step-by-Step 信息采集流程。

### 2026-06-24

- `f064829`：Allow service port script output override。`query_service_ports.sh` 支持透传 `--output`，可自定义服务端口查询 JSON 输出路径。

## 版本维护规则

- 每次用户可见变更都必须更新本文件。
- 未发布变更先写入 `Unreleased`。
- 正式发版时，将 `Unreleased` 内容移动到对应版本号，并同步 `pyproject.toml`。
- 没有 tag 的历史提交只作为历史开发记录，不倒填虚构版本号。

---

# English Version

# Changelog

This file records user-visible changes to Dataflow Agent. Historical development work is archived by date and commit batch without inventing release versions.

## Unreleased

### Changed

- Unified the overview and service dependency diagrams around the information-rich entry-context, primary-dataflow, control-summary, and edge-ledger view, with stronger lane-based orthogonal routing, line halos, numbered labels, and ledger traceability for primary dataflow lines.

## 0.1.1 - 2026-07-01

### Added

- Added `scripts/doctor.sh` for first-use or new-machine environment checks with `READY / WARN / MISSING` output.
- Added `scripts/setup_env.sh` for creating a local `.venv` and installing runtime/development dependencies.
- Added `samples/DCP_clean_v0.1/` as a clean passing sample while keeping `samples/DCP_v0.1/` as a risk-demo sample.
- Added runtime fields and explicit dependency target fields to the sample DCP workbook, so users can directly fill `Runtime_Type`, `Runtime_ID`, `Runtime_Name`, `Runtime_Namespace`, `Runtime_Cluster`, `Runtime_Region`, `Target_Type`, `Target_ID`, and `Interaction_Mode`.

### Changed

- `scripts/check_dcp.sh` and `scripts/build_dataflow_package.sh` now forward lower-level CLI options such as `--env`, `--version`, and `--output`.
- Synchronized the generic v1.0 template package with runtime / target / interaction fields, data dictionary notes, and the nested template bundle.
- Updated README, DCP self-check guide, package generation guide, and DevOps manual with the environment doctor and custom output examples.
- Changed the overview data-flow diagram to a graph-truthful numbered main-flow layout: the main canvas renders only real dataflow edges, and runtime / Firewall / IAM / Monitoring relationships are not disguised as primary dataflow.
- Changed check summaries and fix lists to operational outputs with submission decisions, key metrics, and severity / sheet grouped findings first.
- Added source row, Evidence_ID, and graph edge traceability to `query-port` JSON output.
- Added `schema_version` and `template_version` to `metadata.json`; README now documents schema / template compatibility.
- Split the overview renderer into its own module to reduce diagram-renderer maintenance risk.
- Added draw.io `.drawio` editable source files and GraphML `.graphml` exchange files for layered diagrams, enabling drag editing and import into professional diagram tools.
- Changed the service dependency layer to a numbered main-dataflow view: lines show only edge numbers, while the right-side `Edge ledger` records source rows, relationship types, ports, and source/target objects to reduce label overlap.
- Changed the overview layer to the same numbered main-dataflow view and changed the security / monitoring layer to a row-based relationship view to avoid dense crossing control relationships.
- Changed numbered main-dataflow rendering to draw lines first, nodes second, and edge-number badges last, with badges anchored to horizontal edge segments so numbers are not covered by lines.
- Changed the security and monitoring layer to the same light C4 palette used by the other regular layered diagrams; numbered topology is kept only for the overview and service dependency diagrams.
- Added the completeness/risk rule matrix and expanded `architecture_findings.md` / `architecture_findings.json`, summarizing services, dependencies, data assets, external systems, network, CI/CD, security, monitoring, IAM, evidence, the coverage matrix, missing information and risk list, real dataflow paths, finding groups, review observations, and source-sheet fix locations directly from the graph model, validation findings, risk findings, and reviewable facts generated from the Excel/DCP source.
- Added executive overview readiness checks to state whether the collected data is sufficient for a meeting-level executive overview; when it is not, the report lists missing entry boundary, core dataflow, data assets, external dependencies, network egress, security controls, monitoring, IAM, CI/CD, or evidence inputs.

### Fixed

- Fixed dependency-level monitoring relationships that could otherwise create dropped graph edges.

## 0.1.0 - 2026-06-24

### Added

- Added the rule-driven deterministic Dataflow Agent for reading DCP workbooks, validation, normalization, graph construction, risk checks, rendering, reporting, and packaging.
- Added script-first entry points: `scripts/check_dcp.sh`, `scripts/build_dataflow_package.sh`, `scripts/merge_dcp.sh`, `scripts/build_service_drilldown.sh`, and `scripts/query_service_ports.sh`.
- Added CLI commands: `check`, `quick-build`, `merge`, `drilldown`, `query-port`, `validate`, `normalize`, `build`, `risk`, `render`, `report`, `package`, and `run`.
- Added `Dropped graph edges` audit output so invalid references or missing targets are not silently discarded.
- Added `GraphEdge.metadata` with source sheet, record ID, status, evidence, risk tags, and runtime context.
- Added `field-level conflict diff`; merge conflicts now produce `conflict_diff.xlsx`, `conflict_diff.json`, and `DRAFT_CONFLICTS.md`.
- Added optional runtime / target / interaction fields including `Runtime_Type`, `Runtime_ID`, `Target_Type`, `Target_ID`, and `Interaction_Mode`.
- Added service drilldown diagrams with depth, direction, theme, and risk-focus controls.
- Added `query-port` service port query output for listen ports, upstream/downstream dependencies, firewall rules, and monitoring coverage.
- Added the DevOps DCP Collection Manual with a Step-by-Step collection workflow.
- Added the generic data-flow template package under `templates/dataflow_v1.0/`.

### Changed

- Upgraded diagram rendering to built-in C4-style and security audit styles, emitting SVG, PNG, PDF, and Mermaid.
- Added overview denoising to prioritize entries, P0/P1 services, key data assets, external dependencies, security controls, and monitoring controls.
- `query_service_ports.sh` now forwards `--output`, allowing custom JSON output paths.
- Hardened workbook selection: standard names are preferred, and ambiguous non-standard workbooks require an explicit path.
- Clarified merge behavior: identical rows with the same key are de-duplicated; differing rows with the same key block final packages by default; `--allow-conflicts` creates Draft packages only.

### Fixed

- Fixed silent graph-edge drops for missing references.
- Fixed unclear first-kept semantics in draft merge packages.
- Removed personal Python runtime coupling from scripts; scripts now use `DATAFLOW_PYTHON` or `python3`.

### Security

- Switched the project to the MIT License.
- Added `SECURITY.md`, `DATA_HANDLING.md`, and `scripts/scan_sensitive.sh`.
- Documented that real DCPs, real evidence, raw exports, and generated delivery packages must not be committed to Git.
- Added sensitive data scanning to CI.

### Docs

- Updated README with script-first usage, MIT License, template package location, and daily operation entry points.
- Added DevOps filling guide, self-check guide, aggregation guide, package generation guide, and Step-by-Step manual.
- Kept repository documents Chinese first and English second.

### Validation

- Added GitHub Actions CI covering install, sensitive data scan, pytest, sample check, sample package build, sample merge, service drilldown, and artifact upload.
- Added tests for schema, foreign keys, Rejected / Pending statuses, graph generation, seven diagram views, merge conflicts, service drilldown, query-port, documentation format, and naming constraints.

## Historical Development Record - 2026-06-23 To 2026-06-24

### 2026-06-23

- `9dadfab`: Initial dataflow agent. Created the Python CLI, schema, normalizer, graph builder, risk checker, diagram renderer, report generator, packager, sample DCP, and baseline tests.
- `bc2b0e0`: Use neutral role wording in docs. Adjusted document role wording where required.
- `de17391`: Add generic dataflow template bundle. Imported and cleaned the generic data-flow template package.
- `4061b2b`: Switch to MIT open source license. Added the standard MIT License and removed private-license remnants.
- `2293e6c`: Improve diagram rendering style. Improved diagram visual quality with a more professional architecture style.
- `ddec35d`: Harden script python and workbook selection. Removed personal runtime paths, supported `DATAFLOW_PYTHON`, and strengthened workbook selection.
- `19c68ec`: Add security data handling safeguards. Added security and data-handling documents, sample notes, and sensitive-data scanning.
- `c0ff735`: Add CI sample package validation. Added GitHub Actions covering core script flows and sample artifacts.
- `5cd3e55`: Document deterministic agent workflow. Clarified that the agent is rule-driven and deterministic, does not invent dependencies, does not accept security exceptions automatically, and does not modify production environments.
- `bd3f51d`: Add service drilldown diagrams. Added single-service upstream/downstream, runtime, data asset, security control, and monitoring drilldown diagrams.
- `9983860`: Enhance risk reporting rules. Enhanced Cloud Armor, NAT, PSC / Peering, Firewall, IAM, and monitoring coverage risk rules.
- `ee336a5`: Gate merge conflicts and track lineage. Blocked unresolved merge conflicts by default and added lineage reporting and Draft package marking.
- `32d50ab`: Implement dataflow roadmap enhancements. Added dropped edges, edge metadata, runtime/target/interaction support, field-level conflict diff, query-port, accessible SVG risk markers, and end-to-end tests.
- `2c5ed49`: Enhance drilldown review controls. Added drilldown depth, direction, theme, and risk-focus controls.
- `3ea9d76`: Add DevOps DCP collection manual. Added the DevOps DCP Collection Manual with Step-by-Step collection guidance.

### 2026-06-24

- `f064829`: Allow service port script output override. `query_service_ports.sh` now forwards `--output` for custom service-port JSON output paths.

## Version Maintenance Rule

- Every user-visible change must update this file.
- Unreleased changes should be added to `Unreleased` first.
- On release, move `Unreleased` entries into the release version and update `pyproject.toml`.
- Historical commits without tags remain historical development records and must not be backfilled as fictional versions.
