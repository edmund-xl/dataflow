from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .models import Finding, GraphEdge, GraphModel, GraphNode, Row, WorkbookData
from .normalizer import active_rows


DATAFLOW_EDGE_TYPES = {"calls", "calls_external", "reads_from", "writes_to"}


@dataclass(frozen=True)
class ReviewObservation:
    severity: str
    category: str
    sheet: str
    row_id: str
    message_cn: str
    message_en: str


@dataclass(frozen=True)
class ArchitectureFinding:
    severity: str
    category: str
    sheet: str
    row_id: str
    field: str
    message_cn: str
    message_en: str
    suggested_action_cn: str
    suggested_action_en: str
    evidence_id: str = ""
    source: str = "architecture"

    def as_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "category": self.category,
            "sheet": self.sheet,
            "row_id": self.row_id,
            "field": self.field,
            "message_cn": self.message_cn,
            "message_en": self.message_en,
            "suggested_action_cn": self.suggested_action_cn,
            "suggested_action_en": self.suggested_action_en,
            "evidence_id": self.evidence_id,
            "source": self.source,
        }

    def as_finding(self) -> Finding:
        return Finding(
            "Architecture",
            self.severity,
            self.sheet,
            self.row_id,
            self.field,
            self.message_en,
            self.suggested_action_en,
            evidence_id=self.evidence_id,
        )


def write_architecture_findings(
    path: Path,
    workbook: WorkbookData,
    graph: GraphModel,
    validation_findings: list[Finding],
    risk_findings: list[Finding],
) -> None:
    findings = validation_findings + risk_findings
    architecture_findings = build_architecture_findings(workbook, graph, validation_findings, risk_findings)
    completeness_findings = build_completeness_findings(workbook, graph)
    dataflow_edges = [edge for edge in graph.edges if edge.type in DATAFLOW_EDGE_TYPES]
    blocking = [finding for finding in architecture_findings if finding.severity in {"P0", "P1"}]
    pending = [finding for finding in findings if finding.status == "Pending_Confirmation"]
    observations = _review_observations(workbook, graph)
    coverage = _coverage_matrix(architecture_findings, observations)
    conclusion = _architecture_conclusion(architecture_findings, pending)
    lines: list[str] = []
    _append_chinese(lines, workbook, graph, findings, architecture_findings, completeness_findings, dataflow_edges, blocking, pending, observations, coverage, conclusion)
    lines.extend(["---", ""])
    _append_english(lines, workbook, graph, findings, architecture_findings, completeness_findings, dataflow_edges, blocking, pending, observations, coverage, conclusion)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    _write_architecture_json(path.with_suffix(".json"), conclusion, architecture_findings, completeness_findings, observations, coverage, dataflow_edges, graph)


def build_architecture_findings(
    workbook: WorkbookData,
    graph: GraphModel,
    validation_findings: list[Finding],
    risk_findings: list[Finding],
) -> list[ArchitectureFinding]:
    return [_from_finding(finding) for finding in validation_findings + risk_findings] + build_completeness_findings(workbook, graph)


def build_completeness_findings(workbook: WorkbookData, graph: GraphModel) -> list[ArchitectureFinding]:
    findings: list[ArchitectureFinding] = []
    findings.extend(_overview_readiness_findings(workbook, graph))
    findings.extend(_graph_completeness_findings(graph))
    findings.extend(_service_completeness_findings(workbook, graph))
    findings.extend(_dependency_completeness_findings(workbook))
    findings.extend(_data_asset_completeness_findings(workbook))
    findings.extend(_external_service_completeness_findings(workbook))
    findings.extend(_network_completeness_findings(workbook))
    findings.extend(_firewall_completeness_findings(workbook))
    findings.extend(_iam_completeness_findings(workbook))
    findings.extend(_monitoring_completeness_findings(workbook))
    findings.extend(_cicd_completeness_findings(workbook))
    findings.extend(_issue_evidence_completeness_findings(workbook))
    return findings


def _append_chinese(
    lines: list[str],
    workbook: WorkbookData,
    graph: GraphModel,
    findings: list[Finding],
    architecture_findings: list[ArchitectureFinding],
    completeness_findings: list[ArchitectureFinding],
    dataflow_edges: list[GraphEdge],
    blocking: list[ArchitectureFinding],
    pending: list[Finding],
    observations: list[ReviewObservation],
    coverage: list[dict[str, str]],
    conclusion: str,
) -> None:
    severity_counts = _severity_counts(architecture_findings)
    lines.extend(
        [
            "# 中文版本",
            "",
            "# 架构问题分析报告",
            "",
            "## 结论",
            "",
            f"- 分析结论：`{conclusion}`",
            f"- 输入工作簿：`{workbook.path}`",
            f"- 必须处理的问题：{len(blocking)}",
            f"- 缺失/风险发现：P0={severity_counts['P0']}，P1={severity_counts['P1']}，P2={severity_counts['P2']}，Info={severity_counts['Info']}",
            f"- 新增完整性发现：{len(completeness_findings)}",
            f"- 待确认记录：{len(pending)}",
            f"- 丢弃关系：{len(graph.dropped_edges)}",
            f"- 真实数据流关系：{len(dataflow_edges)}",
            f"- 审查观察项：{len(observations)}",
            "",
            "## 判断依据",
            "",
            "本报告只使用 Excel/DCP 生成的 graph model、校验结果、风险结果和可审查事实。下面的链路只来自真实 graph edge；不存在的关系不会被补画或补写。需要修复的项看 `缺失与风险清单` 和 `修复定位清单`。",
            "",
            "## 真实数据流链路",
            "",
        ]
    )
    _append_dataflow_edges_cn(lines, graph, dataflow_edges)
    _append_coverage_matrix_cn(lines, coverage)
    _append_architecture_findings_cn(lines, architecture_findings)
    _append_observations_cn(lines, observations)
    lines.extend(["## 问题分组", ""])
    _append_category_cn(lines, "必须优先处理", [finding.as_finding() for finding in blocking])
    _append_category_cn(lines, "待确认或例外", pending)
    _append_category_cn(lines, "安全与访问控制", _category_findings(findings, ["firewall", "iam", "privilege", "cloud armor", "ingress", "egress", "nat", "psc", "peering"]))
    _append_category_cn(lines, "监控覆盖", _category_findings(findings, ["monitoring", "dashboard", "logging", "alert", "coverage"]))
    _append_category_cn(lines, "证据与可追溯性", _category_findings(findings, ["evidence", "dropped graph edge", "foreign key", "does not exist", "missing target"]))
    lines.extend(
        [
            "## 修复定位清单",
            "",
            "| Severity | Sheet | Row_ID | Field | 问题 | 建议 | Evidence_ID |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    if findings:
        for finding in sorted(findings, key=_finding_sort_key):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _cell(finding.severity),
                        _cell(finding.sheet),
                        _cell(finding.row_id or "N/A"),
                        _cell(finding.field or "N/A"),
                        _cell(_cn_message(finding)),
                        _cell(_cn_action(finding)),
                        _cell(finding.evidence_id or "N/A"),
                    ]
                )
                + " |"
            )
    else:
        lines.append("| PASS | N/A | N/A | N/A | 未发现自动化校验或风险问题。 | 保留人工证据复核。 | N/A |")
    lines.extend(
        [
            "",
            "## 处理规则",
            "",
            "修改源 Excel/DCP 后重新运行脚本。不要直接修改生成的图、报告或压缩包。",
            "",
        ]
    )


def _append_english(
    lines: list[str],
    workbook: WorkbookData,
    graph: GraphModel,
    findings: list[Finding],
    architecture_findings: list[ArchitectureFinding],
    completeness_findings: list[ArchitectureFinding],
    dataflow_edges: list[GraphEdge],
    blocking: list[ArchitectureFinding],
    pending: list[Finding],
    observations: list[ReviewObservation],
    coverage: list[dict[str, str]],
    conclusion: str,
) -> None:
    severity_counts = _severity_counts(architecture_findings)
    lines.extend(
        [
            "# English Version",
            "",
            "# Architecture Findings Report",
            "",
            "## Conclusion",
            "",
            f"- Analysis conclusion: `{conclusion}`",
            f"- Input workbook: `{workbook.path}`",
            f"- Must-fix findings: {len(blocking)}",
            f"- Completeness/risk findings: P0={severity_counts['P0']}, P1={severity_counts['P1']}, P2={severity_counts['P2']}, Info={severity_counts['Info']}",
            f"- New completeness findings: {len(completeness_findings)}",
            f"- Pending records: {len(pending)}",
            f"- Dropped edges: {len(graph.dropped_edges)}",
            f"- Real dataflow edges: {len(dataflow_edges)}",
            f"- Review observations: {len(observations)}",
            "",
            "## Review Basis",
            "",
            "This report uses only the graph model, validation findings, risk findings, and reviewable facts generated from Excel/DCP. The dataflow paths below are derived only from real graph edges; nonexistent relationships are not invented. Use `Missing Information And Risk List` and `Fix Location List` for actions.",
            "",
            "## Real Dataflow Paths",
            "",
        ]
    )
    _append_dataflow_edges_en(lines, graph, dataflow_edges)
    _append_coverage_matrix_en(lines, coverage)
    _append_architecture_findings_en(lines, architecture_findings)
    _append_observations_en(lines, observations)
    lines.extend(["## Finding Groups", ""])
    _append_category_en(lines, "Must Fix First", [finding.as_finding() for finding in blocking])
    _append_category_en(lines, "Pending Or Exceptions", pending)
    _append_category_en(lines, "Security And Access Control", _category_findings(findings, ["firewall", "iam", "privilege", "cloud armor", "ingress", "egress", "nat", "psc", "peering"]))
    _append_category_en(lines, "Monitoring Coverage", _category_findings(findings, ["monitoring", "dashboard", "logging", "alert", "coverage"]))
    _append_category_en(lines, "Evidence And Traceability", _category_findings(findings, ["evidence", "dropped graph edge", "foreign key", "does not exist", "missing target"]))
    lines.extend(
        [
            "## Fix Location List",
            "",
            "| Severity | Sheet | Row_ID | Field | Message | Suggested action | Evidence_ID |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    if findings:
        for finding in sorted(findings, key=_finding_sort_key):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _cell(finding.severity),
                        _cell(finding.sheet),
                        _cell(finding.row_id or "N/A"),
                        _cell(finding.field or "N/A"),
                        _cell(finding.message),
                        _cell(finding.suggested_action or "Review and correct the source workbook."),
                        _cell(finding.evidence_id or "N/A"),
                    ]
                )
                + " |"
            )
    else:
        lines.append("| PASS | N/A | N/A | N/A | No automated validation or risk findings were detected. | Keep manual evidence review. | N/A |")
    lines.extend(
        [
            "",
            "## Handling Rule",
            "",
            "Correct the source Excel/DCP and rerun the script. Do not directly edit generated diagrams, reports, or archives.",
            "",
        ]
    )


