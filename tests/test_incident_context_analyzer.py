from __future__ import annotations

import json
from pathlib import Path

from dataflow_agent.analyzers.incident_context import build_incident_context, write_incident_context_report
from dataflow_agent.analyzers.indexes import build_analysis_indexes
from dataflow_agent.cli import main
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
                    "Record_ID": "rec-svc-api",
                    "Service_ID": "svc-api",
                    "Service_Name": "API",
                    "Service_Priority": "P0",
                    "Service_Owner": "team-api",
                    "Running_On_Instance_ID": "inst-api",
                    "Protocol": "TCP",
                    "Listen_Ports": "443;8443",
                    "Evidence_ID": "ev-api",
                    "Confirmation_Status": "Confirmed",
                },
                {
                    "Record_ID": "rec-svc-worker",
                    "Service_ID": "svc-worker",
                    "Service_Name": "Worker",
                    "Service_Priority": "P1",
                    "Service_Owner": "team-worker",
                    "Evidence_ID": "ev-worker",
                    "Confirmation_Status": "Confirmed",
                },
            ],
            "05_Dependencies": [
                {
                    "Record_ID": "rec-dep-worker",
                    "Dependency_ID": "dep-worker",
                    "Source_Service_ID": "svc-api",
                    "Target_Service_ID": "svc-worker",
                    "Target_Port": "8443",
                    "Target_Port_Protocol": "TCP",
                    "Auth_Method": "",
                    "Dependency_Criticality": "P1",
                    "Evidence_ID": "ev-dep-worker",
                    "Confirmation_Status": "Confirmed",
                },
                {
                    "Record_ID": "rec-dep-ext",
                    "Dependency_ID": "dep-ext",
                    "Source_Service_ID": "svc-api",
                    "Target_Type": "external_service",
                    "Target_ID": "ext-payments",
                    "Target_External_ID": "ext-payments",
                    "Target_Port": "443",
                    "Target_Port_Protocol": "HTTPS",
                    "Auth_Method": "API key",
                    "Evidence_ID": "ev-dep-ext",
                    "Confirmation_Status": "Confirmed",
                },
            ],
            "06_Data_Assets": [
                {
                    "Record_ID": "rec-data-orders",
                    "Data_Asset_ID": "data-orders",
                    "Data_Asset_Name": "Orders",
                    "Used_By_Service_ID": "svc-api",
                    "Sensitivity": "High",
                    "Evidence_ID": "ev-data-orders",
                    "Confirmation_Status": "Confirmed",
                }
            ],
            "09_IAM_SA": [
                {
                    "Record_ID": "rec-iam-api",
                    "IAM_Binding_ID": "iam-api",
                    "Service_Account_ID": "sa-api",
                    "Service_Account_Email": "sa-api@example.invalid",
                    "Used_By_Service_ID": "svc-api",
                    "Role": "roles/owner",
                    "Is_High_Privilege": "Yes",
                    "Justification": "",
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
                    "Dashboard_URL": "https://dash.example/svc-api",
                    "Alert_Rule": "",
                    "Evidence_ID": "ev-mon-api",
                    "Confirmation_Status": "Confirmed",
                }
            ],
            "11_CICD": [
                {
                    "Record_ID": "rec-cicd-api",
                    "CICD_ID": "cicd-api",
                    "Pipeline_Name": "deploy-api",
                    "Target_Service_ID": "svc-api",
                    "Deployment_Entry": "manual approval",
                    "Deployment_Account": "deploy-api",
                    "Approval_Required": "Yes",
                    "Evidence_ID": "ev-cicd-api",
                    "Confirmation_Status": "Confirmed",
                }
            ],
            "12_External_Services": [
                {
                    "Record_ID": "rec-ext",
                    "External_ID": "ext-payments",
                    "External_Name": "Payments",
                    "Used_By_Service_ID": "svc-api",
                    "Endpoint": "https://payments.example.invalid",
                    "Evidence_ID": "ev-ext",
                    "Confirmation_Status": "Confirmed",
                }
            ],
        }
    )
    graph = GraphModel(
        nodes={
            "svc-api": GraphNode("svc-api", "service", "API", "04_Services"),
            "svc-worker": GraphNode("svc-worker", "service", "Worker", "04_Services"),
            "ext-payments": GraphNode("ext-payments", "external_service", "Payments", "12_External_Services"),
            "data-orders": GraphNode("data-orders", "data_asset", "Orders", "06_Data_Assets"),
        },
        edges=[
            GraphEdge("edge-worker", "calls", "svc-api", "svc-worker", metadata={"dependency_id": "dep-worker"}),
            GraphEdge("edge-ext", "calls_external", "svc-api", "ext-payments", metadata={"dependency_id": "dep-ext"}),
            GraphEdge("edge-data", "reads_from", "svc-api", "data-orders"),
        ],
    )
    return workbook, graph


def test_incident_context_collects_service_related_operational_context(tmp_path: Path) -> None:
    workbook, graph = _fixture()
    indexes = build_analysis_indexes(workbook, graph)

    context = build_incident_context(workbook, graph, indexes, "svc-api", "high error rate")
    outputs = write_incident_context_report(tmp_path, context)

    assert context["service"]["Service_Owner"] == "team-api"
    assert context["ports"]["listen_ports"] == ["443", "8443"]
    assert context["downstream"][0]["id"] == "data-orders"
    assert {row["Data_Asset_ID"] for row in context["data_assets"]} == {"data-orders"}
    assert {row["External_ID"] for row in context["external_dependencies"]} == {"ext-payments"}
    assert context["monitoring"][0]["Monitoring_ID"] == "mon-api"
    assert context["iam"][0]["IAM_Binding_ID"] == "iam-api"
    assert context["cicd"][0]["CICD_ID"] == "cicd-api"
    assert any(risk["object_id"] == "svc-api" for risk in context["related_risks"])
    assert outputs["md"].exists()
    assert outputs["json"].exists()
    assert "Alert: high error rate" in outputs["md"].read_text(encoding="utf-8")


def test_incident_context_rejects_unknown_service() -> None:
    workbook, graph = _fixture()
    indexes = build_analysis_indexes(workbook, graph)

    try:
        build_incident_context(workbook, graph, indexes, "svc-missing")
    except ValueError as exc:
        assert "svc-missing" in str(exc)
    else:
        raise AssertionError("expected missing service to raise ValueError")


def test_incident_cli_writes_context_files_for_clean_sample(tmp_path: Path) -> None:
    output_dir = tmp_path / "incident"

    code = main(
        [
            "incident",
            "--input",
            "samples/DCP_clean_v0.1",
            "--service-id",
            "svc-rpc-api",
            "--alert",
            "rpc latency elevated",
            "--output",
            str(output_dir),
        ]
    )

    assert code == 0
    json_path = output_dir / "incident_context_svc-rpc-api.json"
    assert json_path.exists()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["service_id"] == "svc-rpc-api"
    assert payload["alert"] == "rpc latency elevated"
