from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dataflow_agent.constants import find_workbook
from dataflow_agent.graph_builder import build_graph
from dataflow_agent.models import DroppedEdge, GraphEdge, GraphModel, GraphNode, Row, WorkbookData
from dataflow_agent.normalizer import active_rows, normalize_workbook
from dataflow_agent.schema import load_schema
from dataflow_agent.util import write_json
from dataflow_agent.xlsx_reader import read_workbook


WORKBOOK_CATEGORIES = {
    "services": ("04_Services", "Service_ID"),
    "dependencies": ("05_Dependencies", "Dependency_ID"),
    "data_assets": ("06_Data_Assets", "Data_Asset_ID"),
    "external_services": ("12_External_Services", "External_ID"),
    "iam": ("09_IAM_SA", "IAM_Binding_ID"),
    "firewalls": ("07_Firewalls", "Firewall_ID"),
    "cloud_armor": ("08_Cloud_Armor", "Policy_ID"),
    "monitoring": ("10_Monitoring", "Monitoring_ID"),
    "cicd": ("11_CICD", "CICD_ID"),
    "evidence": ("14_Evidence_Index", "Evidence_ID"),
}
GRAPH_EDGE_TYPES = {"calls", "calls_external", "reads_from", "writes_to", "depends_on"}
SENSITIVE_LEVELS = {"restricted", "high", "critical"}
HIGH_PRIVILEGE_ROLE_TOKENS = ("owner", "editor", "admin", "*")


@dataclass(frozen=True)
class ChangeSource:
    path: Path
    source_type: str
    workbook: WorkbookData | None
    graph: GraphModel


@dataclass(frozen=True)
class ChangeRisk:
    risk_id: str
    severity: str
    category: str
    object_type: str
    object_id: str
    change_type: str
    message: str
    suggested_action: str
    evidence_id: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "risk_id": self.risk_id,
            "severity": self.severity,
            "category": self.category,
            "object_type": self.object_type,
            "object_id": self.object_id,
            "change_type": self.change_type,
            "message": self.message,
            "suggested_action": self.suggested_action,
            "evidence_id": self.evidence_id,
        }


def build_change_diff(base: Path, new: Path) -> dict[str, Any]:
    base_source = load_change_source(base)
    new_source = load_change_source(new)
    changes = _build_changes(base_source, new_source)
    risks = _build_risks(changes, new_source)
    return {
        "summary": {
            "base": str(base_source.path),
            "base_type": base_source.source_type,
            "new": str(new_source.path),
            "new_type": new_source.source_type,
            "added": _count_change_type(changes, "added"),
            "removed": _count_change_type(changes, "removed"),
            "changed": _count_change_type(changes, "changed"),
            "risks": len(risks),
        },
        "changes": changes,
        "risks": [risk.as_dict() for risk in risks],
    }


def write_change_diff_report(output_dir: Path, diff: dict[str, Any]) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    md_path = output / "change_diff_report.md"
    json_path = output / "change_diff_risk.json"
    pr_path = output / "pr_review_comment.md"
    md_path.write_text(_render_report(diff), encoding="utf-8")
    write_json(json_path, diff)
    pr_path.write_text(_render_pr_comment(diff), encoding="utf-8")
    return {"md": md_path, "json": json_path, "pr": pr_path}


def load_change_source(path: Path) -> ChangeSource:
    resolved = Path(path).resolve()
    if resolved.is_file() and resolved.suffix.lower() == ".json":
        graph = _read_graph_json(resolved)
        return ChangeSource(path=resolved, source_type="graph_json", workbook=None, graph=graph)
    schema = load_schema()
    workbook = normalize_workbook(read_workbook(find_workbook(resolved), schema), schema)
    return ChangeSource(path=resolved, source_type="dcp", workbook=workbook, graph=build_graph(workbook))


