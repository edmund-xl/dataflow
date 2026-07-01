from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas

from .editable_exporter import write_editable_outputs
from .models import GraphEdge, GraphModel, GraphNode
from .util import xml_escape
from .diagram_renderer import (
    TYPE_ORDER,
    View,
    _clip,
    _display_type,
    _draw_arrowhead,
    _draw_polyline,
    _edge_accessible_label,
    _edge_label,
    _edge_risk_level,
    _font,
    _mmd_id,
    _node_accessible_label,
    _node_detail,
    _node_risk_level,
    _status_badge,
    _status_kind,
    _text_width,
    _wrap_label,
)


OVERVIEW_DATAFLOW_EDGES = {"calls", "calls_external", "reads_from", "writes_to", "depends_on"}
OVERVIEW_CONTEXT_EDGES = {"runs_on", "runs_on_runtime", "allowed_by", "protected_by", "uses_sa", "monitored_by"}
OVERVIEW_NODE_WIDTH = 230
OVERVIEW_NODE_HEIGHT = 94
OVERVIEW_LEDGER_WIDTH = 430
LEFT_MARGIN = 72


def render_overview_outputs(graph: GraphModel, diagrams_dir: Path, view: View) -> list[Path]:
    layout = _overview_layout(graph)
    visible_nodes = [node for node_id, node in layout.nodes.items() if node_id in layout.positions]
    outputs = [
        _write_overview_svg(diagrams_dir / f"{view.filename}.svg", view, layout),
        _write_overview_png(diagrams_dir / f"{view.filename}.png", view, layout),
        _write_overview_pdf(diagrams_dir / f"{view.filename}.pdf", view, layout),
        _write_overview_mermaid(diagrams_dir / f"{view.filename}.mmd", view, layout),
    ]
    outputs.extend(
        write_editable_outputs(
            diagrams_dir / view.filename,
            view.title,
            visible_nodes,
            layout.main_edges,
            layout.positions,
            node_width=OVERVIEW_NODE_WIDTH,
            node_height=OVERVIEW_NODE_HEIGHT,
        )
    )
    return outputs


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
        _overview_push_terminal_nodes_right(levels, nodes, component_edges)
        rows_by_level: dict[int, list[str]] = {}
        for node_id in component:
            rows_by_level.setdefault(levels.get(node_id, 0), []).append(node_id)
        max_rows = 1
        for level, ids in rows_by_level.items():
            ids.sort(key=lambda node_id: _overview_node_sort(nodes.get(node_id)))
            max_rows = max(max_rows, len(ids))
            for row_index, node_id in enumerate(ids):
                x = 120 + level * (OVERVIEW_NODE_WIDTH + 150)
                y = y_cursor + row_index * (OVERVIEW_NODE_HEIGHT + 104)
                positions[node_id] = (x, y)
        y_cursor += max_rows * (OVERVIEW_NODE_HEIGHT + 104) + 80
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


