from __future__ import annotations

from itertools import count

from .models import GraphEdge, GraphModel, GraphNode, Row, WorkbookData
from .normalizer import active_rows
from .util import safe_id, split_multi


def build_graph(workbook: WorkbookData) -> GraphModel:
    graph = GraphModel()
    _project_nodes(graph, workbook)
    _network_nodes(graph, workbook)
    _server_nodes(graph, workbook)
    _service_nodes(graph, workbook)
    _runtime_nodes(graph, workbook)
    _data_asset_nodes(graph, workbook)
    _firewall_nodes(graph, workbook)
    _cloud_armor_nodes(graph, workbook)
    _iam_nodes(graph, workbook)
    _monitoring_nodes(graph, workbook)
    _cicd_nodes(graph, workbook)
    _external_nodes(graph, workbook)
    _contains_edges(graph, workbook)
    _service_edges(graph, workbook)
    _dependency_edges(graph, workbook)
    _security_edges(graph, workbook)
    _monitoring_edges(graph, workbook)
    _cicd_edges(graph, workbook)
    return graph


NODE_SEMANTICS = {
    "gcp_project": ("project", "Project", "System"),
    "network": ("network", "Network", "Container"),
    "vpc": ("network", "Network", "Container"),
    "subnet": ("network", "Network", "Container"),
    "nat": ("network", "Network", "Component"),
    "lb": ("network", "Network", "Component"),
    "psc_peering": ("network", "Network", "Component"),
    "entry_point": ("edge", "Entry", "Component"),
    "server": ("runtime", "Runtime", "Container"),
    "runtime": ("runtime", "Runtime", "Container"),
    "service": ("service", "Service", "Container"),
    "port": ("interface", "Interface", "Component"),
    "dependency_ref": ("interface", "Interface", "Component"),
    "data_asset": ("data", "Data", "Container"),
    "external_service": ("external", "External", "ExternalSystem"),
    "firewall_rule": ("security", "Security", "Component"),
    "cloud_armor_policy": ("security", "Security", "Component"),
    "service_account": ("identity", "Identity", "Component"),
    "iam_binding": ("identity", "Identity", "Component"),
    "monitoring_control": ("monitoring", "Monitoring", "Component"),
    "cicd_component": ("delivery", "Delivery", "Component"),
}


def _node(row: Row, node_id: str, node_type: str, label: str, sheet: str, **metadata: str) -> GraphNode:
    layer, group, c4_type = NODE_SEMANTICS.get(node_type, ("other", "Other", "Component"))
    parent_id = metadata.pop("parent_id", "") or row.get("Project_ID", "") or row.get("Network_ID", "")
    return GraphNode(
        id=node_id,
        type=node_type,
        label=label or node_id,
        sheet=sheet,
        status=row.get("Confirmation_Status", "Confirmed"),
        layer=metadata.pop("layer", "") or layer,
        group=metadata.pop("group", "") or group,
        parent_id=parent_id,
        c4_type=metadata.pop("c4_type", "") or c4_type,
        metadata={key: value for key, value in metadata.items() if value},
    )


def _project_nodes(graph: GraphModel, workbook: WorkbookData) -> None:
    for row in active_rows(workbook, "01_Projects"):
        graph.add_node(_node(row, row["Project_ID"], "gcp_project", row.get("Project_Name") or row["Project_ID"], "01_Projects", owner=row.get("Owner", ""), environment=row.get("Environment", "")))


def _network_nodes(graph: GraphModel, workbook: WorkbookData) -> None:
    for row in active_rows(workbook, "02_Networks"):
        network_type = (row.get("Network_Type") or "network").lower().replace(" ", "_")
        graph.add_node(_node(row, row["Network_ID"], network_type, row.get("Subnet_Name") or row.get("VPC_Name") or row["Network_ID"], "02_Networks", vpc=row.get("VPC_Name", ""), cidr=row.get("CIDR", ""), region=row.get("Region", "")))
        for field, node_type in (("NAT_Name", "nat"), ("LB_Name", "lb"), ("PSC_or_Peering_Name", "psc_peering")):
            if row.get(field):
                node_id = f"{node_type}:{safe_id(row[field])}"
                graph.add_node(_node(row, node_id, node_type, row[field], "02_Networks", network_id=row["Network_ID"]))


