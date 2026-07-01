from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, sin
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import landscape, letter
from reportlab.pdfgen import canvas

from .editable_exporter import write_editable_outputs
from .models import Finding, GraphEdge, GraphModel, GraphNode
from .util import safe_id, xml_escape


@dataclass(frozen=True)
class View:
    filename: str
    title: str
    node_types: set[str]
    edge_types: set[str]
    theme: str = "auto"


@dataclass(frozen=True)
class NodeStyle:
    fill: str
    stroke: str
    accent: str
    group: str


VIEWS = [
    View("00_overview", "Dataflow Project Data Flow Overview", {"gcp_project", "lb", "entry_point", "service", "server", "runtime", "data_asset", "external_service", "firewall_rule", "cloud_armor_policy", "monitoring_control"}, {"contains", "runs_on", "runs_on_runtime", "uses_runtime", "calls", "calls_external", "reads_from", "writes_to", "depends_on", "allowed_by", "protected_by", "monitored_by"}),
    View("01_network_layer", "Network Layer", {"gcp_project", "network", "vpc", "subnet", "nat", "lb", "psc_peering", "firewall_rule", "cloud_armor_policy", "entry_point"}, {"contains", "allowed_by", "protected_by"}),
    View("02_compute_service_layer", "Compute And Service Layer", {"server", "runtime", "service", "port"}, {"runs_on", "runs_on_runtime", "uses_runtime", "listens_on"}),
    View("03_service_dependency_layer", "Service Dependency Layer", {"service", "runtime", "external_service", "data_asset", "dependency_ref", "firewall_rule"}, {"calls", "calls_external", "reads_from", "writes_to", "depends_on", "uses_runtime", "allowed_by"}),
    View("04_data_storage_layer", "Data And Storage Layer", {"service", "data_asset"}, {"reads_from", "writes_to"}),
    View("05_security_monitoring_layer", "Security And Monitoring Layer", {"service", "server", "firewall_rule", "cloud_armor_policy", "service_account", "iam_binding", "monitoring_control", "entry_point"}, {"allowed_by", "protected_by", "uses_sa", "has_binding", "monitored_by"}),
    View("06_cicd_delivery_layer", "CI/CD Delivery Layer", {"cicd_component", "service", "server", "runtime"}, {"deployed_by", "runs_on", "runs_on_runtime"}),
]

NODE_WIDTH = 236
NODE_HEIGHT = 86
LEFT_MARGIN = 72
RIGHT_MARGIN = 72
HEADER_HEIGHT = 126
COLUMN_GAP = 96
ROW_GAP = 34
BOTTOM_MARGIN = 76
MIN_WIDTH = 1180
MIN_HEIGHT = 680

TYPE_ORDER = {
    "gcp_project": 0,
    "network": 1,
    "vpc": 1,
    "subnet": 1,
    "nat": 1,
    "lb": 1,
    "psc_peering": 1,
    "entry_point": 1,
    "cicd_component": 1,
    "server": 2,
    "runtime": 2,
    "service": 3,
    "port": 4,
    "dependency_ref": 4,
    "data_asset": 5,
    "external_service": 5,
    "service_account": 5,
    "iam_binding": 6,
    "firewall_rule": 6,
    "cloud_armor_policy": 6,
    "monitoring_control": 7,
}

TYPE_STYLES = {
    "gcp_project": NodeStyle("#F8FAFC", "#CBD5E1", "#64748B", "Project"),
    "network": NodeStyle("#E0F2FE", "#7DD3FC", "#0284C7", "Network"),
    "vpc": NodeStyle("#E0F2FE", "#7DD3FC", "#0284C7", "Network"),
    "subnet": NodeStyle("#E0F2FE", "#7DD3FC", "#0284C7", "Network"),
    "nat": NodeStyle("#E0F2FE", "#7DD3FC", "#0284C7", "Network"),
    "lb": NodeStyle("#E0F2FE", "#7DD3FC", "#0284C7", "Network"),
    "psc_peering": NodeStyle("#E0F2FE", "#7DD3FC", "#0284C7", "Network"),
    "entry_point": NodeStyle("#F1F5F9", "#CBD5E1", "#475569", "Entry"),
    "server": NodeStyle("#FEF3C7", "#FBBF24", "#D97706", "Runtime"),
    "runtime": NodeStyle("#FEF3C7", "#FBBF24", "#D97706", "Runtime"),
    "service": NodeStyle("#DBEAFE", "#60A5FA", "#2563EB", "Service"),
    "port": NodeStyle("#EDE9FE", "#A78BFA", "#7C3AED", "Interface"),
    "dependency_ref": NodeStyle("#EDE9FE", "#A78BFA", "#7C3AED", "Interface"),
    "data_asset": NodeStyle("#F3E8FF", "#C084FC", "#9333EA", "Data"),
    "external_service": NodeStyle("#F8FAFC", "#CBD5E1", "#64748B", "External"),
    "firewall_rule": NodeStyle("#FEE2E2", "#FCA5A5", "#DC2626", "Security"),
    "cloud_armor_policy": NodeStyle("#FEE2E2", "#FCA5A5", "#DC2626", "Security"),
    "service_account": NodeStyle("#F5F3FF", "#A78BFA", "#6D28D9", "Identity"),
    "iam_binding": NodeStyle("#F5F3FF", "#A78BFA", "#6D28D9", "Identity"),
    "monitoring_control": NodeStyle("#DCFCE7", "#86EFAC", "#16A34A", "Monitoring"),
    "cicd_component": NodeStyle("#FFEDD5", "#FDBA74", "#EA580C", "Delivery"),
}

CONTROL_EDGES = {"allowed_by", "protected_by", "uses_sa", "has_binding", "monitored_by", "deployed_by"}
DATAFLOW_EDGES = {"calls", "calls_external", "reads_from", "writes_to", "depends_on"}
SERVICE_DEP_NODE_WIDTH = 310
SERVICE_DEP_NODE_HEIGHT = 92
SERVICE_DEP_LEDGER_WIDTH = 560
LAYER_ORDER = {
    "project": 0,
    "network": 1,
    "edge": 1,
    "delivery": 1,
    "runtime": 2,
    "service": 3,
    "interface": 4,
    "data": 5,
    "external": 5,
    "identity": 6,
    "security": 6,
    "monitoring": 7,
    "other": 8,
}
DETAIL_KEYS = (
    "environment",
    "role",
    "protocol",
    "ports",
    "data_asset_type",
    "sensitivity",
    "action",
    "coverage",
    "scope",
    "system",
    "endpoint",
    "cidr",
    "region",
    "owner",
    "priority",
)


def render_diagrams(graph: GraphModel, diagrams_dir: Path, findings: list[Finding] | None = None) -> list[Path]:
    diagrams_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for view in VIEWS:
        nodes, edges = _select_view(graph, view)
        if view.filename in {"00_overview", "03_service_dependency_layer", "05_security_monitoring_layer"}:
            from .diagram_overview import render_overview_outputs

            outputs.extend(render_overview_outputs(graph, diagrams_dir, view, findings=findings))
            continue
        else:
            positions = _layout(nodes)
            outputs.append(_write_svg(diagrams_dir / f"{view.filename}.svg", view, nodes, edges, positions))
            outputs.append(_write_png(diagrams_dir / f"{view.filename}.png", view, nodes, edges, positions))
            outputs.append(_write_pdf(diagrams_dir / f"{view.filename}.pdf", view, nodes, edges, positions))
        outputs.append(_write_mermaid(diagrams_dir / f"{view.filename}.mmd", view, nodes, edges))
        outputs.extend(
            write_editable_outputs(
                diagrams_dir / view.filename,
                view.title,
                nodes,
                edges,
                positions,
                node_width=SERVICE_DEP_NODE_WIDTH if view.filename in {"00_overview", "03_service_dependency_layer"} else NODE_WIDTH,
                node_height=SERVICE_DEP_NODE_HEIGHT if view.filename in {"00_overview", "03_service_dependency_layer"} else NODE_HEIGHT,
            )
        )
    return outputs


def render_service_drilldown(
    graph: GraphModel,
    service_id: str,
    diagrams_dir: Path,
    depth: int = 1,
    direction: str = "both",
    theme: str = "auto",
    risk_focus: bool = False,
) -> list[Path]:
    if service_id not in graph.nodes or graph.nodes[service_id].type != "service":
        raise ValueError(f"Service {service_id} does not exist in graph.")
    diagrams_dir.mkdir(parents=True, exist_ok=True)
    nodes, edges = _select_service_drilldown(graph, service_id, max(1, depth), direction, risk_focus)
    positions = _layout(nodes)
    base = f"service_drilldown_{safe_id(service_id)}"
    detail = f"depth={max(1, depth)} | direction={direction}"
    if risk_focus:
        detail += " | risk focus"
    view = View(base, f"Service Drilldown: {service_id} ({detail})", {node.type for node in nodes}, {edge.type for edge in edges}, theme)
    return [
        _write_svg(diagrams_dir / f"{base}.svg", view, nodes, edges, positions),
        _write_png(diagrams_dir / f"{base}.png", view, nodes, edges, positions),
        _write_pdf(diagrams_dir / f"{base}.pdf", view, nodes, edges, positions),
        _write_mermaid(diagrams_dir / f"{base}.mmd", view, nodes, edges),
        *write_editable_outputs(
            diagrams_dir / base,
            view.title,
            nodes,
            edges,
            positions,
            node_width=NODE_WIDTH,
            node_height=NODE_HEIGHT,
        ),
    ]


def _select_view(graph: GraphModel, view: View) -> tuple[list[GraphNode], list[GraphEdge]]:
    included_edges = [edge for edge in graph.edges if edge.type in view.edge_types]
    node_ids = {edge.source for edge in included_edges}.union(edge.target for edge in included_edges)
    nodes = [node for node in graph.nodes.values() if node.type in view.node_types or node.id in node_ids]
    node_ids = {node.id for node in nodes}
    edges = [edge for edge in included_edges if edge.source in node_ids and edge.target in node_ids]
    if view.filename == "00_overview":
        nodes, edges = _denoise_overview(nodes, edges)
    if not nodes:
        nodes = list(graph.nodes.values())[:12]
    return nodes, edges


