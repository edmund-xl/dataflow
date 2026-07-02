from __future__ import annotations

import csv
import json
from pathlib import Path

from dataflow_agent.analyzers.indexes import build_analysis_indexes
from dataflow_agent.analyzers.monitoring import (
    analyze_monitoring_gaps,
    monitoring_requirements_rows,
    suggested_alerts_rows,
    write_monitoring_gap_report,
    write_monitoring_requirements_csv,
    write_suggested_alerts_csv,
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


def _graph() -> GraphModel:
    return GraphModel(
        nodes={
            "svc-api": GraphNode("svc-api", "service", "API", "04_Services"),
            "svc-admin": GraphNode("svc-admin", "service", "Admin", "04_Services"),
            "svc-ok": GraphNode("svc-ok", "service", "OK", "04_Services"),
            "ext-payments": GraphNode("ext-payments", "external_service", "Payments", "12_External_Services"),
        },
        edges=[
            GraphEdge(
                "edge-external",
                "calls_external",
                "svc-api",
                "ext-payments",
                evidence_id="ev-dep-external",
                metadata={"dependency_id": "dep-external"},
            )
        ],
    )


def _fixture() -> tuple[WorkbookData, GraphModel]:
    workbook = _workbook(
        {
            "04_Services": [
                {
                    "Record_ID": "rec-svc-api",
                    "Service_ID": "svc-api",
                    "Service_Priority": "P0",
                    "Evidence_ID": "ev-svc-api",
                    "Confirmation_Status": "Confirmed",
                },
                {
                    "Record_ID": "rec-svc-admin",
                    "Service_ID": "svc-admin",
                    "Service_Priority": "P1",
                    "Evidence_ID": "ev-svc-admin",
                    "Confirmation_Status": "Confirmed",
                },
                {
                    "Record_ID": "rec-svc-ok",
                    "Service_ID": "svc-ok",
                    "Service_Priority": "P0",
                    "Evidence_ID": "ev-svc-ok",
                    "Confirmation_Status": "Confirmed",
                },
            ],
            "05_Dependencies": [
                {
                    "Record_ID": "rec-dep-critical",
                    "Dependency_ID": "dep-critical",
                    "Source_Service_ID": "svc-api",
                    "Target_Service_ID": "svc-admin",
                    "Dependency_Criticality": "P1",
                    "Evidence_ID": "ev-dep-critical",
                    "Confirmation_Status": "Confirmed",
                },
                {
                    "Record_ID": "rec-dep-external",
                    "Dependency_ID": "dep-external",
                    "Source_Service_ID": "svc-api",
                    "Target_Type": "external_service",
                    "Target_ID": "ext-payments",
                    "Dependency_Criticality": "P2",
                    "Evidence_ID": "ev-dep-external",
                    "Confirmation_Status": "Confirmed",
                },
                {
                    "Record_ID": "rec-dep-async",
                    "Dependency_ID": "dep-async",
                    "Source_Service_ID": "svc-api",
                    "Target_Service_ID": "svc-admin",
                    "Call_Description": "publish order events for async consume",
                    "Dependency_Criticality": "P2",
                    "Evidence_ID": "ev-dep-async",
                    "Confirmation_Status": "Confirmed",
                },
                {
                    "Record_ID": "rec-dep-monitored",
                    "Dependency_ID": "dep-monitored",
                    "Source_Service_ID": "svc-api",
                    "Target_Service_ID": "svc-ok",
                    "Dependency_Criticality": "P0",
                    "Evidence_ID": "ev-dep-monitored",
                    "Confirmation_Status": "Confirmed",
                },
            ],
            "06_Data_Assets": [
                {
                    "Record_ID": "rec-data-secret",
                    "Data_Asset_ID": "data-secret",
                    "Sensitivity": "High",
                    "Evidence_ID": "ev-data-secret",
                    "Confirmation_Status": "Confirmed",
                },
                {
                    "Record_ID": "rec-data-public",
                    "Data_Asset_ID": "data-public",
                    "Sensitivity": "Low",
                    "Evidence_ID": "ev-data-public",
                    "Confirmation_Status": "Confirmed",
                },
            ],
            "10_Monitoring": [
                {
                    "Record_ID": "rec-mon-api",
                    "Monitoring_ID": "mon-api",
                    "Object_Type": "service",
                    "Object_ID": "svc-api",
                    "Dashboard_URL": "",
                    "Alert_Rule": "",
                    "Logging_Coverage": "No",
                    "XDR_Coverage": "Unknown",
                    "Coverage_Status": "Partial",
                    "Evidence_ID": "ev-mon-api",
                    "Confirmation_Status": "Confirmed",
                },
                {
                    "Record_ID": "rec-mon-ok",
                    "Monitoring_ID": "mon-ok",
                    "Object_Type": "service",
                    "Object_ID": "svc-ok",
                    "Dashboard_URL": "https://dash.example/svc-ok",
                    "Alert_Rule": "svc-ok-error-rate",
                    "Logging_Coverage": "Yes",
                    "XDR_Coverage": "Yes",
                    "Coverage_Status": "Covered",
                    "Evidence_ID": "ev-mon-ok",
                    "Confirmation_Status": "Confirmed",
                },
                {
                    "Record_ID": "rec-mon-dep",
                    "Monitoring_ID": "mon-dep",
                    "Object_Type": "dependency",
                    "Object_ID": "dep-monitored",
                    "Dashboard_URL": "https://dash.example/dep",
                    "Alert_Rule": "dep-error-rate",
                    "Logging_Coverage": "Yes",
                    "XDR_Coverage": "Yes",
                    "Coverage_Status": "Covered",
                    "Evidence_ID": "ev-mon-dep",
                    "Confirmation_Status": "Confirmed",
                },
            ],
            "12_External_Services": [
                {
                    "Record_ID": "rec-ext-payments",
                    "External_ID": "ext-payments",
                    "Evidence_ID": "ev-ext-payments",
                    "Confirmation_Status": "Confirmed",
                }
            ],
        }
    )
    return workbook, _graph()


def test_analyze_monitoring_gaps_covers_all_rules_with_stable_ids() -> None:
    workbook, graph = _fixture()
    indexes = build_analysis_indexes(workbook, graph)

    findings = analyze_monitoring_gaps(workbook, graph, indexes)

    assert [finding.finding_id for finding in findings] == [
        "MON-0001",
        "MON-0002",
        "MON-0003",
        "MON-0004",
        "MON-0005",
        "MON-0006",
    ]
    by_category = {finding.category: finding for finding in findings}
    assert by_category["missing_service_monitoring"].severity == "P1"
    assert by_category["missing_service_monitoring"].object_id == "svc-admin"
    assert by_category["incomplete_p0_service_monitoring"].severity == "P2"
    assert by_category["incomplete_p0_service_monitoring"].sheet == "10_Monitoring"
    assert by_category["incomplete_p0_service_monitoring"].field == (
        "Dashboard_URL,Alert_Rule,Logging_Coverage,XDR_Coverage,Coverage_Status"
    )
    assert by_category["missing_dependency_monitoring"].object_id == "dep-critical"
    assert by_category["external_dependency_monitoring_recommendation"].object_id == "dep-external"
    assert by_category["async_dependency_monitoring_recommendation"].object_id == "dep-async"
    assert by_category["missing_sensitive_data_asset_monitoring"].object_id == "data-secret"
    assert all(finding.impact for finding in findings)
    assert all(finding.suggested_action for finding in findings)
    assert all(finding.evidence_id for finding in findings)


def test_missing_or_unknown_p0_service_coverage_is_p1() -> None:
    workbook, graph = _fixture()
    workbook.sheets["10_Monitoring"][0]["Coverage_Status"] = "Unknown"
    indexes = build_analysis_indexes(workbook, graph)

    findings = analyze_monitoring_gaps(workbook, graph, indexes)

    incomplete = next(finding for finding in findings if finding.category == "incomplete_p0_service_monitoring")
    assert incomplete.severity == "P1"


def test_recommendation_helpers_are_deterministic() -> None:
    workbook, graph = _fixture()
    indexes = build_analysis_indexes(workbook, graph)
    findings = analyze_monitoring_gaps(workbook, graph, indexes)

    requirement_rows = monitoring_requirements_rows(findings)
    alert_rows = suggested_alerts_rows(findings)

    assert [row["finding_id"] for row in requirement_rows] == [finding.finding_id for finding in findings]
    external_alerts = {
        row["required_metric"]
        for row in alert_rows
        if row["object_id"] == "dep-external" and row["object_type"] == "dependency"
    }
    async_alerts = {
        row["required_metric"]
        for row in alert_rows
        if row["object_id"] == "dep-async" and row["object_type"] == "dependency"
    }
    assert {"timeout", "error_rate", "latency", "fallback"}.issubset(external_alerts)
    assert {"queue_depth", "consumer_lag", "retry_rate", "dead_letter"}.issubset(async_alerts)
    assert all({"object_id", "object_type", "required_metric", "suggested_alert", "priority", "reason", "evidence_id"} <= row.keys() for row in alert_rows)


def test_report_and_csv_writers_create_expected_files(tmp_path: Path) -> None:
    workbook, graph = _fixture()
    indexes = build_analysis_indexes(workbook, graph)
    findings = analyze_monitoring_gaps(workbook, graph, indexes)

    report_paths = write_monitoring_gap_report(tmp_path, findings)
    requirements_path = write_monitoring_requirements_csv(tmp_path, findings)
    alerts_path = write_suggested_alerts_csv(tmp_path, findings)

    assert set(report_paths) == {"md", "json", "csv"}
    assert (tmp_path / "monitoring_gap_report.md").exists()
    assert (tmp_path / "monitoring_gap_report.json").exists()
    assert (tmp_path / "monitoring_gap_report.csv").exists()
    assert requirements_path == tmp_path / "monitoring_requirements.csv"
    assert alerts_path == tmp_path / "suggested_alerts.csv"

    report_payload = json.loads((tmp_path / "monitoring_gap_report.json").read_text(encoding="utf-8"))
    assert report_payload["summary"]["total_findings"] == len(findings)
    assert report_payload["findings"][0]["finding_id"].startswith("MON-")

    with requirements_path.open(newline="", encoding="utf-8") as file:
        requirement_rows = list(csv.DictReader(file))
    with alerts_path.open(newline="", encoding="utf-8") as file:
        alert_rows = list(csv.DictReader(file))
    assert len(requirement_rows) == len(findings)
    assert any(row["required_control"] == "external dependency monitoring recommendation" for row in requirement_rows)
    assert any(row["required_metric"] == "timeout" and row["object_id"] == "dep-external" for row in alert_rows)