def _server_nodes(graph: GraphModel, workbook: WorkbookData) -> None:
    for row in active_rows(workbook, "03_Servers"):
        graph.add_node(_node(row, row["Instance_ID"], "server", row.get("Hostname") or row["Instance_ID"], "03_Servers", ip_internal=row.get("IP_Internal", ""), ip_external=row.get("IP_External", ""), role=row.get("Server_Role", "")))


def _service_nodes(graph: GraphModel, workbook: WorkbookData) -> None:
    for row in active_rows(workbook, "04_Services"):
        graph.add_node(
            _node(
                row,
                row["Service_ID"],
                "service",
                row.get("Service_Name") or row["Service_ID"],
                "04_Services",
                priority=row.get("Service_Priority", ""),
                protocol=row.get("Protocol", ""),
                ports=row.get("Listen_Ports", ""),
                runtime_type=row.get("Runtime_Type", ""),
                runtime_id=row.get("Runtime_ID", ""),
            )
        )
        for port in split_multi(row.get("Listen_Ports", "")):
            port_id = f"port:{row['Service_ID']}:{safe_id(port)}"
            graph.add_node(_node(row, port_id, "port", f"{row.get('Protocol') or 'port'} {port}", "04_Services", service_id=row["Service_ID"]))


def _runtime_nodes(graph: GraphModel, workbook: WorkbookData) -> None:
    for row in active_rows(workbook, "04_Services"):
        runtime_id = _runtime_node_id(row)
        runtime_type = row.get("Runtime_Type", "")
        if not runtime_id:
            continue
        label = row.get("Runtime_Name") or row.get("Runtime_ID") or f"{runtime_type or 'Runtime'} for {row.get('Service_ID', '')}"
        graph.add_node(
            _node(
                row,
                runtime_id,
                "runtime",
                label,
                "04_Services",
                runtime_type=runtime_type,
                namespace=row.get("Runtime_Namespace", ""),
                cluster=row.get("Runtime_Cluster", ""),
                region=row.get("Runtime_Region", "") or row.get("Location", ""),
                service_id=row.get("Service_ID", ""),
            )
        )


def _data_asset_nodes(graph: GraphModel, workbook: WorkbookData) -> None:
    for row in active_rows(workbook, "06_Data_Assets"):
        graph.add_node(_node(row, row["Data_Asset_ID"], "data_asset", row.get("Data_Asset_Name") or row["Data_Asset_ID"], "06_Data_Assets", data_asset_type=row.get("Data_Asset_Type", ""), sensitivity=row.get("Sensitivity", "")))


def _firewall_nodes(graph: GraphModel, workbook: WorkbookData) -> None:
    for row in active_rows(workbook, "07_Firewalls"):
        graph.add_node(_node(row, row["Firewall_ID"], "firewall_rule", row.get("Firewall_Name") or row["Firewall_ID"], "07_Firewalls", action=row.get("Action", ""), ports=row.get("Ports", ""), source=row.get("Source_Allowed", "")))


def _cloud_armor_nodes(graph: GraphModel, workbook: WorkbookData) -> None:
    for row in active_rows(workbook, "08_Cloud_Armor"):
        graph.add_node(_node(row, row["Policy_ID"], "cloud_armor_policy", row.get("Policy_Name") or row["Policy_ID"], "08_Cloud_Armor", action=row.get("Rule_Action", ""), entry=row.get("Protected_Entry_ID", "")))


def _iam_nodes(graph: GraphModel, workbook: WorkbookData) -> None:
    for row in active_rows(workbook, "09_IAM_SA"):
        if row.get("Service_Account_ID"):
            graph.add_node(_node(row, row["Service_Account_ID"], "service_account", row.get("Service_Account_Email") or row["Service_Account_ID"], "09_IAM_SA", role=row.get("Role", ""), high_privilege=row.get("Is_High_Privilege", "")))
        graph.add_node(_node(row, row["IAM_Binding_ID"], "iam_binding", row.get("Role") or row["IAM_Binding_ID"], "09_IAM_SA", scope=row.get("Scope", "")))