def _denoise_overview(nodes: list[GraphNode], edges: list[GraphEdge]) -> tuple[list[GraphNode], list[GraphEdge]]:
    node_by_id = {node.id: node for node in nodes}
    keep: set[str] = set()
    for node in nodes:
        priority = node.metadata.get("priority", "")
        text = f"{node.id} {node.label} {node.metadata.get('role', '')}".lower()
        if node.type in {"gcp_project", "lb", "entry_point", "data_asset", "external_service", "cloud_armor_policy", "monitoring_control"}:
            keep.add(node.id)
        elif node.type == "service" and (priority in {"P0", "P1"} or any(token in text for token in ("rpc", "sequencer", "database", "nginx", "da "))):
            keep.add(node.id)
    changed = True
    while changed:
        changed = False
        for edge in edges:
            source = node_by_id.get(edge.source)
            target = node_by_id.get(edge.target)
            if not source or not target:
                continue
            if edge.type in {"runs_on", "runs_on_runtime"} and edge.source in keep and edge.target not in keep:
                keep.add(edge.target)
                changed = True
            if edge.type in {"calls", "calls_external", "reads_from", "writes_to", "depends_on", "uses_runtime"} and (edge.source in keep or edge.target in keep):
                if source.type == "service" and source.metadata.get("priority", "") in {"P0", "P1"}:
                    keep.add(edge.source)
                if target.type in {"service", "runtime", "data_asset", "external_service"}:
                    keep.add(edge.target)
            if edge.type in {"allowed_by", "protected_by", "monitored_by"} and edge.source in keep:
                keep.add(edge.target)
    filtered_nodes = [node for node in nodes if node.id in keep]
    filtered_ids = {node.id for node in filtered_nodes}
    filtered_edges = [edge for edge in edges if edge.source in filtered_ids and edge.target in filtered_ids]
    return filtered_nodes or nodes, filtered_edges or edges


def _select_service_dependency_main_flow(graph: GraphModel) -> tuple[list[GraphNode], list[GraphEdge]]:
    best: dict[tuple[str, str, str], GraphEdge] = {}
    for edge in graph.edges:
        if edge.type not in DATAFLOW_EDGES:
            continue
        key = (edge.type, edge.source, edge.target)
        current = best.get(key)
        if current is None or _edge_record_id(edge) < _edge_record_id(current):
            best[key] = edge
    edges = sorted(best.values(), key=lambda edge: (_edge_record_id(edge), edge.source, edge.target, edge.id))
    node_ids = {edge.source for edge in edges}.union(edge.target for edge in edges)
    nodes = [node for node in graph.nodes.values() if node.id in node_ids]
    return nodes, edges


def _select_service_drilldown(graph: GraphModel, service_id: str, depth: int, direction: str, risk_focus: bool) -> tuple[list[GraphNode], list[GraphEdge]]:
    node_ids = {service_id}
    selected_edges: list[GraphEdge] = []
    frontier = {service_id}
    direction = direction if direction in {"upstream", "downstream", "both"} else "both"
    for _level in range(depth):
        next_frontier: set[str] = set()
        for edge in graph.edges:
            include = False
            if direction in {"downstream", "both"} and edge.source in frontier:
                include = True
            if direction in {"upstream", "both"} and edge.target in frontier:
                include = True
            if include:
                selected_edges.append(edge)
                before = len(node_ids)
                node_ids.update({edge.source, edge.target})
                if len(node_ids) != before:
                    next_frontier.update({edge.source, edge.target} - frontier)
        frontier = next_frontier - node_ids.intersection(frontier)
        if not frontier:
            break
    changed = True
    while changed:
        changed = False
        for edge in graph.edges:
            if edge.type in {"has_binding", "allowed_by", "monitored_by", "runs_on_runtime", "uses_runtime"} and (edge.source in node_ids or edge.target in node_ids):
                before = len(node_ids)
                selected_edges.append(edge)
                node_ids.update({edge.source, edge.target})
                changed = changed or len(node_ids) != before
    deduped_edges: list[GraphEdge] = []
    seen_edges: set[str] = set()
    for edge in selected_edges:
        if edge.id not in seen_edges:
            deduped_edges.append(edge)
            seen_edges.add(edge.id)
    nodes = [node for node in graph.nodes.values() if node.id in node_ids]
    if risk_focus:
        risk_node_ids = {service_id}
        risk_edges = [edge for edge in deduped_edges if _edge_risk_level(edge) != "normal" or edge.source == service_id or edge.target == service_id]
        for edge in risk_edges:
            risk_node_ids.update({edge.source, edge.target})
        nodes = [node for node in nodes if node.id in risk_node_ids or _node_risk_level(node) != "normal"]
        deduped_edges = [edge for edge in deduped_edges if edge.source in {node.id for node in nodes} and edge.target in {node.id for node in nodes}]
    return nodes, deduped_edges


def _layout(nodes: list[GraphNode]) -> dict[str, tuple[int, int]]:
    columns: dict[int, list[GraphNode]] = {}
    for node in sorted(nodes, key=lambda item: (_node_order(item), item.group.lower(), item.label.lower(), item.id)):
        columns.setdefault(_node_order(node), []).append(node)

    positions: dict[str, tuple[int, int]] = {}
    x_step = NODE_WIDTH + COLUMN_GAP
    y_step = NODE_HEIGHT + ROW_GAP
    for col_idx, col in enumerate(sorted(columns)):
        for row_idx, node in enumerate(columns[col]):
            positions[node.id] = (LEFT_MARGIN + col_idx * x_step, HEADER_HEIGHT + 32 + row_idx * y_step)
    return positions


def _node_order(node: GraphNode) -> int:
    if node.layer:
        return LAYER_ORDER.get(node.layer, TYPE_ORDER.get(node.type, 9))
    return TYPE_ORDER.get(node.type, 9)


def _size(positions: dict[str, tuple[int, int]]) -> tuple[int, int]:
    if not positions:
        return MIN_WIDTH, MIN_HEIGHT
    width = max(x for x, _ in positions.values()) + NODE_WIDTH + RIGHT_MARGIN
    height = max(y for _, y in positions.values()) + NODE_HEIGHT + BOTTOM_MARGIN
    return max(width, MIN_WIDTH), max(height, MIN_HEIGHT)


def _service_dependency_layout(nodes: list[GraphNode], edges: list[GraphEdge]) -> dict[str, tuple[int, int]]:
    node_by_id = {node.id: node for node in nodes}
    incoming: dict[str, list[GraphEdge]] = {node.id: [] for node in nodes}
    outgoing: dict[str, list[GraphEdge]] = {node.id: [] for node in nodes}
    for edge in edges:
        incoming.setdefault(edge.target, []).append(edge)
        outgoing.setdefault(edge.source, []).append(edge)
    levels: dict[str, int] = {}
    frontier = sorted([node.id for node in nodes if not incoming.get(node.id)], key=lambda item: _service_dep_node_sort(node_by_id[item]))
    if not frontier and nodes:
        frontier = [sorted(nodes, key=_service_dep_node_sort)[0].id]
    for node_id in frontier:
        levels[node_id] = 0
    queue = list(frontier)
    while queue:
        node_id = queue.pop(0)
        for edge in sorted(outgoing.get(node_id, []), key=lambda item: (_edge_record_id(item), item.target)):
            next_level = levels[node_id] + 1
            if levels.get(edge.target, -1) < next_level:
                levels[edge.target] = next_level
                queue.append(edge.target)
    for node in nodes:
        levels.setdefault(node.id, _node_order(node))

    columns: dict[int, list[GraphNode]] = {}
    for node in nodes:
        columns.setdefault(levels[node.id], []).append(node)
    for level, items in columns.items():
        items.sort(key=lambda node: _service_dep_layout_sort(node, incoming, outgoing))
    positions: dict[str, tuple[int, int]] = {}
    x_step = SERVICE_DEP_NODE_WIDTH + 170
    y_step = SERVICE_DEP_NODE_HEIGHT + 96
    for col_idx, level in enumerate(sorted(columns)):
        col = columns[level]
        for row_idx, node in enumerate(col):
            positions[node.id] = (LEFT_MARGIN + col_idx * x_step, HEADER_HEIGHT + 92 + row_idx * y_step)
    return positions


def _service_dep_node_sort(node: GraphNode) -> tuple[int, str, str]:
    return _node_order(node), node.label.lower(), node.id


def _service_dep_layout_sort(node: GraphNode, incoming: dict[str, list[GraphEdge]], outgoing: dict[str, list[GraphEdge]]) -> tuple[str, int, str, str]:
    related = incoming.get(node.id) or outgoing.get(node.id) or []
    first_record = min((_edge_record_id(edge) or edge.id for edge in related), default="")
    return first_record, _node_order(node), node.label.lower(), node.id


def _service_dependency_size(positions: dict[str, tuple[int, int]], edges: list[GraphEdge]) -> tuple[int, int, int]:
    if not positions:
        return MIN_WIDTH + SERVICE_DEP_LEDGER_WIDTH, MIN_HEIGHT, MIN_WIDTH
    graph_width = max(x for x, _ in positions.values()) + SERVICE_DEP_NODE_WIDTH + 72
    ledger_x = graph_width + 40
    width = ledger_x + SERVICE_DEP_LEDGER_WIDTH + 50
    graph_height = max(y for _, y in positions.values()) + SERVICE_DEP_NODE_HEIGHT + 100
    ledger_height = HEADER_HEIGHT + 132 + len(edges) * 74
    height = max(MIN_HEIGHT, graph_height, ledger_height)
    return width, height, ledger_x


