# 中文版本

# DevOps DCP 信息采集 Step-by-Step Manual

## 使用方式

本 manual 给第一次填写 DCP 的 DevOps 或信息采集人员使用。请按 Step 0 到 Step 11 顺序完成；不要手工修改 Agent 生成的图、报告或交付包，所有修正都回到源 Excel。

首次使用前，在仓库根目录运行环境自检：

```bash
scripts/doctor.sh
```

## Step 0：准备 DCP 目录

创建一个独立目录，例如：

```text
DCP_v0.1/
  dataflow_collection_template_v0.1.xlsx
  raw_exports/
  evidence/
  notes/
```

合格标准：

- `dataflow_collection_template_v0.1.xlsx` 是主工作簿。
- `raw_exports/` 放脱敏后的导出文件。
- `evidence/` 放脱敏截图、配置片段、命令输出或审计记录。
- `notes/` 放待确认说明和已知例外说明。
- 不要把真实生产 DCP、真实证据、真实导出文件或生成交付包提交到 Git。

常见错误：

- 一个目录里放多个非标准名称 Excel，导致 Agent 无法判断要读取哪一个。
- 证据文件中包含密钥、凭证、完整私有地址清单或敏感截图。

## Step 1：复制或打开标准 workbook

优先使用仓库中的模板和样例作为参考：

```text
templates/dataflow_v1.0/
samples/DCP_v0.1/
```

主工作簿名应为：

```text
dataflow_collection_template_v0.1.xlsx
```

合格标准：

- Sheet 名称不要改。
- 表头不要删除。
- 不确定字段先留空或写入 `Notes`，不要编造事实。

## Step 2：填写 `00_Metadata`

打开 `00_Metadata`，至少填写：

| 字段 | 填写标准 |
|---|---|
| `Project_Name` | 本次 DCP 的项目或系统名称。 |
| `Environment` | 使用枚举值，例如 `Production`、`Prod`、`Testnetv2`、`Staging`、`UAT`。 |
| `Version` | 本次采集版本，例如 `v0.1-demo` 或内部版本号。 |
| `Owner` | 本次采集负责人或团队。 |

合格标准：

- `Environment` 和 `Version` 后续会进入 metadata 和交付包名称。
- 不要在 `Environment` 里写自由文本说明，说明放到 `Notes`。

## Step 3：填写基础资源表

依次填写 `01_Projects`、`02_Networks`、`03_Servers`。

`01_Projects` 必填重点：

- `Project_ID`
- `Project_Name`
- `Environment`
- `Included_In_Scope`
- `Evidence_ID`
- `Confirmation_Status`

`02_Networks` 必填重点：

- `Network_ID`
- `Project_ID`
- `VPC_Name`
- `Subnet_Name`
- `Region`
- `CIDR`
- `Network_Type`
- `Evidence_ID`

`03_Servers` 必填重点：

- `Instance_ID`
- `Hostname`
- `Status`
- `IP_Internal`
- `Project_ID`
- `VPC`
- `Subnet`
- `Server_Role`
- `Evidence_ID`

合格标准：

- `Project_ID` 必须能在 `01_Projects` 找到。
- 服务要运行在哪台服务器，后续会通过 `04_Services.Running_On_Instance_ID` 引用 `03_Servers.Instance_ID`。

常见错误：

- `Running_On_Instance_ID` 写了主机名而不是 `Instance_ID`。
- 网络和服务器的 `Project_ID` 不一致。

## Step 4：填写服务表 `04_Services`

每个可部署、可调用、可监控的服务都应有一行。

必填重点：