def _build_changes(base: ChangeSource, new: ChangeSource) -> dict[str, dict[str, list[dict[str, Any]]]]:
    changes: dict[str, dict[str, list[dict[str, Any]]]] = {}
    if base.workbook and new.workbook:
        for category, (sheet, key_field) in WORKBOOK_CATEGORIES.items():
            changes[category] = _diff_maps(
                _rows_by_key(base.workbook, sheet, key_field),
                _rows_by_key(new.workbook, sheet, key_field),
            )
    changes["graph_nodes"] = _diff_maps(_graph_nodes(base.graph), _graph_nodes(new.graph))
    changes["graph_dataflow_edges"] = _diff_maps(_graph_edges(base.graph), _graph_edges(new.graph))
    return changes


def _build_risks(changes: dict[str, dict[str, list[dict[str, Any]]]], new_source: ChangeSource) -> list[ChangeRisk]:
    risks: list[ChangeRisk] = []
    for item in changes.get("services", {}).get("added", []):
        row = item["after"]
        if _is_public_service(row):
            risks.append(
                _risk(
                    "P1",
                    "added_public_service",
                    "service",
                    item["object_id"],
                    "added",
                    f"New public or entry-like service {item['object_id']} was added.",
                    "Confirm exposure, Cloud Armor/firewall controls, owner, monitoring, and rollback plan before rollout.",
                    row.get("Evidence_ID", ""),
                )
            )
    for item in changes.get("graph_dataflow_edges", {}).get("added", []):
        edge = item["after"]
        if edge.get("type") == "calls_external":
            risks.append(
                _risk(
                    "P1",
                    "added_external_call",
                    "graph_edge",
                    item["object_id"],
                    "added",
                    f"New external call {edge.get('source')} -> {edge.get('target')} was added.",
                    "Review egress path, authentication, data classification, timeout/fallback behavior, and monitoring.",
                    edge.get("evidence_id", ""),
                )
            )
        if edge.get("type") in {"reads_from", "writes_to"} and _edge_touches_sensitive_data(edge, new_source.graph):
            risks.append(
                _risk(
                    "P1",
                    "added_sensitive_data_access",
                    "graph_edge",
                    item["object_id"],
                    "added",
                    f"New sensitive data access {edge.get('source')} -> {edge.get('target')} was added.",
                    "Confirm least privilege, encryption, backup, audit logging, and monitoring coverage.",
                    edge.get("evidence_id", ""),
                )
            )
    for item in changes.get("iam", {}).get("added", []):
        row = item["after"]
        if _is_high_privilege_iam(row):
            risks.append(
                _risk(
                    "P1",
                    "added_high_privilege_iam",
                    "iam",
                    item["object_id"],
                    "added",
                    f"New high-privilege IAM binding {item['object_id']} was added.",
                    "Require least-privilege justification, scope review, owner approval, and evidence.",
                    row.get("Evidence_ID", ""),
                )
            )
    for category, object_type, message, action in (
        ("monitoring", "monitoring", "Monitoring coverage was removed.", "Confirm the replacement monitoring path before rollout."),
        ("firewalls", "firewall", "Firewall rule was removed.", "Confirm the removed rule is obsolete or replaced by an equivalent control."),
        ("cloud_armor", "cloud_armor", "Cloud Armor policy was removed.", "Confirm public entry protection remains in place."),
        ("evidence", "evidence", "Evidence record was removed.", "Confirm audit traceability remains sufficient for the changed object."),
    ):
        for item in changes.get(category, {}).get("removed", []):
            before = item["before"]
            severity = "P1" if category in {"monitoring", "cloud_armor"} else "P2"
            risks.append(
                _risk(
                    severity,
                    f"removed_{category}",
                    object_type,
                    item["object_id"],
                    "removed",
                    f"{message} Object: {item['object_id']}.",
                    action,
                    before.get("Evidence_ID", before.get("Evidence_ID", "")),
                )
            )
    return [
        ChangeRisk(
            risk_id=f"CD-{index:04d}",
            severity=risk.severity,
            category=risk.category,
            object_type=risk.object_type,
            object_id=risk.object_id,
            change_type=risk.change_type,
            message=risk.message,
            suggested_action=risk.suggested_action,
            evidence_id=risk.evidence_id,
        )
        for index, risk in enumerate(sorted(risks, key=lambda item: (item.severity, item.category, item.object_id, item.message)), start=1)
    ]