def _write_service_dependency_svg(path: Path, view: View, nodes: list[GraphNode], edges: list[GraphEdge], positions: dict[str, tuple[int, int]]) -> Path:
    width, height, ledger_x = _service_dependency_size(positions, edges)
    routes = _service_dependency_routes(edges, positions)
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{xml_escape(view.title)} main dataflow with edge ledger">',
        "<defs>",
        '<marker id="svcArrow" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto"><path d="M0,0 L10,5 L0,10 Z" fill="#475569"/></marker>',
        '<filter id="svcShadow"><feDropShadow dx="3" dy="5" stdDeviation="0" flood-color="#CBD5E1" flood-opacity="0.9"/></filter>',
        "</defs>",
        '<rect width="100%" height="100%" fill="#F5F7FB"/>',
        f'<text x="60" y="48" font-family="Arial, Helvetica, sans-serif" font-size="30" font-weight="700" fill="#111827">{xml_escape(view.title)}</text>',
        '<text x="60" y="82" font-family="Arial, Helvetica, sans-serif" font-size="14" fill="#5B6573">Main dataflow view with numbered edges and source-record ledger</text>',
        f'<text x="60" y="104" font-family="Arial, Helvetica, sans-serif" font-size="12" fill="#5B6573">{len(nodes)} nodes | {len(edges)} real dataflow edges | no inferred relationships</text>',
        f'<rect x="40" y="{HEADER_HEIGHT}" width="{ledger_x - 58}" height="{height - HEADER_HEIGHT - 42}" rx="18" fill="#FFFFFF" stroke="#CBD5E1"/>',
        f'<rect x="{ledger_x}" y="{HEADER_HEIGHT}" width="{SERVICE_DEP_LEDGER_WIDTH}" height="{height - HEADER_HEIGHT - 42}" rx="18" fill="#FFFFFF" stroke="#CBD5E1"/>',
    ]
    _append_service_dependency_svg_edges(lines, edges, routes)
    for node in nodes:
        x, y = positions.get(node.id, (LEFT_MARGIN, HEADER_HEIGHT + 92))
        _append_service_dependency_svg_node(lines, node, x, y)
    _append_service_dependency_svg_badges(lines, edges, routes)
    _append_service_dependency_svg_ledger(lines, edges, ledger_x)
    lines.append("</svg>")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _append_service_dependency_svg_edges(lines: list[str], edges: list[GraphEdge], routes: dict[str, list[tuple[float, float]]]) -> None:
    for idx, edge in enumerate(edges, 1):
        points = routes.get(edge.id)
        if not points:
            continue
        color = _service_dependency_edge_color(edge)
        point_text = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
        lines.append(f'<polyline points="{point_text}" fill="none" stroke="{color}" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round" marker-end="url(#svcArrow)" data-edge-id="{xml_escape(edge.id)}" data-edge-number="{idx}" data-edge-type="{xml_escape(edge.type)}" data-source="{xml_escape(edge.source)}" data-target="{xml_escape(edge.target)}"><title>{xml_escape(_service_dependency_edge_title(edge))}</title></polyline>')


def _append_service_dependency_svg_badges(lines: list[str], edges: list[GraphEdge], routes: dict[str, list[tuple[float, float]]]) -> None:
    for idx, edge in enumerate(edges, 1):
        points = routes.get(edge.id)
        if not points:
            continue
        color = _service_dependency_edge_color(edge)
        cx, cy = _service_dependency_badge_position(points, idx)
        lines.append(f'<g data-edge-badge-id="{xml_escape(edge.id)}"><circle cx="{cx:.1f}" cy="{cy:.1f}" r="16" fill="#FFFFFF" stroke="#FFFFFF" stroke-width="5"/>')
        lines.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="13" fill="{color}" stroke="#FFFFFF" stroke-width="2"/>')
        lines.append(f'<text x="{cx:.1f}" y="{cy + 4:.1f}" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="12" font-weight="700" fill="#FFFFFF">{idx}</text></g>')