def _append_dataflow_edges_cn(lines: list[str], graph: GraphModel, edges: list[GraphEdge]) -> None:
    if not edges:
        lines.extend(["未发现 `calls`、`calls_external`、`reads_from` 或 `writes_to` 数据流关系。", ""])
        return
    lines.extend(["| Edge_ID | 类型 | 来源 | 目标 | 状态 | 来源记录 | Evidence_ID |", "| --- | --- | --- | --- | --- | --- | --- |"])
    for edge in edges:
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(edge.id),
                    _cell(edge.type),
                    _cell(_node_label(graph.nodes.get(edge.source), edge.source)),
                    _cell(_node_label(graph.nodes.get(edge.target), edge.target)),
                    _cell(edge.status),
                    _cell(_source_record(edge)),
                    _cell(edge.evidence_id or edge.metadata.get("evidence_id", "N/A")),
                ]
            )
            + " |"
        )
    lines.append("")


def _append_dataflow_edges_en(lines: list[str], graph: GraphModel, edges: list[GraphEdge]) -> None:
    if not edges:
        lines.extend(["No `calls`, `calls_external`, `reads_from`, or `writes_to` dataflow edges were detected.", ""])
        return
    lines.extend(["| Edge_ID | Type | Source | Target | Status | Source record | Evidence_ID |", "| --- | --- | --- | --- | --- | --- | --- |"])
    for edge in edges:
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(edge.id),
                    _cell(edge.type),
                    _cell(_node_label(graph.nodes.get(edge.source), edge.source)),
                    _cell(_node_label(graph.nodes.get(edge.target), edge.target)),
                    _cell(edge.status),
                    _cell(_source_record(edge)),
                    _cell(edge.evidence_id or edge.metadata.get("evidence_id", "N/A")),
                ]
            )
            + " |"
        )
    lines.append("")


def _append_coverage_matrix_cn(lines: list[str], coverage: list[dict[str, str]]) -> None:
    lines.extend(["## 覆盖矩阵", "", "| 类别 | 状态 | P0 | P1 | P2 | Info | 说明 |", "| --- | --- | --- | --- | --- | --- | --- |"])
    for row in coverage:
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(row["category"]),
                    _cell(row["status_cn"]),
                    _cell(row["P0"]),
                    _cell(row["P1"]),
                    _cell(row["P2"]),
                    _cell(row["Info"]),
                    _cell(row["summary_cn"]),
                ]
            )
            + " |"
        )
    lines.append("")


def _append_coverage_matrix_en(lines: list[str], coverage: list[dict[str, str]]) -> None:
    lines.extend(["## Coverage Matrix", "", "| Category | Status | P0 | P1 | P2 | Info | Summary |", "| --- | --- | --- | --- | --- | --- | --- |"])
    for row in coverage:
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(row["category"]),
                    _cell(row["status_en"]),
                    _cell(row["P0"]),
                    _cell(row["P1"]),
                    _cell(row["P2"]),
                    _cell(row["Info"]),
                    _cell(row["summary_en"]),
                ]
            )
            + " |"
        )
    lines.append("")


def _append_architecture_findings_cn(lines: list[str], findings: list[ArchitectureFinding]) -> None:
    lines.extend(["## 缺失与风险清单", "", "| Severity | Category | Sheet | Row_ID | Field | 问题 | 建议 | Evidence_ID |", "| --- | --- | --- | --- | --- | --- | --- | --- |"])
    actionable = [finding for finding in findings if finding.severity != "Info"]
    if not actionable:
        lines.append("| PASS | N/A | N/A | N/A | N/A | 未发现需要处理的完整性或风险问题。 | 保留人工复核。 | N/A |")
    else:
        for finding in sorted(actionable, key=_architecture_finding_sort_key):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _cell(finding.severity),
                        _cell(finding.category),
                        _cell(finding.sheet),
                        _cell(finding.row_id or "N/A"),
                        _cell(finding.field or "N/A"),
                        _cell(finding.message_cn),
                        _cell(finding.suggested_action_cn),
                        _cell(finding.evidence_id or "N/A"),
                    ]
                )
                + " |"
            )
    lines.append("")


def _append_architecture_findings_en(lines: list[str], findings: list[ArchitectureFinding]) -> None:
    lines.extend(["## Missing Information And Risk List", "", "| Severity | Category | Sheet | Row_ID | Field | Message | Suggested action | Evidence_ID |", "| --- | --- | --- | --- | --- | --- | --- | --- |"])
    actionable = [finding for finding in findings if finding.severity != "Info"]
    if not actionable:
        lines.append("| PASS | N/A | N/A | N/A | N/A | No actionable completeness or risk findings were detected. | Keep manual review. | N/A |")
    else:
        for finding in sorted(actionable, key=_architecture_finding_sort_key):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _cell(finding.severity),
                        _cell(finding.category),
                        _cell(finding.sheet),
                        _cell(finding.row_id or "N/A"),
                        _cell(finding.field or "N/A"),
                        _cell(finding.message_en),
                        _cell(finding.suggested_action_en),
                        _cell(finding.evidence_id or "N/A"),
                    ]
                )
                + " |"
            )
    lines.append("")


def _append_observations_cn(lines: list[str], observations: list[ReviewObservation]) -> None:
    lines.extend(["## 审查观察项", ""])
    if not observations:
        lines.extend(["无额外审查观察项。", ""])
        return
    lines.extend(["| 等级 | 类别 | Sheet | Row_ID | 观察 |", "| --- | --- | --- | --- | --- |"])
    for observation in observations:
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(observation.severity),
                    _cell(observation.category),
                    _cell(observation.sheet),
                    _cell(observation.row_id or "N/A"),
                    _cell(observation.message_cn),
                ]
            )
            + " |"
        )
    lines.append("")


def _append_observations_en(lines: list[str], observations: list[ReviewObservation]) -> None:
    lines.extend(["## Review Observations", ""])
    if not observations:
        lines.extend(["No additional review observations.", ""])
        return
    lines.extend(["| Level | Category | Sheet | Row_ID | Observation |", "| --- | --- | --- | --- | --- |"])
    for observation in observations:
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(observation.severity),
                    _cell(observation.category),
                    _cell(observation.sheet),
                    _cell(observation.row_id or "N/A"),
                    _cell(observation.message_en),
                ]
            )
            + " |"
        )
    lines.append("")


def _append_category_cn(lines: list[str], title: str, findings: list[Finding]) -> None:
    lines.extend([f"### {title}", ""])
    if not findings:
        lines.extend(["无自动化发现。", ""])
        return
    for finding in sorted(findings, key=_finding_sort_key):
        lines.append(f"- `{finding.severity}` `{finding.sheet}` `{finding.row_id or 'N/A'}`：{_cn_message(finding)}")
    lines.append("")


def _append_category_en(lines: list[str], title: str, findings: list[Finding]) -> None:
    lines.extend([f"### {title}", ""])
    if not findings:
        lines.extend(["No automated findings.", ""])
        return
    for finding in sorted(findings, key=_finding_sort_key):
        lines.append(f"- `{finding.severity}` `{finding.sheet}` `{finding.row_id or 'N/A'}`: {finding.message}")
    lines.append("")


def _category_findings(findings: list[Finding], keywords: list[str]) -> list[Finding]:
    selected = []
    for finding in findings:
        text = f"{finding.gate} {finding.sheet} {finding.field} {finding.message} {finding.suggested_action}".lower()
        if any(keyword in text for keyword in keywords):
            selected.append(finding)
    return selected


def _from_finding(finding: Finding) -> ArchitectureFinding:
    return ArchitectureFinding(
        finding.severity,
        _category_from_sheet(finding.sheet),
        finding.sheet,
        finding.row_id,
        finding.field,
        _cn_message(finding),
        finding.message,
        _cn_action(finding),
        finding.suggested_action or "Review and correct the source workbook.",
        finding.evidence_id,
        source="validation_or_risk",
    )


def _graph_completeness_findings(graph: GraphModel) -> list[ArchitectureFinding]:
    findings: list[ArchitectureFinding] = []
    if not graph.nodes:
        findings.append(_arch("P0", "Graph", "normalized", "", "nodes", "Graph has no nodes.", "图模型没有节点，生成产物不可信。", "Rebuild from a workbook with valid in-scope records.", "补充有效的源表记录后重新生成。"))
    if not graph.edges:
        findings.append(_arch("P0", "Graph", "normalized", "", "edges", "Graph has no edges.", "图模型没有关系，无法进行数据流分析。", "Add valid dependencies, runtime, monitoring, security, or delivery relationships.", "补充有效依赖、运行、监控、安全或交付关系。"))
    if not any(edge.type in DATAFLOW_EDGE_TYPES for edge in graph.edges):
        findings.append(_arch("P0", "Graph", "normalized", "", "edges", "Graph has no real dataflow edges.", "图模型没有真实数据流关系。", "Add calls, external calls, reads, or writes in the workbook.", "在工作簿中补充 calls、external calls、reads 或 writes 关系。"))
    return findings


