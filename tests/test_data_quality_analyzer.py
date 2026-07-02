from __future__ import annotations

import csv
import json
from pathlib import Path

from dataflow_agent.analyzers.data_quality import analyze_data_quality, write_data_quality_report
from dataflow_agent.analyzers.indexes import build_analysis_indexes
from dataflow_agent.models import DroppedEdge, GraphEdge, GraphModel, GraphNode, WorkbookData


def _workbook(rows_by_sheet: dict[str, list[dict[str, str]]]) -> WorkbookData:
    return WorkbookData(
        path=Path("test-workbook.xlsx"),
        sheets=rows_by_sheet,
        headers={sheet: list(rows[0]) if rows else [] for sheet, rows in rows_by_sheet.items()},
        metadata={},
        enums={},
    )


def _graph(
    edges: list[GraphEdge] | None = None,
    dropped_edges: list[DroppedEdge] | None = None,
) -> GraphModel:
    return GraphModel(
        nodes={
            "svc-connected": GraphNode("svc-connected", "service", "Connected", "04_Services"),
            "svc-worker": GraphNode("svc-worker", "service", "Worker", "04_Services"),
            "svc-p1": GraphNode("svc-p1", "service", "P1", "04_Services"),
            "data-orders": GraphNode("data-orders", "data_asset", "Orders", "06_Data_Assets"),
            "ext-payments": GraphNode("ext-payments", "external_service", "Payments", "12_External_Services"),
        },
        edges=edges or [],
        dropped_edges=dropped_edges or [],
    )


def test_data_quality_flags_critical_service_gaps_and_isolation_severity() -> None:
    workbook = _workbook(
        {
            "04_Services": [
                {
                    "Record_ID": "rec-svc-p0",
                    "Service_ID": "svc-p0",
                    "Service_Name": "P0 API",
                    "Service_Priority": "P0",
                    "Running_On_Instance_ID": "",
                    "Runtime_ID": "",
                    "Listen_Ports": "",
                    "Service_Owner": "",
                    "Evidence_ID": "ev-svc-p0",
                    "Confirmation_Status": "Confirmed",
                },
                {
                    "Record_ID": "rec-svc-p1",
                    "Service_ID": "svc-p1",
                    "Service_Name": "P1 Worker",
                    "Service_Priority": "P1",
                    "Running_On_Instance_ID": "inst-1",
                    "Runtime_ID": "",
                    "Listen_Ports": "443",
                    "Service_Owner": "team-a",
                    "Evidence_ID": "ev-svc-p1",
                    "Confirmation_Status": "Confirmed",
                },
                {
                    "Record_ID": "rec-svc-deprecated",
                    "Service_ID": "svc-deprecated",
                    "Service_Name": "Deprecated P1 Worker",
                    "Service_Priority": "P1",
                    "Running_On_Instance_ID": "inst-2",
                    "Runtime_ID": "",
                    "Listen_Ports": "8443",
                    "Service_Owner": "team-a",
                    "Evidence_ID": "ev-svc-deprecated",
                    "Confirmation_Status": "Confirmed",
                    "Notes": "deprecated and scheduled for removal",
                },
                {
                    "Record_ID": "rec-svc-connected",
                    "Service_ID": "svc-connected",
                    "Service_Name": "Connected API",
                    "Service_Priority": "P0",
                    "Running_On_Instance_ID": "",
                    "Runtime_ID": "runtime-connected",
                    "Listen_Ports": "443",
                    "Service_Owner": "team-a",
                    "Evidence_ID": "ev-svc-connected",
                    "Confirmation_Status": "Confirmed",
                },
            ]
        }
    )
    graph = _graph([GraphEdge("edge-1", "calls", "svc-connected", "svc-worker")])
    indexes = build_analysis_indexes(workbook, graph)

    findings = analyze_data_quality(workbook, graph, indexes)

    by_category = {(finding.category, finding.object_id): finding for finding in findings}
    assert by_category[("critical_service_isolated", "svc-p0")].severity == "P1"
    assert by_category[("critical_service_isolated", "svc-p1")].severity == "P2"
    assert ("critical_service_isolated", "svc-deprecated") not in by_category
    assert ("critical_service_isolated", "svc-connected") not in by_category
    assert by_category[("critical_service_missing_owner", "svc-p0")].severity == "P1"
    assert by_category[("critical_service_missing_runtime", "svc-p0")].field == "Running_On_Instance_ID,Runtime_ID"
    assert by_category[("critical_service_missing_listen_ports", "svc-p0")].evidence_id == "ev-svc-p0"
    assert all(finding.domain == "data_quality" for finding in findings)
    assert all(finding.sheet and finding.row_id and finding.object_type and finding.object_id for finding in findings)
    assert all(finding.field and finding.impact and finding.suggested_action for finding in findings)