def _risk(
    severity: str,
    category: str,
    object_type: str,
    object_id: str,
    change_type: str,
    message: str,
    suggested_action: str,
    evidence_id: str = "",
) -> ChangeRisk:
    return ChangeRisk("", severity, category, object_type, object_id, change_type, message, suggested_action, evidence_id)


def _rows_by_key(workbook: WorkbookData, sheet: str, key_field: str) -> dict[str, dict[str, str]]:
    return {row[key_field]: _clean_row(row) for row in active_rows(workbook, sheet) if row.get(key_field)}


def _clean_row(row: Row) -> dict[str, str]:
    return {key: value for key, value in sorted(row.items()) if value not in ("", None)}


def _graph_nodes(graph: GraphModel) -> dict[str, dict[str, Any]]:
    return {node_id: node.as_dict() for node_id, node in sorted(graph.nodes.items())}


def _graph_edges(graph: GraphModel) -> dict[str, dict[str, Any]]:
    return {_edge_key(edge): edge.as_dict() for edge in graph.edges if edge.type in GRAPH_EDGE_TYPES}


def _edge_key(edge: GraphEdge) -> str:
    metadata = edge.metadata if isinstance(edge.metadata, dict) else {}
    record_id = metadata.get("record_id", "")
    return "|".join([edge.type, edge.source, edge.target, edge.label, str(record_id), edge.evidence_id])


