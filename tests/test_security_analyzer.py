from __future__ import annotations

import json
from pathlib import Path

from dataflow_agent.analyzers.indexes import build_analysis_indexes
from dataflow_agent.analyzers.security import (
    analyze_security_risks,
    permission_blast_radius,
    security_control_gap_rows,
    sensitive_data_flow_rows,
    write_permission_blast_radius_json,
    write_security_control_gap_report_csv,
    write_security_risk_report,
    write_sensitive_data_flow_report_md,
)
from dataflow_agent.models import GraphEdge, GraphModel, GraphNode, WorkbookData


def _workbook(rows_by_sheet: dict[str, list[dict[str, str]]]) -> WorkbookData:
    return WorkbookData(
        path=Path("test-workbook.xlsx"),
        sheets=rows_by_sheet,
        headers={sheet: list(rows[0]) if rows else [] for sheet, rows in rows_by_sheet.items()},
        metadata={},
        enums={},
    )


def _fixture() -> tuple[WorkbookData, GraphModel]:
    workbook = _workbook(
        {
            "04_Services": [
                {
                    "Record_ID": "rec-svc-entry",
                    "Service_ID": "svc-entry",
                    "Service_Name": "Public Nginx Entry",
                    "Service_Priority": "P0",
                    "Service_Role": "public entry nginx",
                    "Listen_Ports": "443",
                    "Running_On_Instance_ID": "inst-entry",
                    "Evidence_ID": "ev-svc-entry",
                    "Confirmation_Status": "Confirmed",
                    "Notes": "",
                },
                {
                    "Record_ID": "rec-svc-app",
                    "Service_ID": "svc-app",
                    "Service_Name": "App API",
                    "Service_Priority": "P1",
                    "Service_Role": "api",
                    "Listen_Ports": "8443",
                    "Running_On_Instance_ID": "inst-app",
                    "Evidence_ID": "ev-svc-app",
                    "Confirmation_Status": "Confirmed",
                    "Notes": "",
                },
                {
                    "Record_ID": "rec-svc-admin",
                    "Service_ID": "svc-admin",
                    "Service_Name": "Admin Worker",
                    "Service_Priority": "P2",
                    "Service_Role": "admin",
                    "Listen_Ports": "",
                    "Running_On_Instance_ID": "inst-admin",
                    "Evidence_ID": "ev-svc-admin",
                    "Confirmation_Status": "Confirmed",
                    "Notes": "",
                },
                {
                    "Record_ID": "rec-svc-unmonitored",
                    "Service_ID": "svc-unmonitored",
                    "Service_Name": "Batch Job",
                    "Service_Priority": "P2",
                    "Service_Role": "worker",
                    "Listen_Ports": "",
                    "Running_On_Instance_ID": "inst-batch",
                    "Evidence_ID": "ev-svc-unmonitored",
                    "Confirmation_Status": "Confirmed",
                    "Notes": "",
                },
                {
                    "Record_ID": "rec-svc-worker",
                    "Service_ID": "svc-worker",
                    "Service_Name": "Shared Worker",
                    "Service_Priority": "P2",
                    "Service_Role": "worker",
                    "Listen_Ports": "",
                    "Running_On_Instance_ID": "inst-worker",
                    "Evidence_ID": "ev-svc-worker",
                    "Confirmation_Status": "Confirmed",
                    "Notes": "",
                },
            ],
            "05_Dependencies": [
                {
                    "Record_ID": "rec-dep-data",
                    "Dependency_ID": "dep-app-data",
                    "Source_Service_ID": "svc-app",
                    "Target_Type": "data_asset",
                    "Target_ID": "data-secrets",
                    "Target_Data_Asset_ID": "",
                    "Evidence_ID": "ev-dep-data",
                    "Confirmation_Status": "Confirmed",
                },
                {
                    "Record_ID": "rec-dep-ext",
                    "Dependency_ID": "dep-app-payments",
                    "Source_Service_ID": "svc-app",
                    "Target_Type": "external_service",
                    "Target_ID": "ext-payments",
                    "Target_External_ID": "",
                    "Evidence_ID": "ev-dep-ext",
                    "Confirmation_Status": "Confirmed",
                },
            ],
            "06_Data_Assets": [
                {
                    "Record_ID": "rec-data-secrets",
                    "Data_Asset_ID": "data-secrets",
                    "Data_Asset_Name": "Secrets DB",
                    "Sensitivity": "restricted",
                    "Access_Type": "read/write",
                    "Used_By_Service_ID": "svc-app; svc-admin; svc-unmonitored",
                    "Evidence_ID": "ev-data-secrets",
                    "Confirmation_Status": "Confirmed",
                }
            ],
            "07_Firewalls": [
                {
                    "Record_ID": "rec-fw-open",
                    "Firewall_ID": "fw-open",
                    "Source_Allowed": "0.0.0.0/0",
                    "Reason": "",
                    "Evidence_ID": "ev-fw-open",
                    "Confirmation_Status": "Confirmed",
                }
            ],
            "08_Cloud_Armor": [],
            "09_IAM_SA": [
                {
                    "Record_ID": "rec-iam-admin",
                    "IAM_Binding_ID": "iam-admin",
                    "Service_Account_ID": "sa-admin",
                    "Service_Account_Email": "sa-admin@example.test",
                    "Used_By_Service_ID": "svc-admin",
                    "Role": "roles/owner",
                    "Scope": "project",
                    "Justification": "",
                    "Is_High_Privilege": "Yes",
                    "Evidence_ID": "ev-iam-admin",
                    "Confirmation_Status": "Confirmed",
                },
                {
                    "Record_ID": "rec-iam-shared",
                    "IAM_Binding_ID": "iam-shared",
                    "Service_Account_ID": "sa-shared",
                    "Service_Account_Email": "sa-shared@example.test",
                    "Used_By_Service_ID": "svc-app; svc-worker",
                    "Role": "roles/viewer",
                    "Scope": "project",
                    "Justification": "",
                    "Is_High_Privilege": "No",
                    "Evidence_ID": "ev-iam-shared",
                    "Confirmation_Status": "Confirmed",
                },
                {
                    "Record_ID": "rec-iam-editor",
                    "IAM_Binding_ID": "iam-editor",
                    "Service_Account_ID": "sa-editor",
                    "Service_Account_Email": "sa-editor@example.test",
                    "Used_By_Service_ID": "svc-worker",
                    "Role": "roles/editor",
                    "Scope": "project",
                    "Justification": "",
                    "Is_High_Privilege": "No",
                    "Evidence_ID": "ev-iam-editor",
                    "Confirmation_Status": "Confirmed",
                },
            ],
            "10_Monitoring": [
                {
                    "Record_ID": "rec-mon-app",
                    "Monitoring_ID": "mon-app",
                    "Object_Type": "service",
                    "Object_ID": "svc-app",
                    "Coverage_Status": "Partial",
                    "Evidence_ID": "ev-mon-app",
                    "Confirmation_Status": "Confirmed",
                },
                {
                    "Record_ID": "rec-mon-admin",
                    "Monitoring_ID": "mon-admin",
                    "Object_Type": "service",
                    "Object_ID": "svc-admin",
                    "Coverage_Status": "Covered",
                    "Evidence_ID": "ev-mon-admin",
                    "Confirmation_Status": "Confirmed",
                },
            ],
            "11_CICD": [
                {
                    "Record_ID": "rec-pipe-entry",
                    "CICD_ID": "pipe-entry",
                    "Pipeline_Name": "Entry Deploy",
                    "Runner": "github-hosted",
                    "Artifact_Registry": "registry/entry",
                    "Deployment_Account": "deploy-entry",
                    "Target_Service_ID": "svc-entry",
                    "Target_Instance_ID": "",
                    "Approval_Required": "No",
                    "Evidence_ID": "ev-pipe-entry",
                    "Confirmation_Status": "Confirmed",
                },
                {
                    "Record_ID": "rec-pipe-app",
                    "CICD_ID": "pipe-app",
                    "Pipeline_Name": "App Deploy",
                    "Runner": "self-hosted",
                    "Artifact_Registry": "registry/app",
                    "Deployment_Account": "deploy-app",
                    "Target_Service_ID": "svc-app",
                    "Target_Instance_ID": "",
                    "Approval_Required": "Yes",
                    "Evidence_ID": "ev-pipe-app",
                    "Confirmation_Status": "Confirmed",
                },
                {
                    "Record_ID": "rec-pipe-bad",
                    "CICD_ID": "pipe-bad",
                    "Pipeline_Name": "Unmapped Deploy",
                    "Runner": "",
                    "Artifact_Registry": "",
                    "Deployment_Account": "",
                    "Target_Service_ID": "",
                    "Target_Instance_ID": "",
                    "Approval_Required": "Yes",
                    "Evidence_ID": "ev-pipe-bad",
                    "Confirmation_Status": "Confirmed",
                },
            ],
            "12_External_Services": [
                {
                    "Record_ID": "rec-ext-missing",
                    "External_ID": "ext-missing",
                    "External_Name": "Missing Vendor",
                    "Auth_Method": "",
                    "Purpose": "",
                    "Data_Classification": "",
                    "Used_By_Service_ID": "",
                    "Direction": "egress",
                    "Evidence_ID": "ev-ext-missing",
                    "Confirmation_Status": "Confirmed",
                },
                {
                    "Record_ID": "rec-ext-payments",
                    "External_ID": "ext-payments",
                    "External_Name": "Payments",
                    "Auth_Method": "mTLS",
                    "Purpose": "payments",
                    "Data_Classification": "confidential",
                    "Used_By_Service_ID": "svc-app",
                    "Direction": "egress",
                    "Evidence_ID": "ev-ext-payments",
                    "Confirmation_Status": "Confirmed",
                },
            ],
        }
    )
    graph = GraphModel(
        nodes={
            "svc-app": GraphNode("svc-app", "service", "App API", "04_Services"),
            "data-secrets": GraphNode("data-secrets", "data_asset", "Secrets DB", "06_Data_Assets"),
            "ext-payments": GraphNode("ext-payments", "external_service", "Payments", "12_External_Services"),
        },
        edges=[
            GraphEdge("edge-data", "reads_from", "svc-app", "data-secrets"),
            GraphEdge("edge-ext", "calls_external", "svc-app", "ext-payments"),
        ],
    )
    return workbook, graph


