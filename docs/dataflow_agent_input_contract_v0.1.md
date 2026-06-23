# 中文版本

# Dataflow Project 数据流图智能体输入输出契约工程白皮书

## 摘要

本文定义 Dataflow Project 数据流图智能体与数据采集包之间的稳定接口。该契约规定输入目录结构、工作簿表单、状态语义、主键、外键、节点生成规则、边生成规则、质量门禁和输出产物。契约的目标是保证智能体不会脱离结构化输入推断生产事实，所有图、报告和归档包都可以从同一份数据采集包重复生成。

## 关键词

输入契约；数据采集包；工作簿；主键；外键；图模型；质量门禁；交付包。

## 一、研究背景

数据流图交付必须建立在可追溯的事实数据之上。为了避免人工画图导致的事实漂移，本项目将数据采集包作为唯一结构化输入，并要求智能体只基于该输入执行校验、建模、渲染、报告和打包。

## 二、输入目录结构

推荐的数据采集包结构如下：

```text
DCP_v0.1/
  dataflow_collection_template_v0.1.xlsx
  raw_exports/
    gcloud_instances.csv
    gcloud_networks.csv
    gcloud_subnets.csv
    gcloud_firewalls.csv
    gcloud_sql_instances.csv
    gcloud_iam_policy.json
  evidence/
    screenshots/
    config_samples/
    command_outputs/
    docs/
  notes/
    pending_confirmation.md
    known_exceptions.md
```

工作簿是唯一结构化输入。原始导出和证据文件用于追溯、复核和必要时的人工确认。

## 三、必需工作表

智能体要求以下工作表名称保持稳定：

| 序号 | 工作表 |
|---|---|
| 1 | 00_Metadata |
| 2 | 01_Projects |
| 3 | 02_Networks |
| 4 | 03_Servers |
| 5 | 04_Services |
| 6 | 05_Dependencies |
| 7 | 06_Data_Assets |
| 8 | 07_Firewalls |
| 9 | 08_Cloud_Armor |
| 10 | 09_IAM_SA |
| 11 | 10_Monitoring |
| 12 | 11_CICD |
| 13 | 12_External_Services |
| 14 | 13_Issues_Exceptions |
| 15 | 14_Evidence_Index |
| 16 | 90_Enums |

## 四、记录状态语义

| 状态值 | 智能体行为 |
|---|---|
| Confirmed | 纳入正式图模型和报告，视为已确认事实。 |
| Auto_Detected | 纳入图模型，但标记为自动发现或较低置信度。 |
| Pending_Confirmation | 纳入草稿视图和问题清单，不视为最终事实。 |
| Rejected | 从最终图模型中排除；如有必要保留在问题轨迹中。 |
| Not_Applicable | 对不适用的校验规则忽略。 |

## 五、主键定义

| 工作表 | 主键 |
|---|---|
| 01_Projects | Project_ID |
| 02_Networks | Network_ID |
| 03_Servers | Instance_ID |
| 04_Services | Service_ID |
| 05_Dependencies | Dependency_ID |
| 06_Data_Assets | Data_Asset_ID |
| 07_Firewalls | Firewall_ID |
| 08_Cloud_Armor | Policy_ID |
| 09_IAM_SA | IAM_Binding_ID |
| 10_Monitoring | Monitoring_ID |
| 11_CICD | CICD_ID |
| 12_External_Services | External_ID |
| 13_Issues_Exceptions | Issue_ID |
| 14_Evidence_Index | Evidence_ID |

## 六、核心外键规则