def _diff_maps(base: dict[str, dict[str, Any]], new: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    base_keys = set(base)
    new_keys = set(new)
    added = [{"object_id": key, "after": new[key]} for key in sorted(new_keys - base_keys)]
    removed = [{"object_id": key, "before": base[key]} for key in sorted(base_keys - new_keys)]
    changed = [
        {"object_id": key, "before": base[key], "after": new[key], "changed_fields": _changed_fields(base[key], new[key])}
        for key in sorted(base_keys & new_keys)
        if base[key] != new[key]
    ]
    return {"added": added, "removed": removed, "changed": changed}


def _changed_fields(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    return sorted(key for key in set(before) | set(after) if before.get(key) != after.get(key))


def _count_change_type(changes: dict[str, dict[str, list[dict[str, Any]]]], change_type: str) -> int:
    return sum(len(bucket.get(change_type, [])) for bucket in changes.values())


def _is_public_service(row: dict[str, str]) -> bool:
    text = " ".join(
        [
            row.get("Service_ID", ""),
            row.get("Service_Name", ""),
            row.get("Service_Role", ""),
            row.get("Listen_Ports", ""),
            row.get("Notes", ""),
        ]
    ).lower()
    return row.get("Service_Priority") in {"P0", "P1"} and any(token in text for token in ("public", "entry", "nginx", "lb", "external", "internet", "0.0.0.0/0"))


def _is_high_privilege_iam(row: dict[str, str]) -> bool:
    role = row.get("Role", "").lower()
    return row.get("Is_High_Privilege", "").lower() == "yes" or any(token in role for token in HIGH_PRIVILEGE_ROLE_TOKENS)


def _edge_touches_sensitive_data(edge: dict[str, Any], graph: GraphModel) -> bool:
    for endpoint in (edge.get("source", ""), edge.get("target", "")):
        node = graph.nodes.get(str(endpoint))
        if not node or node.type != "data_asset":
            continue
        metadata = node.metadata if isinstance(node.metadata, dict) else {}
        if str(metadata.get("sensitivity", "")).lower() in SENSITIVE_LEVELS:
            return True
    return False


def _read_graph_json(path: Path) -> GraphModel:
    payload = json.loads(path.read_text(encoding="utf-8"))
    graph = GraphModel()
    for row in payload.get("nodes", []):
        graph.add_node(
            GraphNode(
                id=row.get("id", ""),
                type=row.get("type", ""),
                label=row.get("label", ""),
                sheet=row.get("sheet", ""),
                status=row.get("status", "Confirmed"),
                layer=row.get("layer", ""),
                group=row.get("group", ""),
                parent_id=row.get("parent_id", ""),
                c4_type=row.get("c4_type", ""),
                metadata=row.get("metadata", {}) if isinstance(row.get("metadata", {}), dict) else {},
            )
        )
    for row in payload.get("edges", []):
        graph.edges.append(
            GraphEdge(
                id=row.get("id", ""),
                type=row.get("type", ""),
                source=row.get("source", ""),
                target=row.get("target", ""),
                label=row.get("label", ""),
                status=row.get("status", "Confirmed"),
                evidence_id=row.get("evidence_id", ""),
                metadata=row.get("metadata", {}) if isinstance(row.get("metadata", {}), dict) else {},
            )
        )
    for row in payload.get("dropped_edges", []):
        graph.dropped_edges.append(
            DroppedEdge(
                id=row.get("id", ""),
                type=row.get("type", ""),
                source=row.get("source", ""),
                target=row.get("target", ""),
                label=row.get("label", ""),
                status=row.get("status", "Confirmed"),
                evidence_id=row.get("evidence_id", ""),
                reason=row.get("reason", ""),
                metadata=row.get("metadata", {}) if isinstance(row.get("metadata", {}), dict) else {},
            )
        )
    return graph


def _render_report(diff: dict[str, Any]) -> str:
    summary = diff["summary"]
    lines = [
        "# Change Diff Report",
        "",
        "This branch-only report compares source-collected DCP or graph JSON artifacts. It reports observed changes only; it does not infer missing relationships.",
        "",
        f"- Base: {summary['base']}",
        f"- New: {summary['new']}",
        f"- Added: {summary['added']}",
        f"- Removed: {summary['removed']}",
        f"- Changed: {summary['changed']}",
        f"- Risks: {summary['risks']}",
        "",
        "## Risk Summary",
        "",
    ]
    _append_risk_table(lines, diff["risks"])
    lines.extend(["", "## Change Summary", ""])
    for category, bucket in diff["changes"].items():
        lines.append(f"### {category}")
        lines.append("")
        lines.append(f"- added: {len(bucket['added'])}")
        lines.append(f"- removed: {len(bucket['removed'])}")
        lines.append(f"- changed: {len(bucket['changed'])}")
        lines.append("")
    return "\n".join(lines) + "\n"


def _render_pr_comment(diff: dict[str, Any]) -> str:
    summary = diff["summary"]
    lines = [
        "## Dataflow Change Diff",
        "",
        f"Added: {summary['added']} | Removed: {summary['removed']} | Changed: {summary['changed']} | Risks: {summary['risks']}",
        "",
    ]
    if not diff["risks"]:
        lines.append("No high-signal dataflow change risks were detected from the provided sources.")
        return "\n".join(lines) + "\n"
    lines.append("### Review Required")
    lines.append("")
    for risk in diff["risks"]:
        lines.append(f"- [{risk['severity']}] {risk['category']}: {risk['message']} Action: {risk['suggested_action']}")
    return "\n".join(lines) + "\n"


def _append_risk_table(lines: list[str], risks: list[dict[str, str]]) -> None:
    fields = ("risk_id", "severity", "category", "object_type", "object_id", "change_type", "message", "suggested_action", "evidence_id")
    if not risks:
        lines.append("No change risks detected.")
        return
    lines.append("| " + " | ".join(fields) + " |")
    lines.append("| " + " | ".join(["---"] * len(fields)) + " |")
    for risk in risks:
        lines.append("| " + " | ".join(_md(risk.get(field, "")) for field in fields) + " |")


def _md(value: str) -> str:
    return (value or "").replace("|", "\\|").replace("\n", "<br>")