| 字段 | 填写标准 |
|---|---|
| `Service_ID` | 稳定唯一 ID，例如 `svc-rpc-api`。 |
| `Service_Name` | 人可读服务名，例如 `RPC API`。 |
| `Service_Priority` | `P0`、`P1`、`P2`、`P3` 或 `Info`。 |
| `Running_On_Instance_ID` | 引用 `03_Servers.Instance_ID`。 |
| `Protocol` | 使用枚举值，例如 `TCP`、`HTTP`、`HTTPS`、`GRPC`。 |
| `Listen_Ports` | 监听端口，例如 `443`、`8545`、`9090`。 |
| `Service_Role` | 说明服务职责。 |
| `Evidence_ID` | 引用 `14_Evidence_Index.Evidence_ID`。 |

可选 runtime 字段：

| 字段 | 什么时候填写 |
|---|---|
| `Runtime_Type` | 服务运行在 Kubernetes、CloudRun、VM、Managed_Service 等环境时填写。 |
| `Runtime_ID` | deployment、service、job、revision 或托管运行时 ID。 |
| `Runtime_Name` | 人可读 runtime 名称。 |
| `Runtime_Namespace` | Kubernetes namespace。 |
| `Runtime_Cluster` | Kubernetes cluster 或运行时集群名。 |
| `Runtime_Region` | 运行区域。 |

合格标准：

- P0/P1 服务必须能追溯运行实例、端口、证据和监控。
- 如果服务运行在 Kubernetes 或 CloudRun，建议填写 runtime 字段，便于下钻图展示上下文。

常见错误：

- 多个服务共用同一个 `Service_ID`。
- `Listen_Ports` 写成说明文字而不是端口值。
- `Protocol` 写成未批准枚举。

## Step 5：填写依赖表 `05_Dependencies`

每条服务调用、外部调用或数据访问都应有一行。

必填重点：

| 字段 | 填写标准 |
|---|---|
| `Dependency_ID` | 稳定唯一 ID，例如 `dep-rpc-db`。 |
| `Source_Service_ID` | 调用发起方，引用 `04_Services.Service_ID`。 |
| `Target_Service_ID` | 目标是内部服务时填写。 |
| `Target_External_ID` | 目标是外部系统时填写。 |
| `Target_Data_Asset_ID` | 目标是数据库、缓存、存储时填写。 |
| `Target_Port` | 目标端口。 |
| `Target_Port_Protocol` | 目标协议，例如 `TCP`、`HTTPS`、`GRPC`。 |
| `Direction` | 例如 `internal`、`egress`、`read`、`write`、`read_write`。 |
| `Dependency_Criticality` | 关键性，P0/P1 依赖需要安全和监控解释。 |
| `Evidence_ID` | 依赖证据。 |

可选增强字段：

| 字段 | 填写标准 |
|---|---|
| `Target_Type` | 目标类型，例如 `service`、`external_service`、`data_asset`、`runtime`。 |
| `Target_ID` | 与 `Target_Type` 匹配的目标 ID。 |
| `Interaction_Mode` | 交互方式，例如 `sync`、`async`、`batch`、`stream`、`read`、`write`。 |

合格标准：

- 每条依赖必须至少有一个目标：内部服务、外部服务或数据资产。
- `Source_Service_ID` 和目标 ID 必须能在对应 Sheet 中找到。
- 如果使用 `Target_Type` / `Target_ID`，两者必须同时填写。

常见错误：

- 只写了自然语言说明，没写目标 ID。
- 把读数据库写成服务调用，但没有填写 `Target_Data_Asset_ID`。
- P0/P1 依赖没有防火墙、监控或例外说明。

## Step 6：填写数据资产 `06_Data_Assets`

数据资产包括数据库、缓存、对象存储、队列、表、bucket 等。

必填重点：

- `Data_Asset_ID`
- `Data_Asset_Name`
- `Data_Asset_Type`
- `Project_ID`
- `Region`
- `Access_Method`
- `Port`
- `Used_By_Service_ID`
- `Access_Type`
- `Sensitivity`
- `Evidence_ID`

合格标准：

- 高敏或关键数据资产应填写 `Sensitivity`，并有监控覆盖。
- `Used_By_Service_ID` 引用真实存在的服务。
- 如果服务通过 `05_Dependencies` 访问数据资产，两边 ID 应一致。