def _overview_readiness_findings(workbook: WorkbookData, graph: GraphModel) -> list[ArchitectureFinding]:
    missing = _overview_readiness_missing(workbook, graph)
    if not missing:
        return []
    return [
        _arch(
            "P2",
            "Executive Overview",
            "workbook",
            "",
            "overview_readiness",
            "Executive overview is not ready for a demo-level summary because required source information is missing or incomplete: "
            + "; ".join(item["en"] for item in missing)
            + ".",
            "当前数据还不足以支撑示例级总览图，缺失或不完整的信息包括："
            + "；".join(item["cn"] for item in missing)
            + "。",
            "Complete the listed workbook sheets and rerun the agent. Do not add inferred lines or diagram-only nodes.",
            "补齐上述源工作簿信息后重新运行 Agent；不要在图里补推断线或仅用于展示的节点。",
        )
    ]


def _service_completeness_findings(workbook: WorkbookData, graph: GraphModel) -> list[ArchitectureFinding]:
    findings: list[ArchitectureFinding] = []
    monitored = _monitored_object_ids(workbook)
    dataflow_connected = _dataflow_connected_ids(graph)
    for row in active_rows(workbook, "04_Services"):
        service_id = row.get("Service_ID", "")
        if row.get("Service_Priority") in {"P0", "P1"}:
            if not row.get("Service_Owner"):
                findings.append(_row_arch("P1", "Service", "04_Services", row, "Service_Owner", f"Critical service {service_id} has no Service_Owner.", f"关键服务 `{service_id}` 未填写 Service_Owner。", "Fill Service_Owner so accountability is clear.", "补充 Service_Owner，明确负责人。"))
            if not row.get("Listen_Ports"):
                findings.append(_row_arch("P1", "Service", "04_Services", row, "Listen_Ports", f"Critical service {service_id} has no Listen_Ports.", f"关键服务 `{service_id}` 未填写 Listen_Ports。", "Fill the listening ports or document why it has no listener.", "补充监听端口，或说明该服务无监听端口的原因。"))
            if not row.get("Running_On_Instance_ID"):
                findings.append(_row_arch("P1", "Service", "04_Services", row, "Running_On_Instance_ID", f"Critical service {service_id} has no runtime instance.", f"关键服务 `{service_id}` 未关联运行实例。", "Link the service to a server/runtime record.", "关联服务运行的服务器或 runtime 记录。"))
            if service_id not in monitored:
                findings.append(_row_arch("P1", "Service", "04_Services", row, "Service_ID", f"Critical service {service_id} has no monitoring coverage.", f"关键服务 `{service_id}` 没有监控覆盖记录。", "Add a 10_Monitoring row for the service.", "在 10_Monitoring 中补充该服务的监控记录。"))
            if service_id not in dataflow_connected:
                findings.append(_row_arch("P2", "Service", "04_Services", row, "Service_ID", f"Critical service {service_id} has no dataflow in/out edge.", f"关键服务 `{service_id}` 没有数据流入/流出关系。", "Confirm whether the service is isolated or add missing dependencies.", "确认该服务是否孤立；如不是，补充依赖关系。"))
        if not row.get("Evidence_ID"):
            findings.append(_row_arch("P2", "Service", "04_Services", row, "Evidence_ID", f"Service {service_id} has no Evidence_ID.", f"服务 `{service_id}` 未填写 Evidence_ID。", "Link evidence for this service inventory row.", "为服务清单记录关联证据。"))
    return findings


def _dependency_completeness_findings(workbook: WorkbookData) -> list[ArchitectureFinding]:
    findings: list[ArchitectureFinding] = []
    firewalls = _firewalls_by_dependency(workbook)
    monitored = _monitored_object_ids(workbook)
    has_egress_path = _has_egress_path(workbook)
    for row in active_rows(workbook, "05_Dependencies"):
        dep_id = row.get("Dependency_ID", "")
        critical = row.get("Dependency_Criticality") in {"P0", "P1"}
        if not (row.get("Target_Service_ID") or row.get("Target_External_ID") or row.get("Target_Data_Asset_ID") or row.get("Target_ID")):
            findings.append(_row_arch("P1" if critical else "P2", "Dependency", "05_Dependencies", row, "Target_ID", f"Dependency {dep_id} has no explicit target.", f"依赖 `{dep_id}` 没有明确目标。", "Fill a target service, external system, data asset, or explicit Target_ID.", "补充目标服务、外部系统、数据资产或 Target_ID。"))
        if critical and not firewalls.get(dep_id):
            findings.append(_row_arch("P1", "Dependency", "05_Dependencies", row, "Dependency_ID", f"Critical dependency {dep_id} has no related firewall rule.", f"关键依赖 `{dep_id}` 未关联 Firewall 规则。", "Link a 07_Firewalls row through Related_Dependency_ID or document the exception.", "通过 Related_Dependency_ID 关联防火墙规则，或记录例外说明。"))
        if critical and dep_id not in monitored:
            findings.append(_row_arch("P2", "Dependency", "05_Dependencies", row, "Dependency_ID", f"Critical dependency {dep_id} has no direct monitoring coverage.", f"关键依赖 `{dep_id}` 没有直接监控覆盖。", "Add dependency-level monitoring or document service-level coverage.", "补充依赖级监控，或说明由服务级监控覆盖。"))
        if not row.get("Auth_Method"):
            findings.append(_row_arch("P2", "Dependency", "05_Dependencies", row, "Auth_Method", f"Dependency {dep_id} has no Auth_Method.", f"依赖 `{dep_id}` 未填写 Auth_Method。", "Fill the authentication or trust model.", "补充认证方式或信任模型。"))
        if row.get("Target_External_ID") and not has_egress_path:
            findings.append(_row_arch("P2", "Dependency", "05_Dependencies", row, "Target_External_ID", f"External dependency {dep_id} has no recorded NAT/PSC/Peering egress path.", f"外部依赖 `{dep_id}` 没有记录 NAT/PSC/Peering 出站路径。", "Add network egress details or document why direct egress is acceptable.", "补充网络出站路径，或说明直接出站可接受的原因。"))
    return findings


def _data_asset_completeness_findings(workbook: WorkbookData) -> list[ArchitectureFinding]:
    findings: list[ArchitectureFinding] = []
    monitored = _monitored_object_ids(workbook)
    for row in active_rows(workbook, "06_Data_Assets"):
        asset_id = row.get("Data_Asset_ID", "")
        sensitive = row.get("Sensitivity", "").lower() in {"restricted", "high", "critical"}
        if not row.get("Used_By_Service_ID"):
            findings.append(_row_arch("P2", "Data Asset", "06_Data_Assets", row, "Used_By_Service_ID", f"Data asset {asset_id} has no Used_By_Service_ID.", f"数据资产 `{asset_id}` 未填写 Used_By_Service_ID。", "Link the services that read or write this asset.", "关联读取或写入该资产的服务。"))
        if not row.get("Access_Method"):
            findings.append(_row_arch("P2", "Data Asset", "06_Data_Assets", row, "Access_Method", f"Data asset {asset_id} has no Access_Method.", f"数据资产 `{asset_id}` 未填写 Access_Method。", "Fill database/storage access method and port if applicable.", "补充数据库或存储访问方式及端口。"))
        if not row.get("Sensitivity"):
            findings.append(_row_arch("P2", "Data Asset", "06_Data_Assets", row, "Sensitivity", f"Data asset {asset_id} has no Sensitivity.", f"数据资产 `{asset_id}` 未填写 Sensitivity。", "Classify the data sensitivity.", "补充数据敏感性分类。"))
        if not row.get("Backup_Policy"):
            findings.append(_row_arch("P2", "Data Asset", "06_Data_Assets", row, "Backup_Policy", f"Data asset {asset_id} has no Backup_Policy.", f"数据资产 `{asset_id}` 未填写 Backup_Policy。", "Document backup or explicitly mark not applicable.", "补充备份策略，或明确标记不适用。"))
        if sensitive and asset_id not in monitored:
            findings.append(_row_arch("P1", "Data Asset", "06_Data_Assets", row, "Data_Asset_ID", f"Sensitive data asset {asset_id} has no monitoring coverage.", f"敏感数据资产 `{asset_id}` 没有监控覆盖。", "Add monitoring/logging/alert coverage for the asset.", "为该资产补充监控、日志或告警覆盖。"))
    return findings


def _external_service_completeness_findings(workbook: WorkbookData) -> list[ArchitectureFinding]:
    findings: list[ArchitectureFinding] = []
    for row in active_rows(workbook, "12_External_Services"):
        external_id = row.get("External_ID", "")
        for field, cn_label in [("Auth_Method", "Auth_Method"), ("Purpose", "Purpose"), ("Data_Classification", "Data_Classification"), ("Used_By_Service_ID", "Used_By_Service_ID")]:
            if not row.get(field):
                findings.append(_row_arch("P2", "External Service", "12_External_Services", row, field, f"External service {external_id} has no {field}.", f"外部系统 `{external_id}` 未填写 {cn_label}。", f"Fill {field} for external dependency review.", f"补充 {cn_label}，用于外部依赖复核。"))
    return findings


