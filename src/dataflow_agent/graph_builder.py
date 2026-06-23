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


def _node(row: Row, node_id: str, node_type: str, label: str, sheet: str, **metadata: str) -> GraphNode:
    return GraphNode(
        id=node_id,
        type=node_type,
        label=label or node_id,
        sheet=sheet,
        status=row.get("Confirmation_Status", "Confirmed"),
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
        graph.add_node(_node(row, row["Service_ID"], "service", row.get("Service_Name") or row["Service_ID"], "04_Services", priority=row.get("Service_Priority", ""), protocol=row.get("Protocol", ""), ports=row.get("Listen_Ports", "")))
        for port in split_multi(row.get("Listen_Ports", "")):
            port_id = f"port:{row['Service_ID']}:{safe_id(port)}"
            graph.add_node(_node(row, port_id, "port", f"{row.get('Protocol') or 'port'} {port}", "04_Services", service_id=row["Service_ID"]))


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
            if row.get("Project_ID") in graph.nodes and row.get(node_field) in graph.nodes:
                graph.add_edge(_edge(edge_no, "contains", row["Project_ID"], row[node_field], "", row))
    for row in active_rows(workbook, "02_Networks"):
        for field, node_type in (("NAT_Name", "nat"), ("LB_Name", "lb"), ("PSC_or_Peering_Name", "psc_peering")):
            node_id = f"{node_type}:{safe_id(row.get(field, ''))}" if row.get(field) else ""
            if row.get("Network_ID") in graph.nodes and node_id in graph.nodes:
                graph.add_edge(_edge(edge_no, "contains", row["Network_ID"], node_id, field, row))


def _service_edges(graph: GraphModel, workbook: WorkbookData) -> None:
    edge_no = count(1000)
    for row in active_rows(workbook, "04_Services"):
        if row.get("Running_On_Instance_ID") in graph.nodes:
            graph.add_edge(_edge(edge_no, "runs_on", row["Service_ID"], row["Running_On_Instance_ID"], "", row))
        for port in split_multi(row.get("Listen_Ports", "")):
            port_id = f"port:{row['Service_ID']}:{safe_id(port)}"
            graph.add_edge(_edge(edge_no, "listens_on", row["Service_ID"], port_id, port, row))


def _dependency_edges(graph: GraphModel, workbook: WorkbookData) -> None:
    edge_no = count(2000)
    for row in active_rows(workbook, "05_Dependencies"):
        source = row.get("Source_Service_ID", "")
        label = " ".join(part for part in [row.get("Target_Port_Protocol", ""), row.get("Target_Port", ""), row.get("Target_Path", "")] if part)
        if row.get("Target_Service_ID"):
            graph.add_edge(_edge(edge_no, "calls", source, row["Target_Service_ID"], label, row))
        if row.get("Target_External_ID"):
            graph.add_edge(_edge(edge_no, "calls_external", source, row["Target_External_ID"], label, row))
        if row.get("Target_Data_Asset_ID"):
            edge_type = "writes_to" if row.get("Direction", "").lower() in {"write", "outbound_write"} else "reads_from"
            graph.add_edge(_edge(edge_no, edge_type, source, row["Target_Data_Asset_ID"], label, row))
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
            graph.add_edge(_edge(edge_no, "monitored_by", row["Object_ID"], row["Monitoring_ID"], row.get("Coverage_Status", ""), row))


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
    )