## Step 7：填写安全相关表

依次填写 `07_Firewalls`、`08_Cloud_Armor`、`09_IAM_SA`。

`07_Firewalls` 重点：

- `Firewall_ID`
- `Direction`
- `Action`
- `Source_Allowed`
- `Protocol`
- `Ports`
- `Related_Service_ID`
- `Related_Dependency_ID`
- `Reason`

`08_Cloud_Armor` 重点：

- `Policy_ID`
- `Protected_Entry_ID`
- `Entry_Type`
- `Rule_Action`
- `Backend_Service`
- `LB_Name`

`09_IAM_SA` 重点：

- `IAM_Binding_ID`
- `Service_Account_ID`
- `Service_Account_Email`
- `Used_By_Service_ID`
- `Role`
- `Scope`
- `Is_High_Privilege`
- `Justification`

合格标准：

- P0/P1 依赖应能关联到防火墙规则或明确例外。
- 公网入口应有入口防护记录或明确例外。
- 高权限 IAM 必须有 `Justification`。

常见错误：

- 防火墙端口和依赖端口不一致。
- `0.0.0.0/0` 开放但没有 `Reason`。
- 高权限账号没有说明用途和责任人。

## Step 8：填写监控、交付、外部服务、问题和证据

填写 `10_Monitoring`：

- P0 服务、P0/P1 依赖、关键数据资产应有监控记录。
- `Coverage_Status` 使用 `Covered`、`Partial`、`Missing`、`Unknown`。

填写 `11_CICD`：

- 记录 pipeline、repo、runner、artifact registry、部署入口和目标服务。

填写 `12_External_Services`：

- 外部服务 ID、endpoint、protocol、port、认证方式、方向和数据分类。

填写 `13_Issues_Exceptions`：

- 记录待确认、风险、例外、负责人、到期时间和处理状态。

填写 `14_Evidence_Index`：

- 每个 `Evidence_ID` 必须唯一。
- `File_or_URL` 指向证据文件或内部链接。
- 证据必须脱敏。

合格标准：

- 其他 Sheet 引用的每个 `Evidence_ID` 都能在 `14_Evidence_Index` 找到。
- `Pending_Confirmation` 和安全例外必须能在问题或说明中追踪。

## Step 9：运行自检脚本

在项目根目录执行：

```bash
scripts/check_dcp.sh path/to/DCP_v0.1
```

如果需要指定 Python：

```bash
DATAFLOW_PYTHON=/path/to/python scripts/check_dcp.sh path/to/DCP_v0.1
```

如果需要指定输出目录：

```bash
scripts/check_dcp.sh path/to/DCP_v0.1 --output /tmp/agent_check
```

输出目录：

```text
path/to/DCP_v0.1/agent_check/
```

## Step 10：按自检结果修正源 Excel

先看：

```text
agent_check/check_summary.md
```

再看：

```text
agent_check/fix_list.md
```

处理规则：

- `NEEDS_FIX`：先修 Excel，再重新运行 `scripts/check_dcp.sh`。
- P0/P1：优先处理，通常是缺 Sheet、缺字段、主键重复、外键断裂或证据缺失。
- `Dropped graph edges` 大于 0：说明有关系没有进入正式图，通常是 ID 写错或目标记录缺失。
- `Pending_Confirmation`：可以保留为待确认项，但不能当作最终事实验收。

不要修改：

- `agent_check/` 下的生成报告。
- `dist/` 下的生成图。
- zip 交付包内部文件。

## Step 11：提交给汇总负责人

达到以下最小标准后再提交：

- `scripts/check_dcp.sh path/to/DCP_v0.1` 可以成功运行。
- 没有 P0/P1 schema 或 foreign-key 问题。
- 关键服务、关键依赖、关键数据资产都有记录。
- 关键记录都有 `Evidence_ID`。
- `Dropped graph edges` 为 0，或已说明原因并修正源 Excel。
- `Pending_Confirmation` 已明确列入待确认事项。