| 来源字段 | 目标字段 | 规则 |
|---|---|---|
| 04_Services.Running_On_Instance_ID | 03_Servers.Instance_ID | 服务必须关联到已存在服务器。 |
| 05_Dependencies.Source_Service_ID | 04_Services.Service_ID | 依赖源服务必须存在。 |
| 05_Dependencies.Target_Service_ID | 04_Services.Service_ID | 填写时目标服务必须存在。 |
| 05_Dependencies.Target_External_ID | 12_External_Services.External_ID | 填写时外部服务必须存在。 |
| 05_Dependencies.Target_Data_Asset_ID | 06_Data_Assets.Data_Asset_ID | 填写时数据资产必须存在。 |
| 06_Data_Assets.Used_By_Service_ID | 04_Services.Service_ID | 填写时使用方服务必须存在。 |
| 07_Firewalls.Related_Service_ID | 04_Services.Service_ID | 填写时关联服务必须存在。 |
| 07_Firewalls.Related_Dependency_ID | 05_Dependencies.Dependency_ID | 填写时关联依赖必须存在。 |
| 09_IAM_SA.Used_By_Service_ID | 04_Services.Service_ID | 填写时使用方服务必须存在。 |
| 14_Evidence_Index.Evidence_ID | 其他证据字段 | 被引用证据必须存在且唯一。 |

每条服务依赖至少应填写一个目标字段：目标服务、目标外部服务或目标数据资产。

## 七、节点生成规则

| 工作表 | 节点类型 |
|---|---|
| 01_Projects | 云项目 |
| 02_Networks | 网络、子网、出口、负载均衡、专用连接 |
| 03_Servers | 服务器 |
| 04_Services | 服务 |
| 06_Data_Assets | 数据资产 |
| 07_Firewalls | 防火墙规则 |
| 08_Cloud_Armor | 外部入口防护策略 |
| 09_IAM_SA | 服务账号、权限绑定 |
| 10_Monitoring | 监控控制 |
| 11_CICD | 持续交付组件 |
| 12_External_Services | 外部服务 |

## 八、关系生成规则

| 关系类型 | 来源 | 目标 | 触发数据 |
|---|---|---|---|
| 包含 | 项目 | 网络、服务器、数据资产 | 项目和网络归属字段 |
| 运行于 | 服务 | 服务器 | 服务运行实例字段 |
| 监听端口 | 服务 | 端口 | 服务监听端口字段 |
| 调用 | 源服务 | 目标服务 | 服务依赖目标服务字段 |
| 读写 | 服务 | 数据资产 | 服务依赖目标数据资产字段 |
| 调用外部 | 服务 | 外部服务 | 服务依赖目标外部服务字段 |
| 被允许 | 服务或依赖 | 防火墙规则 | 防火墙关联字段 |
| 被保护 | 入口或服务 | 外部入口防护策略 | 入口保护字段 |
| 使用账号 | 服务 | 服务账号 | 权限使用方字段 |
| 被监控 | 对象 | 监控控制 | 监控对象字段 |
| 被部署 | 交付流水线 | 服务或服务器 | 交付目标字段 |

## 九、质量门禁

| 门禁 | 名称 | 通过标准 |
|---|---|---|
| 一 | 模式校验 | 必需工作表、字段、类型和枚举合法。 |
| 二 | 外键校验 | 服务、服务器、依赖、证据等引用完整。 |
| 三 | 核心链路完整性 | 核心服务、数据库、数据可用性链路和关键依赖可追溯。 |
| 四 | 安全与监控校验 | 外部入口、防火墙、权限、监控覆盖具备解释和证据。 |
| 五 | 产物生成校验 | 图模型、图、报告、清单和压缩包成功生成。 |

## 十、输出产物

```text
dataflow_package_v0.1/
  input/
    dataflow_collection_template_v0.1.xlsx
  normalized/
    nodes.csv
    edges.csv
    dataflow_graph.json
    dataflow_graph.yaml
  diagrams/
    00_overview.svg
    01_network_layer.svg
    02_compute_service_layer.svg
    03_service_dependency_layer.svg
    04_data_storage_layer.svg
    05_security_monitoring_layer.svg
    06_cicd_delivery_layer.svg
  reports/
    validation_report.xlsx
    logic_mapping_validation_report.docx
    issue_risk_register.xlsx
    acceptance_checklist.xlsx
  README.md
  metadata.json
```

## 十一、版权与授权

本项目版权归属 edmund-xl，并采用保留全部权利的私有授权。未经 edmund-xl 事先书面许可，不得复制、修改、分发或商用。完整授权文本见仓库根目录 `LICENSE` 文件。

## 十二、结论

