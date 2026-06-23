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
        nodes, edges = _select_view(graph, view)
        positions = _layout(nodes)
        outputs.append(_write_svg(diagrams_dir / f"{view.filename}.svg", view, nodes, edges, positions))
        outputs.append(_write_png(diagrams_dir / f"{view.filename}.png", view, nodes, edges, positions))
        outputs.append(_write_pdf(diagrams_dir / f"{view.filename}.pdf", view, nodes, edges, positions))
        outputs.append(_write_mermaid(diagrams_dir / f"{view.filename}.mmd", view, nodes, edges))
    return outputs


def render_service_drilldown(graph: GraphModel, service_id: str, diagrams_dir: Path) -> list[Path]:
    if service_id not in graph.nodes or graph.nodes[service_id].type != "service":
        raise ValueError(f"Service {service_id} does not exist in graph.")
    diagrams_dir.mkdir(parents=True, exist_ok=True)
    nodes, edges = _select_service_drilldown(graph, service_id)
    positions = _layout(nodes)
    base = f"service_drilldown_{safe_id(service_id)}"
    view = View(base, f"Service Drilldown: {service_id}", {node.type for node in nodes}, {edge.type for edge in edges})
    return [
        _write_svg(diagrams_dir / f"{base}.svg", view, nodes, edges, positions),
        _write_png(diagrams_dir / f"{base}.png", view, nodes, edges, positions),
        _write_pdf(diagrams_dir / f"{base}.pdf", view, nodes, edges, positions),
        _write_mermaid(diagrams_dir / f"{base}.mmd", view, nodes, edges),
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


def _select_service_drilldown(graph: GraphModel, service_id: str) -> tuple[list[GraphNode], list[GraphEdge]]:
    node_ids = {service_id}
    selected_edges: list[GraphEdge] = []
    for edge in graph.edges:
        if edge.source == service_id or edge.target == service_id:
            selected_edges.append(edge)
            node_ids.update({edge.source, edge.target})
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
    return view.filename == "05_security_monitoring_layer"


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