def _overview_push_terminal_nodes_right(levels: dict[str, int], nodes: dict[str, GraphNode], edges: list[GraphEdge]) -> None:
    terminal_types = {"external_service", "data_asset"}
    for edge in edges:
        target = nodes.get(edge.target)
        if not target or target.type not in terminal_types:
            continue
        if edge.source in levels:
            levels[edge.target] = max(levels.get(edge.target, 0), levels[edge.source] + 2)


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
    edge_number = layout.main_edges.index(edge) + 1 if edge in layout.main_edges else 0
    lines.append(f'<g role="img" aria-label="{xml_escape(_edge_accessible_label(edge))}" data-risk-level="{risk}">')
    lines.append(f'<title>{xml_escape(_edge_accessible_label(edge))}</title>')
    lines.append(f'<polyline points="{point_text}" fill="none" stroke="#FFFFFF" stroke-width="9.5" stroke-linecap="round" stroke-linejoin="round" data-overview-role="main-dataflow-halo" data-edge-id="{xml_escape(edge.id)}" data-edge-number="E{edge_number}"/>')
    lines.append(f'<polyline points="{point_text}" fill="none" stroke="{color}" stroke-width="{_overview_edge_width(edge)}" stroke-linecap="round" stroke-linejoin="round" marker-end="url(#{marker})"{dash} data-overview-role="main-dataflow" data-edge-id="{xml_escape(edge.id)}" data-edge-number="E{edge_number}" data-edge-type="{xml_escape(edge.type)}" data-source="{xml_escape(edge.source)}" data-target="{xml_escape(edge.target)}"/>')
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
        lines.append(f'<text x="{x + 76}" y="{y + 16}" font-family="Arial, Helvetica, sans-serif" font-size="10" fill="#334155">{xml_escape(_clip(edge.source + " -> " + edge.target, 48))}</text>')
        lines.append(f'<text x="{x + 76}" y="{y + 32}" font-family="Arial, Helvetica, sans-serif" font-size="10" fill="#475569">{xml_escape(_clip(_overview_edge_ledger_label(edge), 48))}</text>')
        lines.append(f'<text x="{x + 76}" y="{y + 48}" font-family="Arial, Helvetica, sans-serif" font-size="10" fill="#64748B">{xml_escape(_clip(record_ids, 48))}</text>')
        y += 86
    lines.append(f'<rect x="{x + 24}" y="{layout.height - 312}" width="{OVERVIEW_LEDGER_WIDTH - 48}" height="78" rx="10" fill="#FFF7ED" stroke="#F59E0B" stroke-width="1.5"/>')
    lines.append(f'<text x="{x + 42}" y="{layout.height - 282}" font-family="Arial, Helvetica, sans-serif" font-size="12" font-weight="700" fill="#92400E">Semantic guardrail</text>')
    lines.append(f'<text x="{x + 42}" y="{layout.height - 258}" font-family="Arial, Helvetica, sans-serif" font-size="10" fill="#92400E">No relationship is rendered as dataflow unless it exists in graph.</text>')
    lines.append("</g>")


def _append_overview_svg_badge(lines: list[str], x: float, y: float, label: str, color: str, fill: str, role: str, edge: GraphEdge | None = None) -> None:
    width = 46 if role == "main-dataflow-label" and label.startswith("E") and label[1:].isdigit() else max(66, min(220, len(label) * 7 + 34))
    edge_attrs = ""
    if edge:
        badge_attr = f' data-edge-badge-id="{xml_escape(edge.id)}"' if role == "main-dataflow-label" else ""
        edge_attrs = f'{badge_attr} data-edge-id="{xml_escape(edge.id)}" data-edge-type="{xml_escape(edge.type)}" data-source="{xml_escape(edge.source)}" data-target="{xml_escape(edge.target)}"'
    lines.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{width}" height="28" rx="14" fill="{fill}" stroke="{color}" stroke-width="1.5" data-overview-role="{role}"{edge_attrs}/>')
    lines.append(f'<circle cx="{x + 13:.1f}" cy="{y + 14:.1f}" r="4" fill="{color}"/>')
    lines.append(f'<text x="{x + 24:.1f}" y="{y + 19:.1f}" font-family="Arial, Helvetica, sans-serif" font-size="12" font-weight="700" fill="#1F2937">{xml_escape(_clip(label, 30))}</text>')