def _append_service_dependency_svg_node(lines: list[str], node: GraphNode, x: int, y: int) -> None:
    fill, stroke = _service_dependency_node_colors(node)
    risk_level = _node_risk_level(node)
    lines.append(f'<g filter="url(#svcShadow)" data-node-id="{xml_escape(node.id)}" role="img" aria-label="{xml_escape(_node_accessible_label(node))}" data-risk-level="{risk_level}"><title>{xml_escape(node.id)} | {xml_escape(node.type)}</title>')
    lines.append(f'<rect x="{x}" y="{y}" width="{SERVICE_DEP_NODE_WIDTH}" height="{SERVICE_DEP_NODE_HEIGHT}" rx="10" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
    lines.append(f'<rect x="{x}" y="{y}" width="8" height="{SERVICE_DEP_NODE_HEIGHT}" rx="4" fill="{stroke}"/>')
    lines.append(f'<text x="{x + 20}" y="{y + 34}" font-family="Arial, Helvetica, sans-serif" font-size="17" font-weight="700" fill="#111827">{xml_escape(_clip(node.label, 31))}</text>')
    lines.append(f'<text x="{x + 20}" y="{y + 62}" font-family="Arial, Helvetica, sans-serif" font-size="12" fill="#5B6573">{xml_escape(node.type)}</text>')
    badge = _status_badge(_status_kind(node.status))
    if badge:
        badge_text, badge_bg, badge_fg = badge
        badge_width = max(42, len(badge_text) * 7 + 18)
        lines.append(f'<rect x="{x + SERVICE_DEP_NODE_WIDTH - badge_width - 14}" y="{y + 12}" width="{badge_width}" height="20" rx="10" fill="{badge_bg}" stroke="{stroke}" stroke-width="0.8"/>')
        lines.append(f'<text x="{x + SERVICE_DEP_NODE_WIDTH - badge_width / 2 - 14:.1f}" y="{y + 26}" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="10" font-weight="700" fill="{badge_fg}">{badge_text}</text>')
    lines.append("</g>")


def _append_service_dependency_svg_ledger(lines: list[str], edges: list[GraphEdge], x: int) -> None:
    lines.append(f'<text x="{x + 30}" y="{HEADER_HEIGHT + 42}" font-family="Arial, Helvetica, sans-serif" font-size="18" font-weight="700" fill="#111827">Edge ledger</text>')
    lines.append(f'<text x="{x + 30}" y="{HEADER_HEIGHT + 68}" font-family="Arial, Helvetica, sans-serif" font-size="12" fill="#5B6573">Line numbers map to source workbook records.</text>')
    y = HEADER_HEIGHT + 108
    for idx, edge in enumerate(edges, 1):
        color = _service_dependency_edge_color(edge)
        label = _service_dependency_ledger_label(edge)
        lines.append(f'<g data-ledger-edge-id="{xml_escape(edge.id)}">')
        lines.append(f'<circle cx="{x + 42}" cy="{y}" r="14" fill="{color}"/>')
        lines.append(f'<text x="{x + 42}" y="{y + 4}" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="12" font-weight="700" fill="#FFFFFF">{idx}</text>')
        lines.append(f'<text x="{x + 68}" y="{y - 4}" font-family="Arial, Helvetica, sans-serif" font-size="14" font-weight="700" fill="#111827">{xml_escape(_clip(label, 58))}</text>')
        lines.append(f'<text x="{x + 68}" y="{y + 18}" font-family="Arial, Helvetica, sans-serif" font-size="11" fill="#5B6573">{xml_escape(_clip(_service_dependency_flow_label(edge), 72))}</text>')
        lines.append("</g>")
        y += 74


def _write_service_dependency_png(path: Path, view: View, nodes: list[GraphNode], edges: list[GraphEdge], positions: dict[str, tuple[int, int]]) -> Path:
    width, height, ledger_x = _service_dependency_size(positions, edges)
    routes = _service_dependency_routes(edges, positions)
    image = Image.new("RGB", (width, height), "#F5F7FB")
    draw = ImageDraw.Draw(image)
    title_font = _font(30, bold=True)
    note_font = _font(14)
    small_font = _font(12)
    node_font = _font(17, bold=True)
    node_meta_font = _font(12)
    ledger_title_font = _font(18, bold=True)
    ledger_font = _font(14, bold=True)
    draw.text((60, 25), view.title, fill="#111827", font=title_font)
    draw.text((60, 68), "Main dataflow view with numbered edges and source-record ledger", fill="#5B6573", font=note_font)
    draw.text((60, 94), f"{len(nodes)} nodes | {len(edges)} real dataflow edges | no inferred relationships", fill="#5B6573", font=small_font)
    draw.rounded_rectangle((40, HEADER_HEIGHT, ledger_x - 18, height - 42), radius=18, fill="#FFFFFF", outline="#CBD5E1")
    draw.rounded_rectangle((ledger_x, HEADER_HEIGHT, ledger_x + SERVICE_DEP_LEDGER_WIDTH, height - 42), radius=18, fill="#FFFFFF", outline="#CBD5E1")
    for idx, edge in enumerate(edges, 1):
        points = routes.get(edge.id)
        if not points:
            continue
        color = _service_dependency_edge_color(edge)
        _draw_polyline(draw, points, color, width=4, dashed=False)
        _draw_arrowhead(draw, points[-2], points[-1], color)
    for node in nodes:
        x, y = positions.get(node.id, (LEFT_MARGIN, HEADER_HEIGHT + 92))
        fill, stroke = _service_dependency_node_colors(node)
        draw.rounded_rectangle((x + 3, y + 5, x + SERVICE_DEP_NODE_WIDTH + 3, y + SERVICE_DEP_NODE_HEIGHT + 5), radius=10, fill="#CBD5E1")
        draw.rounded_rectangle((x, y, x + SERVICE_DEP_NODE_WIDTH, y + SERVICE_DEP_NODE_HEIGHT), radius=10, fill=fill, outline=stroke, width=2)
        draw.rounded_rectangle((x, y, x + 8, y + SERVICE_DEP_NODE_HEIGHT), radius=4, fill=stroke)
        draw.text((x + 20, y + 20), _clip(node.label, 31), fill="#111827", font=node_font)
        draw.text((x + 20, y + 54), node.type, fill="#5B6573", font=node_meta_font)
        badge = _status_badge(_status_kind(node.status))
        if badge:
            badge_text, badge_bg, badge_fg = badge
            badge_width = max(42, len(badge_text) * 7 + 18)
            box = (x + SERVICE_DEP_NODE_WIDTH - badge_width - 14, y + 12, x + SERVICE_DEP_NODE_WIDTH - 14, y + 32)
            draw.rounded_rectangle(box, radius=10, fill=badge_bg, outline=stroke)
            draw.text((box[0] + badge_width / 2 - _text_width(draw, badge_text, small_font) / 2, y + 15), badge_text, fill=badge_fg, font=small_font)
    for idx, edge in enumerate(edges, 1):
        points = routes.get(edge.id)
        if not points:
            continue
        color = _service_dependency_edge_color(edge)
        cx, cy = _service_dependency_badge_position(points, idx)
        draw.ellipse((cx - 16, cy - 16, cx + 16, cy + 16), fill="#FFFFFF", outline="#FFFFFF", width=5)
        draw.ellipse((cx - 13, cy - 13, cx + 13, cy + 13), fill=color, outline="#FFFFFF", width=2)
        number = str(idx)
        draw.text((cx - _text_width(draw, number, small_font) / 2, cy - 7), number, fill="#FFFFFF", font=small_font)
    draw.text((ledger_x + 30, HEADER_HEIGHT + 25), "Edge ledger", fill="#111827", font=ledger_title_font)
    draw.text((ledger_x + 30, HEADER_HEIGHT + 56), "Line numbers map to source workbook records.", fill="#5B6573", font=small_font)
    y = HEADER_HEIGHT + 94
    for idx, edge in enumerate(edges, 1):
        color = _service_dependency_edge_color(edge)
        draw.ellipse((ledger_x + 28, y - 14, ledger_x + 56, y + 14), fill=color)
        number = str(idx)
        draw.text((ledger_x + 42 - _text_width(draw, number, small_font) / 2, y - 7), number, fill="#FFFFFF", font=small_font)
        draw.text((ledger_x + 68, y - 12), _clip(_service_dependency_ledger_label(edge), 58), fill="#111827", font=ledger_font)
        draw.text((ledger_x + 68, y + 15), _clip(_service_dependency_flow_label(edge), 72), fill="#5B6573", font=_font(11))
        y += 74
    image.save(path)
    return path


def _write_service_dependency_pdf(path: Path, view: View, nodes: list[GraphNode], edges: list[GraphEdge], positions: dict[str, tuple[int, int]]) -> Path:
    png_path = path.with_suffix(".pdf.png")
    _write_service_dependency_png(png_path, view, nodes, edges, positions)
    image = Image.open(png_path)
    width, height = image.size
    c = canvas.Canvas(str(path), pagesize=(width, height))
    c.drawImage(str(png_path), 0, 0, width=width, height=height)
    c.save()
    png_path.unlink(missing_ok=True)
    return path


def _service_dependency_routes(edges: list[GraphEdge], positions: dict[str, tuple[int, int]]) -> dict[str, list[tuple[float, float]]]:
    outgoing: dict[str, list[GraphEdge]] = {}
    incoming: dict[str, list[GraphEdge]] = {}
    for edge in edges:
        if edge.source not in positions or edge.target not in positions:
            continue
        outgoing.setdefault(edge.source, []).append(edge)
        incoming.setdefault(edge.target, []).append(edge)
    for grouped in (outgoing, incoming):
        for node_edges in grouped.values():
            node_edges.sort(key=lambda item: (_edge_record_id(item), item.target, item.source, item.id))

    outgoing_port = _service_dependency_ports(outgoing, SERVICE_DEP_NODE_HEIGHT)
    incoming_port = _service_dependency_ports(incoming, SERVICE_DEP_NODE_HEIGHT)
    routes: dict[str, list[tuple[float, float]]] = {}
    for index, edge in enumerate(edges, 1):
        if edge.source not in positions or edge.target not in positions:
            continue
        source = positions[edge.source]
        target = positions[edge.target]
        sx = source[0] + SERVICE_DEP_NODE_WIDTH
        sy = source[1] + outgoing_port.get(edge.id, SERVICE_DEP_NODE_HEIGHT / 2)
        tx = target[0]
        ty = target[1] + incoming_port.get(edge.id, SERVICE_DEP_NODE_HEIGHT / 2)
        if sx <= tx:
            distance = tx - sx
            if abs(sy - ty) < 10:
                routes[edge.id] = [(sx, sy), (tx, ty)]
                continue
            gutter_base = sx + min(max(44, distance * 0.22), 104)
            lane = ((index - 1) % 5) * 12
            mid_x = min(tx - 34, gutter_base + lane)
            routes[edge.id] = [(sx, sy), (mid_x, sy), (mid_x, ty), (tx, ty)]
            continue
        gutter = max(sx, tx + SERVICE_DEP_NODE_WIDTH) + 72 + (index % 4) * 22
        routes[edge.id] = [(sx, sy), (gutter, sy), (gutter, ty), (tx, ty)]
    return routes


def _service_dependency_ports(grouped_edges: dict[str, list[GraphEdge]], node_height: int) -> dict[str, float]:
    ports: dict[str, float] = {}
    for node_edges in grouped_edges.values():
        count = len(node_edges)
        if count == 1:
            ports[node_edges[0].id] = node_height / 2
            continue
        top = 24.0
        bottom = node_height - 24.0
        step = (bottom - top) / max(1, count - 1)
        for idx, edge in enumerate(node_edges):
            ports[edge.id] = top + idx * step
    return ports


def _service_dependency_badge_position(points: list[tuple[float, float]], index: int) -> tuple[float, float]:
    if len(points) < 2:
        return points[0] if points else (0.0, 0.0)
    segments = list(zip(points, points[1:]))
    horizontal = [
        pair
        for pair in segments
        if abs(pair[1][1] - pair[0][1]) <= 1 and abs(pair[1][0] - pair[0][0]) >= 42
    ]
    if horizontal:
        start, end = max(horizontal, key=lambda pair: abs(pair[1][0] - pair[0][0]))
    else:
        start, end = max(segments, key=lambda pair: (pair[1][0] - pair[0][0]) ** 2 + (pair[1][1] - pair[0][1]) ** 2)
    x = (start[0] + end[0]) / 2
    y = (start[1] + end[1]) / 2
    offset = ((index % 3) - 1) * 20
    if abs(end[0] - start[0]) < abs(end[1] - start[1]):
        x += offset
    else:
        y += offset * 0.45
    return x, y


def _service_dependency_node_colors(node: GraphNode) -> tuple[str, str]:
    if node.type == "service":
        return "#DBEAFE", "#2563EB"
    if node.type == "data_asset":
        return "#F3E8FF", "#7C3AED"
    if node.type == "external_service":
        return "#F8FAFC", "#64748B"
    return "#FFFFFF", "#64748B"


def _service_dependency_edge_color(edge: GraphEdge) -> str:
    if edge.type in {"reads_from", "writes_to"}:
        return "#7C3AED"
    if edge.type == "calls_external":
        return "#64748B"
    if edge.type == "depends_on":
        return "#D97706"
    return "#2563EB"


def _edge_record_id(edge: GraphEdge) -> str:
    return str(edge.metadata.get("record_id", "")) if isinstance(edge.metadata, dict) else ""


def _service_dependency_ledger_label(edge: GraphEdge) -> str:
    return f"{_edge_record_id(edge) or edge.id} | {edge.type.replace('_', ' ')} | {edge.label or ''}"


def _service_dependency_flow_label(edge: GraphEdge) -> str:
    return f"{edge.source} -> {edge.target}"


def _service_dependency_edge_title(edge: GraphEdge) -> str:
    return f"{_service_dependency_ledger_label(edge)} | {_service_dependency_flow_label(edge)}"


def _security_relationship_rows(nodes: list[GraphNode], edges: list[GraphEdge]) -> tuple[dict[str, GraphNode], list[GraphEdge]]:
    node_by_id = {node.id: node for node in nodes}
    rows = [
        edge
        for edge in edges
        if edge.source in node_by_id and edge.target in node_by_id
    ]
    rows.sort(key=lambda edge: (_security_edge_order(edge), _edge_record_id(edge), edge.source, edge.target, edge.id))
    return node_by_id, rows


def _security_edge_order(edge: GraphEdge) -> int:
    return {
        "protected_by": 0,
        "allowed_by": 1,
        "uses_sa": 2,
        "has_binding": 3,
        "monitored_by": 4,
    }.get(edge.type, 9)


def _security_relationship_size(rows: list[GraphEdge]) -> tuple[int, int]:
    row_height = 112
    height = HEADER_HEIGHT + 92 + max(1, len(rows)) * row_height + 72
    return 1880, max(MIN_HEIGHT, height)


def _write_security_relationship_svg(path: Path, view: View, nodes: list[GraphNode], edges: list[GraphEdge]) -> Path:
    node_by_id, rows = _security_relationship_rows(nodes, edges)
    width, height = _security_relationship_size(rows)
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{xml_escape(view.title)} relationship ledger">',
        "<defs>",
        '<marker id="securityArrow" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto"><path d="M0,0 L10,5 L0,10 Z" fill="#94A3B8"/></marker>',
        "</defs>",
        '<rect width="100%" height="100%" fill="#F5F7FB"/>',
        f'<text x="60" y="48" font-family="Arial, Helvetica, sans-serif" font-size="30" font-weight="700" fill="#111827">{xml_escape(view.title)}</text>',
        '<text x="60" y="82" font-family="Arial, Helvetica, sans-serif" font-size="14" fill="#5B6573">One row per real security / monitoring graph edge. No crossing lines, no inferred controls.</text>',
        f'<text x="60" y="104" font-family="Arial, Helvetica, sans-serif" font-size="12" fill="#5B6573">{len(node_by_id)} nodes | {len(rows)} control relationships | source workbook trace included</text>',
        f'<rect x="40" y="{HEADER_HEIGHT}" width="{width - 80}" height="{height - HEADER_HEIGHT - 44}" rx="18" fill="#FFFFFF" stroke="#CBD5E1"/>',
        f'<text x="84" y="{HEADER_HEIGHT + 42}" font-family="Arial, Helvetica, sans-serif" font-size="15" font-weight="700" fill="#334155">Source</text>',
        f'<text x="548" y="{HEADER_HEIGHT + 42}" font-family="Arial, Helvetica, sans-serif" font-size="15" font-weight="700" fill="#334155">Relationship</text>',
        f'<text x="1080" y="{HEADER_HEIGHT + 42}" font-family="Arial, Helvetica, sans-serif" font-size="15" font-weight="700" fill="#334155">Target control / monitoring</text>',
        f'<text x="1500" y="{HEADER_HEIGHT + 42}" font-family="Arial, Helvetica, sans-serif" font-size="15" font-weight="700" fill="#334155">Source record</text>',
    ]
    if not rows:
        lines.append(f'<text x="84" y="{HEADER_HEIGHT + 96}" font-family="Arial, Helvetica, sans-serif" font-size="14" fill="#64748B">No security or monitoring relationships were found in this view.</text>')
    for idx, edge in enumerate(rows, 1):
        source = node_by_id[edge.source]
        target = node_by_id[edge.target]
        y = HEADER_HEIGHT + 70 + (idx - 1) * 112
        fill = "#F8FAFC" if idx % 2 else "#FFFFFF"
        lines.append(f'<g data-security-row="{idx}" data-edge-id="{xml_escape(edge.id)}" data-edge-number="{idx}" data-edge-type="{xml_escape(edge.type)}" data-source="{xml_escape(edge.source)}" data-target="{xml_escape(edge.target)}" role="img" aria-label="{xml_escape(_edge_accessible_label(edge))}">')
        lines.append(f'<rect x="64" y="{y}" width="{width - 128}" height="88" rx="12" fill="{fill}" stroke="#E2E8F0"/>')
        _append_security_svg_node_chip(lines, source, 84, y + 14, 370, "source")
        color = _security_relationship_color(edge)
        lines.append(f'<line x1="474" y1="{y + 44}" x2="1038" y2="{y + 44}" stroke="{color}" stroke-width="3" marker-end="url(#securityArrow)"/>')
        lines.append(f'<circle cx="528" cy="{y + 44}" r="15" fill="#FFFFFF" stroke="#FFFFFF" stroke-width="5"/>')
        lines.append(f'<circle cx="528" cy="{y + 44}" r="13" fill="{color}" stroke="#FFFFFF" stroke-width="2"/>')
        lines.append(f'<text x="528" y="{y + 48}" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="11" font-weight="700" fill="#FFFFFF">{idx}</text>')
        lines.append(f'<text x="560" y="{y + 34}" font-family="Arial, Helvetica, sans-serif" font-size="14" font-weight="700" fill="#111827">{xml_escape(edge.type.replace("_", " "))}</text>')
        lines.append(f'<text x="560" y="{y + 58}" font-family="Arial, Helvetica, sans-serif" font-size="12" fill="#64748B">{xml_escape(_clip(edge.label or _edge_label(edge) or "-", 62))}</text>')
        _append_security_svg_node_chip(lines, target, 1080, y + 14, 360, "target")
        lines.append(f'<text x="1500" y="{y + 34}" font-family="Arial, Helvetica, sans-serif" font-size="13" font-weight="700" fill="#111827">{xml_escape(_clip(_edge_record_id(edge) or edge.id, 34))}</text>')
        lines.append(f'<text x="1500" y="{y + 58}" font-family="Arial, Helvetica, sans-serif" font-size="11" fill="#64748B">{xml_escape(_clip(edge.metadata.get("source_sheet", "") if isinstance(edge.metadata, dict) else "", 36))}</text>')
        lines.append("</g>")
    lines.append("</svg>")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _append_security_svg_node_chip(lines: list[str], node: GraphNode, x: int, y: int, width: int, role: str) -> None:
    style = _node_style(node, dark=False)
    status = _status_badge(_status_kind(node.status))
    lines.append(f'<g data-{role}-node-id="{xml_escape(node.id)}">')
    lines.append(f'<rect x="{x}" y="{y}" width="{width}" height="60" rx="10" fill="{style.fill}" stroke="{style.stroke}" stroke-width="1.5"/>')
    lines.append(f'<rect x="{x}" y="{y}" width="7" height="60" rx="3.5" fill="{style.accent}"/>')
    lines.append(f'<text x="{x + 18}" y="{y + 24}" font-family="Arial, Helvetica, sans-serif" font-size="13" font-weight="700" fill="#111827">{xml_escape(_clip(node.label, 38))}</text>')
    lines.append(f'<text x="{x + 18}" y="{y + 46}" font-family="Arial, Helvetica, sans-serif" font-size="11" fill="#64748B">{xml_escape(node.type)}</text>')
    if status:
        badge_text, badge_bg, badge_fg = status
        lines.append(f'<rect x="{x + width - 72}" y="{y + 12}" width="54" height="20" rx="10" fill="{badge_bg}" stroke="{style.stroke}" stroke-width="0.6"/>')
        lines.append(f'<text x="{x + width - 45}" y="{y + 26}" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="9" font-weight="700" fill="{badge_fg}">{badge_text}</text>')
    lines.append("</g>")


