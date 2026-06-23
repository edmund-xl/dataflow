from __future__ import annotations

from .models import Finding, GraphModel, WorkbookData
from .normalizer import active_rows


def check_risks(workbook: WorkbookData, graph: GraphModel) -> list[Finding]:
    findings: list[Finding] = []
    findings.extend(_pending_confirmation_findings(workbook))
    findings.extend(_core_link_findings(workbook, graph))
    findings.extend(_firewall_findings(workbook))
    findings.extend(_iam_findings(workbook))
    findings.extend(_monitoring_findings(workbook))
    findings.extend(_artifact_findings(graph))
    return findings


def _pending_confirmation_findings(workbook: WorkbookData) -> list[Finding]:
    findings = []
    for sheet, rows in workbook.sheets.items():
        for row in rows:
            if row.get("Confirmation_Status") == "Pending_Confirmation":
                row_id = row.get("Record_ID") or row.get("Dependency_ID") or row.get("Service_ID") or row.get("External_ID", "")
                findings.append(
                    Finding(
                        "Gate 3",
                        "P2",
                        sheet,
                        row_id,
                        "Confirmation_Status",
                        "Row is pending confirmation and should not be treated as final fact.",
                        "Confirm the row or move it to an accepted exception before final sign-off.",
                        "Pending_Confirmation",
                    )
                )
    return findings


def _core_link_findings(workbook: WorkbookData, graph: GraphModel) -> list[Finding]:
    findings = []
    service_text = " ".join(
        f"{row.get('Service_ID', '')} {row.get('Service_Name', '')} {row.get('Service_Role', '')}".lower()
        for row in active_rows(workbook, "04_Services")
    )
    dependency_text = " ".join(
        f"{row.get('Dependency_ID', '')} {row.get('Call_Description', '')} {row.get('Target_External_ID', '')}".lower()
        for row in active_rows(workbook, "05_Dependencies")
    )
    data_asset_count = len(active_rows(workbook, "06_Data_Assets"))
    if "rpc" not in service_text:
        findings.append(Finding("Gate 3", "P1", "04_Services", "", "Service_Name", "No RPC service detected in core service inventory."))
    if "sequencer" not in service_text:
        findings.append(Finding("Gate 3", "P1", "04_Services", "", "Service_Name", "No Sequencer service detected in core service inventory."))
    if data_asset_count == 0:
        findings.append(Finding("Gate 3", "P1", "06_Data_Assets", "", "Data_Asset_ID", "No data asset exists for database/storage validation."))
    if "da" not in dependency_text and "eigen" not in dependency_text:
        findings.append(Finding("Gate 3", "P2", "05_Dependencies", "", "Target_External_ID", "No DA/EigenDA dependency detected."))
    if not any(edge.type in {"calls", "calls_external", "reads_from", "writes_to"} for edge in graph.edges):
        findings.append(Finding("Gate 3", "P0", "05_Dependencies", "", "Dependency_ID", "Graph has no communication or data access edges."))
    return findings


def _firewall_findings(workbook: WorkbookData) -> list[Finding]:
    findings = []
    firewall_by_dependency = {row.get("Related_Dependency_ID", "") for row in active_rows(workbook, "07_Firewalls") if row.get("Related_Dependency_ID")}
    for dep in active_rows(workbook, "05_Dependencies"):
        if dep.get("Dependency_Criticality") in {"P0", "P1"} and dep.get("Dependency_ID") not in firewall_by_dependency:
            findings.append(
                Finding(
                    "Gate 4",
                    "P2",
                    "05_Dependencies",
                    dep.get("Record_ID") or dep.get("Dependency_ID", ""),
                    "Dependency_ID",
                    f"Critical dependency {dep.get('Dependency_ID')} has no related firewall row.",
                    "Link a firewall rule through Related_Dependency_ID or document the exception.",
                )
            )
    for row in active_rows(workbook, "07_Firewalls"):
        wide_open = row.get("Direction", "").lower() == "ingress" and "0.0.0.0/0" in row.get("Source_Allowed", "")
        if wide_open and not row.get("Reason"):
            findings.append(
                Finding(
                    "Gate 4",
                    "P1",
                    "07_Firewalls",
                    row.get("Record_ID") or row.get("Firewall_ID", ""),
                    "Reason",
                    "Ingress firewall allows 0.0.0.0/0 without a documented reason.",
                    "Add a business/security reason or restrict the source range.",
                )
            )
    return findings


def _iam_findings(workbook: WorkbookData) -> list[Finding]:
    findings = []
    for row in active_rows(workbook, "09_IAM_SA"):
        high = row.get("Is_High_Privilege", "").lower() == "yes"
        broad_role = row.get("Role", "").lower() in {"owner", "editor"} or row.get("Role", "").lower().endswith("/owner")
        if (high or broad_role) and not row.get("Justification"):
            findings.append(
                Finding(
                    "Gate 4",
                    "P1",
                    "09_IAM_SA",
                    row.get("Record_ID") or row.get("IAM_Binding_ID", ""),
                    "Justification",
                    "High privilege IAM binding has no justification.",
                    "Document the reason, scope, and approver or reduce privilege.",
                )
            )
    return findings


def _monitoring_findings(workbook: WorkbookData) -> list[Finding]:
    findings = []
    monitored = {row.get("Object_ID", "") for row in active_rows(workbook, "10_Monitoring") if row.get("Coverage_Status") in {"Covered", "Partial"}}
    for row in active_rows(workbook, "04_Services"):
        if row.get("Service_Priority") == "P0" and row.get("Service_ID") not in monitored:
            findings.append(
                Finding(
                    "Gate 4",
                    "P1",
                    "04_Services",
                    row.get("Record_ID") or row.get("Service_ID", ""),
                    "Service_ID",
                    f"P0 service {row.get('Service_ID')} has no covered monitoring row.",
                    "Add a 10_Monitoring row with dashboard/logging/alert coverage.",
                )
            )
    for row in active_rows(workbook, "10_Monitoring"):
        if row.get("Coverage_Status") in {"Missing", "Unknown"}:
            findings.append(
                Finding(
                    "Gate 4",
                    "P2",
                    "10_Monitoring",
                    row.get("Record_ID") or row.get("Monitoring_ID", ""),
                    "Coverage_Status",
                    "Monitoring coverage is missing or unknown.",
                    "Confirm dashboard, logging, alerting, and XDR coverage.",
                )
            )
    return findings


def _artifact_findings(graph: GraphModel) -> list[Finding]:
    if not graph.nodes:
        return [Finding("Gate 5", "P0", "normalized", "", "nodes", "Graph has no nodes; artifacts cannot be trusted.")]
    if not graph.edges:
        return [Finding("Gate 5", "P0", "normalized", "", "edges", "Graph has no edges; artifacts cannot be trusted.")]
    return []

