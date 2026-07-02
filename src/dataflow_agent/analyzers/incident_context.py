from __future__ import annotations

from pathlib import Path
from typing import Any

from dataflow_agent.models import GraphModel, Row, WorkbookData
from dataflow_agent.util import safe_id, split_multi, write_json

from .data_quality import analyze_data_quality
from .indexes import AnalysisIndexes
from .models import AnalysisFinding
from .monitoring import analyze_monitoring_gaps
from .security import analyze_security_risks


def build_incident_context(
    workbook: WorkbookData,
    graph: GraphModel,
    indexes: AnalysisIndexes,
    service_id: str,
    alert_text: str = "",
) -> dict[str, Any]:
    service = indexes.services.get(service_id)
    if not service:
        raise ValueError(f"Service_ID does not exist in workbook: {service_id}")
    related_findings = _related_findings(
        service_id,
        analyze_data_quality(workbook, graph, indexes)
        + analyze_monitoring_gaps(workbook, graph, indexes)
        + analyze_security_risks(workbook, graph, indexes),
    )
    context = {
        "service_id": service_id,
        "alert": alert_text,
        "service": _service_context(service),
        "upstream": _node_refs(graph, sorted(indexes.upstream.get(service_id, set()))),
        "downstream": _node_refs(graph, sorted(indexes.downstream.get(service_id, set()))),
        "ports": _ports_context(service, indexes),
        "dependencies": _dependency_context(service_id, indexes),
        "data_assets": [_row_subset(row, ("Data_Asset_ID", "Data_Asset_Name", "Data_Asset_Type", "Access_Method", "Sensitivity", "Evidence_ID")) for row in indexes.data_assets_by_service.get(service_id, [])],
        "external_dependencies": [_row_subset(row, ("External_ID", "External_Name", "Endpoint", "Purpose", "Data_Classification", "Evidence_ID")) for row in indexes.external_by_service.get(service_id, [])],
        "monitoring": [_row_subset(row, ("Monitoring_ID", "Object_Type", "Object_ID", "Dashboard_URL", "Alert_Rule", "Logging_Coverage", "XDR_Coverage", "Coverage_Status", "Evidence_ID")) for row in _monitoring_rows(service_id, indexes)],
        "iam": [_row_subset(row, ("IAM_Binding_ID", "Service_Account_ID", "Service_Account_Email", "Role", "Scope", "Is_High_Privilege", "Justification", "Evidence_ID")) for row in indexes.iam_by_service.get(service_id, [])],
        "cicd": [_row_subset(row, ("CICD_ID", "Pipeline_Name", "System", "Repo", "Runner", "Deployment_Entry", "Deployment_Account", "Approval_Required", "Evidence_ID")) for row in indexes.cicd_by_target_service.get(service_id, [])],
        "related_risks": [finding.as_dict() for finding in related_findings],
    }
    context["investigation_order"] = _investigation_order(context)
    return context


def write_incident_context_report(
    output_dir: Path,
    context: dict[str, Any],
) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    service_id = safe_id(str(context["service_id"]))
    md_path = output / f"incident_context_{service_id}.md"
    json_path = output / f"incident_context_{service_id}.json"
    md_path.write_text(_render_markdown(context), encoding="utf-8")
    write_json(json_path, context)
    return {"md": md_path, "json": json_path}


def _service_context(row: Row) -> dict[str, str]:
    return _row_subset(
        row,
        (
            "Service_ID",
            "Service_Name",
            "Service_Priority",
            "Service_Owner",
            "Service_Role",
            "Running_On_Instance_ID",
            "Runtime_ID",
            "Protocol",
            "Listen_Ports",
            "Evidence_ID",
        ),
    )


def _node_refs(graph: GraphModel, node_ids: list[str]) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    for node_id in node_ids:
        node = graph.nodes.get(node_id)
        refs.append(
            {
                "id": node_id,
                "type": node.type if node else "",
                "label": node.label if node else node_id,
                "sheet": node.sheet if node else "",
            }
        )
    return refs


def _ports_context(service: Row, indexes: AnalysisIndexes) -> dict[str, Any]:
    service_id = service.get("Service_ID", "")
    inbound = [
        _dependency_port(row)
        for row in indexes.dependencies_by_target.get(service_id, [])
        if row.get("Dependency_ID")
    ]
    outbound = [
        _dependency_port(row)
        for row in indexes.dependencies_by_source.get(service_id, [])
        if row.get("Dependency_ID")
    ]
    return {
        "listen_ports": split_multi(service.get("Listen_Ports", "")),
        "protocol": service.get("Protocol", ""),
        "inbound_dependencies": inbound,
        "outbound_dependencies": outbound,
    }


def _dependency_context(service_id: str, indexes: AnalysisIndexes) -> dict[str, list[dict[str, str]]]:
    return {
        "inbound": [_dependency_row(row) for row in indexes.dependencies_by_target.get(service_id, [])],
        "outbound": [_dependency_row(row) for row in indexes.dependencies_by_source.get(service_id, [])],
    }


def _dependency_row(row: Row) -> dict[str, str]:
    return _row_subset(
        row,
        (
            "Dependency_ID",
            "Source_Service_ID",
            "Target_Service_ID",
            "Target_External_ID",
            "Target_Data_Asset_ID",
            "Target_Type",
            "Target_ID",
            "Target_Port",
            "Target_Port_Protocol",
            "Auth_Method",
            "Direction",
            "Dependency_Criticality",
            "Evidence_ID",
        ),
    )


def _dependency_port(row: Row) -> dict[str, str]:
    return _row_subset(row, ("Dependency_ID", "Source_Service_ID", "Target_ID", "Target_Port", "Target_Port_Protocol", "Direction", "Evidence_ID"))


