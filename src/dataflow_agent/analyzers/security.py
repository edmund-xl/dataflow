from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dataflow_agent.models import GraphModel, Row, WorkbookData
from dataflow_agent.normalizer import active_rows
from dataflow_agent.util import split_multi, write_csv, write_json

from .indexes import AnalysisIndexes
from .models import AnalysisFinding
from .report_writer import write_analysis_findings


SECURITY_REPORT_TITLE = "Security Risk Report"
SENSITIVE_LEVELS = {"high", "restricted", "critical"}
APPROVAL_GAP_VALUES = {"", "no", "not_required"}
MONITORING_COVERED_STATUSES = {"covered", "partial"}

SECURITY_CONTROL_GAP_FIELDS = [
    "finding_id",
    "severity",
    "category",
    "sheet",
    "row_id",
    "object_type",
    "object_id",
    "field",
    "evidence_id",
    "impact",
    "suggested_action",
]

SENSITIVE_DATA_FLOW_FIELDS = [
    "data_asset_id",
    "data_asset_name",
    "sensitivity",
    "service_id",
    "service_name",
    "service_priority",
    "access_type",
    "external_dependencies",
    "iam_roles",
    "high_privilege_iam",
    "cicd_deployments",
    "monitoring_status",
    "evidence_id",
]


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
        return (self.rule, self.object_type, self.object_id, self.row_id, self.field)


def analyze_security_risks(workbook: WorkbookData, graph: GraphModel, indexes: AnalysisIndexes) -> list[AnalysisFinding]:
    drafts: list[_FindingDraft] = []
    drafts.extend(_firewall_public_source_findings(workbook))
    drafts.extend(_entry_protection_findings(workbook))
    drafts.extend(_external_service_findings(workbook))
    drafts.extend(_sensitive_data_access_findings(workbook, indexes))
    drafts.extend(_high_privilege_iam_findings(workbook))
    drafts.extend(_shared_service_account_findings(workbook))
    drafts.extend(_cicd_approval_findings(workbook, indexes))
    drafts.extend(_cicd_completeness_findings(workbook))
    return _assign_finding_ids(drafts)


def write_security_risk_report(output_dir: Path, findings: list[AnalysisFinding]) -> dict[str, Path]:
    return write_analysis_findings(output_dir, "security_risk_report", findings, SECURITY_REPORT_TITLE)


def security_control_gap_rows(findings: list[AnalysisFinding]) -> list[dict[str, str]]:
    return [
        {field: finding.as_dict().get(field, "") for field in SECURITY_CONTROL_GAP_FIELDS}
        for finding in _sorted_findings(findings)
    ]


def write_security_control_gap_report_csv(output_dir: Path, findings: list[AnalysisFinding]) -> Path:
    path = output_dir / "security_control_gap_report.csv"
    write_csv(path, security_control_gap_rows(findings), SECURITY_CONTROL_GAP_FIELDS)
    return path


def permission_blast_radius(workbook: WorkbookData, graph: GraphModel, indexes: AnalysisIndexes) -> dict[str, dict[str, Any]]:
    radius: dict[str, dict[str, Any]] = {}
    for service_id, service in sorted(indexes.services.items()):
        monitoring_status = _service_monitoring_status(indexes, service_id)
        iam_rows = indexes.iam_by_service.get(service_id, [])
        cicd_rows = indexes.cicd_by_target_service.get(service_id, [])
        radius[service_id] = {
            "service_id": service_id,
            "service_name": service.get("Service_Name", ""),
            "service_priority": service.get("Service_Priority", ""),
            "monitoring_status": monitoring_status,
            "data_assets": _data_asset_entries(indexes.data_assets_by_service.get(service_id, [])),
            "external_calls": _external_service_entries(indexes.external_by_service.get(service_id, [])),
            "iam_roles": _iam_role_entries(iam_rows),
            "high_privilege": any(_is_high_privilege_iam(row) for row in iam_rows),
            "cicd_deployments": _cicd_entries(cicd_rows),
        }
    return radius


def write_permission_blast_radius_json(
    output_dir: Path,
    workbook: WorkbookData,
    graph: GraphModel,
    indexes: AnalysisIndexes,
) -> Path:
    path = output_dir / "permission_blast_radius.json"
    write_json(path, permission_blast_radius(workbook, graph, indexes))
    return path