def _overview_edge_points(edge: GraphEdge, layout: OverviewLayout) -> list[tuple[float, float]]:
    source = layout.positions.get(edge.source)
    target = layout.positions.get(edge.target)
    if not source or not target:
        return []
    outgoing = _overview_edges_by_node(layout.main_edges, "source")
    incoming = _overview_edges_by_node(layout.main_edges, "target")
    source_port = _overview_port_offset(edge, outgoing.get(edge.source, []), OVERVIEW_NODE_HEIGHT, "out")
    target_port = _overview_port_offset(edge, incoming.get(edge.target, []), OVERVIEW_NODE_HEIGHT, "in")
    route_lane = _overview_route_lane(edge, layout)
    sx = source[0] + OVERVIEW_NODE_WIDTH
    sy = source[1] + source_port
    tx = target[0]
    ty = target[1] + target_port
    source_rank = _overview_node_lane_rank(edge.source, layout)
    target_rank = _overview_node_lane_rank(edge.target, layout)
    target_node = layout.nodes.get(edge.target)
    if edge.type == "calls_external" or (target_node and target_node.type in {"external_service", "data_asset"}):
        terminal_lane = _overview_terminal_lane_index(edge, layout)
        lane_y = _overview_terminal_bus_y(edge, layout, source, target, terminal_lane)
        lane_x = sx + 42 + terminal_lane * 26
        return [(sx, sy), (lane_x, sy), (lane_x, lane_y), (tx - 56, lane_y), (tx - 56, ty), (tx, ty)]
    if target[1] > source[1] + 70:
        lane_x = sx + 42 + route_lane * 18
        route_y = ty
        return [(sx, sy), (lane_x, sy), (lane_x, route_y), (tx, route_y)]
    if sx <= tx:
        distance = max(1, tx - sx)
        lane_x = sx + min(max(54, distance * 0.34), distance - 34 if distance > 88 else distance * 0.5) + route_lane * 16
        lane_x = min(max(sx + 34, lane_x), tx - 34 if tx - sx > 76 else sx + distance / 2)
        if abs(sy - ty) < 10:
            elbow_y = sy + (route_lane - 1) * 16
            return [(sx, sy), (lane_x, sy), (lane_x, elbow_y), (tx, elbow_y), (tx, ty)]
        return [(sx, sy), (lane_x, sy), (lane_x, ty), (tx, ty)]
    outer_x = max(source[0], target[0]) + OVERVIEW_NODE_WIDTH + 58 + route_lane * 24
    route_y = max(sy, ty) + 48 + abs(target_rank - source_rank) * 10
    return [(sx, sy), (outer_x, sy), (outer_x, route_y), (tx - 52, route_y), (tx - 52, ty), (tx, ty)]


def _overview_edges_by_node(edges: list[GraphEdge], side: str) -> dict[str, list[GraphEdge]]:
    grouped: dict[str, list[GraphEdge]] = {}
    for edge in edges:
        key = edge.source if side == "source" else edge.target
        grouped.setdefault(key, []).append(edge)
    for node_edges in grouped.values():
        node_edges.sort(key=lambda item: (_overview_edge_type_rank(item), _edge_number(item), item.source, item.target, item.id))
    return grouped


def _overview_port_offset(edge: GraphEdge, node_edges: list[GraphEdge], node_height: int, side: str) -> float:
    if not node_edges:
        return node_height * 0.52
    count = len(node_edges)
    if count == 1:
        return node_height * 0.52
    top = 26.0
    bottom = node_height - 24.0
    index = node_edges.index(edge) if edge in node_edges else 0
    if side == "in":
        index = min(count - 1, max(0, index))
    return top + (bottom - top) * index / max(1, count - 1)


def _overview_route_lane(edge: GraphEdge, layout: OverviewLayout) -> int:
    same_source = [item for item in layout.main_edges if item.source == edge.source]
    same_target = [item for item in layout.main_edges if item.target == edge.target]
    same_pair = [item for item in layout.main_edges if item.source == edge.source and item.target == edge.target]
    source_index = same_source.index(edge) if edge in same_source else 0
    target_index = same_target.index(edge) if edge in same_target else 0
    pair_index = same_pair.index(edge) if edge in same_pair else 0
    return (_overview_edge_type_rank(edge) + source_index * 2 + target_index + pair_index) % 5


def _overview_terminal_lane_index(edge: GraphEdge, layout: OverviewLayout) -> int:
    direction = _overview_terminal_direction(edge, layout)
    terminal_edges = [
        item
        for item in layout.main_edges
        if _overview_terminal_direction(item, layout) == direction
    ]
    terminal_edges.sort(
        key=lambda item: (
            _overview_node_lane_rank(item.source, layout),
            _overview_node_lane_rank(item.target, layout),
            _overview_edge_type_rank(item),
            _edge_number(item),
            item.source,
            item.target,
            item.id,
        )
    )
    return terminal_edges.index(edge) if edge in terminal_edges else 0


def _overview_terminal_direction(edge: GraphEdge, layout: OverviewLayout) -> str:
    target_node = layout.nodes.get(edge.target)
    if not (edge.type == "calls_external" or (target_node and target_node.type in {"external_service", "data_asset"})):
        return "non_terminal"
    source = layout.positions.get(edge.source)
    target = layout.positions.get(edge.target)
    if not source or not target:
        return "same"
    if target[1] > source[1] + OVERVIEW_NODE_HEIGHT * 0.45:
        return "down"
    if target[1] < source[1] - OVERVIEW_NODE_HEIGHT * 0.45:
        return "up"
    if source[1] <= layout.main_top + OVERVIEW_NODE_HEIGHT * 1.2:
        return "same_top"
    return "same_bottom"


