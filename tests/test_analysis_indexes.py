from __future__ import annotations

from pathlib import Path

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


def _graph(edges: list[GraphEdge]) -> GraphModel:
    return GraphModel(
        nodes={
            "svc-api": GraphNode("svc-api", "service", "API", "04_Services"),
            "svc-worker": GraphNode("svc-worker", "service", "Worker", "04_Services"),
            "svc-admin": GraphNode("svc-admin", "service", "Admin", "04_Services"),
            "data-orders": GraphNode("data-orders", "data_asset", "Orders", "06_Data_Assets"),
            "ext-payments": GraphNode("ext-payments", "external_service", "Payments", "12_External_Services"),
        },
        edges=edges,
    )


def test_indexes_service_upstream_downstream_and_dataflow_connected_ids() -> None:
    workbook = _workbook({"04_Services": [{"Service_ID": "svc-api", "Confirmation_Status": "Confirmed"}]})
    graph = _graph(
        [
            GraphEdge("edge-1", "calls", "svc-api", "svc-worker"),
            GraphEdge("edge-2", "reads_from", "svc-api", "data-orders"),
            GraphEdge("edge-3", "uses_sa", "svc-api", "sa-api"),
        ]
    )

    indexes = build_analysis_indexes(workbook, graph)

    assert indexes.downstream["svc-api"] == {"svc-worker", "data-orders"}
    assert indexes.upstream["svc-worker"] == {"svc-api"}
    assert indexes.upstream["data-orders"] == {"svc-api"}
    assert indexes.dataflow_connected_ids == {"svc-api", "svc-worker", "data-orders"}
    assert "sa-api" not in indexes.dataflow_connected_ids


def test_indexes_monitoring_iam_cicd_and_firewalls() -> None:
    workbook = _workbook(
        {
            "09_IAM_SA": [
                {
                    "Record_ID": "rec-iam-1",
                    "IAM_Binding_ID": "iam-1",
                    "Used_By_Service_ID": "svc-api; svc-worker",
                    "Confirmation_Status": "Confirmed",
                }
            ],
            "10_Monitoring": [
                {
                    "Record_ID": "rec-mon-1",
                    "Monitoring_ID": "mon-1",
                    "Object_ID": "svc-api",
                    "Confirmation_Status": "Confirmed",
                }
            ],
            "11_CICD": [
                {
                    "Record_ID": "rec-cicd-1",
                    "CICD_ID": "pipe-1",
                    "Target_Service_ID": "svc-api",
                    "Confirmation_Status": "Confirmed",
                }
            ],
            "07_Firewalls": [
                {
                    "Record_ID": "rec-fw-1",
                    "Firewall_ID": "fw-1",
                    "Related_Service_ID": "svc-api",
                    "Related_Dependency_ID": "dep-api-worker",
                    "Confirmation_Status": "Confirmed",
                }
            ],
        }
    )

    indexes = build_analysis_indexes(workbook, _graph([]))

    assert indexes.monitoring_by_object["svc-api"][0]["Monitoring_ID"] == "mon-1"
    assert indexes.iam_by_service["svc-api"][0]["IAM_Binding_ID"] == "iam-1"
    assert indexes.iam_by_service["svc-worker"][0]["IAM_Binding_ID"] == "iam-1"
    assert indexes.cicd_by_target_service["svc-api"][0]["CICD_ID"] == "pipe-1"
    assert indexes.firewalls_by_service["svc-api"][0]["Firewall_ID"] == "fw-1"
    assert indexes.firewalls_by_dependency["dep-api-worker"][0]["Firewall_ID"] == "fw-1"


def test_indexes_data_assets_and_external_services_by_service() -> None:
    workbook = _workbook(
        {
            "06_Data_Assets": [
                {
                    "Record_ID": "rec-data-1",
                    "Data_Asset_ID": "data-orders",
                    "Used_By_Service_ID": "svc-api; svc-worker",
                    "Confirmation_Status": "Confirmed",
                }
            ],
            "12_External_Services": [
                {
                    "Record_ID": "rec-ext-1",
                    "External_ID": "ext-payments",
                    "Used_By_Service_ID": "svc-api",
                    "Confirmation_Status": "Confirmed",
                }
            ],
        }
    )

    indexes = build_analysis_indexes(workbook, _graph([]))

    assert indexes.data_assets["data-orders"]["Data_Asset_ID"] == "data-orders"
    assert indexes.external_services["ext-payments"]["External_ID"] == "ext-payments"
    assert indexes.data_assets_by_service["svc-api"][0]["Data_Asset_ID"] == "data-orders"
    assert indexes.data_assets_by_service["svc-worker"][0]["Data_Asset_ID"] == "data-orders"
    assert indexes.external_by_service["svc-api"][0]["External_ID"] == "ext-payments"