def _monitoring_rows(service_id: str, indexes: AnalysisIndexes) -> list[Row]:
    rows = list(indexes.monitoring_by_object.get(("service", service_id), []))
    for dependency in indexes.dependencies_by_source.get(service_id, []):
        rows.extend(indexes.monitoring_by_object.get(("dependency", dependency.get("Dependency_ID", "")), []))
    seen: set[str] = set()
    unique: list[Row] = []
    for row in rows:
        key = row.get("Monitoring_ID", "") or row.get("Record_ID", "")
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return sorted(unique, key=lambda row: row.get("Monitoring_ID", ""))


def _related_findings(service_id: str, findings: list[AnalysisFinding]) -> list[AnalysisFinding]:
    rows: list[AnalysisFinding] = []
    for finding in findings:
        if finding.object_id == service_id:
            rows.append(finding)
            continue
        if service_id in finding.message or service_id in finding.impact:
            rows.append(finding)
    return sorted(rows, key=lambda item: (item.severity, item.domain, item.finding_id))


def _investigation_order(context: dict[str, Any]) -> list[dict[str, str]]:
    steps: list[dict[str, str]] = []
    related_risks = context.get("related_risks", [])
    if related_risks:
        steps.append({"step": "1", "focus": "Review related analysis findings", "reason": f"{len(related_risks)} related findings are already linked to this service."})
    monitoring = context.get("monitoring", [])
    if not monitoring:
        steps.append({"step": str(len(steps) + 1), "focus": "Confirm monitoring coverage", "reason": "No service or dependency monitoring row is linked to this service."})
    else:
        steps.append({"step": str(len(steps) + 1), "focus": "Open dashboards and alert rules", "reason": "Use collected monitoring records as the first operational evidence."})
    if context.get("dependencies", {}).get("inbound"):
        steps.append({"step": str(len(steps) + 1), "focus": "Check upstream callers", "reason": "Inbound dependencies may explain traffic, error, or timeout propagation."})
    if context.get("dependencies", {}).get("outbound"):
        steps.append({"step": str(len(steps) + 1), "focus": "Check downstream dependencies", "reason": "Outbound service, data asset, or external dependency failures may surface as this service alert."})
    if context.get("iam"):
        steps.append({"step": str(len(steps) + 1), "focus": "Validate IAM and deployment identity", "reason": "IAM bindings can affect data access, runtime behavior, and emergency changes."})
    if context.get("cicd"):
        steps.append({"step": str(len(steps) + 1), "focus": "Review recent deployment path", "reason": "CI/CD records identify deployment entry, account, runner, and approval context."})
    return steps


def _row_subset(row: Row, fields: tuple[str, ...]) -> dict[str, str]:
    return {field: row.get(field, "") for field in fields}


def _render_markdown(context: dict[str, Any]) -> str:
    service = context["service"]
    lines = [
        f"# Incident Context: {context['service_id']}",
        "",
        "This branch-only report is generated from the collected workbook and graph. Alert text is included as operator context only; it is not treated as source-of-truth data.",
        "",
        f"- Alert: {context.get('alert') or 'N/A'}",
        f"- Service name: {service.get('Service_Name') or context['service_id']}",
        f"- Owner: {service.get('Service_Owner') or 'N/A'}",
        f"- Priority: {service.get('Service_Priority') or 'N/A'}",
        f"- Listen ports: {', '.join(context['ports']['listen_ports']) if context['ports']['listen_ports'] else 'N/A'}",
        "",
        "## Investigation Order",
        "",
    ]
    for step in context["investigation_order"]:
        lines.append(f"{step['step']}. {step['focus']} - {step['reason']}")
    lines.extend(["", "## Upstream", ""])
    _append_table(lines, context["upstream"], ("id", "type", "label", "sheet"))
    lines.extend(["", "## Downstream", ""])
    _append_table(lines, context["downstream"], ("id", "type", "label", "sheet"))
    lines.extend(["", "## Outbound Dependencies", ""])
    _append_table(lines, context["dependencies"]["outbound"], ("Dependency_ID", "Target_Service_ID", "Target_External_ID", "Target_Data_Asset_ID", "Target_Port", "Target_Port_Protocol", "Auth_Method", "Evidence_ID"))
    lines.extend(["", "## Monitoring", ""])
    _append_table(lines, context["monitoring"], ("Monitoring_ID", "Object_Type", "Object_ID", "Coverage_Status", "Dashboard_URL", "Alert_Rule", "Evidence_ID"))
    lines.extend(["", "## IAM", ""])
    _append_table(lines, context["iam"], ("IAM_Binding_ID", "Service_Account_ID", "Role", "Is_High_Privilege", "Justification", "Evidence_ID"))
    lines.extend(["", "## CI/CD", ""])
    _append_table(lines, context["cicd"], ("CICD_ID", "Pipeline_Name", "Deployment_Entry", "Deployment_Account", "Approval_Required", "Evidence_ID"))
    lines.extend(["", "## Related Findings", ""])
    _append_table(lines, context["related_risks"], ("finding_id", "domain", "severity", "category", "message", "suggested_action", "evidence_id"))
    return "\n".join(lines) + "\n"


def _append_table(lines: list[str], rows: list[dict[str, Any]], fields: tuple[str, ...]) -> None:
    if not rows:
        lines.append("None recorded.")
        return
    lines.append("| " + " | ".join(fields) + " |")
    lines.append("| " + " | ".join(["---"] * len(fields)) + " |")
    for row in rows:
        lines.append("| " + " | ".join(_md(str(row.get(field, ""))) for field in fields) + " |")


def _md(value: str) -> str:
    return (value or "").replace("|", "\\|").replace("\n", "<br>")