def test_data_quality_flags_dependency_asset_external_and_dropped_edge_rules() -> None:
    workbook = _workbook(
        {
            "05_Dependencies": [
                {
                    "Record_ID": "rec-dep-missing",
                    "Dependency_ID": "dep-missing-target",
                    "Source_Service_ID": "svc-connected",
                    "Target_ID": "",
                    "Target_Service_ID": "",
                    "Target_External_ID": "",
                    "Target_Data_Asset_ID": "",
                    "Auth_Method": "",
                    "Evidence_ID": "ev-dep-missing",
                    "Confirmation_Status": "Confirmed",
                },
                {
                    "Record_ID": "rec-dep-legacy",
                    "Dependency_ID": "dep-legacy-target",
                    "Source_Service_ID": "svc-connected",
                    "Target_ID": "",
                    "Target_Service_ID": "svc-worker",
                    "Auth_Method": "mTLS",
                    "Evidence_ID": "ev-dep-legacy",
                    "Confirmation_Status": "Confirmed",
                },
                {
                    "Record_ID": "rec-dep-auth",
                    "Dependency_ID": "dep-missing-auth",
                    "Source_Service_ID": "svc-connected",
                    "Target_ID": "data-orders",
                    "Target_Type": "data_asset",
                    "Auth_Method": "",
                    "Evidence_ID": "ev-dep-auth",
                    "Confirmation_Status": "Confirmed",
                },
            ],
            "06_Data_Assets": [
                {
                    "Record_ID": "rec-data-missing",
                    "Data_Asset_ID": "data-unlinked",
                    "Used_By_Service_ID": "",
                    "Evidence_ID": "ev-data-missing",
                    "Confirmation_Status": "Confirmed",
                }
            ],
            "12_External_Services": [
                {
                    "Record_ID": "rec-ext-missing",
                    "External_ID": "ext-unlinked",
                    "Used_By_Service_ID": "",
                    "Evidence_ID": "ev-ext-missing",
                    "Confirmation_Status": "Confirmed",
                }
            ],
        }
    )
    dropped_edge = DroppedEdge(
        id="edge-9000",
        type="calls",
        source="svc-connected",
        target="missing-svc",
        evidence_id="ev-edge",
        reason="target node missing-svc does not exist",
        metadata={"source_sheet": "05_Dependencies", "record_id": "rec-dep-edge"},
    )
    graph = _graph(dropped_edges=[dropped_edge])
    indexes = build_analysis_indexes(workbook, graph)

    findings = analyze_data_quality(workbook, graph, indexes)

    by_category = {(finding.category, finding.object_id): finding for finding in findings}
    assert by_category[("dependency_missing_target", "dep-missing-target")].severity == "P1"
    assert by_category[("dependency_missing_auth_method", "dep-missing-target")].severity == "P2"
    assert by_category[("dependency_missing_auth_method", "dep-missing-auth")].field == "Auth_Method"
    assert ("dependency_missing_target", "dep-legacy-target") not in by_category
    assert by_category[("data_asset_missing_used_by", "data-unlinked")].severity == "P2"
    assert by_category[("external_service_missing_used_by", "ext-unlinked")].severity == "P2"
    dropped = by_category[("graph_dropped_edge", "edge-9000")]
    assert dropped.severity == "P1"
    assert dropped.object_type == "graph_edge"
    assert dropped.sheet == "05_Dependencies"
    assert dropped.row_id == "rec-dep-edge"
    assert dropped.evidence_id == "ev-edge"


def test_data_quality_finding_ids_are_deterministic_by_rule_and_object() -> None:
    workbook = _workbook(
        {
            "06_Data_Assets": [
                {
                    "Record_ID": "rec-data-b",
                    "Data_Asset_ID": "data-b",
                    "Used_By_Service_ID": "",
                    "Confirmation_Status": "Confirmed",
                },
                {
                    "Record_ID": "rec-data-a",
                    "Data_Asset_ID": "data-a",
                    "Used_By_Service_ID": "",
                    "Confirmation_Status": "Confirmed",
                },
            ],
            "12_External_Services": [
                {
                    "Record_ID": "rec-ext-a",
                    "External_ID": "ext-a",
                    "Used_By_Service_ID": "",
                    "Confirmation_Status": "Confirmed",
                }
            ],
        }
    )
    graph = _graph()
    indexes = build_analysis_indexes(workbook, graph)

    first = analyze_data_quality(workbook, graph, indexes)
    second = analyze_data_quality(workbook, graph, indexes)

    assert [finding.finding_id for finding in first] == ["DQ-0001", "DQ-0002", "DQ-0003"]
    assert [(finding.finding_id, finding.category, finding.object_id) for finding in first] == [
        ("DQ-0001", "data_asset_missing_used_by", "data-a"),
        ("DQ-0002", "data_asset_missing_used_by", "data-b"),
        ("DQ-0003", "external_service_missing_used_by", "ext-a"),
    ]
    assert [finding.as_dict() for finding in first] == [finding.as_dict() for finding in second]


def test_write_data_quality_report_creates_md_json_and_csv(tmp_path: Path) -> None:
    workbook = _workbook(
        {
            "12_External_Services": [
                {
                    "Record_ID": "rec-ext-missing",
                    "External_ID": "ext-unlinked",
                    "Used_By_Service_ID": "",
                    "Evidence_ID": "ev-ext-missing",
                    "Confirmation_Status": "Confirmed",
                }
            ]
        }
    )
    graph = _graph()
    indexes = build_analysis_indexes(workbook, graph)
    findings = analyze_data_quality(workbook, graph, indexes)

    paths = write_data_quality_report(tmp_path, findings)

    assert set(paths) == {"md", "json", "csv"}
    assert paths["md"] == tmp_path / "data_quality_report.md"
    assert paths["json"] == tmp_path / "data_quality_report.json"
    assert paths["csv"] == tmp_path / "data_quality_report.csv"
    assert "# Data Quality Report" in paths["md"].read_text(encoding="utf-8")
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["summary"]["total_findings"] == 1
    assert payload["findings"][0]["finding_id"] == "DQ-0001"
    with paths["csv"].open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["category"] == "external_service_missing_used_by"