def _network_completeness_findings(workbook: WorkbookData) -> list[ArchitectureFinding]:
    findings: list[ArchitectureFinding] = []
    rows = active_rows(workbook, "02_Networks")
    external_deps = [row for row in active_rows(workbook, "05_Dependencies") if row.get("Target_External_ID")]
    if external_deps and not _has_egress_path(workbook):
        findings.append(_arch("P2", "Network", "02_Networks", "", "NAT_Name", "External dependencies exist but no NAT/PSC/Peering path is recorded.", "存在外部依赖，但网络记录中没有 NAT/PSC/Peering 出站路径。", "Document the egress path in 02_Networks.", "在 02_Networks 中补充出站路径。"))
    for row in rows:
        if not row.get("Subnet_Name"):
            findings.append(_row_arch("P2", "Network", "02_Networks", row, "Subnet_Name", f"Network {row.get('Network_ID')} has no Subnet_Name.", f"网络 `{row.get('Network_ID')}` 未填写 Subnet_Name。", "Fill the subnet boundary or mark not applicable in notes.", "补充 subnet 边界，或在备注说明不适用。"))
        if not row.get("CIDR"):
            findings.append(_row_arch("P2", "Network", "02_Networks", row, "CIDR", f"Network {row.get('Network_ID')} has no CIDR.", f"网络 `{row.get('Network_ID')}` 未填写 CIDR。", "Fill CIDR for boundary review.", "补充 CIDR 以支持边界复核。"))
    return findings


def _firewall_completeness_findings(workbook: WorkbookData) -> list[ArchitectureFinding]:
    findings: list[ArchitectureFinding] = []
    issues = _issues_by_object(workbook)
    for row in active_rows(workbook, "07_Firewalls"):
        fw_id = row.get("Firewall_ID", "")
        wide_open = row.get("Direction", "").lower() == "ingress" and "0.0.0.0/0" in row.get("Source_Allowed", "")
        accepted = row.get("Confirmation_Status") == "Accepted_Exception"
        if wide_open and not accepted:
            findings.append(_row_arch("P1", "Firewall", "07_Firewalls", row, "Source_Allowed", f"Firewall {fw_id} allows ingress from 0.0.0.0/0 without Accepted_Exception status.", f"Firewall `{fw_id}` 允许 0.0.0.0/0 入站，但未标记为 Accepted_Exception。", "Restrict the source range or record an accepted exception with evidence.", "收敛来源范围，或记录带证据的已接受例外。"))
        if accepted:
            issue = issues.get(fw_id)
            if not issue:
                findings.append(_row_arch("P1", "Firewall", "07_Firewalls", row, "Confirmation_Status", f"Accepted exception firewall {fw_id} has no linked issue record.", f"已接受例外 Firewall `{fw_id}` 没有关联 Issue 记录。", "Add a 13_Issues_Exceptions row for this exception.", "在 13_Issues_Exceptions 中补充该例外记录。"))
            else:
                missing_fields = [field for field in ("Owner", "Due_Date", "Related_Evidence_ID") if not issue.get(field)]
                if missing_fields:
                    findings.append(_arch("P2", "Firewall", "13_Issues_Exceptions", issue.get("Issue_ID", ""), ",".join(missing_fields), f"Accepted exception for firewall {fw_id} is missing {', '.join(missing_fields)}.", f"Firewall `{fw_id}` 的已接受例外缺少 {', '.join(missing_fields)}。", "Complete owner, due date, and evidence for exception governance.", "补充负责人、到期时间和证据，便于例外治理。", issue.get("Related_Evidence_ID", "")))
    return findings


def _iam_completeness_findings(workbook: WorkbookData) -> list[ArchitectureFinding]:
    rows = active_rows(workbook, "09_IAM_SA")
    if not rows:
        return [_arch("P2", "IAM", "09_IAM_SA", "", "IAM_Binding_ID", "No IAM / Service Account records are present.", "未提供 IAM / Service Account 记录，无法评估权限链路。", "Collect IAM bindings or explicitly document why IAM is out of scope.", "补充 IAM 绑定信息，或明确说明权限链路不在本次范围内。")]
    findings: list[ArchitectureFinding] = []
    usage: dict[str, int] = {}
    for row in rows:
        if row.get("Service_Account_ID"):
            usage[row["Service_Account_ID"]] = usage.get(row["Service_Account_ID"], 0) + len([item for item in row.get("Used_By_Service_ID", "").split(";") if item.strip()])
    for row in rows:
        role = row.get("Role", "")
        role_lower = role.lower()
        high = row.get("Is_High_Privilege", "").lower() == "yes" or role_lower in {"owner", "editor"} or role_lower.endswith("/owner") or "admin" in role_lower or "*" in role
        if high and not row.get("Justification"):
            findings.append(_row_arch("P1", "IAM", "09_IAM_SA", row, "Justification", f"High privilege IAM binding {row.get('IAM_Binding_ID')} has no justification.", f"高权限 IAM 绑定 `{row.get('IAM_Binding_ID')}` 未填写 Justification。", "Document least-privilege reason, scope, and approver.", "补充最小权限原因、范围和审批人。"))
        if row.get("Service_Account_ID") and usage.get(row["Service_Account_ID"], 0) > 1 and not row.get("Justification"):
            findings.append(_row_arch("P2", "IAM", "09_IAM_SA", row, "Service_Account_ID", f"Shared service account {row.get('Service_Account_ID')} has no justification.", f"共享服务账号 `{row.get('Service_Account_ID')}` 未填写 Justification。", "Document why the service account is shared or split it by service.", "说明共享原因，或按服务拆分账号。"))
    return findings


def _monitoring_completeness_findings(workbook: WorkbookData) -> list[ArchitectureFinding]:
    findings: list[ArchitectureFinding] = []
    for row in active_rows(workbook, "10_Monitoring"):
        monitoring_id = row.get("Monitoring_ID", "")
        if row.get("Coverage_Status") in {"Missing", "Unknown"}:
            findings.append(_row_arch("P2", "Monitoring", "10_Monitoring", row, "Coverage_Status", f"Monitoring {monitoring_id} is {row.get('Coverage_Status')}.", f"监控 `{monitoring_id}` 覆盖状态为 {row.get('Coverage_Status')}。", "Confirm and update monitoring coverage.", "确认并更新监控覆盖。"))
        if row.get("Coverage_Status") == "Partial":
            missing = [field for field in ("Dashboard_URL", "Alert_Rule", "Logging_Coverage", "XDR_Coverage") if not row.get(field) or row.get(field) in {"Unknown", "Not confirmed in repo"}]
            if missing:
                findings.append(_row_arch("P2", "Monitoring", "10_Monitoring", row, ",".join(missing), f"Partial monitoring {monitoring_id} is missing or has unconfirmed controls: {', '.join(missing)}.", f"Partial 监控 `{monitoring_id}` 存在缺失或未确认控制项：{', '.join(missing)}。", "Complete dashboard, alert, logging, and XDR coverage evidence or document gaps.", "补充 dashboard、alert、logging、XDR 证据，或记录缺口。"))
    return findings


def _cicd_completeness_findings(workbook: WorkbookData) -> list[ArchitectureFinding]:
    findings: list[ArchitectureFinding] = []
    for row in active_rows(workbook, "11_CICD"):
        cicd_id = row.get("CICD_ID", "")
        for field in ("Deployment_Account", "Runner", "Artifact_Registry"):
            if not row.get(field):
                findings.append(_row_arch("P2", "CI/CD", "11_CICD", row, field, f"CI/CD record {cicd_id} has no {field}.", f"CI/CD 记录 `{cicd_id}` 未填写 {field}。", f"Fill {field} for delivery-chain review.", f"补充 {field}，用于交付链路复核。"))
        if row.get("Approval_Required") in {"", "No", "Not_Required"}:
            findings.append(_row_arch("P2", "CI/CD", "11_CICD", row, "Approval_Required", f"CI/CD record {cicd_id} does not show required approval.", f"CI/CD 记录 `{cicd_id}` 未体现审批要求。", "Confirm deployment approval requirements.", "确认部署审批要求。"))
        if not (row.get("Target_Service_ID") or row.get("Target_Instance_ID")):
            findings.append(_row_arch("P2", "CI/CD", "11_CICD", row, "Target_Service_ID", f"CI/CD record {cicd_id} has no deployment target.", f"CI/CD 记录 `{cicd_id}` 未关联部署目标。", "Link the deployment to a target service or instance.", "关联部署目标服务或实例。"))
    return findings


def _issue_evidence_completeness_findings(workbook: WorkbookData) -> list[ArchitectureFinding]:
    findings: list[ArchitectureFinding] = []
    for row in active_rows(workbook, "13_Issues_Exceptions"):
        issue_id = row.get("Issue_ID", "")
        if row.get("Status") == "Accepted_Exception":
            missing = [field for field in ("Owner", "Due_Date", "Related_Evidence_ID") if not row.get(field)]
            if missing:
                findings.append(_row_arch("P2", "Issue", "13_Issues_Exceptions", row, ",".join(missing), f"Accepted exception {issue_id} is missing governance fields: {', '.join(missing)}.", f"已接受例外 `{issue_id}` 缺少治理字段：{', '.join(missing)}。", "Complete owner, due date, and evidence.", "补充负责人、到期时间和证据。", evidence_id=row.get("Related_Evidence_ID", "")))
    for row in active_rows(workbook, "14_Evidence_Index"):
        if not row.get("Integrity_Note"):
            findings.append(_row_arch("P2", "Evidence", "14_Evidence_Index", row, "Integrity_Note", f"Evidence {row.get('Evidence_ID')} has no Integrity_Note.", f"证据 `{row.get('Evidence_ID')}` 未填写 Integrity_Note。", "Add a short integrity or retention note.", "补充完整性或留存说明。"))
    indexed = {row.get("Evidence_ID", "") for row in active_rows(workbook, "14_Evidence_Index")}
    for sheet, rows in workbook.sheets.items():
        if sheet in {"00_Metadata", "90_Enums", "14_Evidence_Index"}:
            continue
        for row in active_rows(workbook, sheet):
            evidence_id = row.get("Evidence_ID") or row.get("Related_Evidence_ID")
            if evidence_id and evidence_id not in indexed:
                findings.append(_row_arch("P2", "Evidence", sheet, row, "Evidence_ID", f"Evidence reference {evidence_id} is not in 14_Evidence_Index.", f"证据引用 `{evidence_id}` 不存在于 14_Evidence_Index。", "Add the evidence index row or correct the reference.", "补充证据索引行或修正引用。", evidence_id=evidence_id))
    return findings