该契约将采集表、证据、图模型、报告和最终归档连接为同一条可验证链路。智能体可以自动完成复杂处理，但不得越过契约推断未提供的生产事实。

## 十三、不可变规则

如果生成图或报告存在错误，不允许手工修改图或报告。必须修正源工作簿并重新生成交付包。

---

# English Version

# Dataflow Project Dataflow Agent Input And Output Contract Engineering White Paper

## Abstract

This document defines the stable interface between the Dataflow Project Dataflow Agent and the Data Collection Package. The contract specifies the input directory structure, workbook sheets, record-status semantics, primary keys, foreign keys, node-generation rules, edge-generation rules, quality gates, and output artifacts. Its purpose is to ensure that the agent never infers production facts outside structured input and that every diagram, report, and archive can be regenerated from the same collection package.

## Keywords

Input contract; Data Collection Package; workbook; primary key; foreign key; graph model; quality gate; delivery package.

## 1. Background

Data-flow delivery must be based on traceable factual data. To avoid fact drift caused by manual diagramming, this project treats the Data Collection Package as the only structured input and requires the agent to perform validation, modeling, rendering, reporting, and packaging only from that input.

## 2. Input Directory Structure

The recommended Data Collection Package structure is:

```text
DCP_v0.1/
  dataflow_collection_template_v0.1.xlsx
  raw_exports/
    gcloud_instances.csv
    gcloud_networks.csv
    gcloud_subnets.csv
    gcloud_firewalls.csv
    gcloud_sql_instances.csv
    gcloud_iam_policy.json
  evidence/
    screenshots/
    config_samples/
    command_outputs/
    docs/
  notes/
    pending_confirmation.md
    known_exceptions.md
```

The workbook is the only structured input. Raw exports and evidence files are used for traceability, review, and manual confirmation when needed.

## 3. Required Workbook Sheets

The agent requires the following sheet names to remain stable:

| Number | Sheet |
|---|---|
| 1 | 00_Metadata |
| 2 | 01_Projects |
| 3 | 02_Networks |
| 4 | 03_Servers |
| 5 | 04_Services |
| 6 | 05_Dependencies |
| 7 | 06_Data_Assets |
| 8 | 07_Firewalls |
| 9 | 08_Cloud_Armor |
| 10 | 09_IAM_SA |
| 11 | 10_Monitoring |
| 12 | 11_CICD |
| 13 | 12_External_Services |
| 14 | 13_Issues_Exceptions |
| 15 | 14_Evidence_Index |
| 16 | 90_Enums |

## 4. Record Status Semantics

| Status | Agent Behavior |
|---|---|
| Confirmed | Included in the formal graph model and reports as confirmed fact. |
| Auto_Detected | Included in the graph model and marked as auto-detected or lower confidence. |
| Pending_Confirmation | Included in draft views and issue lists, but not treated as final fact. |
| Rejected | Excluded from the final graph model and optionally retained in the issue trail. |
| Not_Applicable | Ignored for validation rules that do not apply. |

## 5. Primary Keys

| Sheet | Primary Key |
|---|---|
| 01_Projects | Project_ID |
| 02_Networks | Network_ID |
| 03_Servers | Instance_ID |
| 04_Services | Service_ID |
| 05_Dependencies | Dependency_ID |
| 06_Data_Assets | Data_Asset_ID |
| 07_Firewalls | Firewall_ID |
| 08_Cloud_Armor | Policy_ID |
| 09_IAM_SA | IAM_Binding_ID |
| 10_Monitoring | Monitoring_ID |
| 11_CICD | CICD_ID |
| 12_External_Services | External_ID |
| 13_Issues_Exceptions | Issue_ID |
| 14_Evidence_Index | Evidence_ID |

## 6. Core Foreign-Key Rules

