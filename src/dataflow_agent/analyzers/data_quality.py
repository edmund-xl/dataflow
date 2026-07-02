from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dataflow_agent.models import DroppedEdge, GraphModel, Row, WorkbookData

from .indexes import AnalysisIndexes
from .models import AnalysisFinding
from .report_writer import write_analysis_findings


DATA_QUALITY_DOMAIN = "data_quality"
DATA_QUALITY_REPORT_BASENAME = "data_quality_report"
DATA_QUALITY_REPORT_TITLE = "Data Quality Report"
CRITICAL_SERVICE_PRIORITIES = {"P0", "P1"}
LEGACY_DEPENDENCY_TARGET_FIELDS = ("Target_Service_ID", "Target_External_ID", "Target_Data_Asset_ID")


@dataclass(frozen=True)
class _FindingDraft:
    rule: str
    severity: str
    category: str
    object_type: str
    object_id: str
    sheet: str
    row_id: str
    field: str
    message: str
    impact: str
    suggested_action: str
    evidence_id: str

    @property
    def sort_key(self) -> tuple[str, str, str, str, str]:
        return (self.rule, self.object_type, self.object_id, self.field, self.row_id)


def analyze_data_quality(workbook: WorkbookData, graph: GraphModel, indexes: AnalysisIndexes) -> list[AnalysisFinding]:
    del workbook
    drafts: list[_FindingDraft] = []
    drafts.extend(_critical_service_findings(indexes))
    drafts.extend(_dependency_findings(indexes))
    drafts.extend(_data_asset_findings(indexes))
    drafts.extend(_external_service_findings(indexes))
    drafts.extend(_dropped_edge_findings(graph))
    return [
        AnalysisFinding(
            finding_id=f"DQ-{index:04d}",
            domain=DATA_QUALITY_DOMAIN,
            severity=draft.severity,
            category=draft.category,
            object_type=draft.object_type,
            object_id=draft.object_id,
            sheet=draft.sheet,
            row_id=draft.row_id,
            field=draft.field,
            message=draft.message,
            impact=draft.impact,
            suggested_action=draft.suggested_action,
            evidence_id=draft.evidence_id,
        )
        for index, draft in enumerate(sorted(drafts, key=lambda item: item.sort_key), start=1)
    ]


def write_data_quality_report(output_dir: Path, findings: list[AnalysisFinding]) -> dict[str, Path]:
    return write_analysis_findings(
        Path(output_dir),
        DATA_QUALITY_REPORT_BASENAME,
        findings,
        DATA_QUALITY_REPORT_TITLE,
    )


def _critical_service_findings(indexes: AnalysisIndexes) -> list[_FindingDraft]:
    drafts: list[_FindingDraft] = []
    for service_id, row in sorted(indexes.services.items()):
        priority = row.get("Service_Priority", "")
        if priority not in CRITICAL_SERVICE_PRIORITIES:
            continue
        if service_id not in indexes.dataflow_connected_ids and not _has_deprecated_or_exception_signal(row):
            severity = "P1" if priority == "P0" else "P2"
            drafts.append(
                _row_draft(
                    rule="service_isolated",
                    severity=severity,
                    category="critical_service_isolated",
                    row=row,
                    sheet="04_Services",
                    object_type="service",
                    object_id=service_id,
                    field="Service_ID",
                    message=f"{priority} service {service_id} has no graph dataflow in/out edge.",
                    impact="Critical services missing graph dataflow edges can be omitted from dependency, monitoring, and security reviews.",
                    suggested_action="Add the missing service dependency, data asset, or external service relationship, or document a valid exception/deprecation signal.",
                )
            )
        if not row.get("Service_Owner"):
            drafts.append(
                _row_draft(
                    rule="service_missing_owner",
                    severity="P1",
                    category="critical_service_missing_owner",
                    row=row,
                    sheet="04_Services",
                    object_type="service",
                    object_id=service_id,
                    field="Service_Owner",
                    message=f"{priority} service {service_id} has no Service_Owner.",
                    impact="Ownership gaps block follow-up when a critical service needs validation, remediation, or exception approval.",
                    suggested_action="Fill Service_Owner with the accountable owner or owning team.",
                )
            )
        if not row.get("Running_On_Instance_ID") and not row.get("Runtime_ID"):
            drafts.append(
                _row_draft(
                    rule="service_missing_runtime",
                    severity="P1",
                    category="critical_service_missing_runtime",
                    row=row,
                    sheet="04_Services",
                    object_type="service",
                    object_id=service_id,
                    field="Running_On_Instance_ID,Runtime_ID",
                    message=f"{priority} service {service_id} has no Running_On_Instance_ID or Runtime_ID.",
                    impact="Runtime placement gaps prevent the graph from tying critical services to infrastructure or runtime controls.",
                    suggested_action="Fill Running_On_Instance_ID for VM/server placement or Runtime_ID for managed/runtime placement.",
                )
            )
        if not row.get("Listen_Ports"):
            drafts.append(
                _row_draft(
                    rule="service_missing_listen_ports",
                    severity="P1",
                    category="critical_service_missing_listen_ports",
                    row=row,
                    sheet="04_Services",
                    object_type="service",
                    object_id=service_id,
                    field="Listen_Ports",
                    message=f"{priority} service {service_id} has no Listen_Ports.",
                    impact="Missing listener ports weaken firewall review, service exposure review, and runtime connectivity validation.",
                    suggested_action="Fill Listen_Ports or document why the service has no listener.",
                )
            )
    return drafts


