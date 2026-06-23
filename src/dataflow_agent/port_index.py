from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import WorkbookData
from .normalizer import active_rows
from .util import split_multi, write_json


def build_service_port_index(workbook: WorkbookData, service_id: str) -> dict[str, Any]:
    service = next((row for row in active_rows(workbook, "04_Services") if row.get("Service_ID") == service_id), None)
    if not service:
        raise ValueError(f"Service {service_id} does not exist in workbook.")

    inbound_dependencies = [
        row
        for row in active_rows(workbook, "05_Dependencies")
        if row.get("Target_Service_ID") == service_id or (row.get("Target_Type", "").lower() in {"service", "internal_service"} and row.get("Target_ID") == service_id)
    ]
    outbound_dependencies = [
        row
        for row in active_rows(workbook, "05_Dependencies")
        if row.get("Source_Service_ID") == service_id
    ]
    firewalls = [
        row
        for row in active_rows(workbook, "07_Firewalls")
        if row.get("Related_Service_ID") == service_id
        or row.get("Related_Dependency_ID") in {dep.get("Dependency_ID") for dep in inbound_dependencies + outbound_dependencies}
    ]
    monitoring = [
        row
        for row in active_rows(workbook, "10_Monitoring")
        if row.get("Object_ID") == service_id or row.get("Object_ID") in {dep.get("Dependency_ID") for dep in inbound_dependencies + outbound_dependencies}
    ]

    return {
        "service_id": service_id,
        "service_name": service.get("Service_Name", ""),
        "priority": service.get("Service_Priority", ""),
        "protocol": service.get("Protocol", ""),
        "listen_ports": split_multi(service.get("Listen_Ports", "")),
        "runtime": {
            "runtime_type": service.get("Runtime_Type", ""),
            "runtime_id": service.get("Runtime_ID", ""),
            "namespace": service.get("Runtime_Namespace", ""),
            "cluster": service.get("Runtime_Cluster", ""),
            "region": service.get("Runtime_Region", ""),
        },
        "inbound_dependencies": [_dependency_summary(row) for row in inbound_dependencies],
        "outbound_dependencies": [_dependency_summary(row) for row in outbound_dependencies],
        "firewall_rules": [_firewall_summary(row) for row in firewalls],
        "monitoring": [_monitoring_summary(row) for row in monitoring],
    }


def write_service_port_index(workbook: WorkbookData, service_id: str, output_path: Path) -> dict[str, Any]:
    index = build_service_port_index(workbook, service_id)
    write_json(output_path, index)
    return index


def _dependency_summary(row: dict[str, str]) -> dict[str, str]:
    return {
        "dependency_id": row.get("Dependency_ID", ""),
        "source_service_id": row.get("Source_Service_ID", ""),
        "target_service_id": row.get("Target_Service_ID", ""),
        "target_type": row.get("Target_Type", ""),
        "target_id": row.get("Target_ID", ""),
        "target_external_id": row.get("Target_External_ID", ""),
        "target_data_asset_id": row.get("Target_Data_Asset_ID", ""),
        "target_port": row.get("Target_Port", ""),
        "target_port_protocol": row.get("Target_Port_Protocol", ""),
        "direction": row.get("Direction", ""),
        "interaction_mode": row.get("Interaction_Mode", ""),
        "criticality": row.get("Dependency_Criticality", ""),
    }


def _firewall_summary(row: dict[str, str]) -> dict[str, str]:
    return {
        "firewall_id": row.get("Firewall_ID", ""),
        "name": row.get("Firewall_Name", ""),
        "direction": row.get("Direction", ""),
        "action": row.get("Action", ""),
        "source_allowed": row.get("Source_Allowed", ""),
        "protocol": row.get("Protocol", ""),
        "ports": row.get("Ports", ""),
        "related_service_id": row.get("Related_Service_ID", ""),
        "related_dependency_id": row.get("Related_Dependency_ID", ""),
    }


def _monitoring_summary(row: dict[str, str]) -> dict[str, str]:
    return {
        "monitoring_id": row.get("Monitoring_ID", ""),
        "object_id": row.get("Object_ID", ""),
        "object_type": row.get("Object_Type", ""),
        "monitoring_type": row.get("Monitoring_Type", ""),
        "coverage_status": row.get("Coverage_Status", ""),
        "dashboard_url": row.get("Dashboard_URL", ""),
        "alert_rule": row.get("Alert_Rule", ""),
    }