提交内容：

```text
DCP_v0.1/
  dataflow_collection_template_v0.1.xlsx
  raw_exports/
  evidence/
  notes/
```

## 快速参考表

### `Confirmation_Status`

| 值 | 什么时候用 | Agent 行为 |
|---|---|---|
| `Confirmed` | 已人工确认且有证据 | 进入正式图和报告 |
| `Auto_Detected` | 自动发现但仍需复核 | 进入图，但降低信任度表达 |
| `Pending_Confirmation` | 不确定、待确认 | 进入问题清单，不作为最终事实 |
| `Accepted_Exception` | 已接受的例外 | 进入图，但带例外标记 |
| `Rejected` | 明确拒绝 | 不进入正式图 |
| `Not_Applicable` | 明确不适用 | 不参与对应校验 |

### `Evidence_ID`

| 规则 | 标准 |
|---|---|
| 唯一性 | 每个证据 ID 在 `14_Evidence_Index` 唯一。 |
| 可追溯 | 能定位到截图、导出、配置片段、命令输出或内部链接。 |
| 脱敏 | 不包含密钥、凭证、真实敏感截图或不应公开的信息。 |
| 引用 | 其他 Sheet 中的 `Evidence_ID` 必须能在 `14_Evidence_Index` 找到。 |

### 主键 ID

| 对象 | 建议格式 |
|---|---|
| 服务 | `svc-<name>`，例如 `svc-rpc-api` |
| 依赖 | `dep-<source>-<target>`，例如 `dep-rpc-db` |
| 数据资产 | `data-<name>`，例如 `data-cloudsql-state` |
| 防火墙 | `fw-<purpose>`，例如 `fw-allow-rpc-db` |
| 监控 | `mon-<object>`，例如 `mon-rpc-api` |

## 参考位置

| 用途 | 路径 |
|---|---|
| 标准模板资料 | `templates/dataflow_v1.0/` |
| 可运行样例 | `samples/DCP_v0.1/` |
| 输入契约 | `docs/dataflow_agent_input_contract_v0.1.md` |
| 自检说明 | `docs/dcp_self_check_guide.md` |
| 字段规则 | `schemas/workbook_schema.json` |

---

# English Version

# DevOps DCP Collection Step-by-Step Manual

## How To Use This Manual

This manual is for DevOps or information collection personnel filling a DCP for the first time. Follow Step 0 through Step 11. Do not manually edit diagrams, reports, or packages generated by the agent; all corrections must be made in the source Excel workbook.

Before first use, run the environment doctor from the repository root:

```bash
scripts/doctor.sh
```

## Step 0: Prepare The DCP Directory

Create a standalone directory, for example:

```text
DCP_v0.1/
  dataflow_collection_template_v0.1.xlsx
  raw_exports/
  evidence/
  notes/
```

Acceptance standard:

- `dataflow_collection_template_v0.1.xlsx` is the main workbook.
- `raw_exports/` stores sanitized export files.
- `evidence/` stores sanitized screenshots, configuration snippets, command outputs, or audit records.
- `notes/` stores pending-confirmation notes and known exception notes.
- Do not commit real production DCPs, real evidence, raw exports, or generated delivery packages to Git.

Common mistakes:

- Placing multiple non-standard Excel files in one directory, making workbook selection ambiguous.
- Including secrets, credentials, full private address inventories, or sensitive screenshots in evidence files.

## Step 1: Copy Or Open The Standard Workbook

Use the repository template and sample as references:

```text
templates/dataflow_v1.0/
samples/DCP_v0.1/
```

The main workbook file name should be:

```text
dataflow_collection_template_v0.1.xlsx
```

Acceptance standard:

- Do not rename sheets.
- Do not delete headers.
- Leave uncertain fields blank or document them in `Notes`; do not invent facts.

## Step 2: Fill `00_Metadata`

