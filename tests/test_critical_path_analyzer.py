from __future__ import annotations

import csv
import json
from pathlib import Path

from dataflow_agent.analyzers.critical_path import analyze_critical_paths, write_critical_path_report
from dataflow_agent.analyzers.indexes import build_analysis_indexes
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
            "svc-worker": GraphNode("svc-worker", "service", "Worker", "04_Services"),
            "svc-low": GraphNode("svc-low", "service", "Low", "04_Services"),
            "data-secret": GraphNode("data-secret", "data_asset", "Secret", "06_Data_Assets"),
            "ext-payments": GraphNode("ext-payments", "external_service", "Payments", "12_External_Services"),
        },
        edges=[
            GraphEdge("edge-1", "calls", "svc-api", "svc-worker"),
            GraphEdge("edge-2", "calls_external", "svc-api", "ext-payments", metadata={"dependency_id": "dep-ext"}),
            GraphEdge("edge-3", "reads_from", "svc-api", "data-secret", metadata={"data_asset_id": "data-secret"}),
        ],
    )


def test_critical_path_scores_services_with_stable_ranking() -> None:
    workbook = _workbook(
        {
            "04_Services": [
                {
                    "Record_ID": "rec-svc-worker",
                    "Service_ID": "svc-worker",
                    "Service_Name": "Worker",
                    "Service_Priority": "P1",
                    "Evidence_ID": "ev-worker",
                    "Confirmation_Status": "Confirmed",
                },
                {
                    "Record_ID": "rec-svc-api",
                    "Service_ID": "svc-api",
                    "Service_Name": "API",
                    "Service_Priority": "P0",
                    "Evidence_ID": "ev-api",
                    "Confirmation_Status": "Confirmed",
                },
                {
                    "Record_ID": "rec-svc-low",
                    "Service_ID": "svc-low",
                    "Service_Name": "Low",
                    "Service_Priority": "P2",
                    "Evidence_ID": "ev-low",
                    "Confirmation_Status": "Confirmed",
                },
            ],
            "05_Dependencies": [
                {
                    "Record_ID": "rec-dep-ext",
                    "Dependency_ID": "dep-ext",
                    "Source_Service_ID": "svc-api",
                    "Target_Type": "external_service",
                    "Target_ID": "ext-payments",
                    "Target_External_ID": "ext-payments",
                    "Evidence_ID": "ev-dep-ext",
                    "Confirmation_Status": "Confirmed",
                }
            ],
            "06_Data_Assets": [
                {
                    "Record_ID": "rec-data-secret",
                    "Data_Asset_ID": "data-secret",
                    "Used_By_Service_ID": "svc-api",
                    "Sensitivity": "High",
                    "Evidence_ID": "ev-data-secret",
                    "Confirmation_Status": "Confirmed",
                }
            ],
            "09_IAM_SA": [
                {
                    "Record_ID": "rec-iam-api",
                    "IAM_Binding_ID": "iam-api-owner",
                    "Service_Account_ID": "sa-api",
                    "Used_By_Service_ID": "svc-api",
                    "Role": "roles/owner",
                    "Is_High_Privilege": "Yes",
                    "Evidence_ID": "ev-iam-api",
                    "Confirmation_Status": "Confirmed",
                }
            ],
            "10_Monitoring": [
                {
                    "Record_ID": "rec-mon-api",
                    "Monitoring_ID": "mon-api",
                    "Object_Type": "service",
                    "Object_ID": "svc-api",
                    "Coverage_Status": "Partial",
                    "Evidence_ID": "ev-mon-api",
                    "Confirmation_Status": "Confirmed",
                },
                {
                    "Record_ID": "rec-mon-worker",
                    "Monitoring_ID": "mon-worker",
                    "Object_Type": "service",
                    "Object_ID": "svc-worker",
                    "Coverage_Status": "Covered",
                    "Evidence_ID": "ev-mon-worker",
                    "Confirmation_Status": "Confirmed",
                },
            ],
            "12_External_Services": [
                {
                    "Record_ID": "rec-ext",
                    "External_ID": "ext-payments",
                    "Used_By_Service_ID": "svc-api",
                    "Evidence_ID": "ev-ext",
                    "Confirmation_Status": "Confirmed",
                }
            ],
        }
    )
    indexes = build_analysis_indexes(workbook, _graph())

    impacts = analyze_critical_paths(workbook, _graph(), indexes)

    assert [impact.service_id for impact in impacts] == ["svc-api", "svc-worker", "svc-low"]
    top = impacts[0]
    assert top.rank == 1
    assert top.score >= 75
    assert top.suggested_priority == "P0"
    assert top.evidence_id == "ev-api"
    factor_names = {factor.name for factor in top.factors}
    assert {
        "service_priority",
        "downstream_services",
        "sensitive_data_assets",
        "external_dependencies",
        "high_privilege_iam",
        "monitoring_gap",
    }.issubset(factor_names)


def test_critical_path_handles_empty_workbook() -> None:
    workbook = _workbook({})
    graph = GraphModel()
    indexes = build_analysis_indexes(workbook, graph)

    assert analyze_critical_paths(workbook, graph, indexes) == []


def test_write_critical_path_report_outputs_markdown_csv_and_json(tmp_path: Path) -> None:
    workbook = _workbook(
        {
            "04_Services": [
                {
                    "Record_ID": "rec-svc-a",
                    "Service_ID": "svc-a",
                    "Service_Name": "A",
                    "Service_Priority": "P0",
                    "Evidence_ID": "ev-a",
                    "Confirmation_Status": "Confirmed",
                }
            ]
        }
    )
    graph = GraphModel(nodes={"svc-a": GraphNode("svc-a", "service", "A", "04_Services")})
    impacts = analyze_critical_paths(workbook, graph, build_analysis_indexes(workbook, graph))

    outputs = write_critical_path_report(tmp_path, impacts)

    assert set(outputs) == {"md", "csv", "json"}
    assert "# Critical Path Report" in outputs["md"].read_text(encoding="utf-8")
    rows = list(csv.DictReader(outputs["csv"].open(encoding="utf-8")))
    assert rows[0]["service_id"] == "svc-a"
    payload = json.loads(outputs["json"].read_text(encoding="utf-8"))
    assert payload["summary"]["total_services"] == 1
    assert payload["services"][0]["service_id"] == "svc-a"