def _write_security_relationship_png(path: Path, view: View, nodes: list[GraphNode], edges: list[GraphEdge]) -> Path:
    node_by_id, rows = _security_relationship_rows(nodes, edges)
    width, height = _security_relationship_size(rows)
    image = Image.new("RGB", (width, height), "#F5F7FB")
    draw = ImageDraw.Draw(image)
    title_font = _font(30, bold=True)
    note_font = _font(14)
    small_font = _font(12)
    row_font = _font(13, bold=True)
    draw.text((60, 25), view.title, fill="#111827", font=title_font)
    draw.text((60, 68), "One row per real security / monitoring graph edge. No crossing lines, no inferred controls.", fill="#5B6573", font=note_font)
    draw.text((60, 94), f"{len(node_by_id)} nodes | {len(rows)} control relationships | source workbook trace included", fill="#5B6573", font=small_font)
    draw.rounded_rectangle((40, HEADER_HEIGHT, width - 40, height - 44), radius=18, fill="#FFFFFF", outline="#CBD5E1")
    draw.text((84, HEADER_HEIGHT + 27), "Source", fill="#334155", font=row_font)
    draw.text((548, HEADER_HEIGHT + 27), "Relationship", fill="#334155", font=row_font)
    draw.text((1080, HEADER_HEIGHT + 27), "Target control / monitoring", fill="#334155", font=row_font)
    draw.text((1500, HEADER_HEIGHT + 27), "Source record", fill="#334155", font=row_font)
    for idx, edge in enumerate(rows, 1):
        source = node_by_id[edge.source]
        target = node_by_id[edge.target]
        y = HEADER_HEIGHT + 70 + (idx - 1) * 112
        fill = "#F8FAFC" if idx % 2 else "#FFFFFF"
        draw.rounded_rectangle((64, y, width - 64, y + 88), radius=12, fill=fill, outline="#E2E8F0")
        _draw_security_png_node_chip(draw, source, 84, y + 14, 370)
        color = _security_relationship_color(edge)
        draw.line((474, y + 44, 1038, y + 44), fill=color, width=3)
        _draw_arrowhead(draw, (1008, y + 44), (1038, y + 44), color)
        draw.ellipse((512, y + 28, 544, y + 60), fill="#FFFFFF", outline="#FFFFFF", width=5)
        draw.ellipse((515, y + 31, 541, y + 57), fill=color, outline="#FFFFFF", width=2)
        number = str(idx)
        draw.text((528 - _text_width(draw, number, small_font) / 2, y + 36), number, fill="#FFFFFF", font=small_font)
        draw.text((560, y + 20), edge.type.replace("_", " "), fill="#111827", font=row_font)
        draw.text((560, y + 45), _clip(edge.label or _edge_label(edge) or "-", 62), fill="#64748B", font=small_font)
        _draw_security_png_node_chip(draw, target, 1080, y + 14, 360)
        draw.text((1500, y + 20), _clip(_edge_record_id(edge) or edge.id, 34), fill="#111827", font=row_font)
        sheet = edge.metadata.get("source_sheet", "") if isinstance(edge.metadata, dict) else ""
        draw.text((1500, y + 45), _clip(sheet, 36), fill="#64748B", font=_font(11))
    image.save(path)
    return path


def _draw_security_png_node_chip(draw: ImageDraw.ImageDraw, node: GraphNode, x: int, y: int, width: int) -> None:
    style = _node_style(node, dark=False)
    draw.rounded_rectangle((x, y, x + width, y + 60), radius=10, fill=style.fill, outline=style.stroke, width=2)
    draw.rounded_rectangle((x, y, x + 7, y + 60), radius=4, fill=style.accent)
    draw.text((x + 18, y + 12), _clip(node.label, 38), fill="#111827", font=_font(13, bold=True))
    draw.text((x + 18, y + 38), node.type, fill="#64748B", font=_font(11))
    badge = _status_badge(_status_kind(node.status))
    if badge:
        badge_text, badge_bg, badge_fg = badge
        box = (x + width - 72, y + 12, x + width - 18, y + 32)
        draw.rounded_rectangle(box, radius=10, fill=badge_bg, outline=style.stroke)
        draw.text((box[0] + 27 - _text_width(draw, badge_text, _font(9, bold=True)) / 2, y + 16), badge_text, fill=badge_fg, font=_font(9, bold=True))


def _write_security_relationship_pdf(path: Path, view: View, nodes: list[GraphNode], edges: list[GraphEdge]) -> Path:
    png_path = path.with_suffix(".pdf.png")
    _write_security_relationship_png(png_path, view, nodes, edges)
    image = Image.open(png_path)
    width, height = image.size
    c = canvas.Canvas(str(path), pagesize=(width, height))
    c.drawImage(str(png_path), 0, 0, width=width, height=height)
    c.save()
    png_path.unlink(missing_ok=True)
    return path


def _security_relationship_color(edge: GraphEdge) -> str:
    if edge.type == "monitored_by":
        return "#16A34A"
    if edge.type in {"uses_sa", "has_binding"}:
        return "#7C3AED"
    if edge.type == "protected_by":
        return "#DC2626"
    if edge.type == "allowed_by":
        return "#EA580C"
    return "#64748B"