def _monitoring_nodes(graph: GraphModel, workbook: WorkbookData) -> None:
    for row in active_rows(workbook, "10_Monitoring"):
        graph.add_node(_node(row, row["Monitoring_ID"], "monitoring_control", row.get("Monitoring_Type") or row["Monitoring_ID"], "10_Monitoring", coverage=row.get("Coverage_Status", ""), object_id=row.get("Object_ID", "")))


def _cicd_nodes(graph: GraphModel, workbook: WorkbookData) -> None:
    for row in active_rows(workbook, "11_CICD"):
        graph.add_node(_node(row, row["CICD_ID"], "cicd_component", row.get("Pipeline_Name") or row["CICD_ID"], "11_CICD", system=row.get("System", ""), repo=row.get("Repo", "")))


def _external_nodes(graph: GraphModel, workbook: WorkbookData) -> None:
    for row in active_rows(workbook, "12_External_Services"):
        graph.add_node(_node(row, row["External_ID"], "external_service", row.get("External_Name") or row["External_ID"], "12_External_Services", endpoint=row.get("Endpoint", ""), direction=row.get("Direction", "")))


def _contains_edges(graph: GraphModel, workbook: WorkbookData) -> None:
    edge_no = count(1)
    for sheet, node_field in (("02_Networks", "Network_ID"), ("03_Servers", "Instance_ID"), ("06_Data_Assets", "Data_Asset_ID"), ("07_Firewalls", "Firewall_ID")):
        for row in active_rows(workbook, sheet):
            if row.get("Project_ID") or row.get(node_field):
                graph.add_edge(_edge(edge_no, "contains", row["Project_ID"], row[node_field], "", row))
    for row in active_rows(workbook, "02_Networks"):
        for field, node_type in (("NAT_Name", "nat"), ("LB_Name", "lb"), ("PSC_or_Peering_Name", "psc_peering")):
            node_id = f"{node_type}:{safe_id(row.get(field, ''))}" if row.get(field) else ""
            if row.get("Network_ID") and node_id:
                graph.add_edge(_edge(edge_no, "contains", row["Network_ID"], node_id, field, row))


def _service_edges(graph: GraphModel, workbook: WorkbookData) -> None:
    edge_no = count(1000)
    for row in active_rows(workbook, "04_Services"):
        if row.get("Running_On_Instance_ID"):
            graph.add_edge(_edge(edge_no, "runs_on", row["Service_ID"], row["Running_On_Instance_ID"], "", row))
        runtime_id = _runtime_node_id(row)
        if runtime_id:
            graph.add_edge(_edge(edge_no, "runs_on_runtime", row["Service_ID"], runtime_id, row.get("Runtime_Type", ""), row))
        for port in split_multi(row.get("Listen_Ports", "")):
            port_id = f"port:{row['Service_ID']}:{safe_id(port)}"
            graph.add_edge(_edge(edge_no, "listens_on", row["Service_ID"], port_id, port, row))


def _dependency_edges(graph: GraphModel, workbook: WorkbookData) -> None:
    edge_no = count(2000)
    for row in active_rows(workbook, "05_Dependencies"):
        source = row.get("Source_Service_ID", "")
        label = " ".join(part for part in [row.get("Target_Port_Protocol", ""), row.get("Target_Port", ""), row.get("Target_Path", "")] if part)
        explicit_target = _explicit_dependency_target(row)
        if explicit_target:
            edge_type, target = explicit_target
            graph.add_edge(_edge(edge_no, edge_type, source, target, label, row))
            continue
        for edge_type, target in _legacy_dependency_targets(row):
            graph.add_edge(_edge(edge_no, edge_type, source, target, label, row))
    for row in active_rows(workbook, "06_Data_Assets"):
        for service_id in split_multi(row.get("Used_By_Service_ID", "")):
            graph.add_edge(_edge(edge_no, "reads_from", service_id, row["Data_Asset_ID"], row.get("Access_Type", ""), row))
    for row in active_rows(workbook, "12_External_Services"):
        if row.get("Used_By_Service_ID"):
            graph.add_edge(_edge(edge_no, "calls_external", row["Used_By_Service_ID"], row["External_ID"], row.get("Protocol", ""), row))