def _overview_node_lane_rank(node_id: str, layout: OverviewLayout) -> int:
    position = layout.positions.get(node_id)
    if not position:
        return 0
    return int(position[1] // max(1, OVERVIEW_NODE_HEIGHT + 74))


def _overview_edge_type_rank(edge: GraphEdge) -> int:
    return {"calls": 0, "depends_on": 1, "calls_external": 2, "writes_to": 3, "reads_from": 4}.get(edge.type, 5)


def _overview_terminal_bus_y(
    edge: GraphEdge,
    layout: OverviewLayout,
    source: tuple[int, int],
    target: tuple[int, int],
    lane: int,
) -> float:
    source_y = source[1]
    target_y = target[1]
    direction = _overview_terminal_direction(edge, layout)
    top_bus = min(source_y, target_y) - 38 - lane * 16
    bottom_bus = max(source_y, target_y) + OVERVIEW_NODE_HEIGHT + 38 + lane * 16
    if direction in {"up", "same_top"}:
        return max(layout.main_top + 72, top_bus)
    if direction in {"down", "same_bottom"}:
        return min(layout.controls_top - 72, bottom_bus)
    return max(layout.main_top + 72, min(layout.controls_top - 72, bottom_bus))


def _overview_label_anchor(points: list[tuple[float, float]]) -> tuple[float, float]:
    if len(points) < 2:
        return 120, 120
    longest = max(zip(points, points[1:]), key=lambda pair: ((pair[1][0] - pair[0][0]) ** 2 + (pair[1][1] - pair[0][1]) ** 2))
    return (longest[0][0] + longest[1][0]) / 2, (longest[0][1] + longest[1][1]) / 2


def _overview_label_badge_position(edge: GraphEdge, points: list[tuple[float, float]], layout: OverviewLayout) -> tuple[float, float]:
    label_x, label_y = _overview_label_anchor(points)
    source = layout.positions.get(edge.source, (0, 0))
    target = layout.positions.get(edge.target, (0, 0))
    target_node = layout.nodes.get(edge.target)
    if edge.type == "calls_external" or (target_node and target_node.type in {"external_service", "data_asset"}):
        lane = _overview_route_lane(edge, layout)
        vertical_shift = -46 if lane % 2 else 18
        return label_x - 96, label_y + vertical_shift
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
    return f"E{index}" if index else "E"


def _overview_edge_ledger_label(edge: GraphEdge) -> str:
    status = f" | {edge.status}" if edge.status else ""
    action = "write " if edge.type == "writes_to" else "read " if edge.type == "reads_from" else ""
    value = edge.label or edge.type
    return f"{action}{value}{status}".strip()


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
    _draw_png_polyline_with_arrow(draw, points, "#FFFFFF", 10, False)
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
        draw.text((x + 76, y + 4), _clip(edge.source + " -> " + edge.target, 48), fill="#334155", font=tiny_font)
        draw.text((x + 76, y + 20), _clip(_overview_edge_ledger_label(edge), 48), fill="#475569", font=tiny_font)
        draw.text((x + 76, y + 36), _clip(_overview_equivalent_record_ids(edge, layout.all_edges), 48), fill="#64748B", font=tiny_font)
        y += 86
    guard_y = layout.height - 312
    draw.rounded_rectangle((x + 24, guard_y, x + OVERVIEW_LEDGER_WIDTH - 24, guard_y + 78), radius=10, fill="#FFF7ED", outline="#F59E0B")
    draw.text((x + 42, guard_y + 16), "Semantic guardrail", fill="#92400E", font=small_font)
    draw.text((x + 42, guard_y + 42), "No dataflow unless it exists in graph.", fill="#92400E", font=tiny_font)


def _draw_overview_png_badge(draw: ImageDraw.ImageDraw, x: float, y: float, label: str, color: str, fill: str, font: ImageFont.ImageFont, text_fill: str = "#1F2937") -> None:
    width = 46 if label.startswith("E") and label[1:].isdigit() else max(66, min(220, _text_width(draw, label, font) + 34))
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
