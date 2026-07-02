from __future__ import annotations

from dataclasses import dataclass, field

from dataflow_agent.models import GraphEdge, GraphModel, Row, WorkbookData
from dataflow_agent.normalizer import active_rows
from dataflow_agent.util import split_multi


DATAFLOW_EDGE_TYPES = {"calls", "calls_external", "depends_on", "reads_from", "writes_to"}


@dataclass
class AnalysisIndexes:
    services: dict[str, Row] = field(default_factory=dict)
    dependencies: dict[str, Row] = field(default_factory=dict)
    data_assets: dict[str, Row] = field(default_factory=dict)
    external_services: dict[str, Row] = field(default_factory=dict)
    monitoring_by_object: dict[tuple[str, str], list[Row]] = field(default_factory=dict)
    dependencies_by_source: dict[str, list[Row]] = field(default_factory=dict)
    dependencies_by_target: dict[str, list[Row]] = field(default_factory=dict)
    data_assets_by_service: dict[str, list[Row]] = field(default_factory=dict)
    external_by_service: dict[str, list[Row]] = field(default_factory=dict)
    iam_by_service: dict[str, list[Row]] = field(default_factory=dict)
    cicd_by_target_service: dict[str, list[Row]] = field(default_factory=dict)
    firewalls_by_service: dict[str, list[Row]] = field(default_factory=dict)
    firewalls_by_dependency: dict[str, list[Row]] = field(default_factory=dict)
    upstream: dict[str, set[str]] = field(default_factory=dict)
    downstream: dict[str, set[str]] = field(default_factory=dict)
    dataflow_connected_ids: set[str] = field(default_factory=set)


def build_analysis_indexes(workbook: WorkbookData, graph: GraphModel) -> AnalysisIndexes:
    indexes = AnalysisIndexes(
        services=_rows_by_key(active_rows(workbook, "04_Services"), "Service_ID"),
        dependencies=_rows_by_key(active_rows(workbook, "05_Dependencies"), "Dependency_ID"),
        data_assets=_rows_by_key(active_rows(workbook, "06_Data_Assets"), "Data_Asset_ID"),
        external_services=_rows_by_key(active_rows(workbook, "12_External_Services"), "External_ID"),
    )
    _index_dependencies(workbook, indexes)
    _index_data_assets(workbook, indexes)
    _index_external_services(workbook, indexes)
    _index_security_and_operations(workbook, indexes)
    _index_graph_dataflow(graph, indexes)
    _sort_index_lists(indexes)
    return indexes


def _index_dependencies(workbook: WorkbookData, indexes: AnalysisIndexes) -> None:
    for row in active_rows(workbook, "05_Dependencies"):
        source_id = row.get("Source_Service_ID", "")
        if source_id:
            _append(indexes.dependencies_by_source, source_id, row)
        for target_type, target_id in _dependency_targets(row):
            if target_id:
                _append(indexes.dependencies_by_target, target_id, row)
                if target_type == "data_asset" and source_id:
                    asset = indexes.data_assets.get(target_id)
                    if asset:
                        _append(indexes.data_assets_by_service, source_id, asset)
                if target_type == "external_service" and source_id:
                    external = indexes.external_services.get(target_id)
                    if external:
                        _append(indexes.external_by_service, source_id, external)


def _index_data_assets(workbook: WorkbookData, indexes: AnalysisIndexes) -> None:
    for row in active_rows(workbook, "06_Data_Assets"):
        for service_id in split_multi(row.get("Used_By_Service_ID", "")):
            _append(indexes.data_assets_by_service, service_id, row)


def _index_external_services(workbook: WorkbookData, indexes: AnalysisIndexes) -> None:
    for row in active_rows(workbook, "12_External_Services"):
        for service_id in split_multi(row.get("Used_By_Service_ID", "")):
            _append(indexes.external_by_service, service_id, row)


def _index_security_and_operations(workbook: WorkbookData, indexes: AnalysisIndexes) -> None:
    for row in active_rows(workbook, "10_Monitoring"):
        object_type = row.get("Object_Type", "")
        for object_id in split_multi(row.get("Object_ID", "")):
            _append(indexes.monitoring_by_object, (object_type, object_id), row)
    for row in active_rows(workbook, "09_IAM_SA"):
        for service_id in split_multi(row.get("Used_By_Service_ID", "")):
            _append(indexes.iam_by_service, service_id, row)
    for row in active_rows(workbook, "11_CICD"):
        for service_id in split_multi(row.get("Target_Service_ID", "")):
            _append(indexes.cicd_by_target_service, service_id, row)
    for row in active_rows(workbook, "07_Firewalls"):
        for service_id in split_multi(row.get("Related_Service_ID", "")):
            _append(indexes.firewalls_by_service, service_id, row)
        for dependency_id in split_multi(row.get("Related_Dependency_ID", "")):
            _append(indexes.firewalls_by_dependency, dependency_id, row)


def _index_graph_dataflow(graph: GraphModel, indexes: AnalysisIndexes) -> None:
    for edge in _dataflow_edges(graph):
        indexes.downstream.setdefault(edge.source, set()).add(edge.target)
        indexes.upstream.setdefault(edge.target, set()).add(edge.source)
        indexes.dataflow_connected_ids.add(edge.source)
        indexes.dataflow_connected_ids.add(edge.target)


def _dependency_targets(row: Row) -> list[tuple[str, str]]:
    explicit_type = row.get("Target_Type", "")
    explicit_id = row.get("Target_ID", "")
    if explicit_type or explicit_id:
        return [(_canonical_target_type(explicit_type), explicit_id)]

    targets: list[tuple[str, str]] = []
    if row.get("Target_Service_ID"):
        targets.append(("service", row["Target_Service_ID"]))
    if row.get("Target_External_ID"):
        targets.append(("external_service", row["Target_External_ID"]))
    if row.get("Target_Data_Asset_ID"):
        targets.append(("data_asset", row["Target_Data_Asset_ID"]))
    return targets


def _canonical_target_type(target_type: str) -> str:
    normalized = target_type.strip().lower()
    if normalized in {"service", "internal_service"}:
        return "service"
    if normalized in {"external", "external_service"}:
        return "external_service"
    if normalized in {"data_asset", "data", "storage", "database"}:
        return "data_asset"
    return normalized


def _dataflow_edges(graph: GraphModel) -> list[GraphEdge]:
    return [edge for edge in graph.edges if edge.type in DATAFLOW_EDGE_TYPES and edge.source and edge.target]


def _rows_by_key(rows: list[Row], key: str) -> dict[str, Row]:
    return {row[key]: row for row in rows if row.get(key)}


def _append(index: dict[str, list[Row]], key: str, row: Row) -> None:
    rows = index.setdefault(key, [])
    if row not in rows:
        rows.append(row)


def _sort_index_lists(indexes: AnalysisIndexes) -> None:
    for value in indexes.__dict__.values():
        if isinstance(value, dict):
            for rows in value.values():
                if isinstance(rows, list):
                    rows.sort(key=_row_sort_key)


def _row_sort_key(row: Row) -> tuple[str, str, str, str]:
    return (
        row.get("Record_ID", ""),
        row.get("Dependency_ID", ""),
        row.get("Service_ID", ""),
        row.get("Evidence_ID", ""),
    )