Open `00_Metadata` and fill at least:

| Field | Standard |
|---|---|
| `Project_Name` | Project or system name for this DCP. |
| `Environment` | Use an enum value such as `Production`, `Prod`, `Testnetv2`, `Staging`, or `UAT`. |
| `Version` | Collection version, such as `v0.1-demo` or an internal version. |
| `Owner` | Collection owner or team. |

Acceptance standard:

- `Environment` and `Version` are written into metadata and package names.
- Do not put free-form explanations in `Environment`; put explanations in `Notes`.

## Step 3: Fill Base Resource Sheets

Fill `01_Projects`, `02_Networks`, and `03_Servers`.

Key fields for `01_Projects`:

- `Project_ID`
- `Project_Name`
- `Environment`
- `Included_In_Scope`
- `Evidence_ID`
- `Confirmation_Status`

Key fields for `02_Networks`:

- `Network_ID`
- `Project_ID`
- `VPC_Name`
- `Subnet_Name`
- `Region`
- `CIDR`
- `Network_Type`
- `Evidence_ID`

Key fields for `03_Servers`:

- `Instance_ID`
- `Hostname`
- `Status`
- `IP_Internal`
- `Project_ID`
- `VPC`
- `Subnet`
- `Server_Role`
- `Evidence_ID`

Acceptance standard:

- `Project_ID` must exist in `01_Projects`.
- Services reference server runtime placement through `04_Services.Running_On_Instance_ID` pointing to `03_Servers.Instance_ID`.

Common mistakes:

- Writing hostnames instead of `Instance_ID` in `Running_On_Instance_ID`.
- Using inconsistent `Project_ID` values across networks and servers.

## Step 4: Fill Service Sheet `04_Services`

Every deployable, callable, or monitored service should have one row.

Key fields:

| Field | Standard |
|---|---|
| `Service_ID` | Stable unique ID, for example `svc-rpc-api`. |
| `Service_Name` | Human-readable name, for example `RPC API`. |
| `Service_Priority` | `P0`, `P1`, `P2`, `P3`, or `Info`. |
| `Running_On_Instance_ID` | References `03_Servers.Instance_ID`. |
| `Protocol` | Enum value such as `TCP`, `HTTP`, `HTTPS`, or `GRPC`. |
| `Listen_Ports` | Listen ports such as `443`, `8545`, or `9090`. |
| `Service_Role` | Service responsibility. |
| `Evidence_ID` | References `14_Evidence_Index.Evidence_ID`. |

Optional runtime fields:

| Field | When To Fill |
|---|---|
| `Runtime_Type` | Fill when the service runs on Kubernetes, CloudRun, VM, or Managed_Service. |
| `Runtime_ID` | Deployment, service, job, revision, or managed runtime ID. |
| `Runtime_Name` | Human-readable runtime name. |
| `Runtime_Namespace` | Kubernetes namespace. |
| `Runtime_Cluster` | Kubernetes cluster or runtime cluster name. |
| `Runtime_Region` | Runtime region. |

Acceptance standard:

- P0/P1 services must trace to runtime placement, ports, evidence, and monitoring.
- If the service runs on Kubernetes or CloudRun, fill runtime fields where possible for drilldown context.

Common mistakes:

- Reusing the same `Service_ID` for multiple services.
- Writing prose instead of port values in `Listen_Ports`.
- Using an unapproved `Protocol` enum value.

## Step 5: Fill Dependency Sheet `05_Dependencies`

Every service call, external call, or data access should have one row.

Key fields:

| Field | Standard |
|---|---|
| `Dependency_ID` | Stable unique ID, for example `dep-rpc-db`. |
| `Source_Service_ID` | Caller, references `04_Services.Service_ID`. |
| `Target_Service_ID` | Fill when the target is an internal service. |
| `Target_External_ID` | Fill when the target is an external system. |
| `Target_Data_Asset_ID` | Fill when the target is a database, cache, or storage. |
| `Target_Port` | Target port. |
| `Target_Port_Protocol` | Target protocol such as `TCP`, `HTTPS`, or `GRPC`. |
| `Direction` | For example `internal`, `egress`, `read`, `write`, or `read_write`. |
| `Dependency_Criticality` | Criticality. P0/P1 dependencies need security and monitoring explanation. |
| `Evidence_ID` | Dependency evidence. |