def _review_observations(workbook: WorkbookData, graph: GraphModel) -> list[ReviewObservation]:
    observations: list[ReviewObservation] = []
    observations.extend(_overview_readiness_observations(workbook, graph))
    observations.extend(_inventory_observations(workbook, graph))
    observations.extend(_network_observations(workbook))
    observations.extend(_service_inventory_observations(workbook, graph))
    observations.extend(_service_monitoring_observations(workbook))
    observations.extend(_dependency_observations(workbook))
    observations.extend(_data_asset_observations(workbook))
    observations.extend(_external_service_observations(workbook))
    observations.extend(_firewall_observations(workbook))
    observations.extend(_monitoring_observations(workbook))
    observations.extend(_iam_observations(workbook))
    observations.extend(_cicd_observations(workbook))
    observations.extend(_issue_evidence_observations(workbook))
    if not graph.dropped_edges:
        observations.append(
            ReviewObservation(
                "Info",
                "Traceability",
                "normalized",
                "",
                "没有 dropped edge，说明本次生成出的图关系都能回溯到工作簿中的有效节点。",
                "No dropped edges were detected, so generated graph relationships can be traced back to valid workbook nodes.",
            )
        )
    return observations


def _overview_readiness_observations(workbook: WorkbookData, graph: GraphModel) -> list[ReviewObservation]:
    missing = _overview_readiness_missing(workbook, graph)
    if missing:
        return [
            ReviewObservation(
                "Review",
                "Executive Overview",
                "workbook",
                "",
                "总览图就绪度：NEEDS_REVIEW。当前数据只能生成真实但信息有限的图；缺失项包括："
                + "；".join(item["cn"] for item in missing)
                + "。",
                "Executive overview readiness: NEEDS_REVIEW. The current data can produce a truthful but limited diagram; missing items include: "
                + "; ".join(item["en"] for item in missing)
                + ".",
            )
        ]
    return [
        ReviewObservation(
            "Info",
            "Executive Overview",
            "workbook",
            "",
            "总览图就绪度：READY。当前源表包含入口边界、核心数据流、数据资产、外部依赖、网络出口、安全控制、监控、IAM、CI/CD 和证据，可支撑会议级总览图生成。",
            "Executive overview readiness: READY. The source workbook includes entry boundary, core dataflow, data assets, external dependencies, network egress, security controls, monitoring, IAM, CI/CD, and evidence, so it can support an executive overview diagram.",
        )
    ]


def _inventory_observations(workbook: WorkbookData, graph: GraphModel) -> list[ReviewObservation]:
    counts = {
        "projects": len(active_rows(workbook, "01_Projects")),
        "networks": len(active_rows(workbook, "02_Networks")),
        "servers": len(active_rows(workbook, "03_Servers")),
        "services": len(active_rows(workbook, "04_Services")),
        "dependencies": len(active_rows(workbook, "05_Dependencies")),
        "data_assets": len(active_rows(workbook, "06_Data_Assets")),
        "external_services": len(active_rows(workbook, "12_External_Services")),
    }
    return [
        ReviewObservation(
            "Info",
            "Inventory",
            "workbook",
            "",
            "采集库存："
            + "，".join(
                [
                    f"项目={counts['projects']}",
                    f"网络={counts['networks']}",
                    f"服务器={counts['servers']}",
                    f"服务={counts['services']}",
                    f"依赖={counts['dependencies']}",
                    f"数据资产={counts['data_assets']}",
                    f"外部系统={counts['external_services']}",
                    f"graph 节点={len(graph.nodes)}",
                    f"graph 关系={len(graph.edges)}",
                ]
            )
            + "。",
            "Collection inventory: "
            + ", ".join(
                [
                    f"projects={counts['projects']}",
                    f"networks={counts['networks']}",
                    f"servers={counts['servers']}",
                    f"services={counts['services']}",
                    f"dependencies={counts['dependencies']}",
                    f"data_assets={counts['data_assets']}",
                    f"external_services={counts['external_services']}",
                    f"graph_nodes={len(graph.nodes)}",
                    f"graph_edges={len(graph.edges)}",
                ]
            )
            + ".",
        )
    ]


def _network_observations(workbook: WorkbookData) -> list[ReviewObservation]:
    rows = active_rows(workbook, "02_Networks")
    if not rows:
        return [
            ReviewObservation(
                "Review",
                "Network",
                "02_Networks",
                "",
                "未提供网络记录，因此无法判断 VPC、Subnet、NAT、LB 或 PSC/Peering 边界。",
                "No network records were provided, so VPC, subnet, NAT, LB, or PSC/peering boundaries cannot be assessed.",
            )
        ]
    nat = sorted({row.get("NAT_Name", "") for row in rows if row.get("NAT_Name")})
    lbs = sorted({row.get("LB_Name", "") for row in rows if row.get("LB_Name")})
    psc = sorted({row.get("PSC_or_Peering_Name", "") for row in rows if row.get("PSC_or_Peering_Name")})
    subnets = sorted({row.get("Subnet_Name", "") for row in rows if row.get("Subnet_Name")})
    observations = [
        ReviewObservation(
            "Info",
            "Network",
            "02_Networks",
            "",
            f"网络记录共 {len(rows)} 条；Subnet={len(subnets)}，NAT={_join_items(nat)}，LB={_join_items(lbs)}，PSC/Peering={_join_items(psc)}。",
            f"Network records: {len(rows)}; subnets={len(subnets)}, NAT={_join_items_en(nat)}, LB={_join_items_en(lbs)}, PSC/Peering={_join_items_en(psc)}.",
        )
    ]
    external_deps = [row for row in active_rows(workbook, "05_Dependencies") if row.get("Target_External_ID")]
    if external_deps and not nat and not psc:
        observations.append(
            ReviewObservation(
                "Review",
                "Network",
                "02_Networks",
                "",
                f"存在 {len(external_deps)} 条外部依赖，但网络记录中未体现 NAT 或 PSC/Peering，建议确认出站路径。",
                f"There are {len(external_deps)} external dependencies, but no NAT or PSC/peering is recorded; confirm the egress path.",
            )
        )
    return observations


def _service_inventory_observations(workbook: WorkbookData, graph: GraphModel) -> list[ReviewObservation]:
    rows = active_rows(workbook, "04_Services")
    if not rows:
        return [
            ReviewObservation(
                "Review",
                "Service",
                "04_Services",
                "",
                "未提供服务记录，因此无法判断服务清单、端口、运行位置或上下游关系。",
                "No service records were provided, so service inventory, ports, runtime location, or upstream/downstream relationships cannot be assessed.",
            )
        ]
    priority_summary = _value_summary(rows, "Service_Priority")
    runtime_types = sorted({row.get("Runtime_Type", "") for row in rows if row.get("Runtime_Type")})
    missing_ports = [row.get("Service_ID", "") for row in rows if not row.get("Listen_Ports")]
    isolated = _isolated_services(rows, graph)
    observations = [
        ReviewObservation(
            "Info",
            "Service",
            "04_Services",
            "",
            f"服务共 {len(rows)} 个；优先级分布：{priority_summary}；显式 Runtime_Type：{_join_items(runtime_types)}。",
            f"Services: {len(rows)}; priority summary: {priority_summary}; explicit Runtime_Type: {_join_items_en(runtime_types)}.",
        )
    ]
    if missing_ports:
        observations.append(
            ReviewObservation(
                "Review",
                "Service",
                "04_Services",
                "",
                f"存在 {len(missing_ports)} 个服务未填写 Listen_Ports：{_join_items(missing_ports)}。",
                f"{len(missing_ports)} services have blank Listen_Ports: {_join_items_en(missing_ports)}.",
            )
        )
    if isolated:
        observations.append(
            ReviewObservation(
                "Review",
                "Service",
                "04_Services",
                "",
                f"存在 {len(isolated)} 个服务没有数据流入/流出关系：{_join_items(isolated)}。",
                f"{len(isolated)} services have no dataflow in/out relationships: {_join_items_en(isolated)}.",
            )
        )
    return observations


def _service_monitoring_observations(workbook: WorkbookData) -> list[ReviewObservation]:
    p0_services = [row for row in active_rows(workbook, "04_Services") if row.get("Service_Priority") == "P0"]
    if not p0_services:
        return []
    monitored_ids = {row.get("Object_ID", "") for row in active_rows(workbook, "10_Monitoring") if row.get("Object_ID")}
    covered = [row.get("Service_Name") or row.get("Service_ID", "") for row in p0_services if row.get("Service_ID") in monitored_ids]
    missing = [row.get("Service_Name") or row.get("Service_ID", "") for row in p0_services if row.get("Service_ID") not in monitored_ids]
    level = "Review" if missing else "Info"
    return [
        ReviewObservation(
            level,
            "Monitoring",
            "04_Services",
            "",
            f"P0 服务共 {len(p0_services)} 个；已有监控关系：{_join_items(covered)}；缺少监控关系：{_join_items(missing)}。",
            f"P0 services: {len(p0_services)}; with monitoring relationships: {_join_items_en(covered)}; missing monitoring relationships: {_join_items_en(missing)}.",
        )
    ]