def _write_svg(path: Path, view: View, nodes: list[GraphNode], edges: list[GraphEdge], positions: dict[str, tuple[int, int]]) -> Path:
    width, height = _size(positions)
    dark = _is_security_view(view)
    palette = _palette(dark)
    marker_fill = palette["edge"]
    title_note = "Security Review Focus | controls, identity, monitoring" if dark else "Structurizr/C4-style architecture view | generated from workbook graph"
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<defs>",
        f'<filter id="cardShadow" x="-18%" y="-18%" width="136%" height="148%"><feDropShadow dx="0" dy="8" stdDeviation="7" flood-color="{palette["shadow"]}" flood-opacity="{palette["shadow_opacity"]}"/></filter>',
        f'<marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="4.5" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L9,4.5 L0,9 Z" fill="{marker_fill}"/></marker>',
        "</defs>",
        f'<rect width="100%" height="100%" fill="{palette["bg"]}"/>',
        f'<rect x="0" y="0" width="{width}" height="{HEADER_HEIGHT}" fill="{palette["header"]}" stroke="{palette["border"]}" stroke-width="1"/>',
        f'<rect x="40" y="34" width="7" height="54" rx="3.5" fill="{palette["accent"]}"/>',
        f'<text x="64" y="48" font-family="Arial, Helvetica, sans-serif" font-size="24" font-weight="700" fill="{palette["text"]}">{xml_escape(view.title)}</text>',
        f'<text x="64" y="76" font-family="Arial, Helvetica, sans-serif" font-size="13" fill="{palette["muted"]}">{xml_escape(title_note)}</text>',
        f'<text x="64" y="98" font-family="Arial, Helvetica, sans-serif" font-size="11" fill="{palette["muted"]}">{len(nodes)} nodes | {len(edges)} relationships | deterministic layout</text>',
        f'<rect x="{LEFT_MARGIN - 24}" y="{HEADER_HEIGHT + 14}" width="{width - LEFT_MARGIN - RIGHT_MARGIN + 48}" height="{height - HEADER_HEIGHT - 44}" rx="18" fill="{palette["panel"]}" stroke="{palette["border"]}" stroke-width="1"/>',
    ]
    _append_svg_legend(lines, width, nodes, dark, palette)

    for edge in edges:
        if edge.source not in positions or edge.target not in positions:
            continue
        dashed = _edge_is_control(edge)
        edge_color = _edge_color(edge, dark, palette)
        points = _edge_curve_points(positions[edge.source], positions[edge.target])
        path_data = _svg_path(points)
        dash = ' stroke-dasharray="8 7"' if dashed else ""
        width_attr = "1.8" if dashed else "2.2"
        edge_title = _edge_accessible_label(edge)
        risk_level = _edge_risk_level(edge)
        lines.append(f'<g role="img" aria-label="{xml_escape(edge_title)}" data-risk-level="{risk_level}">')
        lines.append(f'<title>{xml_escape(edge_title)}</title>')
        lines.append(f'<path d="{path_data}" fill="none" stroke="{edge_color}" stroke-width="{width_attr}" marker-end="url(#arrow)" opacity="{palette["edge_opacity"]}"{dash}/>')
        label = _edge_label(edge)
        if label:
            lx, ly = _edge_label_position(points)
            label_width = max(54, min(190, len(label) * 6 + 22))
            lines.append(f'<rect x="{lx - label_width / 2:.1f}" y="{ly - 12:.1f}" width="{label_width}" height="20" rx="10" fill="{palette["edge_label_bg"]}" stroke="{palette["border"]}" stroke-width="0.6"/>')
            lines.append(f'<text x="{lx:.1f}" y="{ly + 3:.1f}" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="10" font-weight="600" fill="{palette["edge_label_text"]}">{xml_escape(label)}</text>')
        lines.append("</g>")

    for node in nodes:
        x, y = positions.get(node.id, (LEFT_MARGIN, HEADER_HEIGHT + 32))
        _append_svg_node(lines, node, x, y, dark, palette)

    lines.append("</svg>")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _write_png(path: Path, view: View, nodes: list[GraphNode], edges: list[GraphEdge], positions: dict[str, tuple[int, int]]) -> Path:
    width, height = _size(positions)
    dark = _is_security_view(view)
    palette = _palette(dark)
    image = Image.new("RGB", (width, height), palette["bg"])
    draw = ImageDraw.Draw(image)
    title_font = _font(26, bold=True)
    note_font = _font(13)
    small_font = _font(11)
    label_font = _font(10, bold=True)
    node_title_font = _font(13, bold=True)
    node_meta_font = _font(10)

    draw.rectangle((0, 0, width, HEADER_HEIGHT), fill=palette["header"], outline=palette["border"])
    draw.rounded_rectangle((40, 34, 47, 88), radius=4, fill=palette["accent"])
    draw.text((64, 26), view.title, fill=palette["text"], font=title_font)
    title_note = "Security Review Focus | controls, identity, monitoring" if dark else "Structurizr/C4-style architecture view | generated from workbook graph"
    draw.text((64, 63), title_note, fill=palette["muted"], font=note_font)
    draw.text((64, 91), f"{len(nodes)} nodes | {len(edges)} relationships | deterministic layout", fill=palette["muted"], font=small_font)
    draw.rounded_rectangle((LEFT_MARGIN - 24, HEADER_HEIGHT + 14, width - RIGHT_MARGIN + 24, height - 30), radius=18, fill=palette["panel"], outline=palette["border"])
    _draw_png_legend(draw, width, nodes, dark, palette, small_font)

    for edge in edges:
        if edge.source not in positions or edge.target not in positions:
            continue
        points = _sampled_edge_points(positions[edge.source], positions[edge.target])
        dashed = _edge_is_control(edge)
        edge_color = _edge_color(edge, dark, palette)
        _draw_polyline(draw, points, edge_color, width=3 if not dashed else 2, dashed=dashed)
        _draw_arrowhead(draw, points[-2], points[-1], edge_color)
        label = _edge_label(edge)
        if label:
            lx, ly = _edge_label_position(_edge_curve_points(positions[edge.source], positions[edge.target]))
            label_width = max(58, min(190, _text_width(draw, label, label_font) + 22))
            draw.rounded_rectangle((lx - label_width / 2, ly - 12, lx + label_width / 2, ly + 9), radius=10, fill=palette["edge_label_bg"], outline=palette["border"])
            draw.text((lx - _text_width(draw, label, label_font) / 2, ly - 8), label, fill=palette["edge_label_text"], font=label_font)

    for node in nodes:
        x, y = positions.get(node.id, (LEFT_MARGIN, HEADER_HEIGHT + 32))
        _draw_png_node(draw, node, x, y, dark, palette, node_title_font, node_meta_font, small_font)

    image.save(path)
    return path


def _write_pdf(path: Path, view: View, nodes: list[GraphNode], edges: list[GraphEdge], positions: dict[str, tuple[int, int]]) -> Path:
    width, height = _size(positions)
    page_size = (max(width, landscape(letter)[0]), max(height, landscape(letter)[1]))
    page_width, page_height = page_size
    dark = _is_security_view(view)
    palette = _palette(dark)
    c = canvas.Canvas(str(path), pagesize=page_size)

    _pdf_fill(c, palette["bg"])
    c.rect(0, 0, page_width, page_height, fill=1, stroke=0)
    _pdf_fill(c, palette["header"])
    _pdf_stroke(c, palette["border"])
    c.rect(0, page_height - HEADER_HEIGHT, page_width, HEADER_HEIGHT, fill=1, stroke=1)
    _pdf_fill(c, palette["accent"])
    c.roundRect(40, page_height - 88, 7, 54, 3.5, fill=1, stroke=0)
    _pdf_fill(c, palette["text"])
    c.setFont("Helvetica-Bold", 22)
    c.drawString(64, page_height - 50, _clip(view.title, 74))
    _pdf_fill(c, palette["muted"])
    c.setFont("Helvetica", 10)
    title_note = "Security Review Focus | controls, identity, monitoring" if dark else "Structurizr/C4-style architecture view | generated from workbook graph"
    c.drawString(64, page_height - 76, title_note)
    c.drawString(64, page_height - 98, f"{len(nodes)} nodes | {len(edges)} relationships | deterministic layout")

    _pdf_fill(c, palette["panel"])
    _pdf_stroke(c, palette["border"])
    c.roundRect(LEFT_MARGIN - 24, 30, page_width - LEFT_MARGIN - RIGHT_MARGIN + 48, page_height - HEADER_HEIGHT - 44, 18, fill=1, stroke=1)

    for edge in edges:
        if edge.source not in positions or edge.target not in positions:
            continue
        p0, _p1, _p2, p3 = _edge_curve_points(positions[edge.source], positions[edge.target])
        dashed = _edge_is_control(edge)
        edge_color = _edge_color(edge, dark, palette)
        _pdf_stroke(c, edge_color)
        c.setLineWidth(1.4 if dashed else 1.8)
        if dashed:
            c.setDash(7, 5)
        c.line(p0[0], page_height - p0[1], p3[0], page_height - p3[1])
        c.setDash()
        _draw_pdf_arrowhead(c, p0, p3, page_height, edge_color)
        label = _edge_label(edge)
        if label:
            lx, ly = (p0[0] + p3[0]) / 2, (p0[1] + p3[1]) / 2 - 4
            label_width = max(54, min(180, len(label) * 5 + 22))
            _pdf_fill(c, palette["edge_label_bg"])
            _pdf_stroke(c, palette["border"])
            c.roundRect(lx - label_width / 2, page_height - ly - 10, label_width, 18, 9, fill=1, stroke=1)
            _pdf_fill(c, palette["edge_label_text"])
            c.setFont("Helvetica-Bold", 7)
            c.drawCentredString(lx, page_height - ly - 3, _clip(label, 28))

    for node in nodes:
        x, y = positions.get(node.id, (LEFT_MARGIN, HEADER_HEIGHT + 32))
        _draw_pdf_node(c, node, x, y, page_height, dark, palette)

    c.save()
    return path


