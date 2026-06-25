from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, sin
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import landscape, letter
from reportlab.pdfgen import canvas

from .models import GraphEdge, GraphModel, GraphNode
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
OVERVIEW_DATAFLOW_EDGES = {"calls", "calls_external", "reads_from", "writes_to", "depends_on"}
OVERVIEW_CONTEXT_EDGES = {"runs_on", "runs_on_runtime", "allowed_by", "protected_by", "uses_sa", "monitored_by"}
OVERVIEW_NODE_WIDTH = 230
OVERVIEW_NODE_HEIGHT = 94
OVERVIEW_LEDGER_WIDTH = 360
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


def render_diagrams(graph: GraphModel, diagrams_dir: Path) -> list[Path]:
    diagrams_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for view in VIEWS:
        if view.filename == "00_overview":
            layout = _overview_layout(graph)
            outputs.append(_write_overview_svg(diagrams_dir / f"{view.filename}.svg", view, layout))
            outputs.append(_write_overview_png(diagrams_dir / f"{view.filename}.png", view, layout))
            outputs.append(_write_overview_pdf(diagrams_dir / f"{view.filename}.pdf", view, layout))
            outputs.append(_write_overview_mermaid(diagrams_dir / f"{view.filename}.mmd", view, layout))
            continue
        nodes, edges = _select_view(graph, view)
        positions = _layout(nodes)
        outputs.append(_write_svg(diagrams_dir / f"{view.filename}.svg", view, nodes, edges, positions))
        outputs.append(_write_png(diagrams_dir / f"{view.filename}.png", view, nodes, edges, positions))
        outputs.append(_write_pdf(diagrams_dir / f"{view.filename}.pdf", view, nodes, edges, positions))
        outputs.append(_write_mermaid(diagrams_dir / f"{view.filename}.mmd", view, nodes, edges))
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
    ]


@dataclass(frozen=True)
class OverviewLayout:
    width: int
    height: int
    lane_width: int
    ledger_x: int
    main_top: int
    main_height: int
    controls_top: int
    controls_height: int
    nodes: dict[str, GraphNode]
    positions: dict[str, tuple[int, int]]
    main_edges: list[GraphEdge]
    runtime_edges: list[GraphEdge]
    context_edges: list[GraphEdge]
    perimeter_edges: list[GraphEdge]
    all_edges: list[GraphEdge]


def _overview_layout(graph: GraphModel) -> OverviewLayout:
    main_edges = _overview_main_edges(graph.edges)
    positions = _overview_positions(graph.nodes, main_edges)
    max_x = max((x for x, _ in positions.values()), default=LEFT_MARGIN) + OVERVIEW_NODE_WIDTH
    max_y = max((y for _, y in positions.values()), default=360) + OVERVIEW_NODE_HEIGHT
    ledger_x = max(1490, max_x + 88)
    width = ledger_x + OVERVIEW_LEDGER_WIDTH + 42
    lane_width = ledger_x - 82
    main_top = 280
    main_height = max(420, max_y - main_top + 72)
    controls_top = main_top + main_height + 28
    controls_height = 220
    height = controls_top + controls_height + 82
    data_node_ids = {edge.source for edge in main_edges}.union(edge.target for edge in main_edges)
    context_edges = [
        edge
        for edge in graph.edges
        if edge.type in OVERVIEW_CONTEXT_EDGES and _overview_context_edge_is_relevant(edge, main_edges, data_node_ids)
    ]
    runtime_edges = [edge for edge in context_edges if edge.type in {"runs_on", "runs_on_runtime"}]
    perimeter_edges = [edge for edge in context_edges if edge.type == "protected_by"]
    return OverviewLayout(
        width=width,
        height=height,
        lane_width=lane_width,
        ledger_x=ledger_x,
        main_top=main_top,
        main_height=main_height,
        controls_top=controls_top,
        controls_height=controls_height,
        nodes=graph.nodes,
        positions=positions,
        main_edges=main_edges,
        runtime_edges=runtime_edges,
        context_edges=context_edges,
        perimeter_edges=perimeter_edges,
        all_edges=graph.edges,
    )


def _overview_main_edges(edges: list[GraphEdge]) -> list[GraphEdge]:
    best: dict[tuple[str, str, str], GraphEdge] = {}
    for edge in edges:
        if edge.type not in OVERVIEW_DATAFLOW_EDGES:
            continue
        key = (edge.type, edge.source, edge.target)
        current = best.get(key)
        if current is None or _overview_edge_rank(edge) < _overview_edge_rank(current):
            best[key] = edge
    return sorted(best.values(), key=lambda edge: (_edge_number(edge), edge.type, edge.source, edge.target))


def _overview_edge_rank(edge: GraphEdge) -> tuple[int, int, int]:
    source_sheet = str(edge.metadata.get("source_sheet", "")) if isinstance(edge.metadata, dict) else ""
    preferred_source = 0 if source_sheet == "05_Dependencies" else 1
    preferred_status = 0 if edge.status in {"Confirmed", "Accepted_Exception", "Auto_Detected"} else 1
    label_rank = 0 if edge.label else 1
    return preferred_source, preferred_status, label_rank


def _overview_context_edge_is_relevant(edge: GraphEdge, main_edges: list[GraphEdge], data_node_ids: set[str]) -> bool:
    if edge.type in {"runs_on", "runs_on_runtime", "uses_sa", "monitored_by"}:
        return edge.source in data_node_ids
    if edge.type == "protected_by":
        return True
    if edge.type == "allowed_by":
        dependency_ids = {str(item.metadata.get("dependency_id", "")) for item in main_edges if isinstance(item.metadata, dict)}
        return edge.source in data_node_ids or any(edge.source == f"dependency:{dep_id}" for dep_id in dependency_ids if dep_id)
    return False