def _dependency_observations(workbook: WorkbookData) -> list[ReviewObservation]:
    rows = active_rows(workbook, "05_Dependencies")
    if not rows:
        return [
            ReviewObservation(
                "Review",
                "Dependency",
                "05_Dependencies",
                "",
                "未提供依赖记录，因此无法判断服务之间、外部系统和数据资产访问链路。",
                "No dependency records were provided, so service-to-service, external, or data-asset access paths cannot be assessed.",
            )
        ]
    target_counts = {
        "service": len([row for row in rows if row.get("Target_Service_ID")]),
        "external": len([row for row in rows if row.get("Target_External_ID")]),
        "data_asset": len([row for row in rows if row.get("Target_Data_Asset_ID")]),
    }
    missing_auth = [row.get("Dependency_ID", "") for row in rows if not row.get("Auth_Method")]
    critical = [row for row in rows if row.get("Dependency_Criticality") in {"P0", "P1"}]
    observations = [
        ReviewObservation(
            "Info",
            "Dependency",
            "05_Dependencies",
            "",
            f"依赖共 {len(rows)} 条；关键依赖={len(critical)}；目标分布：service={target_counts['service']}，external={target_counts['external']}，data_asset={target_counts['data_asset']}；Criticality 分布：{_value_summary(rows, 'Dependency_Criticality')}。",
            f"Dependencies: {len(rows)}; critical dependencies={len(critical)}; target summary: service={target_counts['service']}, external={target_counts['external']}, data_asset={target_counts['data_asset']}; criticality summary: {_value_summary(rows, 'Dependency_Criticality')}.",
        )
    ]
    if missing_auth:
        observations.append(
            ReviewObservation(
                "Review",
                "Dependency",
                "05_Dependencies",
                "",
                f"存在 {len(missing_auth)} 条依赖未填写 Auth_Method：{_join_items(missing_auth)}。",
                f"{len(missing_auth)} dependencies have blank Auth_Method: {_join_items_en(missing_auth)}.",
            )
        )
    return observations


def _data_asset_observations(workbook: WorkbookData) -> list[ReviewObservation]:
    rows = active_rows(workbook, "06_Data_Assets")
    if not rows:
        return [
            ReviewObservation(
                "Review",
                "Data Asset",
                "06_Data_Assets",
                "",
                "未提供数据资产记录，因此无法判断存储、数据库、备份、敏感性和服务访问关系。",
                "No data-asset records were provided, so storage, database, backup, sensitivity, and service access relationships cannot be assessed.",
            )
        ]
    missing_backup = [row.get("Data_Asset_ID", "") for row in rows if not row.get("Backup_Policy")]
    sensitive = [row.get("Data_Asset_ID", "") for row in rows if row.get("Sensitivity", "").lower() in {"restricted", "high", "critical"}]
    observations = [
        ReviewObservation(
            "Info",
            "Data Asset",
            "06_Data_Assets",
            "",
            f"数据资产共 {len(rows)} 个；类型分布：{_value_summary(rows, 'Data_Asset_Type')}；敏感性分布：{_value_summary(rows, 'Sensitivity')}；高敏资产：{_join_items(sensitive)}。",
            f"Data assets: {len(rows)}; type summary: {_value_summary(rows, 'Data_Asset_Type')}; sensitivity summary: {_value_summary(rows, 'Sensitivity')}; sensitive assets: {_join_items_en(sensitive)}.",
        )
    ]
    if missing_backup:
        observations.append(
            ReviewObservation(
                "Review",
                "Data Asset",
                "06_Data_Assets",
                "",
                f"存在 {len(missing_backup)} 个数据资产未填写 Backup_Policy：{_join_items(missing_backup)}。",
                f"{len(missing_backup)} data assets have blank Backup_Policy: {_join_items_en(missing_backup)}.",
            )
        )
    return observations


def _external_service_observations(workbook: WorkbookData) -> list[ReviewObservation]:
    rows = active_rows(workbook, "12_External_Services")
    if not rows:
        return [
            ReviewObservation(
                "Info",
                "External Service",
                "12_External_Services",
                "",
                "未提供外部系统记录；如果工作负载确实没有外部依赖，该状态可以接受，否则需要补充外部系统清单。",
                "No external service records were provided. This is acceptable only if the workload truly has no external dependencies; otherwise add the external system inventory.",
            )
        ]
    missing_auth = [row.get("External_ID", "") for row in rows if not row.get("Auth_Method")]
    observations = [
        ReviewObservation(
            "Info",
            "External Service",
            "12_External_Services",
            "",
            f"外部系统共 {len(rows)} 个；类型分布：{_value_summary(rows, 'External_Type')}；方向分布：{_value_summary(rows, 'Direction')}；数据分类分布：{_value_summary(rows, 'Data_Classification')}。",
            f"External services: {len(rows)}; type summary: {_value_summary(rows, 'External_Type')}; direction summary: {_value_summary(rows, 'Direction')}; data classification summary: {_value_summary(rows, 'Data_Classification')}.",
        )
    ]
    if missing_auth:
        observations.append(
            ReviewObservation(
                "Review",
                "External Service",
                "12_External_Services",
                "",
                f"存在 {len(missing_auth)} 个外部系统未填写 Auth_Method：{_join_items(missing_auth)}。",
                f"{len(missing_auth)} external services have blank Auth_Method: {_join_items_en(missing_auth)}.",
            )
        )
    return observations


def _firewall_observations(workbook: WorkbookData) -> list[ReviewObservation]:
    rows = active_rows(workbook, "07_Firewalls")
    if not rows:
        return [
            ReviewObservation(
                "Review",
                "Security",
                "07_Firewalls",
                "",
                "未提供 Firewall 规则，因此无法从本次采集信息判断访问控制覆盖。",
                "No firewall rules were provided, so access-control coverage cannot be assessed from this collection.",
            )
        ]
    observations = [
        ReviewObservation(
            "Info",
            "Security",
            "07_Firewalls",
            "",
            f"Firewall 规则共 {len(rows)} 条；方向分布：{_direction_summary(rows)}。",
            f"Firewall rules: {len(rows)}; direction summary: {_direction_summary(rows)}.",
        )
    ]
    for row in rows:
        accepted = row.get("Confirmation_Status") == "Accepted_Exception"
        wide_open = row.get("Direction", "").lower() == "ingress" and "0.0.0.0/0" in row.get("Source_Allowed", "")
        if accepted or wide_open:
            row_id = row.get("Firewall_ID", "")
            source = row.get("Source_Allowed", "N/A")
            ports = row.get("Ports", "N/A")
            reason = row.get("Reason", "N/A")
            observations.append(
                ReviewObservation(
                    "Review",
                    "Security",
                    "07_Firewalls",
                    row_id,
                    f"Firewall `{row_id}` 需要安全复核：状态={row.get('Confirmation_Status', 'N/A')}，源={source}，端口={ports}，原因={reason}。",
                    f"Firewall `{row_id}` needs security review: status={row.get('Confirmation_Status', 'N/A')}, source={source}, ports={ports}, reason={reason}.",
                )
            )
    return observations


def _monitoring_observations(workbook: WorkbookData) -> list[ReviewObservation]:
    rows = active_rows(workbook, "10_Monitoring")
    if not rows:
        return [
            ReviewObservation(
                "Review",
                "Monitoring",
                "10_Monitoring",
                "",
                "未提供 Monitoring 记录，因此无法判断服务、数据资产和关键依赖的监控覆盖。",
                "No monitoring records were provided, so service, data-asset, and dependency monitoring coverage cannot be assessed.",
            )
        ]
    statuses = _value_summary(rows, "Coverage_Status")
    partial_rows = [row for row in rows if row.get("Coverage_Status") == "Partial"]
    missing_dashboard = [row for row in rows if not row.get("Dashboard_URL")]
    unconfirmed_alert = [row for row in rows if row.get("Alert_Rule", "").lower() in {"", "not confirmed in repo", "unknown"}]
    unknown_xdr = [row for row in rows if row.get("XDR_Coverage", "").lower() in {"", "unknown", "not confirmed in repo"}]
    observations = [
        ReviewObservation(
            "Info",
            "Monitoring",
            "10_Monitoring",
            "",
            f"Monitoring 记录共 {len(rows)} 条；覆盖状态分布：{statuses}。",
            f"Monitoring records: {len(rows)}; coverage status summary: {statuses}.",
        )
    ]
    if partial_rows or missing_dashboard or unconfirmed_alert or unknown_xdr:
        observations.append(
            ReviewObservation(
                "Review",
                "Monitoring",
                "10_Monitoring",
                "",
                f"监控存在需确认项：Partial={len(partial_rows)}，Dashboard_URL 为空={len(missing_dashboard)}，Alert_Rule 未确认={len(unconfirmed_alert)}，XDR_Coverage 未知={len(unknown_xdr)}。",
                f"Monitoring needs review: Partial={len(partial_rows)}, blank Dashboard_URL={len(missing_dashboard)}, unconfirmed Alert_Rule={len(unconfirmed_alert)}, unknown XDR_Coverage={len(unknown_xdr)}.",
            )
        )
    return observations


def _iam_observations(workbook: WorkbookData) -> list[ReviewObservation]:
    rows = active_rows(workbook, "09_IAM_SA")
    if not rows:
        return [
            ReviewObservation(
                "Review",
                "IAM",
                "09_IAM_SA",
                "",
                "当前没有 IAM / Service Account 记录；这不代表没有权限风险，只代表本次采集信息无法评估权限链路。",
                "No IAM / Service Account records are present. This does not prove there is no identity risk; it means permission relationships cannot be assessed from this collection.",
            )
        ]
    return [
        ReviewObservation(
            "Info",
            "IAM",
            "09_IAM_SA",
            "",
            f"IAM / Service Account 记录共 {len(rows)} 条，可用于权限链路复核。",
            f"IAM / Service Account records: {len(rows)}, available for permission-chain review.",
        )
    ]