def _dependency_findings(indexes: AnalysisIndexes) -> list[_FindingDraft]:
    drafts: list[_FindingDraft] = []
    for dependency_id, row in sorted(indexes.dependencies.items()):
        if not row.get("Target_ID") and not any(row.get(field) for field in LEGACY_DEPENDENCY_TARGET_FIELDS):
            drafts.append(
                _row_draft(
                    rule="dependency_missing_target",
                    severity="P1",
                    category="dependency_missing_target",
                    row=row,
                    sheet="05_Dependencies",
                    object_type="dependency",
                    object_id=dependency_id,
                    field="Target_ID",
                    message=f"Dependency {dependency_id} has no target.",
                    impact="Targetless dependencies cannot be resolved into graph edges or reviewed for downstream ownership and controls.",
                    suggested_action="Fill Target_ID with Target_Type, or fill one legacy target field: Target_Service_ID, Target_External_ID, or Target_Data_Asset_ID.",
                )
            )
        if not row.get("Auth_Method"):
            drafts.append(
                _row_draft(
                    rule="dependency_missing_auth_method",
                    severity="P2",
                    category="dependency_missing_auth_method",
                    row=row,
                    sheet="05_Dependencies",
                    object_type="dependency",
                    object_id=dependency_id,
                    field="Auth_Method",
                    message=f"Dependency {dependency_id} has no Auth_Method.",
                    impact="Missing authentication details prevent trust-boundary and access-control review for the dependency.",
                    suggested_action="Fill Auth_Method with the authentication, authorization, or trust model used by this dependency.",
                )
            )
    return drafts


def _data_asset_findings(indexes: AnalysisIndexes) -> list[_FindingDraft]:
    drafts: list[_FindingDraft] = []
    for asset_id, row in sorted(indexes.data_assets.items()):
        if not row.get("Used_By_Service_ID"):
            drafts.append(
                _row_draft(
                    rule="data_asset_missing_used_by",
                    severity="P2",
                    category="data_asset_missing_used_by",
                    row=row,
                    sheet="06_Data_Assets",
                    object_type="data_asset",
                    object_id=asset_id,
                    field="Used_By_Service_ID",
                    message=f"Data asset {asset_id} has no Used_By_Service_ID.",
                    impact="Unlinked data assets may be omitted from service dependency, data access, backup, and monitoring reviews.",
                    suggested_action="Fill Used_By_Service_ID with the services that read from or write to this asset.",
                )
            )
    return drafts


def _external_service_findings(indexes: AnalysisIndexes) -> list[_FindingDraft]:
    drafts: list[_FindingDraft] = []
    for external_id, row in sorted(indexes.external_services.items()):
        if not row.get("Used_By_Service_ID"):
            drafts.append(
                _row_draft(
                    rule="external_service_missing_used_by",
                    severity="P2",
                    category="external_service_missing_used_by",
                    row=row,
                    sheet="12_External_Services",
                    object_type="external_service",
                    object_id=external_id,
                    field="Used_By_Service_ID",
                    message=f"External service {external_id} has no Used_By_Service_ID.",
                    impact="Unlinked external services may be omitted from egress, vendor, authentication, and data-sharing reviews.",
                    suggested_action="Fill Used_By_Service_ID with the services that call or depend on this external service.",
                )
            )
    return drafts


def _dropped_edge_findings(graph: GraphModel) -> list[_FindingDraft]:
    return [_dropped_edge_draft(edge) for edge in sorted(graph.dropped_edges, key=lambda item: item.id)]


def _dropped_edge_draft(edge: DroppedEdge) -> _FindingDraft:
    metadata = edge.metadata if isinstance(edge.metadata, dict) else {}
    sheet = str(metadata.get("source_sheet", "")) or "graph"
    row_id = str(metadata.get("record_id", ""))
    evidence_id = edge.evidence_id or str(metadata.get("evidence_id", ""))
    return _FindingDraft(
        rule="graph_dropped_edge",
        severity="P1",
        category="graph_dropped_edge",
        object_type="graph_edge",
        object_id=edge.id,
        sheet=sheet,
        row_id=row_id,
        field="edge",
        message=f"Dropped graph edge {edge.id} ({edge.type}) from {edge.source or 'N/A'} to {edge.target or 'N/A'}: {edge.reason}.",
        impact="Dropped graph edges mean workbook relationships could not be represented in generated dataflow artifacts.",
        suggested_action="Correct the source workbook references so both edge endpoints resolve, then regenerate the graph.",
        evidence_id=evidence_id,
    )


def _row_draft(
    *,
    rule: str,
    severity: str,
    category: str,
    row: Row,
    sheet: str,
    object_type: str,
    object_id: str,
    field: str,
    message: str,
    impact: str,
    suggested_action: str,
) -> _FindingDraft:
    return _FindingDraft(
        rule=rule,
        severity=severity,
        category=category,
        object_type=object_type,
        object_id=object_id,
        sheet=sheet,
        row_id=row.get("Record_ID", "") or object_id,
        field=field,
        message=message,
        impact=impact,
        suggested_action=suggested_action,
        evidence_id=row.get("Evidence_ID", "") or row.get("Related_Evidence_ID", ""),
    )


def _has_deprecated_or_exception_signal(row: Row) -> bool:
    if row.get("Confirmation_Status") == "Accepted_Exception":
        return True
    if row.get("Accepted_Exception", "").lower() in {"yes", "true", "1"}:
        return True
    if row.get("Status") in {"Accepted_Exception", "False_Positive", "Resolved"}:
        return True
    text = " ".join(
        row.get(field, "")
        for field in (
            "Service_Name",
            "Service_Role",
            "Source_Type",
            "Notes",
            "Exception_Decision",
        )
    ).lower()
    return any(token in text for token in ("deprecated", "decommission", "retired", "exception"))