def _overview_positions(nodes: dict[str, GraphNode], edges: list[GraphEdge]) -> dict[str, tuple[int, int]]:
    node_ids = {edge.source for edge in edges}.union(edge.target for edge in edges)
    if not node_ids:
        service_nodes = [node.id for node in nodes.values() if node.type == "service"][:6]
        return {node_id: (120 + idx * 300, 390) for idx, node_id in enumerate(service_nodes)}

    components = _overview_components(node_ids, edges)
    positions: dict[str, tuple[int, int]] = {}
    y_cursor = 390
    for component in components:
        component_edges = [edge for edge in edges if edge.source in component and edge.target in component]
        levels = _overview_levels(component, component_edges)
        rows_by_level: dict[int, list[str]] = {}
        for node_id in component:
            rows_by_level.setdefault(levels.get(node_id, 0), []).append(node_id)
        max_rows = 1
        for level, ids in rows_by_level.items():
            ids.sort(key=lambda node_id: _overview_node_sort(nodes.get(node_id)))
            max_rows = max(max_rows, len(ids))
            for row_index, node_id in enumerate(ids):
                x = 120 + level * (OVERVIEW_NODE_WIDTH + 110)
                y = y_cursor + row_index * (OVERVIEW_NODE_HEIGHT + 74)
                positions[node_id] = (x, y)
        y_cursor += max_rows * (OVERVIEW_NODE_HEIGHT + 74) + 80
    return positions


def _overview_components(node_ids: set[str], edges: list[GraphEdge]) -> list[set[str]]:
    adjacency = {node_id: set() for node_id in node_ids}
    for edge in edges:
        adjacency.setdefault(edge.source, set()).add(edge.target)
        adjacency.setdefault(edge.target, set()).add(edge.source)
    components: list[set[str]] = []
    seen: set[str] = set()
    for node_id in sorted(node_ids):
        if node_id in seen:
            continue
        stack = [node_id]
        component: set[str] = set()
        while stack:
            current = stack.pop()
            if current in component:
                continue
            component.add(current)
            stack.extend(adjacency.get(current, set()) - component)
        seen.update(component)
        components.append(component)
    components.sort(key=lambda component: (-sum(1 for edge in edges if edge.source in component and edge.target in component), sorted(component)[0]))
    return components


def _overview_levels(component: set[str], edges: list[GraphEdge]) -> dict[str, int]:
    levels = {node_id: 0 for node_id in component}
    incoming = {edge.target for edge in edges}
    for node_id in component - incoming:
        levels[node_id] = 0
    for _ in range(max(1, len(component))):
        changed = False
        for edge in edges:
            if edge.source not in levels or edge.target not in levels:
                continue
            candidate = levels[edge.source] + 1
            if candidate > levels[edge.target]:
                levels[edge.target] = candidate
                changed = True
        if not changed:
            break
    return levels


def _overview_node_sort(node: GraphNode | None) -> tuple[int, str]:
    if node is None:
        return 9, ""
    return TYPE_ORDER.get(node.type, 9), node.label.lower()