def sensitive_data_flow_rows(workbook: WorkbookData, graph: GraphModel, indexes: AnalysisIndexes) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for asset in _sensitive_assets(workbook):
        service_ids = _asset_service_ids(asset, indexes)
        for service_id in service_ids:
            service = indexes.services.get(service_id, {})
            iam_rows = indexes.iam_by_service.get(service_id, [])
            cicd_rows = indexes.cicd_by_target_service.get(service_id, [])
            external_rows = indexes.external_by_service.get(service_id, [])
            rows.append(
                {
                    "data_asset_id": asset.get("Data_Asset_ID", ""),
                    "data_asset_name": asset.get("Data_Asset_Name", ""),
                    "sensitivity": asset.get("Sensitivity", ""),
                    "service_id": service_id,
                    "service_name": service.get("Service_Name", ""),
                    "service_priority": service.get("Service_Priority", ""),
                    "access_type": asset.get("Access_Type", ""),
                    "external_dependencies": _join_ids(external_rows, "External_ID"),
                    "iam_roles": _join_ids(iam_rows, "Role"),
                    "high_privilege_iam": "Yes" if any(_is_high_privilege_iam(row) for row in iam_rows) else "No",
                    "cicd_deployments": _join_ids(cicd_rows, "CICD_ID"),
                    "monitoring_status": _service_monitoring_status(indexes, service_id),
                    "evidence_id": asset.get("Evidence_ID", ""),
                }
            )
    return sorted(rows, key=lambda row: (row["data_asset_id"], row["service_id"]))