Optional enhancement fields:

| Field | Standard |
|---|---|
| `Target_Type` | Target type such as `service`, `external_service`, `data_asset`, or `runtime`. |
| `Target_ID` | Target ID matching `Target_Type`. |
| `Interaction_Mode` | Interaction mode such as `sync`, `async`, `batch`, `stream`, `read`, or `write`. |

Acceptance standard:

- Every dependency must have at least one target: internal service, external service, or data asset.
- `Source_Service_ID` and target IDs must exist in their corresponding sheets.
- If `Target_Type` / `Target_ID` are used, both must be filled.

Common mistakes:

- Writing only natural-language description without target ID.
- Recording database reads as service calls without `Target_Data_Asset_ID`.
- P0/P1 dependencies missing firewall, monitoring, or exception explanation.

## Step 6: Fill Data Assets `06_Data_Assets`

Data assets include databases, caches, object storage, queues, tables, and buckets.

Key fields:

- `Data_Asset_ID`
- `Data_Asset_Name`
- `Data_Asset_Type`
- `Project_ID`
- `Region`
- `Access_Method`
- `Port`
- `Used_By_Service_ID`
- `Access_Type`
- `Sensitivity`
- `Evidence_ID`

Acceptance standard:

- Sensitive or critical data assets should have `Sensitivity` filled and monitoring coverage.
- `Used_By_Service_ID` references existing services.
- If a service accesses a data asset through `05_Dependencies`, IDs should match on both sides.

## Step 7: Fill Security Sheets

Fill `07_Firewalls`, `08_Cloud_Armor`, and `09_IAM_SA`.

Key fields for `07_Firewalls`:

- `Firewall_ID`
- `Direction`
- `Action`
- `Source_Allowed`
- `Protocol`
- `Ports`
- `Related_Service_ID`
- `Related_Dependency_ID`
- `Reason`

Key fields for `08_Cloud_Armor`:

- `Policy_ID`
- `Protected_Entry_ID`
- `Entry_Type`
- `Rule_Action`
- `Backend_Service`
- `LB_Name`

Key fields for `09_IAM_SA`:

- `IAM_Binding_ID`
- `Service_Account_ID`
- `Service_Account_Email`
- `Used_By_Service_ID`
- `Role`
- `Scope`
- `Is_High_Privilege`
- `Justification`

Acceptance standard:

- P0/P1 dependencies should link to firewall rules or documented exceptions.
- Public entries should have entry protection records or documented exceptions.
- High-privilege IAM bindings must include `Justification`.

Common mistakes:

- Firewall ports do not match dependency ports.
- `0.0.0.0/0` is open without `Reason`.
- High-privilege accounts have no purpose or owner explanation.

## Step 8: Fill Monitoring, Delivery, External Services, Issues, And Evidence

Fill `10_Monitoring`:

- P0 services, P0/P1 dependencies, and critical data assets should have monitoring rows.
- `Coverage_Status` uses `Covered`, `Partial`, `Missing`, or `Unknown`.

Fill `11_CICD`:

- Record pipeline, repo, runner, artifact registry, deployment entry, and target service.

Fill `12_External_Services`:

- External service ID, endpoint, protocol, port, auth method, direction, and data classification.

Fill `13_Issues_Exceptions`:

- Record pending confirmations, risks, exceptions, owner, due date, and status.

Fill `14_Evidence_Index`:

- Every `Evidence_ID` must be unique.
- `File_or_URL` points to an evidence file or internal link.
- Evidence must be sanitized.

Acceptance standard:

