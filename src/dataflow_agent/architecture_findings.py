from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .models import Finding, GraphEdge, GraphModel, GraphNode, WorkbookData
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


def write_architecture_findings(
    path: Path,
    workbook: WorkbookData,
    graph: GraphModel,
    validation_findings: list[Finding],
    risk_findings: list[Finding],
) -> None:
    findings = validation_findings + risk_findings
    dataflow_edges = [edge for edge in graph.edges if edge.type in DATAFLOW_EDGE_TYPES]
    blocking = [finding for finding in findings if finding.severity in {"P0", "P1"}]
    pending = [finding for finding in findings if finding.status == "Pending_Confirmation"]
    observations = _review_observations(workbook, graph)
    conclusion = _conclusion(findings)
    lines: list[str] = []
    _append_chinese(lines, workbook, graph, findings, dataflow_edges, blocking, pending, observations, conclusion)
    lines.extend(["---", ""])
    _append_english(lines, workbook, graph, findings, dataflow_edges, blocking, pending, observations, conclusion)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _append_chinese(
    lines: list[str],
    workbook: WorkbookData,
    graph: GraphModel,
    findings: list[Finding],
    dataflow_edges: list[GraphEdge],
    blocking: list[Finding],
    pending: list[Finding],
    observations: list[ReviewObservation],
    conclusion: str,
) -> None:
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
            f"- 待确认记录：{len(pending)}",
            f"- 丢弃关系：{len(graph.dropped_edges)}",
            f"- 真实数据流关系：{len(dataflow_edges)}",
            f"- 审查观察项：{len(observations)}",
            "",
            "## 使用口径",
            "",
            "本报告直接分析 Excel/DCP 生成的 graph model、校验结果、风险结果和可审查事实，不依赖人工阅读图形。下面列出的链路只来自真实 graph edge；不存在的关系不会被补画或补写。`问题分组` 是自动化 finding，`审查观察项` 是通过但仍建议在安全/监控评审中确认的事实。",
            "",
            "## 真实数据流链路",
            "",
        ]
    )
    _append_dataflow_edges_cn(lines, graph, dataflow_edges)
    _append_observations_cn(lines, observations)
    lines.extend(["## 问题分组", ""])
    _append_category_cn(lines, "必须优先处理", blocking)
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
            "如果本报告指出问题，应修改源 Excel/DCP 后重新运行脚本。不要直接修改生成的图、报告或压缩包。",
            "",
        ]
    )


def _append_english(
    lines: list[str],
    workbook: WorkbookData,
    graph: GraphModel,
    findings: list[Finding],
    dataflow_edges: list[GraphEdge],
    blocking: list[Finding],
    pending: list[Finding],
    observations: list[ReviewObservation],
    conclusion: str,
) -> None:
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
            f"- Pending records: {len(pending)}",
            f"- Dropped edges: {len(graph.dropped_edges)}",
            f"- Real dataflow edges: {len(dataflow_edges)}",
            f"- Review observations: {len(observations)}",
            "",
            "## Review Basis",
            "",
            "This report analyzes the graph model, validation findings, risk findings, and reviewable facts generated from the Excel/DCP source. It does not rely on manual diagram reading. The dataflow paths below are derived only from real graph edges; nonexistent relationships are not invented. `Finding Groups` are automated findings, while `Review Observations` are passing facts that should still be confirmed during security or monitoring review.",
            "",
            "## Real Dataflow Paths",
            "",
        ]
    )
    _append_dataflow_edges_en(lines, graph, dataflow_edges)
    _append_observations_en(lines, observations)
    lines.extend(["## Finding Groups", ""])
    _append_category_en(lines, "Must Fix First", blocking)
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
            "If this report identifies a problem, correct the source Excel/DCP and rerun the script. Do not directly edit generated diagrams, reports, or archives.",
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


def _review_observations(workbook: WorkbookData, graph: GraphModel) -> list[ReviewObservation]:
    observations: list[ReviewObservation] = []
    observations.extend(_service_monitoring_observations(workbook))
    observations.extend(_firewall_observations(workbook))
    observations.extend(_monitoring_observations(workbook))
    observations.extend(_iam_observations(workbook))
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


def _direction_summary(rows: list[dict[str, str]]) -> str:
    return _value_summary(rows, "Direction")


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