def _write_mermaid(path: Path, view: View, nodes: list[GraphNode], edges: list[GraphEdge]) -> Path:
    lines = ["flowchart LR", f"  %% {view.title}"]
    for node in nodes:
        status = _status_kind(node.status)
        status_text = f"\\n{node.status}" if status != "confirmed" else ""
        class_suffix = f":::{status}" if status != "confirmed" else ""
        lines.append(f"  {_mmd_id(node.id)}[\"{node.label} ({node.type}){status_text}\"]{class_suffix}")
    node_ids = {node.id for node in nodes}
    for edge in edges:
        if edge.source in node_ids and edge.target in node_ids:
            edge_label = _edge_label(edge)
            label = f"|{edge.type}: {edge_label}|" if edge_label else f"|{edge.type}|"
            lines.append(f"  {_mmd_id(edge.source)} -->{label} {_mmd_id(edge.target)}")
    lines.extend(
        [
            "  classDef auto stroke-dasharray: 6 4,stroke:#6366f1;",
            "  classDef pending stroke-dasharray: 6 4,stroke:#f59e0b,fill:#fff7ed;",
            "  classDef exception stroke:#a855f7,fill:#faf5ff;",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _append_svg_node(lines: list[str], node: GraphNode, x: int, y: int, dark: bool, palette: dict[str, str]) -> None:
    status = _status_kind(node.status)
    style = _status_node_style(_node_style(node, dark), status, dark)
    text_color = palette["text"]
    subtext = palette["muted"]
    dash = ' stroke-dasharray="6 4"' if status in {"auto", "pending"} else ""
    node_title = _node_accessible_label(node)
    risk_level = _node_risk_level(node)
    lines.append(f'<g filter="url(#cardShadow)" role="img" aria-label="{xml_escape(node_title)}" data-risk-level="{risk_level}">')
    lines.append(f'<title>{xml_escape(node_title)}</title>')
    lines.append(f'<rect x="{x}" y="{y}" width="{NODE_WIDTH}" height="{NODE_HEIGHT}" rx="12" fill="{style.fill}" stroke="{style.stroke}" stroke-width="1.3"{dash}/>')
    lines.append(f'<rect x="{x}" y="{y}" width="8" height="{NODE_HEIGHT}" rx="4" fill="{style.accent}"/>')
    type_label = _display_type(node.type)
    lines.append(f'<text x="{x + 18}" y="{y + 22}" font-family="Arial, Helvetica, sans-serif" font-size="10" font-weight="700" fill="{style.accent}">{xml_escape(type_label)}</text>')
    for idx, line in enumerate(_wrap_label(node.label, 27, 2)):
        lines.append(f'<text x="{x + 18}" y="{y + 43 + idx * 15}" font-family="Arial, Helvetica, sans-serif" font-size="13" font-weight="700" fill="{text_color}">{xml_escape(line)}</text>')
    detail = _node_detail(node)
    if detail:
        lines.append(f'<text x="{x + 18}" y="{y + 76}" font-family="Arial, Helvetica, sans-serif" font-size="10" fill="{subtext}">{xml_escape(_clip(detail, 31))}</text>')
    badge = _status_badge(status)
    if badge:
        badge_text, badge_bg, badge_fg = badge
        badge_width = max(38, len(badge_text) * 6 + 16)
        lines.append(f'<rect x="{x + NODE_WIDTH - badge_width - 14}" y="{y + 12}" width="{badge_width}" height="18" rx="9" fill="{badge_bg}" stroke="{style.stroke}" stroke-width="0.6"/>')
        lines.append(f'<text x="{x + NODE_WIDTH - badge_width / 2 - 14:.1f}" y="{y + 25}" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="9" font-weight="700" fill="{badge_fg}">{badge_text}</text>')
    lines.append("</g>")


def _append_svg_legend(lines: list[str], width: int, nodes: list[GraphNode], dark: bool, palette: dict[str, str]) -> None:
    items = _legend_items(nodes, dark)
    x = max(720, width - 378)
    y = 22
    lines.append(f'<g aria-label="Legend">')
    lines.append(f'<rect x="{x}" y="{y}" width="314" height="{80 if len(items) <= 3 else 98}" rx="14" fill="{palette["legend_bg"]}" stroke="{palette["border"]}" stroke-width="1"/>')
    lines.append(f'<text x="{x + 18}" y="{y + 24}" font-family="Arial, Helvetica, sans-serif" font-size="11" font-weight="700" fill="{palette["text"]}">Legend</text>')
    for idx, (group, color) in enumerate(items[:6]):
        col = idx // 3
        row = idx % 3
        item_x = x + 18 + col * 150
        item_y = y + 43 + row * 18
        lines.append(f'<rect x="{item_x}" y="{item_y - 9}" width="10" height="10" rx="2" fill="{color}"/>')
        lines.append(f'<text x="{item_x + 16}" y="{item_y}" font-family="Arial, Helvetica, sans-serif" font-size="10" fill="{palette["muted"]}">{xml_escape(group)}</text>')
    lines.append("</g>")


def _draw_png_node(
    draw: ImageDraw.ImageDraw,
    node: GraphNode,
    x: int,
    y: int,
    dark: bool,
    palette: dict[str, str],
    title_font: ImageFont.ImageFont,
    meta_font: ImageFont.ImageFont,
    small_font: ImageFont.ImageFont,
) -> None:
    style = _node_style(node, dark)
    status = _status_kind(node.status)
    style = _status_node_style(style, status, dark)
    shadow = "#000000" if dark else "#D3DAE7"
    draw.rounded_rectangle((x + 3, y + 5, x + NODE_WIDTH + 3, y + NODE_HEIGHT + 5), radius=12, fill=shadow)
    draw.rounded_rectangle((x, y, x + NODE_WIDTH, y + NODE_HEIGHT), radius=12, fill=style.fill, outline=style.stroke, width=2 if status != "confirmed" else 1)
    draw.rounded_rectangle((x, y, x + 8, y + NODE_HEIGHT), radius=4, fill=style.accent)
    draw.text((x + 18, y + 10), _display_type(node.type), fill=style.accent, font=small_font)
    for idx, line in enumerate(_wrap_label(node.label, 27, 2)):
        draw.text((x + 18, y + 29 + idx * 15), line, fill=palette["text"], font=title_font)
    detail = _node_detail(node)
    if detail:
        draw.text((x + 18, y + 68), _clip(detail, 31), fill=palette["muted"], font=meta_font)
    badge = _status_badge(status)
    if badge:
        badge_text, badge_bg, badge_fg = badge
        badge_width = max(38, len(badge_text) * 6 + 16)
        badge_box = (x + NODE_WIDTH - badge_width - 14, y + 12, x + NODE_WIDTH - 14, y + 30)
        draw.rounded_rectangle(badge_box, radius=9, fill=badge_bg, outline=style.stroke)
        draw.text((badge_box[0] + 8, badge_box[1] + 3), badge_text, fill=badge_fg, font=small_font)


def _draw_png_legend(draw: ImageDraw.ImageDraw, width: int, nodes: list[GraphNode], dark: bool, palette: dict[str, str], font: ImageFont.ImageFont) -> None:
    items = _legend_items(nodes, dark)
    x = max(720, width - 378)
    y = 22
    height = 80 if len(items) <= 3 else 98
    draw.rounded_rectangle((x, y, x + 314, y + height), radius=14, fill=palette["legend_bg"], outline=palette["border"])
    draw.text((x + 18, y + 12), "Legend", fill=palette["text"], font=_font(11, bold=True))
    for idx, (group, color) in enumerate(items[:6]):
        col = idx // 3
        row = idx % 3
        item_x = x + 18 + col * 150
        item_y = y + 38 + row * 18
        draw.rounded_rectangle((item_x, item_y, item_x + 10, item_y + 10), radius=2, fill=color)
        draw.text((item_x + 16, item_y - 2), group, fill=palette["muted"], font=font)


def _draw_pdf_node(c: canvas.Canvas, node: GraphNode, x: int, y: int, page_height: float, dark: bool, palette: dict[str, str]) -> None:
    status = _status_kind(node.status)
    style = _status_node_style(_node_style(node, dark), status, dark)
    pdf_y = page_height - y - NODE_HEIGHT
    _pdf_fill(c, style.fill)
    _pdf_stroke(c, style.stroke)
    if status in {"auto", "pending"}:
        c.setDash(6, 4)
    c.roundRect(x, pdf_y, NODE_WIDTH, NODE_HEIGHT, 12, fill=1, stroke=1)
    c.setDash()
    _pdf_fill(c, style.accent)
    c.roundRect(x, pdf_y, 8, NODE_HEIGHT, 4, fill=1, stroke=0)
    _pdf_fill(c, style.accent)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(x + 18, page_height - y - 21, _clip(_display_type(node.type), 28))
    _pdf_fill(c, palette["text"])
    c.setFont("Helvetica-Bold", 9)
    for idx, line in enumerate(_wrap_label(node.label, 28, 2)):
        c.drawString(x + 18, page_height - y - 42 - idx * 14, _clip(line, 34))
    detail = _node_detail(node)
    if detail:
        _pdf_fill(c, palette["muted"])
        c.setFont("Helvetica", 7)
        c.drawString(x + 18, page_height - y - 75, _clip(detail, 36))
    badge = _status_badge(status)
    if badge:
        badge_text, badge_bg, badge_fg = badge
        badge_width = max(38, len(badge_text) * 5 + 16)
        _pdf_fill(c, badge_bg)
        _pdf_stroke(c, style.stroke)
        c.roundRect(x + NODE_WIDTH - badge_width - 14, page_height - y - 30, badge_width, 18, 9, fill=1, stroke=1)
        _pdf_fill(c, badge_fg)
        c.setFont("Helvetica-Bold", 6)
        c.drawCentredString(x + NODE_WIDTH - badge_width / 2 - 14, page_height - y - 24, badge_text)


def _node_style(node: GraphNode, dark: bool) -> NodeStyle:
    base = TYPE_STYLES.get(node.type, NodeStyle("#F8FAFC", "#CBD5E1", "#64748B", "Other"))
    if not dark:
        return base
    dark_fills = {
        "Project": "#1E293B",
        "Network": "#0F3347",
        "Entry": "#1E293B",
        "Runtime": "#3B2F15",
        "Service": "#102A4C",
        "Interface": "#271D46",
        "Data": "#2B1749",
        "External": "#1E293B",
        "Security": "#451A1A",
        "Identity": "#2E205F",
        "Monitoring": "#123321",
        "Delivery": "#3A2411",
        "Other": "#1E293B",
    }
    return NodeStyle(dark_fills.get(base.group, "#1E293B"), base.stroke, base.accent, base.group)


def _status_node_style(style: NodeStyle, status: str, dark: bool) -> NodeStyle:
    if status == "pending":
        return NodeStyle("#3A2A12" if dark else "#FFF7ED", "#F59E0B", "#F59E0B", style.group)
    if status == "exception":
        return NodeStyle("#2D1D3F" if dark else "#FAF5FF", "#A855F7", "#A855F7", style.group)
    return style


def _status_kind(status: str) -> str:
    if status == "Auto_Detected":
        return "auto"
    if status == "Pending_Confirmation":
        return "pending"
    if status == "Accepted_Exception":
        return "exception"
    return "confirmed"


def _status_badge(status: str) -> tuple[str, str, str] | None:
    if status == "auto":
        return "AUTO", "#EEF2FF", "#3730A3"
    if status == "pending":
        return "PENDING", "#FEF3C7", "#92400E"
    if status == "exception":
        return "EXC", "#F3E8FF", "#6B21A8"
    return None


def _legend_items(nodes: list[GraphNode], dark: bool) -> list[tuple[str, str]]:
    seen: dict[str, str] = {}
    for node in nodes:
        style = _node_style(node, dark)
        seen.setdefault(style.group, style.accent)
    if not seen:
        seen["Graph"] = "#64748B"
    return sorted(seen.items(), key=lambda item: item[0])


def _palette(dark: bool) -> dict[str, str]:
    if dark:
        return {
            "bg": "#101827",
            "header": "#0D1324",
            "panel": "#121B2E",
            "legend_bg": "#172033",
            "border": "#334155",
            "text": "#F8FAFC",
            "muted": "#AEBBD0",
            "edge": "#9DB4D9",
            "edge_opacity": "0.78",
            "edge_label_bg": "#1E293B",
            "edge_label_text": "#E2E8F0",
            "accent": "#38BDF8",
            "shadow": "#000000",
            "shadow_opacity": "0.26",
            "status_bg": "#312E81",
            "status_text": "#E0E7FF",
        }
    return {
        "bg": "#F5F7FB",
        "header": "#FFFFFF",
        "panel": "#FFFFFF",
        "legend_bg": "#FFFFFF",
        "border": "#D8DEE8",
        "text": "#111827",
        "muted": "#5B6573",
        "edge": "#65738A",
        "edge_opacity": "0.82",
        "edge_label_bg": "#FFFFFF",
        "edge_label_text": "#334155",
        "accent": "#2563EB",
        "shadow": "#0F172A",
        "shadow_opacity": "0.13",
        "status_bg": "#EEF2FF",
        "status_text": "#3730A3",
    }


def _edge_curve_points(source: tuple[int, int], target: tuple[int, int]) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float], tuple[float, float]]:
    x1, y1 = source
    x2, y2 = target
    cy1 = y1 + NODE_HEIGHT / 2
    cy2 = y2 + NODE_HEIGHT / 2
    if abs(x2 - x1) < 12:
        sx = x1 + NODE_WIDTH
        tx = x2 + NODE_WIDTH
        offset = 70 + abs(cy2 - cy1) * 0.25
        return (sx, cy1), (sx + offset, cy1), (tx + offset, cy2), (tx, cy2)
    if x1 < x2:
        sx = x1 + NODE_WIDTH
        tx = x2
        bend = max(80, min(180, (tx - sx) * 0.5))
        return (sx, cy1), (sx + bend, cy1), (tx - bend, cy2), (tx, cy2)
    sx = x1
    tx = x2 + NODE_WIDTH
    bend = max(80, min(180, (sx - tx) * 0.5))
    return (sx, cy1), (sx - bend, cy1), (tx + bend, cy2), (tx, cy2)