def test_indexes_dependency_explicit_target_type_target_id_compatibility() -> None:
    workbook = _workbook(
        {
            "05_Dependencies": [
                {
                    "Record_ID": "rec-dep-1",
                    "Dependency_ID": "dep-api-worker",
                    "Source_Service_ID": "svc-api",
                    "Target_Type": "service",
                    "Target_ID": "svc-worker",
                    "Target_Service_ID": "",
                    "Confirmation_Status": "Confirmed",
                },
                {
                    "Record_ID": "rec-dep-2",
                    "Dependency_ID": "dep-api-data",
                    "Source_Service_ID": "svc-api",
                    "Target_Type": "data_asset",
                    "Target_ID": "data-orders",
                    "Confirmation_Status": "Confirmed",
                },
                {
                    "Record_ID": "rec-dep-3",
                    "Dependency_ID": "dep-api-ext",
                    "Source_Service_ID": "svc-api",
                    "Target_Type": "external_service",
                    "Target_ID": "ext-payments",
                    "Confirmation_Status": "Confirmed",
                },
            ],
            "06_Data_Assets": [{"Data_Asset_ID": "data-orders", "Confirmation_Status": "Confirmed"}],
            "12_External_Services": [{"External_ID": "ext-payments", "Confirmation_Status": "Confirmed"}],
        }
    )

    indexes = build_analysis_indexes(workbook, _graph([]))

    assert [row["Dependency_ID"] for row in indexes.dependencies_by_source["svc-api"]] == [
        "dep-api-worker",
        "dep-api-data",
        "dep-api-ext",
    ]
    assert indexes.dependencies_by_target["svc-worker"][0]["Dependency_ID"] == "dep-api-worker"
    assert indexes.dependencies_by_target["data-orders"][0]["Dependency_ID"] == "dep-api-data"
    assert indexes.dependencies_by_target["ext-payments"][0]["Dependency_ID"] == "dep-api-ext"
    assert indexes.data_assets_by_service["svc-api"][0]["Data_Asset_ID"] == "data-orders"
    assert indexes.external_by_service["svc-api"][0]["External_ID"] == "ext-payments"


def test_indexes_dependency_legacy_target_compatibility_and_active_rows_only() -> None:
    workbook = _workbook(
        {
            "05_Dependencies": [
                {
                    "Record_ID": "rec-dep-1",
                    "Dependency_ID": "dep-api-worker",
                    "Source_Service_ID": "svc-api",
                    "Target_Service_ID": "svc-worker",
                    "Target_External_ID": "",
                    "Target_Data_Asset_ID": "",
                    "Confirmation_Status": "Confirmed",
                },
                {
                    "Record_ID": "rec-dep-2",
                    "Dependency_ID": "dep-api-ext",
                    "Source_Service_ID": "svc-api",
                    "Target_External_ID": "ext-payments",
                    "Confirmation_Status": "Confirmed",
                },
                {
                    "Record_ID": "rec-dep-3",
                    "Dependency_ID": "dep-api-data",
                    "Source_Service_ID": "svc-api",
                    "Target_Data_Asset_ID": "data-orders",
                    "Confirmation_Status": "Confirmed",
                },
                {
                    "Record_ID": "rec-dep-rejected",
                    "Dependency_ID": "dep-rejected",
                    "Source_Service_ID": "svc-api",
                    "Target_Service_ID": "svc-admin",
                    "Confirmation_Status": "Rejected",
                },
            ],
            "06_Data_Assets": [{"Data_Asset_ID": "data-orders", "Confirmation_Status": "Confirmed"}],
            "12_External_Services": [{"External_ID": "ext-payments", "Confirmation_Status": "Confirmed"}],
        }
    )

    indexes = build_analysis_indexes(workbook, _graph([]))

    assert "dep-rejected" not in indexes.dependencies
    assert indexes.dependencies_by_target["svc-worker"][0]["Dependency_ID"] == "dep-api-worker"
    assert indexes.dependencies_by_target["ext-payments"][0]["Dependency_ID"] == "dep-api-ext"
    assert indexes.dependencies_by_target["data-orders"][0]["Dependency_ID"] == "dep-api-data"
    assert indexes.data_assets_by_service["svc-api"][0]["Data_Asset_ID"] == "data-orders"
    assert indexes.external_by_service["svc-api"][0]["External_ID"] == "ext-payments"