def _write_overview_svg(path: Path, view: View, layout: OverviewLayout) -> Path:
    width, height = layout.width, layout.height
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{xml_escape(view.title)} graph-truthful overview">',
        "<defs>",
        '<filter id="overviewShadow" x="-20%" y="-20%" width="140%" height="150%"><feDropShadow dx="5" dy="7" stdDeviation="0" flood-color="#CBD5E1" flood-opacity="0.85"/></filter>',
        '<marker id="overviewArrowBlue" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0 0L10 5L0 10z" fill="#2563EB"/></marker>',
        '<marker id="overviewArrowPurple" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0 0L10 5L0 10z" fill="#7C3AED"/></marker>',
        '<marker id="overviewArrowOrange" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0 0L10 5L0 10z" fill="#F97316"/></marker>',
        '<marker id="overviewArrowRed" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0 0L10 5L0 10z" fill="#DC2626"/></marker>',
        "</defs>",
        f'<rect width="{width}" height="{height}" fill="#F5F7FB"/>',
        f'<rect x="0" y="0" width="{width}" height="120" fill="#FFFFFF" stroke="#D8E1EF" stroke-width="1"/>',
        '<rect x="36" y="28" width="8" height="62" rx="4" fill="#2563EB"/>',
        f'<text x="64" y="54" font-family="Arial, Helvetica, sans-serif" font-size="30" font-weight="700" fill="#111827">{xml_escape(view.title)}</text>',
        '<text x="64" y="84" font-family="Arial, Helvetica, sans-serif" font-size="14" fill="#475569">Graph-truthful architecture view | generated from workbook graph | no inferred dataflow edges</text>',
    ]
    _append_overview_svg_legend(lines, width)
    _append_overview_svg_lane(lines, 42, 140, layout.lane_width, 118, "Entry context / perimeter control")
    _append_overview_svg_lane(lines, 42, layout.main_top, layout.lane_width, layout.main_height, "Primary graph dataflow")
    _append_overview_svg_lane(lines, 42, layout.controls_top, layout.lane_width, layout.controls_height, "Controls and runtime summary")
    _append_overview_svg_perimeter(lines, layout)
    for edge in layout.main_edges:
        _append_overview_svg_edge(lines, edge, layout)
    for node_id, position in layout.positions.items():
        node = layout.nodes.get(node_id)
        if node:
            _append_overview_svg_node(lines, node, position[0], position[1])
            _append_overview_svg_node_badges(lines, node, position[0], position[1], layout)
    _append_overview_svg_runtime_chips(lines, layout)
    _append_overview_svg_control_cards(lines, layout)
    _append_overview_svg_ledger(lines, layout)
    lines.append(
        f'<text x="54" y="{height - 46}" font-family="Arial, Helvetica, sans-serif" font-size="13" fill="#475569">Renderer rule: dataflow lines come only from calls / reads_from / writes_to / calls_external graph edges; runtime and controls stay as context.</text>'
    )
    lines.append("</svg>")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _append_overview_svg_legend(lines: list[str], width: int) -> None:
    x = width - 560
    lines.append(f'<g aria-label="Legend"><rect x="{x}" y="24" width="500" height="76" rx="12" fill="#FFFFFF" stroke="#CBD5E1" stroke-width="1"/>')
    items = [
        ("#2563EB", "Service call"),
        ("#7C3AED", "Data read/write"),
        ("#F97316", "Pending external"),
        ("#D97706", "Runtime chip"),
        ("#DC2626", "Security badge"),
        ("#16A34A", "Monitoring badge"),
    ]
    for idx, (color, label) in enumerate(items):
        item_x = x + 24 + (idx % 3) * 160
        item_y = 48 + (idx // 3) * 29
        lines.append(f'<rect x="{item_x}" y="{item_y}" width="16" height="16" rx="4" fill="{color}"/>')
        lines.append(f'<text x="{item_x + 24}" y="{item_y + 12}" font-family="Arial, Helvetica, sans-serif" font-size="10" fill="#475569">{xml_escape(label)}</text>')
    lines.append("</g>")


def _append_overview_svg_lane(lines: list[str], x: int, y: int, width: int, height: int, label: str) -> None:
    lines.append(f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="18" fill="#FFFFFF" stroke="#CBD5E1" stroke-width="1"/>')
    lines.append(f'<text x="{x + 18}" y="{y + 34}" font-family="Arial, Helvetica, sans-serif" font-size="15" font-weight="700" fill="#243449">{xml_escape(label)}</text>')


def _append_overview_svg_perimeter(lines: list[str], layout: OverviewLayout) -> None:
    x = 120
    for idx, edge in enumerate(layout.perimeter_edges[:2]):
        source = layout.nodes.get(edge.source)
        target = layout.nodes.get(edge.target)
        if not source or not target:
            continue
        y = 174 + idx * 74
        _append_overview_svg_node_card(lines, source, x, y, 220, 64, "#475569", "#F8FAFC")
        _append_overview_svg_node_card(lines, target, x + 315, y, 230, 64, "#DC2626", "#FFF1F2")
        label = _overview_badge_text("protected_by", edge.label or edge.type)
        lines.append(f'<polyline points="{x + 220},{y + 32} {x + 315},{y + 32}" fill="none" stroke="#DC2626" stroke-width="2.5" marker-end="url(#overviewArrowRed)" data-overview-role="boundary-control" data-edge-id="{xml_escape(edge.id)}" data-source="{xml_escape(edge.source)}" data-target="{xml_escape(edge.target)}"/>')
        _append_overview_svg_badge(lines, x + 240, y - 18, label, "#DC2626", "#FFF1F2", "boundary-control", edge)
    lines.append('<rect x="780" y="168" width="420" height="76" rx="12" fill="#F8FAFC" stroke="#CBD5E1" stroke-width="1"/>')
    lines.append('<text x="802" y="200" font-family="Arial, Helvetica, sans-serif" font-size="12" font-weight="700" fill="#334155">Display rule</text>')
    lines.append('<text x="802" y="224" font-family="Arial, Helvetica, sans-serif" font-size="12" fill="#475569">Ingress context is not converted into dataflow without a graph edge.</text>')


def _append_overview_svg_edge(lines: list[str], edge: GraphEdge, layout: OverviewLayout) -> None:
    points = _overview_edge_points(edge, layout)
    if not points:
        return
    color = _overview_edge_color(edge)
    marker = {"#2563EB": "overviewArrowBlue", "#7C3AED": "overviewArrowPurple", "#F97316": "overviewArrowOrange"}.get(color, "overviewArrowBlue")
    dash = ' stroke-dasharray="9 7"' if _status_kind(edge.status) == "pending" else ""
    point_text = " ".join(f"{x},{y}" for x, y in points)
    risk = _edge_risk_level(edge)
    label = _overview_edge_display_label(edge, layout)
    label_x, label_y = _overview_label_anchor(points)
    lines.append(f'<g role="img" aria-label="{xml_escape(_edge_accessible_label(edge))}" data-risk-level="{risk}">')
    lines.append(f'<title>{xml_escape(_edge_accessible_label(edge))}</title>')
    lines.append(f'<polyline points="{point_text}" fill="none" stroke="{color}" stroke-width="{_overview_edge_width(edge)}" stroke-linecap="round" stroke-linejoin="round" marker-end="url(#{marker})"{dash} data-overview-role="main-dataflow" data-edge-id="{xml_escape(edge.id)}" data-edge-type="{xml_escape(edge.type)}" data-source="{xml_escape(edge.source)}" data-target="{xml_escape(edge.target)}"/>')
    lines.append(f'<circle cx="{label_x}" cy="{label_y}" r="6" fill="{color}"/>')
    badge_x, badge_y = _overview_label_badge_position(edge, points, layout)
    _append_overview_svg_badge(lines, badge_x, badge_y, label, color, _overview_edge_label_fill(edge), "main-dataflow-label", edge)
    lines.append(f'<polyline points="{label_x},{label_y} {label_x},{badge_y + 14}" fill="none" stroke="{color}" stroke-width="1.2" stroke-linecap="round"/>')
    lines.append("</g>")


def _append_overview_svg_node(lines: list[str], node: GraphNode, x: int, y: int) -> None:
    color, fill = _overview_node_colors(node)
    _append_overview_svg_node_card(lines, node, x, y, OVERVIEW_NODE_WIDTH, OVERVIEW_NODE_HEIGHT, color, fill)


def _append_overview_svg_node_card(lines: list[str], node: GraphNode, x: int, y: int, width: int, height: int, color: str, fill: str) -> None:
    status = _status_kind(node.status)
    dash = ' stroke-dasharray="6 4"' if status in {"auto", "pending"} else ""
    risk = _node_risk_level(node)
    lines.append(f'<g filter="url(#overviewShadow)" role="img" aria-label="{xml_escape(_node_accessible_label(node))}" data-risk-level="{risk}" data-node-id="{xml_escape(node.id)}">')
    lines.append(f'<title>{xml_escape(_node_accessible_label(node))}</title>')
    lines.append(f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="8" fill="{fill}" stroke="{color}" stroke-width="2"{dash}/>')
    lines.append(f'<rect x="{x}" y="{y}" width="9" height="{height}" rx="4" fill="{color}"/>')
    lines.append(f'<text x="{x + 20}" y="{y + 24}" font-family="Arial, Helvetica, sans-serif" font-size="10" fill="{color}">{xml_escape(_display_type(node.type))}</text>')
    for idx, line in enumerate(_wrap_label(node.label, 26, 2)):
        lines.append(f'<text x="{x + 20}" y="{y + 50 + idx * 15}" font-family="Arial, Helvetica, sans-serif" font-size="16" font-weight="700" fill="#111827">{xml_escape(line)}</text>')
    detail = _node_detail(node)
    if detail and height >= 82:
        lines.append(f'<text x="{x + 20}" y="{y + height - 20}" font-family="Arial, Helvetica, sans-serif" font-size="10" fill="#475569">{xml_escape(_clip(detail, 34))}</text>')
    badge = _status_badge(status)
    if badge:
        badge_text, badge_bg, badge_fg = badge
        badge_width = max(46, len(badge_text) * 7 + 18)
        lines.append(f'<rect x="{x + width - badge_width - 14}" y="{y + 12}" width="{badge_width}" height="22" rx="11" fill="{badge_bg}" stroke="{color}" stroke-width="1"/>')
        lines.append(f'<text x="{x + width - badge_width / 2 - 14:.1f}" y="{y + 27}" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="10" font-weight="700" fill="{badge_fg}">{xml_escape(badge_text)}</text>')
    lines.append("</g>")


def _append_overview_svg_node_badges(lines: list[str], node: GraphNode, x: int, y: int, layout: OverviewLayout) -> None:
    monitoring = [edge for edge in layout.context_edges if edge.type == "monitored_by" and edge.source == node.id]
    if monitoring:
        edge = monitoring[0]
        color = "#16A34A" if edge.label == "Covered" else "#F59E0B"
        fill = "#ECFDF5" if edge.label == "Covered" else "#FFF7ED"
        _append_overview_svg_badge(lines, x + OVERVIEW_NODE_WIDTH - 126, y + OVERVIEW_NODE_HEIGHT - 30, edge.label or "Monitored", color, fill, "control-badge", edge)


def _append_overview_svg_runtime_chips(lines: list[str], layout: OverviewLayout) -> None:
    by_source: dict[str, list[GraphEdge]] = {}
    for edge in layout.runtime_edges:
        by_source.setdefault(edge.source, []).append(edge)
    for source, edges in by_source.items():
        position = layout.positions.get(source)
        if not position:
            continue
        x, y = position
        for idx, edge in enumerate(edges[:3]):
            target = layout.nodes.get(edge.target)
            target_label = target.label if target else edge.target
            label = f"{edge.type}: {_clip(target_label, 24)}"
            _append_overview_svg_badge(lines, x + 12, y + OVERVIEW_NODE_HEIGHT + 14 + idx * 34, label, "#D97706", "#FFFBEB", "runtime-context", edge)


def _append_overview_svg_control_badges(lines: list[str], edge: GraphEdge, layout: OverviewLayout, anchor_x: float, anchor_y: float) -> None:
    controls = _overview_controls_for_edge(edge, layout)
    for idx, control in enumerate(controls[:3]):
        color = "#16A34A" if control.type in {"uses_sa", "monitored_by"} else "#DC2626"
        fill = "#ECFDF5" if color == "#16A34A" else "#FFF1F2"
        label = _overview_control_label(control)
        _append_overview_svg_badge(lines, int(anchor_x) - 92 + idx * 112, int(anchor_y) + 18, label, color, fill, "control-badge", control)


def _append_overview_svg_control_cards(lines: list[str], layout: OverviewLayout) -> None:
    cards = _overview_control_cards(layout)
    x = 120
    y = layout.controls_top + 60
    for idx, (title, heading, detail, color, fill, edge) in enumerate(cards[:5]):
        card_x = x + idx * 265
        lines.append(f'<rect x="{card_x}" y="{y}" width="235" height="118" rx="10" fill="{fill}" stroke="{color}" stroke-width="1.6" data-overview-role="control-badge" data-edge-id="{xml_escape(edge.id)}" data-edge-type="{xml_escape(edge.type)}" data-source="{xml_escape(edge.source)}" data-target="{xml_escape(edge.target)}"/>')
        lines.append(f'<text x="{card_x + 20}" y="{y + 30}" font-family="Arial, Helvetica, sans-serif" font-size="12" font-weight="700" fill="{color}">{xml_escape(title)}</text>')
        lines.append(f'<text x="{card_x + 20}" y="{y + 66}" font-family="Arial, Helvetica, sans-serif" font-size="17" font-weight="700" fill="#111827">{xml_escape(_clip(heading, 24))}</text>')
        lines.append(f'<text x="{card_x + 20}" y="{y + 94}" font-family="Arial, Helvetica, sans-serif" font-size="10" fill="#475569">{xml_escape(_clip(detail, 36))}</text>')


def _append_overview_svg_ledger(lines: list[str], layout: OverviewLayout) -> None:
    x = layout.ledger_x
    lines.append(f'<g data-overview-role="edge-ledger"><rect x="{x}" y="140" width="{OVERVIEW_LEDGER_WIDTH}" height="{layout.height - 222}" rx="18" fill="#FFFFFF" stroke="#CBD5E1" stroke-width="1"/>')
    lines.append(f'<text x="{x + 24}" y="180" font-family="Arial, Helvetica, sans-serif" font-size="15" font-weight="700" fill="#243449">Graph edge ledger</text>')
    lines.append(f'<text x="{x + 24}" y="206" font-family="Arial, Helvetica, sans-serif" font-size="12" fill="#475569">Every rendered dataflow line maps to graph edge IDs.</text>')
    y = 244
    for idx, edge in enumerate(layout.main_edges, start=1):
        color = _overview_edge_color(edge)
        record_ids = _overview_equivalent_record_ids(edge, layout.all_edges)
        lines.append(f'<rect x="{x + 24}" y="{y - 13}" width="42" height="22" rx="5" fill="{_overview_edge_label_fill(edge)}" stroke="{color}" stroke-width="1"/>')
        lines.append(f'<text x="{x + 34}" y="{y + 2}" font-family="Arial, Helvetica, sans-serif" font-size="10" fill="{color}">E{idx}</text>')
        lines.append(f'<text x="{x + 76}" y="{y - 2}" font-family="Arial, Helvetica, sans-serif" font-size="12" font-weight="700" fill="#111827">{xml_escape(edge.type)}</text>')
        lines.append(f'<text x="{x + 76}" y="{y + 16}" font-family="Arial, Helvetica, sans-serif" font-size="10" fill="#334155">{xml_escape(_clip(edge.source + " -> " + edge.target, 36))}</text>')
        lines.append(f'<text x="{x + 76}" y="{y + 32}" font-family="Arial, Helvetica, sans-serif" font-size="10" fill="#64748B">{xml_escape(_clip(record_ids, 38))}</text>')
        y += 72
    lines.append(f'<rect x="{x + 24}" y="{layout.height - 312}" width="{OVERVIEW_LEDGER_WIDTH - 48}" height="78" rx="10" fill="#FFF7ED" stroke="#F59E0B" stroke-width="1.5"/>')
    lines.append(f'<text x="{x + 42}" y="{layout.height - 282}" font-family="Arial, Helvetica, sans-serif" font-size="12" font-weight="700" fill="#92400E">Semantic guardrail</text>')
    lines.append(f'<text x="{x + 42}" y="{layout.height - 258}" font-family="Arial, Helvetica, sans-serif" font-size="10" fill="#92400E">No relationship is rendered as dataflow unless it exists in graph.</text>')
    lines.append("</g>")


def _append_overview_svg_badge(lines: list[str], x: float, y: float, label: str, color: str, fill: str, role: str, edge: GraphEdge | None = None) -> None:
    width = max(66, min(220, len(label) * 7 + 34))
    edge_attrs = ""
    if edge:
        edge_attrs = f' data-edge-id="{xml_escape(edge.id)}" data-edge-type="{xml_escape(edge.type)}" data-source="{xml_escape(edge.source)}" data-target="{xml_escape(edge.target)}"'
    lines.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{width}" height="28" rx="14" fill="{fill}" stroke="{color}" stroke-width="1.5" data-overview-role="{role}"{edge_attrs}/>')
    lines.append(f'<circle cx="{x + 13:.1f}" cy="{y + 14:.1f}" r="4" fill="{color}"/>')
    lines.append(f'<text x="{x + 24:.1f}" y="{y + 19:.1f}" font-family="Arial, Helvetica, sans-serif" font-size="12" font-weight="700" fill="#1F2937">{xml_escape(_clip(label, 30))}</text>')


def _overview_edge_points(edge: GraphEdge, layout: OverviewLayout) -> list[tuple[float, float]]:
    source = layout.positions.get(edge.source)
    target = layout.positions.get(edge.target)
    if not source or not target:
        return []
    pair_edges = [item for item in layout.main_edges if item.source == edge.source and item.target == edge.target]
    pair_index = pair_edges.index(edge) if edge in pair_edges else 0
    offset = (pair_index - (len(pair_edges) - 1) / 2) * 24
    sx = source[0] + OVERVIEW_NODE_WIDTH
    sy = source[1] + OVERVIEW_NODE_HEIGHT * 0.52 + offset
    tx = target[0]
    ty = target[1] + OVERVIEW_NODE_HEIGHT * 0.52 + offset
    if target[1] > source[1] + 70:
        sy = source[1] + OVERVIEW_NODE_HEIGHT * 0.76 + offset
        route_y = target[1] + OVERVIEW_NODE_HEIGHT * 0.52 + offset
        return [(sx, sy), (sx + 52, sy), (sx + 52, route_y), (tx, route_y)]
    if sx <= tx:
        if abs(sy - ty) < 18:
            return [(sx, sy), (tx, ty)]
        mid_x = sx + max(48, (tx - sx) * 0.48)
        return [(sx, sy), (mid_x, sy), (mid_x, ty), (tx, ty)]
    route_y = max(sy, ty) + 70
    return [(sx, sy), (sx + 60, sy), (sx + 60, route_y), (tx - 60, route_y), (tx - 60, ty), (tx, ty)]


def _overview_label_anchor(points: list[tuple[float, float]]) -> tuple[float, float]:
    if len(points) < 2:
        return 120, 120
    longest = max(zip(points, points[1:]), key=lambda pair: ((pair[1][0] - pair[0][0]) ** 2 + (pair[1][1] - pair[0][1]) ** 2))
    return (longest[0][0] + longest[1][0]) / 2, (longest[0][1] + longest[1][1]) / 2


def _overview_label_badge_position(edge: GraphEdge, points: list[tuple[float, float]], layout: OverviewLayout) -> tuple[float, float]:
    label_x, label_y = _overview_label_anchor(points)
    source = layout.positions.get(edge.source, (0, 0))
    target = layout.positions.get(edge.target, (0, 0))
    pair_edges = [item for item in layout.main_edges if item.source == edge.source and item.target == edge.target]
    pair_index = pair_edges.index(edge) if edge in pair_edges else 0
    if target[1] > source[1] + 70:
        return label_x - 88, label_y + 18
    if pair_index > 0:
        return label_x - 88, label_y + 28
    return label_x - 88, label_y - 92


def _overview_edge_color(edge: GraphEdge) -> str:
    if _status_kind(edge.status) == "pending" or edge.type == "calls_external":
        return "#F97316"
    if edge.type in {"reads_from", "writes_to"}:
        return "#7C3AED"
    return "#2563EB"


def _overview_edge_label_fill(edge: GraphEdge) -> str:
    if _status_kind(edge.status) == "pending" or edge.type == "calls_external":
        return "#FFF7ED"
    if edge.type in {"reads_from", "writes_to"}:
        return "#F5F3FF"
    return "#EFF6FF"


def _overview_edge_width(edge: GraphEdge) -> str:
    return "3.8" if edge.type in {"calls", "writes_to"} else "3.0"


def _overview_edge_display_label(edge: GraphEdge, layout: OverviewLayout) -> str:
    index = layout.main_edges.index(edge) + 1 if edge in layout.main_edges else 0
    prefix = f"E{index}"
    status = " PENDING" if _status_kind(edge.status) == "pending" else ""
    value = edge.label or edge.type
    action = "write " if edge.type == "writes_to" else "read " if edge.type == "reads_from" else ""
    return _clip(f"{prefix}{status} {action}{value}".strip(), 30)


def _overview_node_colors(node: GraphNode) -> tuple[str, str]:
    if node.type == "external_service" or _status_kind(node.status) == "pending":
        return "#F97316", "#FFF7ED"
    if node.type == "data_asset":
        return "#7C3AED", "#F3E8FF"
    if node.type == "service":
        return "#2563EB", "#EFF6FF"
    return "#64748B", "#F8FAFC"


def _overview_controls_for_edge(edge: GraphEdge, layout: OverviewLayout) -> list[GraphEdge]:
    controls: list[GraphEdge] = []
    dependency_id = str(edge.metadata.get("dependency_id", "")) if isinstance(edge.metadata, dict) else ""
    for control in layout.context_edges:
        if control.type == "allowed_by" and dependency_id and control.source == f"dependency:{dependency_id}":
            controls.append(control)
        elif control.type == "uses_sa" and control.source == edge.source:
            controls.append(control)
    return controls


def _overview_control_label(edge: GraphEdge) -> str:
    if edge.type == "allowed_by":
        return f"FW {edge.label or 'allow'}"
    if edge.type == "uses_sa":
        return _clip(edge.label or "service account", 24)
    if edge.type == "monitored_by":
        return edge.label or "Monitored"
    return edge.type.replace("_", " ")


def _overview_control_cards(layout: OverviewLayout) -> list[tuple[str, str, str, str, str, GraphEdge]]:
    cards: list[tuple[str, str, str, str, str, GraphEdge]] = []
    seen: set[str] = set()
    for edge in layout.context_edges:
        seen_key = f"{edge.type}:{edge.metadata.get('record_id', edge.id)}"
        if edge.type not in {"allowed_by", "uses_sa", "monitored_by"} or seen_key in seen:
            continue
        seen.add(seen_key)
        if edge.type == "allowed_by":
            title = str(edge.metadata.get("record_id", "")) or edge.id
            cards.append((title, _overview_control_heading(edge, layout), f"allow port {edge.label or '-'}", "#DC2626", "#FFF1F2", edge))
        elif edge.type == "uses_sa":
            title = str(edge.metadata.get("record_id", "")) or edge.id
            cards.append((title, f"{edge.source} service account", edge.label or "IAM binding", "#16A34A", "#ECFDF5", edge))
        elif edge.type == "monitored_by":
            title = "Monitoring"
            cards.append((title, f"{edge.source} coverage", edge.label or "coverage", "#16A34A", "#ECFDF5", edge))
    return cards


def _overview_control_heading(edge: GraphEdge, layout: OverviewLayout) -> str:
    dependency = edge.source.removeprefix("dependency:")
    match = next((item for item in layout.main_edges if item.metadata.get("dependency_id") == dependency), None)
    if match:
        source = layout.nodes.get(match.source)
        target = layout.nodes.get(match.target)
        return f"{source.label if source else match.source} -> {target.label if target else match.target}"
    source = layout.nodes.get(edge.source)
    target = layout.nodes.get(edge.target)
    return f"{source.label if source else edge.source} -> {target.label if target else edge.target}"


def _overview_equivalent_record_ids(edge: GraphEdge, all_edges: list[GraphEdge]) -> str:
    records = []
    for item in all_edges:
        if item.type == edge.type and item.source == edge.source and item.target == edge.target:
            record = str(item.metadata.get("record_id", "")) if isinstance(item.metadata, dict) else ""
            records.append(record or item.id)
    return "; ".join(dict.fromkeys(records)) or edge.id


def _overview_badge_text(kind: str, value: str) -> str:
    return _clip(f"{kind} {value}".replace("_", " "), 30)


def _edge_number(edge: GraphEdge) -> int:
    try:
        return int(edge.id.rsplit("-", 1)[1])
    except (IndexError, ValueError):
        return 999999


def _write_overview_png(path: Path, view: View, layout: OverviewLayout) -> Path:
    image = Image.new("RGB", (layout.width, layout.height), "#F5F7FB")
    draw = ImageDraw.Draw(image)
    title_font = _font(30, bold=True)
    subtitle_font = _font(14)
    lane_font = _font(15, bold=True)
    label_font = _font(16, bold=True)
    small_font = _font(11)
    tiny_font = _font(10)

    draw.rectangle((0, 0, layout.width, 120), fill="#FFFFFF", outline="#D8E1EF")
    draw.rounded_rectangle((36, 28, 44, 90), radius=4, fill="#2563EB")
    draw.text((64, 24), view.title, fill="#111827", font=title_font)
    draw.text((64, 72), "Graph-truthful architecture view | generated from workbook graph | no inferred dataflow edges", fill="#475569", font=subtitle_font)
    _draw_overview_png_legend(draw, layout.width, small_font)
    for x, y, w, h, label in [
        (42, 140, layout.lane_width, 118, "Entry context / perimeter control"),
        (42, layout.main_top, layout.lane_width, layout.main_height, "Primary graph dataflow"),
        (42, layout.controls_top, layout.lane_width, layout.controls_height, "Controls and runtime summary"),
    ]:
        draw.rounded_rectangle((x, y, x + w, y + h), radius=18, fill="#FFFFFF", outline="#CBD5E1")
        draw.text((x + 18, y + 18), label, fill="#243449", font=lane_font)
    _draw_overview_png_perimeter(draw, layout, label_font, small_font, tiny_font)
    for edge in layout.main_edges:
        _draw_overview_png_edge(draw, edge, layout, small_font)
    for node_id, (x, y) in layout.positions.items():
        node = layout.nodes.get(node_id)
        if node:
            _draw_overview_png_node(draw, node, x, y, label_font, small_font, tiny_font)
            _draw_overview_png_node_badges(draw, node, x, y, layout, small_font)
    _draw_overview_png_runtime_chips(draw, layout, small_font)
    _draw_overview_png_control_cards(draw, layout, label_font, small_font, tiny_font)
    _draw_overview_png_ledger(draw, layout, small_font, tiny_font)
    draw.text((54, layout.height - 56), "Renderer rule: dataflow lines come only from calls / reads_from / writes_to / calls_external graph edges; runtime and controls stay as context.", fill="#475569", font=subtitle_font)
    image.save(path)
    return path


def _draw_overview_png_legend(draw: ImageDraw.ImageDraw, width: int, font: ImageFont.ImageFont) -> None:
    x = width - 560
    draw.rounded_rectangle((x, 24, x + 500, 100), radius=12, fill="#FFFFFF", outline="#CBD5E1")
    for idx, (color, label) in enumerate([
        ("#2563EB", "Service call"),
        ("#7C3AED", "Data read/write"),
        ("#F97316", "Pending external"),
        ("#D97706", "Runtime chip"),
        ("#DC2626", "Security badge"),
        ("#16A34A", "Monitoring badge"),
    ]):
        item_x = x + 24 + (idx % 3) * 160
        item_y = 48 + (idx // 3) * 29
        draw.rounded_rectangle((item_x, item_y, item_x + 16, item_y + 16), radius=4, fill=color)
        draw.text((item_x + 24, item_y + 1), label, fill="#475569", font=font)


def _draw_overview_png_perimeter(draw: ImageDraw.ImageDraw, layout: OverviewLayout, label_font: ImageFont.ImageFont, small_font: ImageFont.ImageFont, tiny_font: ImageFont.ImageFont) -> None:
    x = 120
    for idx, edge in enumerate(layout.perimeter_edges[:2]):
        source = layout.nodes.get(edge.source)
        target = layout.nodes.get(edge.target)
        if not source or not target:
            continue
        y = 174 + idx * 74
        _draw_overview_png_node_card(draw, source, x, y, 220, 64, "#475569", "#F8FAFC", label_font, small_font, tiny_font)
        _draw_overview_png_node_card(draw, target, x + 315, y, 230, 64, "#DC2626", "#FFF1F2", label_font, small_font, tiny_font)
        _draw_png_polyline_with_arrow(draw, [(x + 220, y + 32), (x + 315, y + 32)], "#DC2626", 3, False)
        _draw_overview_png_badge(draw, x + 240, y - 18, _overview_badge_text("protected_by", edge.label or edge.type), "#DC2626", "#FFF1F2", small_font)
    draw.rounded_rectangle((780, 168, 1200, 244), radius=12, fill="#F8FAFC", outline="#CBD5E1")
    draw.text((802, 184), "Display rule", fill="#334155", font=small_font)
    draw.text((802, 212), "Ingress context is not converted into dataflow without a graph edge.", fill="#475569", font=small_font)


def _draw_overview_png_edge(draw: ImageDraw.ImageDraw, edge: GraphEdge, layout: OverviewLayout, font: ImageFont.ImageFont) -> None:
    points = _overview_edge_points(edge, layout)
    if not points:
        return
    color = _overview_edge_color(edge)
    _draw_png_polyline_with_arrow(draw, points, color, int(float(_overview_edge_width(edge))), _status_kind(edge.status) == "pending")
    label_x, label_y = _overview_label_anchor(points)
    badge_x, badge_y = _overview_label_badge_position(edge, points, layout)
    draw.ellipse((label_x - 6, label_y - 6, label_x + 6, label_y + 6), fill=color)
    draw.line((label_x, label_y, label_x, badge_y + 14), fill=color, width=1)
    _draw_overview_png_badge(draw, badge_x, badge_y, _overview_edge_display_label(edge, layout), color, _overview_edge_label_fill(edge), font)


def _draw_overview_png_node(draw: ImageDraw.ImageDraw, node: GraphNode, x: int, y: int, label_font: ImageFont.ImageFont, small_font: ImageFont.ImageFont, tiny_font: ImageFont.ImageFont) -> None:
    color, fill = _overview_node_colors(node)
    _draw_overview_png_node_card(draw, node, x, y, OVERVIEW_NODE_WIDTH, OVERVIEW_NODE_HEIGHT, color, fill, label_font, small_font, tiny_font)


def _draw_overview_png_node_card(draw: ImageDraw.ImageDraw, node: GraphNode, x: int, y: int, width: int, height: int, color: str, fill: str, label_font: ImageFont.ImageFont, small_font: ImageFont.ImageFont, tiny_font: ImageFont.ImageFont) -> None:
    draw.rounded_rectangle((x + 5, y + 7, x + width + 5, y + height + 7), radius=8, fill="#CBD5E1")
    draw.rounded_rectangle((x, y, x + width, y + height), radius=8, fill=fill, outline=color, width=2)
    draw.rounded_rectangle((x, y, x + 9, y + height), radius=4, fill=color)
    draw.text((x + 20, y + 12), _display_type(node.type), fill=color, font=tiny_font)
    for idx, line in enumerate(_wrap_label(node.label, 26, 2)):
        draw.text((x + 20, y + 34 + idx * 15), line, fill="#111827", font=label_font)
    detail = _node_detail(node)
    if detail and height >= 82:
        draw.text((x + 20, y + height - 22), _clip(detail, 34), fill="#475569", font=tiny_font)
    badge = _status_badge(_status_kind(node.status))
    if badge:
        badge_text, badge_bg, badge_fg = badge
        _draw_overview_png_badge(draw, x + width - 92, y + 12, badge_text, color, badge_bg, small_font, text_fill=badge_fg)


def _draw_overview_png_node_badges(draw: ImageDraw.ImageDraw, node: GraphNode, x: int, y: int, layout: OverviewLayout, font: ImageFont.ImageFont) -> None:
    monitoring = [edge for edge in layout.context_edges if edge.type == "monitored_by" and edge.source == node.id]
    if monitoring:
        edge = monitoring[0]
        color = "#16A34A" if edge.label == "Covered" else "#F59E0B"
        fill = "#ECFDF5" if edge.label == "Covered" else "#FFF7ED"
        _draw_overview_png_badge(draw, x + OVERVIEW_NODE_WIDTH - 126, y + OVERVIEW_NODE_HEIGHT - 30, edge.label or "Monitored", color, fill, font)


def _draw_overview_png_runtime_chips(draw: ImageDraw.ImageDraw, layout: OverviewLayout, font: ImageFont.ImageFont) -> None:
    by_source: dict[str, list[GraphEdge]] = {}
    for edge in layout.runtime_edges:
        by_source.setdefault(edge.source, []).append(edge)
    for source, edges in by_source.items():
        position = layout.positions.get(source)
        if not position:
            continue
        x, y = position
        for idx, edge in enumerate(edges[:3]):
            target = layout.nodes.get(edge.target)
            target_label = target.label if target else edge.target
            _draw_overview_png_badge(draw, x + 12, y + OVERVIEW_NODE_HEIGHT + 14 + idx * 34, f"{edge.type}: {_clip(target_label, 24)}", "#D97706", "#FFFBEB", font)


def _draw_overview_png_control_cards(draw: ImageDraw.ImageDraw, layout: OverviewLayout, label_font: ImageFont.ImageFont, small_font: ImageFont.ImageFont, tiny_font: ImageFont.ImageFont) -> None:
    x = 120
    y = layout.controls_top + 60
    for idx, (title, heading, detail, color, fill, _edge) in enumerate(_overview_control_cards(layout)[:5]):
        card_x = x + idx * 265
        draw.rounded_rectangle((card_x, y, card_x + 235, y + 118), radius=10, fill=fill, outline=color, width=2)
        draw.text((card_x + 20, y + 16), title, fill=color, font=small_font)
        draw.text((card_x + 20, y + 48), _clip(heading, 24), fill="#111827", font=label_font)
        draw.text((card_x + 20, y + 78), _clip(detail, 36), fill="#475569", font=tiny_font)


def _draw_overview_png_ledger(draw: ImageDraw.ImageDraw, layout: OverviewLayout, small_font: ImageFont.ImageFont, tiny_font: ImageFont.ImageFont) -> None:
    x = layout.ledger_x
    draw.rounded_rectangle((x, 140, x + OVERVIEW_LEDGER_WIDTH, layout.height - 82), radius=18, fill="#FFFFFF", outline="#CBD5E1")
    draw.text((x + 24, 164), "Graph edge ledger", fill="#243449", font=small_font)
    draw.text((x + 24, 194), "Every rendered dataflow line maps to graph edge IDs.", fill="#475569", font=tiny_font)
    y = 232
    for idx, edge in enumerate(layout.main_edges, start=1):
        color = _overview_edge_color(edge)
        draw.rounded_rectangle((x + 24, y - 13, x + 66, y + 9), radius=5, fill=_overview_edge_label_fill(edge), outline=color)
        draw.text((x + 34, y - 9), f"E{idx}", fill=color, font=tiny_font)
        draw.text((x + 76, y - 14), edge.type, fill="#111827", font=small_font)
        draw.text((x + 76, y + 4), _clip(edge.source + " -> " + edge.target, 36), fill="#334155", font=tiny_font)
        draw.text((x + 76, y + 20), _clip(_overview_equivalent_record_ids(edge, layout.all_edges), 38), fill="#64748B", font=tiny_font)
        y += 72
    guard_y = layout.height - 312
    draw.rounded_rectangle((x + 24, guard_y, x + OVERVIEW_LEDGER_WIDTH - 24, guard_y + 78), radius=10, fill="#FFF7ED", outline="#F59E0B")
    draw.text((x + 42, guard_y + 16), "Semantic guardrail", fill="#92400E", font=small_font)
    draw.text((x + 42, guard_y + 42), "No dataflow unless it exists in graph.", fill="#92400E", font=tiny_font)


def _draw_overview_png_badge(draw: ImageDraw.ImageDraw, x: float, y: float, label: str, color: str, fill: str, font: ImageFont.ImageFont, text_fill: str = "#1F2937") -> None:
    width = max(66, min(220, _text_width(draw, label, font) + 34))
    draw.rounded_rectangle((x, y, x + width, y + 28), radius=14, fill=fill, outline=color, width=2)
    draw.ellipse((x + 9, y + 10, x + 17, y + 18), fill=color)
    draw.text((x + 24, y + 7), _clip(label, 30), fill=text_fill, font=font)


def _draw_png_polyline_with_arrow(draw: ImageDraw.ImageDraw, points: list[tuple[float, float]], color: str, width: int, dashed: bool) -> None:
    if dashed:
        _draw_polyline(draw, points, color, width=width, dashed=True)
    else:
        draw.line(points, fill=color, width=width, joint="curve")
    if len(points) > 1:
        _draw_arrowhead(draw, points[-2], points[-1], color)


def _write_overview_pdf(path: Path, view: View, layout: OverviewLayout) -> Path:
    png_path = path.with_suffix(".png")
    if not png_path.exists():
        _write_overview_png(png_path, view, layout)
    c = canvas.Canvas(str(path), pagesize=(layout.width, layout.height))
    c.drawImage(str(png_path), 0, 0, width=layout.width, height=layout.height)
    c.save()
    return path


def _write_overview_mermaid(path: Path, view: View, layout: OverviewLayout) -> Path:
    node_ids = {edge.source for edge in layout.main_edges}.union(edge.target for edge in layout.main_edges)
    lines = ["flowchart LR", f"  %% {view.title}", "  %% Overview main dataflow only; runtime and controls are context in SVG/PNG/PDF."]
    for node_id in sorted(node_ids, key=lambda item: (layout.positions.get(item, (9999, 9999))[1], layout.positions.get(item, (9999, 9999))[0], item)):
        node = layout.nodes.get(node_id)
        if not node:
            continue
        status = _status_kind(node.status)
        status_text = f"\\n{node.status}" if status != "confirmed" else ""
        class_suffix = f":::{status}" if status != "confirmed" else ""
        lines.append(f'  {_mmd_id(node.id)}["{node.label} ({node.type}){status_text}"]{class_suffix}')
    for edge in layout.main_edges:
        label = f"{edge.type}: {_edge_label(edge)}"
        lines.append(f"  {_mmd_id(edge.source)} -->|{label}| {_mmd_id(edge.target)}")
    lines.extend(
        [
            "  classDef auto stroke-dasharray: 6 4,stroke:#6366f1;",
            "  classDef pending stroke-dasharray: 6 4,stroke:#f59e0b,fill:#fff7ed;",
            "  classDef exception stroke:#a855f7,fill:#faf5ff;",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


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
    return view.filename == "05_security_monitoring_layer" or view.theme in {"dark", "security"}


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