def _cicd_observations(workbook: WorkbookData) -> list[ReviewObservation]:
    rows = active_rows(workbook, "11_CICD")
    if not rows:
        return [
            ReviewObservation(
                "Review",
                "CI/CD",
                "11_CICD",
                "",
                "未提供 CI/CD 记录，因此无法判断部署入口、审批、Runner、制品仓库或部署账号。",
                "No CI/CD records were provided, so deployment entry, approval, runner, artifact registry, or deployment account cannot be assessed.",
            )
        ]
    approval = _value_summary(rows, "Approval_Required")
    missing_approval = [row.get("CICD_ID", "") for row in rows if row.get("Approval_Required") in {"", "No", "Not_Required"}]
    missing_target = [row.get("CICD_ID", "") for row in rows if not (row.get("Target_Service_ID") or row.get("Target_Instance_ID"))]
    observations = [
        ReviewObservation(
            "Info",
            "CI/CD",
            "11_CICD",
            "",
            f"CI/CD 记录共 {len(rows)} 条；系统分布：{_value_summary(rows, 'System')}；审批分布：{approval}。",
            f"CI/CD records: {len(rows)}; system summary: {_value_summary(rows, 'System')}; approval summary: {approval}.",
        )
    ]
    if missing_approval:
        observations.append(
            ReviewObservation(
                "Review",
                "CI/CD",
                "11_CICD",
                "",
                f"存在 {len(missing_approval)} 条部署记录未体现审批要求：{_join_items(missing_approval)}。",
                f"{len(missing_approval)} deployment records do not show an approval requirement: {_join_items_en(missing_approval)}.",
            )
        )
    if missing_target:
        observations.append(
            ReviewObservation(
                "Review",
                "CI/CD",
                "11_CICD",
                "",
                f"存在 {len(missing_target)} 条部署记录未关联目标服务或实例：{_join_items(missing_target)}。",
                f"{len(missing_target)} deployment records are not linked to a target service or instance: {_join_items_en(missing_target)}.",
            )
        )
    return observations


def _issue_evidence_observations(workbook: WorkbookData) -> list[ReviewObservation]:
    observations: list[ReviewObservation] = []
    issue_rows = active_rows(workbook, "13_Issues_Exceptions")
    evidence_rows = active_rows(workbook, "14_Evidence_Index")
    if issue_rows:
        observations.append(
            ReviewObservation(
                "Info",
                "Issue",
                "13_Issues_Exceptions",
                "",
                f"Issue/Exception 记录共 {len(issue_rows)} 条；严重度分布：{_value_summary(issue_rows, 'Severity')}；状态分布：{_value_summary(issue_rows, 'Status')}。",
                f"Issue/Exception records: {len(issue_rows)}; severity summary: {_value_summary(issue_rows, 'Severity')}; status summary: {_value_summary(issue_rows, 'Status')}.",
            )
        )
    else:
        observations.append(
            ReviewObservation(
                "Info",
                "Issue",
                "13_Issues_Exceptions",
                "",
                "未提供 Issue/Exception 记录；如果存在已知例外或待办项，应补充到该表。",
                "No issue/exception records were provided. Add known exceptions or open action items to this sheet if any exist.",
            )
        )
    observations.append(
        ReviewObservation(
            "Info" if evidence_rows else "Review",
            "Evidence",
            "14_Evidence_Index",
            "",
            f"Evidence 记录共 {len(evidence_rows)} 条；来源系统分布：{_value_summary(evidence_rows, 'Source_System') if evidence_rows else '无'}。",
            f"Evidence records: {len(evidence_rows)}; source system summary: {_value_summary(evidence_rows, 'Source_System') if evidence_rows else 'None'}.",
        )
    )
    missing_integrity = [row.get("Evidence_ID", "") for row in evidence_rows if not row.get("Integrity_Note")]
    if missing_integrity:
        observations.append(
            ReviewObservation(
                "Review",
                "Evidence",
                "14_Evidence_Index",
                "",
                f"存在 {len(missing_integrity)} 条证据未填写 Integrity_Note：{_join_items(missing_integrity)}。",
                f"{len(missing_integrity)} evidence records have blank Integrity_Note: {_join_items_en(missing_integrity)}.",
            )
        )
    return observations


def _overview_readiness_missing(workbook: WorkbookData, graph: GraphModel) -> list[dict[str, str]]:
    missing: list[dict[str, str]] = []
    service_ids = {row.get("Service_ID", "") for row in active_rows(workbook, "04_Services") if row.get("Service_ID")}
    dataflow_edges = [edge for edge in graph.edges if edge.type in DATAFLOW_EDGE_TYPES]
    service_dataflow_edges = [edge for edge in dataflow_edges if edge.source in service_ids or edge.target in service_ids]
    external_dependencies = [row for row in active_rows(workbook, "05_Dependencies") if row.get("Target_External_ID") or row.get("Target_Type") == "external"]
    monitoring_rows = active_rows(workbook, "10_Monitoring")

    if not _has_entry_boundary(workbook):
        missing.append(
            {
                "cn": "`03_Servers.IP_External`、入口服务或 `08_Cloud_Armor` 未提供清晰入口边界",
                "en": "`03_Servers.IP_External`, an entry service, or `08_Cloud_Armor` does not provide a clear entry boundary",
            }
        )
    if not service_dataflow_edges:
        missing.append(
            {
                "cn": "`05_Dependencies` 没有可用于总览图的服务上下游数据流",
                "en": "`05_Dependencies` has no service upstream/downstream dataflow for the overview",
            }
        )
    if not active_rows(workbook, "06_Data_Assets"):
        missing.append(
            {
                "cn": "`06_Data_Assets` 没有数据资产记录",
                "en": "`06_Data_Assets` has no data asset records",
            }
        )
    if external_dependencies and not active_rows(workbook, "12_External_Services"):
        missing.append(
            {
                "cn": "`05_Dependencies` 存在外部依赖，但 `12_External_Services` 没有外部系统记录",
                "en": "`05_Dependencies` has external dependencies but `12_External_Services` has no external service records",
            }
        )
    if external_dependencies and not _has_egress_path(workbook):
        missing.append(
            {
                "cn": "存在外部依赖，但 `02_Networks.NAT_Name` / `PSC_or_Peering_Name` 未记录出站路径",
                "en": "external dependencies exist but `02_Networks.NAT_Name` / `PSC_or_Peering_Name` does not record an egress path",
            }
        )
    if not active_rows(workbook, "07_Firewalls") and not active_rows(workbook, "08_Cloud_Armor"):
        missing.append(
            {
                "cn": "`07_Firewalls` 和 `08_Cloud_Armor` 都没有安全控制记录",
                "en": "`07_Firewalls` and `08_Cloud_Armor` both have no security control records",
            }
        )
    if not monitoring_rows:
        missing.append(
            {
                "cn": "`10_Monitoring` 没有监控覆盖记录",
                "en": "`10_Monitoring` has no monitoring coverage records",
            }
        )
    elif not any(row.get("Coverage_Status") == "Covered" for row in monitoring_rows):
        missing.append(
            {
                "cn": "`10_Monitoring.Coverage_Status` 没有任何 Covered 记录",
                "en": "`10_Monitoring.Coverage_Status` has no Covered records",
            }
        )
    if not active_rows(workbook, "09_IAM_SA"):
        missing.append(
            {
                "cn": "`09_IAM_SA` 没有 IAM / Service Account 记录",
                "en": "`09_IAM_SA` has no IAM / Service Account records",
            }
        )
    if not active_rows(workbook, "11_CICD"):
        missing.append(
            {
                "cn": "`11_CICD` 没有交付链路记录",
                "en": "`11_CICD` has no delivery-chain records",
            }
        )
    if not active_rows(workbook, "14_Evidence_Index"):
        missing.append(
            {
                "cn": "`14_Evidence_Index` 没有证据索引记录",
                "en": "`14_Evidence_Index` has no evidence index records",
            }
        )
    return missing


def _has_entry_boundary(workbook: WorkbookData) -> bool:
    if active_rows(workbook, "08_Cloud_Armor"):
        return True
    for row in active_rows(workbook, "03_Servers"):
        if row.get("IP_External") or row.get("Public_IP_or_LB") or row.get("LB_Name"):
            return True
        role_text = " ".join([row.get("Server_Role", ""), row.get("Network_Tag", ""), row.get("Hostname", "")]).lower()
        if any(keyword in role_text for keyword in ("entry", "ingress", "nginx", "gateway", "lb", "public")):
            return True
    for row in active_rows(workbook, "04_Services"):
        service_text = " ".join([row.get("Service_ID", ""), row.get("Service_Name", ""), row.get("Service_Role", ""), row.get("Description", "")]).lower()
        if any(keyword in service_text for keyword in ("entry", "ingress", "nginx", "gateway", "lb", "public")):
            return True
    return False


def _direction_summary(rows: list[dict[str, str]]) -> str:
    return _value_summary(rows, "Direction")