def write_sensitive_data_flow_report_md(
    output_dir: Path,
    workbook: WorkbookData,
    graph: GraphModel,
    indexes: AnalysisIndexes,
) -> Path:
    path = output_dir / "sensitive_data_flow_report.md"
    rows = sensitive_data_flow_rows(workbook, graph, indexes)
    lines = [
        "# Sensitive Data Flow Report",
        "",
        f"- Sensitive data access rows: {len(rows)}",
        "",
        "| " + " | ".join(SENSITIVE_DATA_FLOW_FIELDS) + " |",
        "| " + " | ".join(["---"] * len(SENSITIVE_DATA_FLOW_FIELDS)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_md_cell(row[field]) for field in SENSITIVE_DATA_FLOW_FIELDS) + " |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _firewall_public_source_findings(workbook: WorkbookData) -> list[_FindingDraft]:
    findings: list[_FindingDraft] = []
    for row in active_rows(workbook, "07_Firewalls"):
        if "0.0.0.0/0" not in row.get("Source_Allowed", ""):
            continue
        accepted_exception = row.get("Confirmation_Status") == "Accepted_Exception"
        has_reason = bool(row.get("Reason", "").strip())
        if accepted_exception and has_reason:
            continue
        firewall_id = row.get("Firewall_ID", "")
        findings.append(
            _draft(
                "SEC-FIREWALL-PUBLIC-SOURCE",
                "P1",
                "Firewall public source",
                "firewall_rule",
                firewall_id,
                "07_Firewalls",
                row,
                "Source_Allowed,Confirmation_Status,Reason",
                f"Firewall {firewall_id} allows 0.0.0.0/0 without accepted exception status and documented reason.",
                "Public source ranges can expose entry points or administrative surfaces beyond the intended trust boundary.",
                "Restrict Source_Allowed or record an Accepted_Exception with a specific business/security reason.",
            )
        )
    return findings


def _entry_protection_findings(workbook: WorkbookData) -> list[_FindingDraft]:
    findings: list[_FindingDraft] = []
    cloud_armor_rows = active_rows(workbook, "08_Cloud_Armor")
    for row in active_rows(workbook, "04_Services"):
        service_id = row.get("Service_ID", "")
        if row.get("Service_Priority") not in {"P0", "P1"} or not _is_external_facing_service(row):
            continue
        if _has_entry_protection(row, cloud_armor_rows):
            continue
        findings.append(
            _draft(
                "SEC-ENTRY-PROTECTION",
                "P1",
                "Entry protection",
                "service",
                service_id,
                "04_Services",
                row,
                "Service_Role,Service_Name,Listen_Ports,Notes",
                f"P0/P1 external-facing service {service_id} has no Cloud Armor/LB/nginx protection evidence.",
                "Public critical entry services without mapped protection have higher exposure to internet-originated attacks.",
                "Add a linked 08_Cloud_Armor row, load balancer evidence, nginx protection evidence, or document an accepted exception.",
            )
        )
    return findings


def _external_service_findings(workbook: WorkbookData) -> list[_FindingDraft]:
    findings: list[_FindingDraft] = []
    required_fields = ["Auth_Method", "Purpose", "Data_Classification", "Used_By_Service_ID"]
    for row in active_rows(workbook, "12_External_Services"):
        missing = [field for field in required_fields if not row.get(field, "").strip()]
        if not missing:
            continue
        external_id = row.get("External_ID", "")
        findings.append(
            _draft(
                "SEC-EXTERNAL-COMPLETENESS",
                "P2",
                "External service completeness",
                "external_service",
                external_id,
                "12_External_Services",
                row,
                ",".join(missing),
                f"External service {external_id} is missing security context fields: {', '.join(missing)}.",
                "External dependencies without auth, purpose, classification, or owning service context are hard to review and monitor.",
                "Fill Auth_Method, Purpose, Data_Classification, and Used_By_Service_ID for the external service.",
            )
        )
    return findings


def _sensitive_data_access_findings(workbook: WorkbookData, indexes: AnalysisIndexes) -> list[_FindingDraft]:
    findings: list[_FindingDraft] = []
    for asset in _sensitive_assets(workbook):
        asset_id = asset.get("Data_Asset_ID", "")
        for service_id in _asset_service_ids(asset, indexes):
            service_monitoring = _service_monitoring_status(indexes, service_id)
            lacks_monitoring = service_monitoring == "Missing"
            high_privilege = any(_is_high_privilege_iam(row) for row in indexes.iam_by_service.get(service_id, []))
            if not lacks_monitoring and not high_privilege:
                continue
            severity = "P1" if high_privilege else "P2"
            reasons = []
            if high_privilege:
                reasons.append("high privilege IAM")
            if lacks_monitoring:
                reasons.append("missing service monitoring")
            findings.append(
                _draft(
                    "SEC-SENSITIVE-DATA-ACCESS",
                    severity,
                    "Sensitive data access",
                    "data_asset",
                    f"{asset_id}:{service_id}",
                    "06_Data_Assets",
                    asset,
                    "Used_By_Service_ID,Sensitivity",
                    f"Sensitive data asset {asset_id} is accessed by {service_id} with {', '.join(reasons)}.",
                    "Sensitive data access through unmonitored or highly privileged services increases breach impact and investigation gaps.",
                    "Add covered service monitoring and reduce or justify privileged IAM for services that access sensitive data.",
                )
            )
    return findings


def _high_privilege_iam_findings(workbook: WorkbookData) -> list[_FindingDraft]:
    findings: list[_FindingDraft] = []
    for row in active_rows(workbook, "09_IAM_SA"):
        if not _is_high_privilege_iam(row) or row.get("Justification", "").strip():
            continue
        iam_id = row.get("IAM_Binding_ID", "")
        findings.append(
            _draft(
                "SEC-IAM-HIGH-PRIVILEGE",
                "P1",
                "High privilege IAM",
                "iam_binding",
                iam_id,
                "09_IAM_SA",
                row,
                "Justification",
                f"High privilege IAM binding {iam_id} lacks Justification.",
                "Unjustified high privilege makes least-privilege review and approval traceability incomplete.",
                "Document the reason, scope, approver, and review date or reduce the IAM role.",
            )
        )
    return findings


def _shared_service_account_findings(workbook: WorkbookData) -> list[_FindingDraft]:
    usage: dict[str, set[str]] = {}
    for row in active_rows(workbook, "09_IAM_SA"):
        service_account = row.get("Service_Account_ID", "")
        if not service_account:
            continue
        usage.setdefault(service_account, set()).update(split_multi(row.get("Used_By_Service_ID", "")))

    findings: list[_FindingDraft] = []
    for row in active_rows(workbook, "09_IAM_SA"):
        service_account = row.get("Service_Account_ID", "")
        if not service_account or len(usage.get(service_account, set())) <= 1 or row.get("Justification", "").strip():
            continue
        findings.append(
            _draft(
                "SEC-IAM-SHARED-SA",
                "P2",
                "Shared service account",
                "service_account",
                service_account,
                "09_IAM_SA",
                row,
                "Justification",
                f"Service account {service_account} is shared by multiple services without Justification.",
                "Shared identities make blast radius and ownership harder to constrain during incident response.",
                "Document the shared-account reason or split the services onto separate service accounts.",
            )
        )
    return findings


def _cicd_approval_findings(workbook: WorkbookData, indexes: AnalysisIndexes) -> list[_FindingDraft]:
    findings: list[_FindingDraft] = []
    for row in active_rows(workbook, "11_CICD"):
        p0_p1_targets = _p0_p1_cicd_targets(row, indexes)
        approval = row.get("Approval_Required", "").strip().lower()
        if not p0_p1_targets or approval not in APPROVAL_GAP_VALUES:
            continue
        cicd_id = row.get("CICD_ID", "")
        findings.append(
            _draft(
                "SEC-CICD-PROD-APPROVAL",
                "P1",
                "CI/CD approval",
                "cicd_pipeline",
                cicd_id,
                "11_CICD",
                row,
                "Approval_Required",
                f"CI/CD pipeline {cicd_id} can deploy P0/P1 service(s) {', '.join(p0_p1_targets)} without required approval.",
                "Critical service deployment without approval increases release, credential, and supply-chain risk.",
                "Require approval for P0/P1 service deployment or document an accepted exception.",
            )
        )
    return findings


def _cicd_completeness_findings(workbook: WorkbookData) -> list[_FindingDraft]:
    findings: list[_FindingDraft] = []
    for row in active_rows(workbook, "11_CICD"):
        missing = [field for field in ("Runner", "Deployment_Account", "Artifact_Registry") if not row.get(field, "").strip()]
        if not (row.get("Target_Service_ID", "").strip() or row.get("Target_Instance_ID", "").strip()):
            missing.append("Target_Service_ID/Target_Instance_ID")
        if not missing:
            continue
        cicd_id = row.get("CICD_ID", "")
        findings.append(
            _draft(
                "SEC-CICD-COMPLETENESS",
                "P2",
                "CI/CD completeness",
                "cicd_pipeline",
                cicd_id,
                "11_CICD",
                row,
                ",".join(missing),
                f"CI/CD pipeline {cicd_id} is missing deployment security fields: {', '.join(missing)}.",
                "Incomplete CI/CD records prevent deployment path, identity, runner, and artifact provenance review.",
                "Fill Runner, Deployment_Account, Artifact_Registry, and either Target_Service_ID or Target_Instance_ID.",
            )
        )
    return findings


def _assign_finding_ids(drafts: list[_FindingDraft]) -> list[AnalysisFinding]:
    findings: list[AnalysisFinding] = []
    for idx, draft in enumerate(sorted(drafts, key=lambda item: item.sort_key), start=1):
        findings.append(
            AnalysisFinding(
                finding_id=f"SEC-{idx:04d}",
                domain="Security",
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
        )
    return findings


def _draft(
    rule: str,
    severity: str,
    category: str,
    object_type: str,
    object_id: str,
    sheet: str,
    row: Row,
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
        row_id=_row_id(row),
        field=field,
        message=message,
        impact=impact,
        suggested_action=suggested_action,
        evidence_id=row.get("Evidence_ID", ""),
    )


def _row_id(row: Row) -> str:
    for field in (
        "Record_ID",
        "Firewall_ID",
        "Policy_ID",
        "IAM_Binding_ID",
        "CICD_ID",
        "External_ID",
        "Data_Asset_ID",
        "Service_ID",
    ):
        if row.get(field):
            return row[field]
    return ""


def _is_external_facing_service(row: Row) -> bool:
    text = " ".join(
        [
            row.get("Service_ID", ""),
            row.get("Service_Name", ""),
            row.get("Service_Role", ""),
            row.get("Notes", ""),
        ]
    ).lower()
    external_tokens = ("public", "entry", "nginx", "external-facing", "external facing", "internet", "ingress", "load balancer", "lb")
    if any(token in text for token in external_tokens):
        return True
    return bool({"80", "443"} & set(split_multi(row.get("Listen_Ports", ""))))


def _has_entry_protection(service: Row, cloud_armor_rows: list[Row]) -> bool:
    service_terms = {
        service.get("Service_ID", "").strip().lower(),
        service.get("Service_Name", "").strip().lower(),
    }
    service_terms.discard("")
    service_is_nginx = "nginx" in " ".join(
        [service.get("Service_ID", ""), service.get("Service_Name", ""), service.get("Service_Role", "")]
    ).lower()
    for row in cloud_armor_rows:
        row_text = " ".join(
            [
                row.get("Protected_Entry_ID", ""),
                row.get("Backend_Service", ""),
                row.get("LB_Name", ""),
                row.get("Nginx_Related", ""),
                row.get("Notes", ""),
            ]
        ).lower()
        if any(term and term in row_text for term in service_terms):
            return True
        if service_is_nginx and row.get("Nginx_Related", "").strip().lower() == "yes":
            return True
    return False


def _sensitive_assets(workbook: WorkbookData) -> list[Row]:
    return [
        row
        for row in active_rows(workbook, "06_Data_Assets")
        if row.get("Sensitivity", "").strip().lower() in SENSITIVE_LEVELS and row.get("Data_Asset_ID", "")
    ]


def _asset_service_ids(asset: Row, indexes: AnalysisIndexes) -> list[str]:
    asset_id = asset.get("Data_Asset_ID", "")
    service_ids = set(split_multi(asset.get("Used_By_Service_ID", "")))
    for service_id, assets in indexes.data_assets_by_service.items():
        if any(row.get("Data_Asset_ID", "") == asset_id for row in assets):
            service_ids.add(service_id)
    return sorted(service_ids)


def _service_monitoring_status(indexes: AnalysisIndexes, service_id: str) -> str:
    rows = indexes.monitoring_by_object.get(("service", service_id), [])
    if not rows:
        return "Missing"
    statuses = sorted({row.get("Coverage_Status", "") or "Unknown" for row in rows})
    if any(status.lower() in MONITORING_COVERED_STATUSES for status in statuses):
        return "Partial" if any(status.lower() == "partial" for status in statuses) else "Covered"
    return "/".join(statuses)


def _is_high_privilege_iam(row: Row) -> bool:
    if row.get("Is_High_Privilege", "").strip().lower() == "yes":
        return True
    role = row.get("Role", "")
    role_lower = role.lower()
    return role_lower in {"owner", "editor"} or role_lower.endswith(("/owner", "/editor")) or "admin" in role_lower or "*" in role


def _p0_p1_cicd_targets(row: Row, indexes: AnalysisIndexes) -> list[str]:
    service_ids = set(split_multi(row.get("Target_Service_ID", "")))
    target_instances = set(split_multi(row.get("Target_Instance_ID", "")))
    if target_instances:
        for service_id, service in indexes.services.items():
            if service.get("Running_On_Instance_ID", "") in target_instances:
                service_ids.add(service_id)
    return sorted(
        service_id
        for service_id in service_ids
        if indexes.services.get(service_id, {}).get("Service_Priority", "") in {"P0", "P1"}
    )


def _data_asset_entries(rows: list[Row]) -> list[dict[str, str]]:
    return [
        {
            "data_asset_id": row.get("Data_Asset_ID", ""),
            "data_asset_name": row.get("Data_Asset_Name", ""),
            "sensitivity": row.get("Sensitivity", ""),
            "access_type": row.get("Access_Type", ""),
        }
        for row in sorted(rows, key=lambda item: item.get("Data_Asset_ID", ""))
    ]


def _external_service_entries(rows: list[Row]) -> list[dict[str, str]]:
    return [
        {
            "external_id": row.get("External_ID", ""),
            "external_name": row.get("External_Name", ""),
            "direction": row.get("Direction", ""),
            "data_classification": row.get("Data_Classification", ""),
        }
        for row in sorted(rows, key=lambda item: item.get("External_ID", ""))
    ]


def _iam_role_entries(rows: list[Row]) -> list[dict[str, str]]:
    return [
        {
            "iam_binding_id": row.get("IAM_Binding_ID", ""),
            "service_account_id": row.get("Service_Account_ID", ""),
            "role": row.get("Role", ""),
            "scope": row.get("Scope", ""),
            "is_high_privilege": row.get("Is_High_Privilege", ""),
        }
        for row in sorted(rows, key=lambda item: (item.get("Service_Account_ID", ""), item.get("IAM_Binding_ID", "")))
    ]


def _cicd_entries(rows: list[Row]) -> list[dict[str, str]]:
    return [
        {
            "cicd_id": row.get("CICD_ID", ""),
            "pipeline_name": row.get("Pipeline_Name", ""),
            "runner": row.get("Runner", ""),
            "deployment_account": row.get("Deployment_Account", ""),
            "artifact_registry": row.get("Artifact_Registry", ""),
            "approval_required": row.get("Approval_Required", ""),
        }
        for row in sorted(rows, key=lambda item: item.get("CICD_ID", ""))
    ]


def _join_ids(rows: list[Row], field: str) -> str:
    return "; ".join(sorted({row.get(field, "") for row in rows if row.get(field, "")}))


def _sorted_findings(findings: list[AnalysisFinding]) -> list[AnalysisFinding]:
    return sorted(findings, key=lambda item: item.finding_id)


def _md_cell(value: str) -> str:
    return (value or "").replace("|", "\\|").replace("\n", "<br>")