def _security_edges(graph: GraphModel, workbook: WorkbookData) -> None:
    edge_no = count(3000)
    for row in active_rows(workbook, "07_Firewalls"):
        if row.get("Related_Dependency_ID"):
            dep_node = f"dependency:{row['Related_Dependency_ID']}"
            if dep_node not in graph.nodes:
                graph.add_node(_node(row, dep_node, "dependency_ref", row["Related_Dependency_ID"], "05_Dependencies"))
            graph.add_edge(_edge(edge_no, "allowed_by", dep_node, row["Firewall_ID"], row.get("Ports", ""), row))
        if row.get("Related_Service_ID"):
            graph.add_edge(_edge(edge_no, "allowed_by", row["Related_Service_ID"], row["Firewall_ID"], row.get("Ports", ""), row))
    for row in active_rows(workbook, "08_Cloud_Armor"):
        entry = row.get("Protected_Entry_ID") or row.get("Backend_Service") or row.get("LB_Name")
        if entry:
            if entry not in graph.nodes:
                graph.add_node(_node(row, entry, "entry_point", entry, "08_Cloud_Armor"))
            graph.add_edge(_edge(edge_no, "protected_by", entry, row["Policy_ID"], row.get("Rule_Action", ""), row))
    for row in active_rows(workbook, "09_IAM_SA"):
        if row.get("Used_By_Service_ID") and row.get("Service_Account_ID"):
            graph.add_edge(_edge(edge_no, "uses_sa", row["Used_By_Service_ID"], row["Service_Account_ID"], row.get("Role", ""), row))
        if row.get("Service_Account_ID") and row.get("IAM_Binding_ID"):
            graph.add_edge(_edge(edge_no, "has_binding", row["Service_Account_ID"], row["IAM_Binding_ID"], row.get("Role", ""), row))


def _monitoring_edges(graph: GraphModel, workbook: WorkbookData) -> None:
    edge_no = count(4000)
    for row in active_rows(workbook, "10_Monitoring"):
        if row.get("Object_ID"):
            graph.add_edge(_edge(edge_no, "monitored_by", _monitoring_source_id(graph, row), row["Monitoring_ID"], row.get("Coverage_Status", ""), row))


def _cicd_edges(graph: GraphModel, workbook: WorkbookData) -> None:
    edge_no = count(5000)
    for row in active_rows(workbook, "11_CICD"):
        if row.get("Target_Service_ID"):
            graph.add_edge(_edge(edge_no, "deployed_by", row["CICD_ID"], row["Target_Service_ID"], row.get("Deployment_Entry", ""), row))
        if row.get("Target_Instance_ID"):
            graph.add_edge(_edge(edge_no, "deployed_by", row["CICD_ID"], row["Target_Instance_ID"], row.get("Deployment_Entry", ""), row))


def _edge(counter: count, edge_type: str, source: str, target: str, label: str, row: Row) -> GraphEdge:
    return GraphEdge(
        id=f"edge-{next(counter)}",
        type=edge_type,
        source=source,
        target=target,
        label=label,
        status=row.get("Confirmation_Status", "Confirmed"),
        evidence_id=row.get("Evidence_ID", ""),
        metadata=_edge_metadata(row),
    )


def _edge_metadata(row: Row) -> dict[str, object]:
    runtime_context = {
        "runtime_type": row.get("Runtime_Type", ""),
        "runtime_id": row.get("Runtime_ID", ""),
        "namespace": row.get("Runtime_Namespace", ""),
        "cluster": row.get("Runtime_Cluster", ""),
        "region": row.get("Runtime_Region", "") or row.get("Location", ""),
    }
    metadata: dict[str, object] = {
        "source_sheet": _row_sheet(row),
        "record_id": row.get("Record_ID", ""),
        "confirmation_status": row.get("Confirmation_Status", ""),
        "source_type": row.get("Source_Type", ""),
        "collected_by": row.get("Collected_By", ""),
        "environment": row.get("Environment", ""),
        "evidence_id": row.get("Evidence_ID", "") or row.get("Related_Evidence_ID", ""),
        "dependency_id": row.get("Dependency_ID", ""),
        "criticality": row.get("Dependency_Criticality", ""),
        "interaction_mode": row.get("Interaction_Mode", ""),
        "target_type": row.get("Target_Type", ""),
        "target_id": row.get("Target_ID", ""),
        "runtime_context": {key: value for key, value in runtime_context.items() if value},
        "risk_tags": _risk_tags(row),
    }
    return {key: value for key, value in metadata.items() if value not in ("", {}, [])}