def test_security_analyzer_covers_all_security_rules() -> None:
    workbook, graph = _fixture()
    indexes = build_analysis_indexes(workbook, graph)

    findings = analyze_security_risks(workbook, graph, indexes)

    assert [finding.finding_id for finding in findings] == [f"SEC-{idx:04d}" for idx in range(1, 11)]
    categories = {finding.category for finding in findings}
    assert categories == {
        "CI/CD approval",
        "CI/CD completeness",
        "Entry protection",
        "External service completeness",
        "Firewall public source",
        "High privilege IAM",
        "Sensitive data access",
        "Shared service account",
    }
    assert any(finding.severity == "P1" and finding.object_id == "svc-entry" for finding in findings)
    assert any(finding.severity == "P2" and finding.object_id == "ext-missing" for finding in findings)
    assert any(finding.severity == "P1" and finding.object_id == "data-secrets:svc-admin" for finding in findings)
    assert any(finding.severity == "P2" and finding.object_id == "data-secrets:svc-unmonitored" for finding in findings)
    assert any(finding.object_id == "iam-admin" and finding.field == "Justification" for finding in findings)
    assert any(finding.object_id == "iam-editor" and finding.field == "Justification" for finding in findings)
    assert any(finding.object_id == "sa-shared" and finding.severity == "P2" for finding in findings)
    assert any(finding.object_id == "pipe-entry" and finding.severity == "P1" for finding in findings)
    assert any(finding.object_id == "pipe-bad" and "Target_Service_ID/Target_Instance_ID" in finding.field for finding in findings)
    for finding in findings:
        assert finding.sheet
        assert finding.row_id
        assert finding.object_type
        assert finding.object_id
        assert finding.field
        assert finding.evidence_id
        assert finding.impact
        assert finding.suggested_action