- Every `Evidence_ID` referenced by other sheets exists in `14_Evidence_Index`.
- `Pending_Confirmation` items and security exceptions are traceable in issues or notes.

## Step 9: Run The Self-Check Script

Run from the repository root:

```bash
scripts/check_dcp.sh path/to/DCP_v0.1
```

To specify Python:

```bash
DATAFLOW_PYTHON=/path/to/python scripts/check_dcp.sh path/to/DCP_v0.1
```

To specify the output directory:

```bash
scripts/check_dcp.sh path/to/DCP_v0.1 --output /tmp/agent_check
```

Output directory:

```text
path/to/DCP_v0.1/agent_check/
```

## Step 10: Fix The Source Excel From Self-Check Results

Read first:

```text
agent_check/check_summary.md
```

Then read:

```text
agent_check/fix_list.md
```

Handling rules:

- `NEEDS_FIX`: correct the Excel workbook and rerun `scripts/check_dcp.sh`.
- P0/P1: handle first; these are usually missing sheets, missing fields, duplicate primary keys, broken foreign keys, or missing evidence.
- `Dropped graph edges` greater than 0: some relationships did not enter the formal graph, usually because IDs are wrong or target records are missing.
- `Pending_Confirmation`: can remain as pending review, but must not be accepted as final fact.

Do not edit:

- Generated reports under `agent_check/`.
- Generated diagrams under `dist/`.
- Files inside zip delivery packages.

## Step 11: Submit To The Aggregation Owner

Submit only after meeting the minimum standard:

- `scripts/check_dcp.sh path/to/DCP_v0.1` runs successfully.
- No P0/P1 schema or foreign-key findings.
- Key services, key dependencies, and key data assets are recorded.
- Key records have `Evidence_ID`.
- `Dropped graph edges` is 0, or the cause has been explained and source Excel corrected.
- `Pending_Confirmation` items are explicitly tracked.

Submit:

```text
DCP_v0.1/
  dataflow_collection_template_v0.1.xlsx
  raw_exports/
  evidence/
  notes/
```

## Quick Reference

### `Confirmation_Status`

| Value | When To Use | Agent Behavior |
|---|---|---|
| `Confirmed` | Manually confirmed and evidence-backed | Enters formal diagrams and reports |
| `Auto_Detected` | Automatically detected but still needs review | Enters graph with lower-confidence styling |
| `Pending_Confirmation` | Uncertain or waiting for confirmation | Enters issue lists, not final fact |
| `Accepted_Exception` | Approved exception | Enters graph with exception styling |
| `Rejected` | Explicitly rejected | Excluded from formal graph |
| `Not_Applicable` | Clearly not applicable | Excluded from applicable validation |

### `Evidence_ID`

| Rule | Standard |
|---|---|
| Uniqueness | Each evidence ID is unique in `14_Evidence_Index`. |
| Traceability | It points to a screenshot, export, configuration snippet, command output, or internal link. |
| Sanitization | It contains no secrets, credentials, sensitive screenshots, or information that should not be public. |
| Reference | Every `Evidence_ID` in other sheets must exist in `14_Evidence_Index`. |

### Primary Key IDs

| Object | Suggested Format |
|---|---|
| Service | `svc-<name>`, for example `svc-rpc-api` |
| Dependency | `dep-<source>-<target>`, for example `dep-rpc-db` |
| Data asset | `data-<name>`, for example `data-cloudsql-state` |
| Firewall | `fw-<purpose>`, for example `fw-allow-rpc-db` |
| Monitoring | `mon-<object>`, for example `mon-rpc-api` |

## Reference Locations

| Purpose | Path |
|---|---|
| Standard template package | `templates/dataflow_v1.0/` |
| Runnable sample | `samples/DCP_v0.1/` |
| Input contract | `docs/dataflow_agent_input_contract_v0.1.md` |
| Self-check guide | `docs/dcp_self_check_guide.md` |
| Field rules | `schemas/workbook_schema.json` |