def _svg_path(points: tuple[tuple[float, float], tuple[float, float], tuple[float, float], tuple[float, float]]) -> str:
    p0, p1, p2, p3 = points
    return f"M {p0[0]:.1f} {p0[1]:.1f} C {p1[0]:.1f} {p1[1]:.1f}, {p2[0]:.1f} {p2[1]:.1f}, {p3[0]:.1f} {p3[1]:.1f}"


def _sampled_edge_points(source: tuple[int, int], target: tuple[int, int]) -> list[tuple[float, float]]:
    p0, p1, p2, p3 = _edge_curve_points(source, target)
    return [_cubic(p0, p1, p2, p3, step / 24) for step in range(25)]


def _cubic(p0: tuple[float, float], p1: tuple[float, float], p2: tuple[float, float], p3: tuple[float, float], t: float) -> tuple[float, float]:
    u = 1 - t
    x = u**3 * p0[0] + 3 * u**2 * t * p1[0] + 3 * u * t**2 * p2[0] + t**3 * p3[0]
    y = u**3 * p0[1] + 3 * u**2 * t * p1[1] + 3 * u * t**2 * p2[1] + t**3 * p3[1]
    return x, y


def _edge_label_position(points: tuple[tuple[float, float], tuple[float, float], tuple[float, float], tuple[float, float]]) -> tuple[float, float]:
    return _cubic(points[0], points[1], points[2], points[3], 0.5)


def _draw_polyline(draw: ImageDraw.ImageDraw, points: list[tuple[float, float]], fill: str, width: int, dashed: bool) -> None:
    if not dashed:
        draw.line(points, fill=fill, width=width, joint="curve")
        return
    dash_len = 10
    gap_len = 7
    distance = 0.0
    draw_dash = True
    remaining = dash_len
    for start, end in zip(points, points[1:]):
        x1, y1 = start
        x2, y2 = end
        seg_len = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        if seg_len == 0:
            continue
        consumed = 0.0
        while consumed < seg_len:
            step = min(remaining, seg_len - consumed)
            a = consumed / seg_len
            b = (consumed + step) / seg_len
            if draw_dash:
                draw.line(((x1 + (x2 - x1) * a, y1 + (y2 - y1) * a), (x1 + (x2 - x1) * b, y1 + (y2 - y1) * b)), fill=fill, width=width)
            consumed += step
            remaining -= step
            if remaining <= 0.001:
                draw_dash = not draw_dash
                remaining = dash_len if draw_dash else gap_len
        distance += seg_len
    if distance < 1:
        draw.line(points, fill=fill, width=width)


def _draw_arrowhead(draw: ImageDraw.ImageDraw, start: tuple[float, float], end: tuple[float, float], fill: str) -> None:
    angle = atan2(end[1] - start[1], end[0] - start[0])
    length = 11
    spread = 0.48
    p1 = (end[0] - length * cos(angle - spread), end[1] - length * sin(angle - spread))
    p2 = (end[0] - length * cos(angle + spread), end[1] - length * sin(angle + spread))
    draw.polygon([end, p1, p2], fill=fill)


def _draw_pdf_arrowhead(c: canvas.Canvas, start: tuple[float, float], end: tuple[float, float], page_height: float, fill: str) -> None:
    angle = atan2(end[1] - start[1], end[0] - start[0])
    length = 9
    spread = 0.48
    p1 = (end[0] - length * cos(angle - spread), end[1] - length * sin(angle - spread))
    p2 = (end[0] - length * cos(angle + spread), end[1] - length * sin(angle + spread))
    _pdf_fill(c, fill)
    c.line(end[0], page_height - end[1], p1[0], page_height - p1[1])
    c.line(end[0], page_height - end[1], p2[0], page_height - p2[1])


def _edge_is_control(edge: GraphEdge) -> bool:
    return edge.type in CONTROL_EDGES or _status_kind(edge.status) in {"auto", "pending", "exception"}


def _edge_color(edge: GraphEdge, dark: bool, palette: dict[str, str]) -> str:
    status = _status_kind(edge.status)
    if status == "pending":
        return "#FBBF24" if dark else "#D97706"
    if status == "exception":
        return "#C084FC" if dark else "#9333EA"
    return palette["edge"]


def _edge_accessible_label(edge: GraphEdge) -> str:
    risk = _edge_risk_level(edge)
    return f"{edge.type} edge from {edge.source or 'N/A'} to {edge.target or 'N/A'}; status {edge.status}; risk {risk}"


def _node_accessible_label(node: GraphNode) -> str:
    risk = _node_risk_level(node)
    return f"{node.label} node; type {node.type}; status {node.status}; layer {node.layer or 'unknown'}; risk {risk}"


def _edge_risk_level(edge: GraphEdge) -> str:
    status = _status_kind(edge.status)
    if status == "pending":
        return "review"
    if status == "exception":
        return "exception"
    tags = edge.metadata.get("risk_tags", []) if isinstance(edge.metadata, dict) else []
    if any(tag in tags for tag in ("critical_dependency", "sensitive_data")):
        return "elevated"
    return "normal"


def _node_risk_level(node: GraphNode) -> str:
    status = _status_kind(node.status)
    if status == "pending":
        return "review"
    if status == "exception":
        return "exception"
    if node.metadata.get("priority") in {"P0", "P1"} or str(node.metadata.get("sensitivity", "")).lower() in {"restricted", "high", "critical"}:
        return "elevated"
    return "normal"


def _edge_label(edge: GraphEdge) -> str:
    value = edge.label.strip() if edge.label else edge.type
    status = _status_kind(edge.status)
    if status == "pending":
        value = f"Pending: {value}"
    elif status == "exception":
        value = f"Exception: {value}"
    elif status == "auto":
        value = f"Auto: {value}"
    return _clip(value.replace("_", " "), 28)


def _node_detail(node: GraphNode) -> str:
    for key in DETAIL_KEYS:
        value = str(node.metadata.get(key, "")).strip()
        if value:
            return f"{key.replace('_', ' ')}: {value}"
    return f"source: {node.sheet}"


def _display_type(value: str) -> str:
    return value.replace("_", " ").title()


def _wrap_label(value: str, length: int, max_lines: int) -> list[str]:
    text = " ".join(value.split()) or "Unnamed"
    words = text.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        if len(word) > length:
            chunks = [word[i : i + length] for i in range(0, len(word), length)]
        else:
            chunks = [word]
        for chunk in chunks:
            candidate = chunk if not current else f"{current} {chunk}"
            if len(candidate) <= length:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = chunk
            if len(lines) == max_lines:
                break
        if len(lines) == max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
    if lines and len(" ".join(words)) > len(" ".join(lines)):
        lines[-1] = _clip(lines[-1], max(4, length))
    return lines or ["Unnamed"]


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Helvetica Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Helvetica.ttf",
        "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return int(bbox[2] - bbox[0])


def _is_security_view(view: View) -> bool:
    return view.theme in {"dark", "security"}


def _mmd_id(value: str) -> str:
    return "n_" + "".join(ch if ch.isalnum() else "_" for ch in value)


def _clip(value: str, length: int) -> str:
    return value if len(value) <= length else value[: max(0, length - 3)] + "..."


def _hex_to_rgb(value: str) -> tuple[float, float, float]:
    value = value.lstrip("#")
    return int(value[0:2], 16) / 255, int(value[2:4], 16) / 255, int(value[4:6], 16) / 255


def _pdf_fill(c: canvas.Canvas, value: str) -> None:
    c.setFillColorRGB(*_hex_to_rgb(value))


def _pdf_stroke(c: canvas.Canvas, value: str) -> None:
    c.setStrokeColorRGB(*_hex_to_rgb(value))