def test_security_helper_outputs_are_grouped_and_deterministic() -> None:
    workbook, graph = _fixture()
    indexes = build_analysis_indexes(workbook, graph)
    findings = analyze_security_risks(workbook, graph, indexes)

    gap_rows = security_control_gap_rows(findings)
    assert [row["finding_id"] for row in gap_rows] == [f"SEC-{idx:04d}" for idx in range(1, 11)]
    assert gap_rows[0]["category"] == "CI/CD completeness"

    radius = permission_blast_radius(workbook, graph, indexes)
    assert radius["svc-app"]["service_priority"] == "P1"
    assert radius["svc-app"]["monitoring_status"] == "Partial"
    assert radius["svc-app"]["data_assets"][0]["data_asset_id"] == "data-secrets"
    assert radius["svc-app"]["external_calls"][0]["external_id"] == "ext-payments"
    assert radius["svc-app"]["iam_roles"][0]["role"] == "roles/viewer"
    assert radius["svc-app"]["high_privilege"] is False
    assert radius["svc-app"]["cicd_deployments"][0]["cicd_id"] == "pipe-app"
    assert radius["svc-admin"]["high_privilege"] is True

    sensitive_rows = sensitive_data_flow_rows(workbook, graph, indexes)
    assert [row["service_id"] for row in sensitive_rows] == ["svc-admin", "svc-app", "svc-unmonitored"]
    app_row = next(row for row in sensitive_rows if row["service_id"] == "svc-app")
    assert app_row["external_dependencies"] == "ext-payments"
    assert app_row["iam_roles"] == "roles/viewer"
    assert app_row["cicd_deployments"] == "pipe-app"


def test_security_report_writers_create_expected_files(tmp_path: Path) -> None:
    workbook, graph = _fixture()
    indexes = build_analysis_indexes(workbook, graph)
    findings = analyze_security_risks(workbook, graph, indexes)

    report_paths = write_security_risk_report(tmp_path, findings)
    gap_path = write_security_control_gap_report_csv(tmp_path, findings)
    radius_path = write_permission_blast_radius_json(tmp_path, workbook, graph, indexes)
    sensitive_path = write_sensitive_data_flow_report_md(tmp_path, workbook, graph, indexes)

    assert set(report_paths) == {"md", "json", "csv"}
    assert (tmp_path / "security_risk_report.md").exists()
    assert (tmp_path / "security_risk_report.json").exists()
    assert (tmp_path / "security_risk_report.csv").exists()
    payload = json.loads(report_paths["json"].read_text(encoding="utf-8"))
    assert payload["summary"]["total_findings"] == 10
    assert "SEC-0001" in gap_path.read_text(encoding="utf-8")
    radius = json.loads(radius_path.read_text(encoding="utf-8"))
    assert radius["svc-app"]["external_calls"][0]["external_id"] == "ext-payments"
    sensitive_report = sensitive_path.read_text(encoding="utf-8")
    assert "# Sensitive Data Flow Report" in sensitive_report
    assert "data-secrets" in sensitive_report
    assert "svc-admin" in sensitive_report
