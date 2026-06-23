from __future__ import annotations

from collections import Counter

from .models import Finding, GraphModel, Row, WorkbookData
from .normalizer import active_rows
from .util import split_multi


def check_risks(workbook: WorkbookData, graph: GraphModel) -> list[Finding]:
    findings: list[Finding] = []
    findings.extend(_pending_confirmation_findings(workbook))
    findings.extend(_core_link_findings(workbook, graph))
    findings.extend(_external_entry_findings(workbook))
    findings.extend(_nat_findings(workbook))
    findings.extend(_psc_peering_findings(workbook))
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
                    _finding(
                        "Gate 3",
                        "P2",
                        sheet,
                        row,
                        "Confirmation_Status",
                        "Row is pending confirmation and should not be treated as final fact.",
                        "Confirm the row or move it to an accepted exception before final sign-off.",
                        status="Pending_Confirmation",
                        row_id=row_id,
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


def _external_entry_findings(workbook: WorkbookData) -> list[Finding]:
    armor_rows = active_rows(workbook, "08_Cloud_Armor")
    has_public_protection = any(
        row.get("Protected_Entry_ID") or row.get("LB_Name") or row.get("Backend_Service") or row.get("Nginx_Related") == "Yes"
        for row in armor_rows
    )
    findings = []
    for row in active_rows(workbook, "04_Services"):
        text = f"{row.get('Service_Name', '')} {row.get('Service_Role', '')}".lower()
        is_entry = row.get("Service_Priority") == "P0" and any(token in text for token in ("entry", "nginx", "public", "external"))
        if is_entry and not has_public_protection:
            findings.append(
                _finding(
                    "Gate 4",
                    "P1",
                    "04_Services",
                    row,
                    "Service_ID",
                    f"External entry service {row.get('Service_ID')} has no Cloud Armor/LB/nginx protection row.",
                    "Add an 08_Cloud_Armor row or document the accepted exception.",
                )
            )
    return findings


def _nat_findings(workbook: WorkbookData) -> list[Finding]:
    nat_names = sorted({row.get("NAT_Name", "") for row in active_rows(workbook, "02_Networks") if row.get("NAT_Name")})
    external_deps = [row for row in active_rows(workbook, "05_Dependencies") if row.get("Target_External_ID")]
    findings = []
    if external_deps and not nat_names:
        findings.append(Finding("Gate 4", "P2", "02_Networks", "", "NAT_Name", "External dependencies exist but no NAT/egress record is present.", "Document the egress path or add NAT records."))
    if len(nat_names) > 1:
        findings.append(Finding("Gate 4", "P2", "02_Networks", "", "NAT_Name", f"Multiple NAT exits detected: {', '.join(nat_names)}.", "Confirm whether multiple egress exits are intended."))
    return findings


def _psc_peering_findings(workbook: WorkbookData) -> list[Finding]:
    findings = []
    psc_names = [row.get("PSC_or_Peering_Name", "") for row in active_rows(workbook, "02_Networks") if row.get("PSC_or_Peering_Name")]
    for row in active_rows(workbook, "02_Networks"):
        if row.get("PSC_or_Peering_Name") and not (row.get("Purpose") or row.get("Notes")):
            findings.append(
                _finding(
                    "Gate 4",
                    "P2",
                    "02_Networks",
                    row,
                    "PSC_or_Peering_Name",
                    "PSC/VPC Peering record has no purpose or exception explanation.",
                    "Document the cross-network dependency purpose or exception reason.",
                )
            )
    for row in active_rows(workbook, "05_Dependencies"):
        if row.get("Target_External_ID") and row.get("Dependency_Criticality") in {"P0", "P1"} and not psc_names:
            findings.append(
                _finding(
                    "Gate 4",
                    "P2",
                    "05_Dependencies",
                    row,
                    "Target_External_ID",
                    f"Critical external dependency {row.get('Dependency_ID')} has no PSC/VPC Peering record.",
                    "Confirm whether the dependency uses public egress, PSC, peering, or an accepted exception.",
                )
            )
    return findings


def _firewall_findings(workbook: WorkbookData) -> list[Finding]:
    findings = []
    firewall_rows = active_rows(workbook, "07_Firewalls")
    firewalls_by_dependency: dict[str, list[Row]] = {}
    for row in firewall_rows:
        if row.get("Related_Dependency_ID"):
            firewalls_by_dependency.setdefault(row["Related_Dependency_ID"], []).append(row)
    for dep in active_rows(workbook, "05_Dependencies"):
        related = firewalls_by_dependency.get(dep.get("Dependency_ID", ""), [])
        if dep.get("Dependency_Criticality") in {"P0", "P1"} and not related:
            findings.append(
                _finding(
                    "Gate 4",
                    "P2",
                    "05_Dependencies",
                    dep,
                    "Dependency_ID",
                    f"Critical dependency {dep.get('Dependency_ID')} has no related firewall row.",
                    "Link a firewall rule through Related_Dependency_ID or document the exception.",
                )
            )
        for firewall in related:
            if not _ports_match(dep.get("Target_Port", ""), firewall.get("Ports", "")) or not _protocols_match(dep.get("Target_Port_Protocol", ""), firewall.get("Protocol", "")):
                findings.append(
                    _finding(
                        "Gate 4",
                        "P1",
                        "07_Firewalls",
                        firewall,
                        "Ports",
                        f"Firewall {firewall.get('Firewall_ID')} does not match dependency {dep.get('Dependency_ID')} protocol/port.",
                        "Align firewall protocol/ports with the related dependency or document the exception.",
                    )
                )
    for row in firewall_rows:
        wide_open = row.get("Direction", "").lower() == "ingress" and "0.0.0.0/0" in row.get("Source_Allowed", "")
        if wide_open and not row.get("Reason"):
            findings.append(
                _finding(
                    "Gate 4",
                    "P1",
                    "07_Firewalls",
                    row,
                    "Reason",
                    "Ingress firewall allows 0.0.0.0/0 without a documented reason.",
                    "Add a business/security reason or restrict the source range.",
                )
            )
    return findings


def _iam_findings(workbook: WorkbookData) -> list[Finding]:
    findings = []
    service_account_usage: Counter[str] = Counter()
    for row in active_rows(workbook, "09_IAM_SA"):
        for service_id in split_multi(row.get("Used_By_Service_ID", "")):
            if row.get("Service_Account_ID"):
                service_account_usage[row["Service_Account_ID"]] += 1
    for row in active_rows(workbook, "09_IAM_SA"):
        high = row.get("Is_High_Privilege", "").lower() == "yes"
        role = row.get("Role", "")
        role_lower = role.lower()
        broad_role = role_lower in {"owner", "editor"} or role_lower.endswith("/owner") or "admin" in role_lower or "*" in role
        if (high or broad_role) and not row.get("Justification"):
            findings.append(
                _finding(
                    "Gate 4",
                    "P1",
                    "09_IAM_SA",
                    row,
                    "Justification",
                    "High privilege IAM binding has no justification.",
                    "Document the reason, scope, and approver or reduce privilege.",
                )
            )
        if row.get("Service_Account_ID") and service_account_usage[row["Service_Account_ID"]] > 1 and not row.get("Justification"):
            findings.append(
                _finding(
                    "Gate 4",
                    "P2",
                    "09_IAM_SA",
                    row,
                    "Service_Account_ID",
                    f"Service account {row.get('Service_Account_ID')} is shared by multiple services without justification.",
                    "Document the shared-account reason or split service accounts.",
                )
            )
    return findings


def _monitoring_findings(workbook: WorkbookData) -> list[Finding]:
    findings = []
    covered_statuses = {"Covered", "Partial", "Partially_Covered"}
    monitored = {row.get("Object_ID", "") for row in active_rows(workbook, "10_Monitoring") if row.get("Coverage_Status") in covered_statuses}
    for row in active_rows(workbook, "04_Services"):
        if row.get("Service_Priority") == "P0" and row.get("Service_ID") not in monitored:
            findings.append(
                _finding(
                    "Gate 4",
                    "P1",
                    "04_Services",
                    row,
                    "Service_ID",
                    f"P0 service {row.get('Service_ID')} has no covered monitoring row.",
                    "Add a 10_Monitoring row with dashboard/logging/alert coverage.",
                )
            )
    for row in active_rows(workbook, "05_Dependencies"):
        if row.get("Dependency_Criticality") in {"P0", "P1"} and row.get("Dependency_ID") not in monitored:
            findings.append(
                _finding(
                    "Gate 4",
                    "P2",
                    "05_Dependencies",
                    row,
                    "Dependency_ID",
                    f"Critical dependency {row.get('Dependency_ID')} has no direct monitoring coverage row.",
                    "Add monitoring coverage for the dependency or document why service-level monitoring is sufficient.",
                )
            )
    for row in active_rows(workbook, "06_Data_Assets"):
        sensitivity = row.get("Sensitivity", "").lower()
        if sensitivity in {"restricted", "high", "critical"} and row.get("Data_Asset_ID") not in monitored:
            findings.append(
                _finding(
                    "Gate 4",
                    "P1",
                    "06_Data_Assets",
                    row,
                    "Data_Asset_ID",
                    f"Sensitive data asset {row.get('Data_Asset_ID')} has no covered monitoring row.",
                    "Add database/storage monitoring, logging, alerting, or dashboard evidence.",
                )
            )
    for row in active_rows(workbook, "10_Monitoring"):
        if row.get("Coverage_Status") in {"Missing", "Unknown"}:
            findings.append(
                _finding(
                    "Gate 4",
                    "P2",
                    "10_Monitoring",
                    row,
                    "Coverage_Status",
                    "Monitoring coverage is missing or unknown.",
                    "Confirm dashboard, logging, alerting, and XDR coverage.",
                )
            )
    return findings


def _artifact_findings(graph: GraphModel) -> list[Finding]:
    findings: list[Finding] = []
    if not graph.nodes:
        findings.append(Finding("Gate 5", "P0", "normalized", "", "nodes", "Graph has no nodes; artifacts cannot be trusted."))
    if not graph.edges:
        findings.append(Finding("Gate 5", "P0", "normalized", "", "edges", "Graph has no edges; artifacts cannot be trusted."))
    for edge in graph.dropped_edges:
        findings.append(
            Finding(
                "Gate 5",
                "P1",
                "normalized",
                edge.metadata.get("record_id", "") if isinstance(edge.metadata, dict) else "",
                "edge",
                f"Dropped graph edge {edge.id} ({edge.type}) from {edge.source or 'N/A'} to {edge.target or 'N/A'}: {edge.reason}.",
                "Correct the source workbook references and regenerate the package.",
                evidence_id=edge.evidence_id,
            )
        )
    return findings


def _ports_match(dependency_port: str, firewall_ports: str) -> bool:
    if not dependency_port or not firewall_ports:
        return True
    firewall_values = set(split_multi(firewall_ports))
    if "all" in {value.lower() for value in firewall_values}:
        return True
    return dependency_port in firewall_values


def _protocols_match(dependency_protocol: str, firewall_protocol: str) -> bool:
    dep = dependency_protocol.lower()
    firewall = firewall_protocol.lower()
    if not dep or not firewall or firewall in {"all", "any"}:
        return True
    if dep in {"private-ip", "http", "https", "http/https", "http/json", "grpc"} and firewall == "tcp":
        return True
    return dep == firewall


def _finding(
    gate: str,
    severity: str,
    sheet: str,
    row: Row,
    field: str,
    message: str,
    suggested_action: str,
    status: str = "Open",
    row_id: str = "",
) -> Finding:
    return Finding(
        gate,
        severity,
        sheet,
        row_id or row.get("Record_ID") or row.get("Issue_ID") or row.get("Dependency_ID") or row.get("Service_ID") or row.get("Data_Asset_ID") or row.get("Firewall_ID") or row.get("IAM_Binding_ID") or row.get("Network_ID") or "",
        field,
        message,
        suggested_action,
        status,
        owner=_owner(row),
        due_date=row.get("Due_Date", ""),
        exception_decision=row.get("Accepted_Exception", ""),
        evidence_id=row.get("Evidence_ID") or row.get("Related_Evidence_ID", ""),
    )


def _owner(row: Row) -> str:
    for field in ("Owner", "Service_Owner", "Business_Owner", "Manage_By", "Collected_By"):
        if row.get(field):
            return row[field]
    return ""