def _row_sheet(row: Row) -> str:
    if row.get("Dependency_ID"):
        return "05_Dependencies"
    if row.get("Service_ID"):
        return "04_Services"
    if row.get("Firewall_ID"):
        return "07_Firewalls"
    if row.get("Data_Asset_ID"):
        return "06_Data_Assets"
    if row.get("Policy_ID"):
        return "08_Cloud_Armor"
    if row.get("IAM_Binding_ID") or row.get("Service_Account_ID"):
        return "09_IAM_SA"
    if row.get("Monitoring_ID"):
        return "10_Monitoring"
    if row.get("CICD_ID"):
        return "11_CICD"
    if row.get("External_ID"):
        return "12_External_Services"
    return ""


def _risk_tags(row: Row) -> list[str]:
    tags: list[str] = []
    if row.get("Confirmation_Status") == "Pending_Confirmation":
        tags.append("pending_confirmation")
    if row.get("Confirmation_Status") == "Accepted_Exception":
        tags.append("accepted_exception")
    if row.get("Dependency_Criticality") in {"P0", "P1"}:
        tags.append("critical_dependency")
    if row.get("Service_Priority") in {"P0", "P1"}:
        tags.append("critical_service")
    if row.get("Sensitivity", "").lower() in {"restricted", "high", "critical"}:
        tags.append("sensitive_data")
    return tags


def _runtime_node_id(row: Row) -> str:
    if not (row.get("Runtime_Type") or row.get("Runtime_ID")):
        return ""
    return row.get("Runtime_ID") or f"runtime:{safe_id(row.get('Service_ID', ''))}"


def _monitoring_source_id(graph: GraphModel, row: Row) -> str:
    object_id = row.get("Object_ID", "")
    if row.get("Object_Type", "").lower() == "dependency":
        dependency_node = f"dependency:{object_id}"
        if dependency_node in graph.nodes:
            return dependency_node
    return object_id


def _explicit_dependency_target(row: Row) -> tuple[str, str] | None:
    target_type = row.get("Target_Type", "").lower()
    target = row.get("Target_ID", "")
    if not target_type and not target:
        return None
    edge_type = _edge_type_for_target(target_type, row)
    return edge_type, target


def _legacy_dependency_targets(row: Row) -> list[tuple[str, str]]:
    targets: list[tuple[str, str]] = []
    if row.get("Target_Service_ID"):
        targets.append(("calls", row["Target_Service_ID"]))
    if row.get("Target_External_ID"):
        targets.append(("calls_external", row["Target_External_ID"]))
    if row.get("Target_Data_Asset_ID"):
        edge_type = "writes_to" if _is_write(row) else "reads_from"
        targets.append((edge_type, row["Target_Data_Asset_ID"]))
    return targets


def _edge_type_for_target(target_type: str, row: Row) -> str:
    if target_type in {"service", "internal_service"}:
        return "calls"
    if target_type in {"external", "external_service"}:
        return "calls_external"
    if target_type in {"data_asset", "data", "storage", "database"}:
        return "writes_to" if _is_write(row) else "reads_from"
    if target_type in {"runtime", "kubernetes", "cloudrun", "cloud_run"}:
        return "uses_runtime"
    if target_type in {"firewall", "firewall_rule", "security_control"}:
        return "allowed_by"
    if target_type in {"monitoring", "monitoring_control"}:
        return "monitored_by"
    return "depends_on"


def _is_write(row: Row) -> bool:
    text = f"{row.get('Direction', '')} {row.get('Interaction_Mode', '')}".lower()
    return any(token in text for token in ("write", "outbound_write", "produce", "publish"))