def _write_architecture_json(
    path: Path,
    conclusion: str,
    findings: list[ArchitectureFinding],
    completeness_findings: list[ArchitectureFinding],
    observations: list[ReviewObservation],
    coverage: list[dict[str, str]],
    dataflow_edges: list[GraphEdge],
    graph: GraphModel,
) -> None:
    payload = {
        "conclusion": conclusion,
        "severity_counts": _severity_counts(findings),
        "new_completeness_finding_count": len(completeness_findings),
        "finding_count": len(findings),
        "review_observation_count": len(observations),
        "dataflow_edge_count": len(dataflow_edges),
        "dropped_edge_count": len(graph.dropped_edges),
        "coverage_matrix": coverage,
        "findings": [finding.as_dict() for finding in sorted(findings, key=_architecture_finding_sort_key)],
        "review_observations": [observation.__dict__ for observation in observations],
        "dataflow_edges": [
            {
                "edge_id": edge.id,
                "type": edge.type,
                "source": edge.source,
                "target": edge.target,
                "status": edge.status,
                "source_record": _source_record(edge),
                "evidence_id": edge.evidence_id or edge.metadata.get("evidence_id", ""),
            }
            for edge in dataflow_edges
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _coverage_matrix(findings: list[ArchitectureFinding], observations: list[ReviewObservation]) -> list[dict[str, str]]:
    categories = ["Executive Overview", "Service", "Dependency", "Data Asset", "External Service", "Network", "Firewall", "IAM", "Monitoring", "CI/CD", "Evidence", "Issue", "Graph", "Inventory", "Traceability"]
    rows: list[dict[str, str]] = []
    for category in categories:
        category_findings = [finding for finding in findings if finding.category == category]
        category_observations = [observation for observation in observations if observation.category == category]
        counts = _severity_counts(category_findings)
        status_cn, status_en = _category_status(counts)
        rows.append(
            {
                "category": category,
                "status_cn": status_cn,
                "status_en": status_en,
                "P0": str(counts["P0"]),
                "P1": str(counts["P1"]),
                "P2": str(counts["P2"]),
                "Info": str(counts["Info"]),
                "summary_cn": f"发现 {len(category_findings)} 条，观察 {len(category_observations)} 条。",
                "summary_en": f"{len(category_findings)} findings, {len(category_observations)} observations.",
            }
        )
    return rows


def _category_status(counts: dict[str, int]) -> tuple[str, str]:
    if counts["P0"]:
        return "BLOCKED", "BLOCKED"
    if counts["P1"]:
        return "NEEDS_FIX", "NEEDS_FIX"
    if counts["P2"]:
        return "NEEDS_REVIEW", "NEEDS_REVIEW"
    return "PASS", "PASS"


def _architecture_conclusion(findings: list[ArchitectureFinding], pending: list[Finding]) -> str:
    counts = _severity_counts(findings)
    if counts["P0"]:
        return "BLOCKED"
    if counts["P1"]:
        return "NEEDS_FIX"
    if counts["P2"] or pending:
        return "NEEDS_REVIEW"
    return "PASS"


def _severity_counts(findings: list[ArchitectureFinding]) -> dict[str, int]:
    counts = {"P0": 0, "P1": 0, "P2": 0, "P3": 0, "Info": 0}
    for finding in findings:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1
    return counts


def _architecture_finding_sort_key(finding: ArchitectureFinding) -> tuple[int, str, str, str]:
    return (_severity_order(finding.severity), finding.category, finding.sheet, finding.row_id)


def _category_from_sheet(sheet: str) -> str:
    return {
        "01_Projects": "Inventory",
        "02_Networks": "Network",
        "03_Servers": "Service",
        "04_Services": "Service",
        "05_Dependencies": "Dependency",
        "06_Data_Assets": "Data Asset",
        "07_Firewalls": "Firewall",
        "08_Cloud_Armor": "Firewall",
        "09_IAM_SA": "IAM",
        "10_Monitoring": "Monitoring",
        "11_CICD": "CI/CD",
        "12_External_Services": "External Service",
        "13_Issues_Exceptions": "Issue",
        "14_Evidence_Index": "Evidence",
        "normalized": "Graph",
    }.get(sheet, "Evidence")


def _arch(
    severity: str,
    category: str,
    sheet: str,
    row_id: str,
    field: str,
    message_en: str,
    message_cn: str,
    action_en: str,
    action_cn: str,
    evidence_id: str = "",
) -> ArchitectureFinding:
    return ArchitectureFinding(severity, category, sheet, row_id, field, message_cn, message_en, action_cn, action_en, evidence_id)


def _row_arch(
    severity: str,
    category: str,
    sheet: str,
    row: Row,
    field: str,
    message_en: str,
    message_cn: str,
    action_en: str,
    action_cn: str,
    evidence_id: str = "",
) -> ArchitectureFinding:
    return _arch(severity, category, sheet, _row_id(row), field, message_en, message_cn, action_en, action_cn, evidence_id or row.get("Evidence_ID") or row.get("Related_Evidence_ID", ""))


def _row_id(row: Row) -> str:
    for field in ("Record_ID", "Issue_ID", "Dependency_ID", "Service_ID", "Data_Asset_ID", "External_ID", "Firewall_ID", "IAM_Binding_ID", "Monitoring_ID", "CICD_ID", "Network_ID", "Evidence_ID"):
        if row.get(field):
            return row[field]
    return ""


def _monitored_object_ids(workbook: WorkbookData) -> set[str]:
    return {row.get("Object_ID", "") for row in active_rows(workbook, "10_Monitoring") if row.get("Object_ID") and row.get("Coverage_Status") in {"Covered", "Partial"}}


def _dataflow_connected_ids(graph: GraphModel) -> set[str]:
    edges = [edge for edge in graph.edges if edge.type in DATAFLOW_EDGE_TYPES]
    return {edge.source for edge in edges} | {edge.target for edge in edges}


def _firewalls_by_dependency(workbook: WorkbookData) -> dict[str, list[Row]]:
    by_dependency: dict[str, list[Row]] = {}
    for row in active_rows(workbook, "07_Firewalls"):
        if row.get("Related_Dependency_ID"):
            by_dependency.setdefault(row["Related_Dependency_ID"], []).append(row)
    return by_dependency


def _has_egress_path(workbook: WorkbookData) -> bool:
    return any(row.get("NAT_Name") or row.get("PSC_or_Peering_Name") for row in active_rows(workbook, "02_Networks"))


def _issues_by_object(workbook: WorkbookData) -> dict[str, Row]:
    issues: dict[str, Row] = {}
    for row in active_rows(workbook, "13_Issues_Exceptions"):
        if row.get("Affected_Object_ID"):
            issues[row["Affected_Object_ID"]] = row
    return issues


def _value_summary(rows: list[dict[str, str]], field: str) -> str:
    counts: dict[str, int] = {}
    for row in rows:
        value = row.get(field) or "Blank"
        counts[value] = counts.get(value, 0) + 1
    return ", ".join(f"{key}={counts[key]}" for key in sorted(counts))


def _join_items(items: list[str]) -> str:
    return ", ".join(item for item in items if item) or "无"


def _join_items_en(items: list[str]) -> str:
    return ", ".join(item for item in items if item) or "None"


def _isolated_services(rows: list[dict[str, str]], graph: GraphModel) -> list[str]:
    dataflow_edges = [edge for edge in graph.edges if edge.type in DATAFLOW_EDGE_TYPES]
    connected = {edge.source for edge in dataflow_edges} | {edge.target for edge in dataflow_edges}
    return [row.get("Service_Name") or row.get("Service_ID", "") for row in rows if row.get("Service_ID") not in connected]


def _conclusion(findings: list[Finding]) -> str:
    if any(finding.severity == "P0" for finding in findings):
        return "BLOCKED"
    if any(finding.severity == "P1" or finding.status == "Pending_Confirmation" for finding in findings):
        return "NEEDS_REVIEW"
    return "PASS"


def _finding_sort_key(finding: Finding) -> tuple[int, str, str, str]:
    return (_severity_order(finding.severity), finding.sheet, finding.row_id, finding.field)


def _severity_order(severity: str) -> int:
    return {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "Info": 4}.get(severity, 9)


def _node_label(node: GraphNode | None, fallback: str) -> str:
    if not node:
        return fallback
    return f"{node.label} ({node.id})"


def _source_record(edge: GraphEdge) -> str:
    sheet = edge.metadata.get("source_sheet", "N/A")
    record = edge.metadata.get("record_id") or edge.metadata.get("dependency_id") or edge.id
    return f"{sheet}:{record}"


def _cn_message(finding: Finding) -> str:
    if finding.status == "Pending_Confirmation":
        return "该记录仍处于待确认状态，不能作为最终事实直接验收。"
    lowered = finding.message.lower()
    if "monitoring" in lowered:
        return "监控覆盖不完整，需要补充监控、日志、告警或仪表盘记录。"
    if "firewall" in lowered:
        return "访问控制信息不完整或与依赖不匹配，需要补充防火墙规则、端口或例外说明。"
    if "privilege" in lowered or "iam" in lowered:
        return "权限记录需要复核，需要补充最小权限、共享账号或高权限说明。"
    if "dropped graph edge" in lowered or "does not exist" in lowered or "foreign key" in lowered:
        return "引用关系无法落到真实对象，需要修正 ID 或补充目标记录。"
    if "evidence" in lowered:
        return "证据引用不完整，需要补充 Evidence_ID 或证据索引。"
    return finding.message


def _cn_action(finding: Finding) -> str:
    if finding.status == "Pending_Confirmation":
        return "确认事实后改为 Confirmed；如确认为例外，按流程记录 Accepted_Exception。"
    lowered = finding.suggested_action.lower()
    if "monitoring" in lowered or "dashboard" in lowered or "alert" in lowered:
        return "在 10_Monitoring 中补充对象级监控、日志、告警或仪表盘记录。"
    if "firewall" in lowered:
        return "在 07_Firewalls 中补充关联规则，或记录已接受例外。"
    if "correct" in lowered or "reference" in lowered or "target" in lowered:
        return "修正源表引用 ID，或补充被引用对象。"
    if finding.suggested_action:
        return finding.suggested_action
    return "复核该行并在源工作簿中修正。"


def _cell(value: object) -> str:
    text = str(value or "").replace("\n", " ").replace("|", "\\|").strip()
    return text or "N/A"