| Source Field | Target Field | Rule |
|---|---|---|
| 04_Services.Running_On_Instance_ID | 03_Servers.Instance_ID | A service must reference an existing server. |
| 05_Dependencies.Source_Service_ID | 04_Services.Service_ID | A dependency source service must exist. |
| 05_Dependencies.Target_Service_ID | 04_Services.Service_ID | A target service must exist when populated. |
| 05_Dependencies.Target_External_ID | 12_External_Services.External_ID | An external service must exist when populated. |
| 05_Dependencies.Target_Data_Asset_ID | 06_Data_Assets.Data_Asset_ID | A data asset must exist when populated. |
| 06_Data_Assets.Used_By_Service_ID | 04_Services.Service_ID | A consuming service must exist when populated. |
| 07_Firewalls.Related_Service_ID | 04_Services.Service_ID | A related service must exist when populated. |
| 07_Firewalls.Related_Dependency_ID | 05_Dependencies.Dependency_ID | A related dependency must exist when populated. |
| 09_IAM_SA.Used_By_Service_ID | 04_Services.Service_ID | A consuming service must exist when populated. |
| 14_Evidence_Index.Evidence_ID | Evidence reference fields | Referenced evidence must exist and be unique. |

Each service dependency should populate at least one target field: target service, target external service, or target data asset.

## 7. Node-Generation Rules

| Sheet | Node Type |
|---|---|
| 01_Projects | Cloud project |
| 02_Networks | Network, subnet, egress, load balancer, private connection |
| 03_Servers | Server |
| 04_Services | Service |
| 06_Data_Assets | Data asset |
| 07_Firewalls | Firewall rule |
| 08_Cloud_Armor | External entry protection policy |
| 09_IAM_SA | Service account, permission binding |
| 10_Monitoring | Monitoring control |
| 11_CICD | Delivery component |
| 12_External_Services | External service |

## 8. Edge-Generation Rules

| Edge Type | Source | Target | Triggering Data |
|---|---|---|---|
| Contains | Project | Network, server, data asset | Project and network ownership fields |
| Runs on | Service | Server | Service runtime instance field |
| Listens on | Service | Port | Service listening-port field |
| Calls | Source service | Target service | Dependency target-service field |
| Reads or writes | Service | Data asset | Dependency target-data-asset field |
| Calls external | Service | External service | Dependency target-external-service field |
| Allowed by | Service or dependency | Firewall rule | Firewall relation fields |
| Protected by | Entry or service | External entry protection policy | Entry protection fields |
| Uses account | Service | Service account | Permission consumer field |
| Monitored by | Object | Monitoring control | Monitoring object field |
| Deployed by | Delivery pipeline | Service or server | Delivery target field |

## 9. Quality Gates

| Gate | Name | Pass Criteria |
|---|---|---|
| One | Schema validation | Required sheets, fields, types, and enum values are valid. |
| Two | Foreign-key validation | Service, server, dependency, and evidence references are complete. |
| Three | Core-link completeness | Core services, database links, data-availability links, and key dependencies are traceable. |
| Four | Security and monitoring validation | External entry, firewall, identity, and monitoring coverage have explanation and evidence. |
| Five | Artifact generation validation | Graph models, diagrams, reports, checklists, and archives are generated successfully. |

## 10. Output Artifacts

```text
dataflow_package_v0.1/
  input/
    dataflow_collection_template_v0.1.xlsx
  normalized/
    nodes.csv
    edges.csv
    dataflow_graph.json
    dataflow_graph.yaml
  diagrams/
    00_overview.svg
    01_network_layer.svg
    02_compute_service_layer.svg
    03_service_dependency_layer.svg
    04_data_storage_layer.svg
    05_security_monitoring_layer.svg
    06_cicd_delivery_layer.svg
  reports/
    validation_report.xlsx
    logic_mapping_validation_report.docx
    issue_risk_register.xlsx
    acceptance_checklist.xlsx
  README.md
  metadata.json
```

## 11. Copyright And License

This project is proprietary to edmund-xl and all rights are reserved. No copying, modification, distribution, or commercial use is permitted without prior written permission from edmund-xl. The full license text is available in the repository root `LICENSE` file.

## 12. Conclusion

This contract connects the collection workbook, evidence, graph model, reports, and final archive into one verifiable chain. The agent can automate complex processing, but it must not infer production facts beyond the contract.

## 13. Invariant Rule

If a generated diagram or report is wrong, do not edit the diagram or report manually. Correct the source workbook and regenerate the delivery package.
