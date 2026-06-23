from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import landscape, letter
from reportlab.pdfgen import canvas

from .models import GraphEdge, GraphModel, GraphNode
from .util import xml_escape


@dataclass(frozen=True)
class View:
    filename: str
    title: str
    node_types: set[str]
    edge_types: set[str]


VIEWS = [
    View("00_overview", "Dataflow Project Data Flow Overview", {"gcp_project", "lb", "entry_point", "service", "server", "data_asset", "external_service", "firewall_rule", "cloud_armor_policy", "monitoring_control"}, {"contains", "runs_on", "calls", "calls_external", "reads_from", "writes_to", "allowed_by", "protected_by", "monitored_by"}),
    View("01_network_layer", "Network Layer", {"gcp_project", "network", "vpc", "subnet", "nat", "lb", "psc_peering", "firewall_rule", "cloud_armor_policy", "entry_point"}, {"contains", "allowed_by", "protected_by"}),
    View("02_compute_service_layer", "Compute And Service Layer", {"server", "service", "port"}, {"runs_on", "listens_on"}),
    View("03_service_dependency_layer", "Service Dependency Layer", {"service", "external_service", "data_asset", "dependency_ref", "firewall_rule"}, {"calls", "calls_external", "reads_from", "writes_to", "allowed_by"}),
    View("04_data_storage_layer", "Data And Storage Layer", {"service", "data_asset"}, {"reads_from", "writes_to"}),
    View("05_security_monitoring_layer", "Security And Monitoring Layer", {"service", "server", "firewall_rule", "cloud_armor_policy", "service_account", "iam_binding", "monitoring_control", "entry_point"}, {"allowed_by", "protected_by", "uses_sa", "has_binding", "monitored_by"}),
    View("06_cicd_delivery_layer", "CI/CD Delivery Layer", {"cicd_component", "service", "server"}, {"deployed_by", "runs_on"}),
]

TYPE_COLORS = {
    "gcp_project": "#E7F0FA",
    "network": "#D9F0EE",
    "vpc": "#D9F0EE",
    "subnet": "#D9F0EE",
    "nat": "#D9F0EE",
    "lb": "#D9F0EE",
    "psc_peering": "#D9F0EE",
    "server": "#F7E7D7",
    "service": "#FDECC8",
    "port": "#F8F2D9",
    "data_asset": "#E5E0F2",
    "external_service": "#EFEFEF",
    "firewall_rule": "#F7D6D0",
    "cloud_armor_policy": "#F7D6D0",
    "service_account": "#E9E4D6",
    "iam_binding": "#E9E4D6",
    "monitoring_control": "#DCEBD9",
    "cicd_component": "#D8E4F2",
    "entry_point": "#EFEFEF",
    "dependency_ref": "#F8F2D9",
}


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


def _select_view(graph: GraphModel, view: View) -> tuple[list[GraphNode], list[GraphEdge]]:
    included_edges = [edge for edge in graph.edges if edge.type in view.edge_types]
    node_ids = {edge.source for edge in included_edges}.union(edge.target for edge in included_edges)
    nodes = [node for node in graph.nodes.values() if node.type in view.node_types or node.id in node_ids]
    node_ids = {node.id for node in nodes}
    edges = [edge for edge in included_edges if edge.source in node_ids and edge.target in node_ids]
    if not nodes:
        nodes = list(graph.nodes.values())[:12]
    return nodes, edges


def _layout(nodes: list[GraphNode]) -> dict[str, tuple[int, int]]:
    type_order = {
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
        "service": 3,
        "port": 4,
        "data_asset": 5,
        "external_service": 5,
        "service_account": 5,
        "iam_binding": 6,
        "firewall_rule": 6,
        "cloud_armor_policy": 6,
        "monitoring_control": 7,
        "dependency_ref": 4,
    }
    columns: dict[int, list[GraphNode]] = {}
    for node in sorted(nodes, key=lambda item: (type_order.get(item.type, 9), item.label)):
        columns.setdefault(type_order.get(node.type, 9), []).append(node)
    positions: dict[str, tuple[int, int]] = {}
    x_start, x_gap, y_start, y_gap = 60, 190, 95, 86
    for col_idx, col in enumerate(sorted(columns)):
        for row_idx, node in enumerate(columns[col]):
            positions[node.id] = (x_start + col_idx * x_gap, y_start + row_idx * y_gap)
    return positions


def _size(positions: dict[str, tuple[int, int]]) -> tuple[int, int]:
    if not positions:
        return 900, 480
    width = max(x for x, _ in positions.values()) + 230
    height = max(y for _, y in positions.values()) + 120
    return max(width, 900), max(height, 480)


def _write_svg(path: Path, view: View, nodes: list[GraphNode], edges: list[GraphEdge], positions: dict[str, tuple[int, int]]) -> Path:
    width, height = _size(positions)
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="8" refY="3" orient="auto"><path d="M0,0 L8,3 L0,6 Z" fill="#555"/></marker></defs>',
        '<rect width="100%" height="100%" fill="#fbfbf8"/>',
        f'<text x="32" y="38" font-family="Arial" font-size="22" font-weight="700" fill="#222">{xml_escape(view.title)}</text>',
    ]
    for edge in edges:
        if edge.source not in positions or edge.target not in positions:
            continue
        x1, y1 = positions[edge.source]
        x2, y2 = positions[edge.target]
        lines.append(f'<line x1="{x1 + 150}" y1="{y1 + 28}" x2="{x2}" y2="{y2 + 28}" stroke="#555" stroke-width="1.4" marker-end="url(#arrow)" opacity="0.72"/>')
        if edge.label:
            mx, my = (x1 + x2 + 150) / 2, (y1 + y2 + 56) / 2 - 6
            lines.append(f'<text x="{mx}" y="{my}" font-family="Arial" font-size="10" fill="#555">{xml_escape(edge.label[:36])}</text>')
    for node in nodes:
        x, y = positions.get(node.id, (40, 80))
        fill = TYPE_COLORS.get(node.type, "#ECECEC")
        stroke_dash = ' stroke-dasharray="5 3"' if node.status == "Auto_Detected" else ""
        lines.append(f'<rect x="{x}" y="{y}" width="150" height="56" rx="6" fill="{fill}" stroke="#333" stroke-width="1"{stroke_dash}/>')
        lines.append(f'<text x="{x + 10}" y="{y + 22}" font-family="Arial" font-size="12" font-weight="700" fill="#222">{xml_escape(_clip(node.label, 20))}</text>')
        lines.append(f'<text x="{x + 10}" y="{y + 42}" font-family="Arial" font-size="10" fill="#555">{xml_escape(node.type)}</text>')
    lines.append("</svg>")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _write_png(path: Path, view: View, nodes: list[GraphNode], edges: list[GraphEdge], positions: dict[str, tuple[int, int]]) -> Path:
    width, height = _size(positions)
    image = Image.new("RGB", (width, height), "#fbfbf8")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    draw.text((32, 22), view.title, fill="#222", font=font)
    for edge in edges:
        if edge.source not in positions or edge.target not in positions:
            continue
        x1, y1 = positions[edge.source]
        x2, y2 = positions[edge.target]
        draw.line((x1 + 150, y1 + 28, x2, y2 + 28), fill="#555", width=2)
    for node in nodes:
        x, y = positions.get(node.id, (40, 80))
        draw.rounded_rectangle((x, y, x + 150, y + 56), radius=6, fill=TYPE_COLORS.get(node.type, "#ECECEC"), outline="#333")
        draw.text((x + 9, y + 13), _clip(node.label, 20), fill="#222", font=font)
        draw.text((x + 9, y + 34), node.type, fill="#555", font=font)
    image.save(path)
    return path


def _write_pdf(path: Path, view: View, nodes: list[GraphNode], edges: list[GraphEdge], positions: dict[str, tuple[int, int]]) -> Path:
    width, height = _size(positions)
    page_size = (max(width, landscape(letter)[0]), max(height, landscape(letter)[1]))
    c = canvas.Canvas(str(path), pagesize=page_size)
    c.setFillColorRGB(0.98, 0.98, 0.96)
    c.rect(0, 0, page_size[0], page_size[1], fill=1, stroke=0)
    c.setFillColorRGB(0.13, 0.13, 0.13)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(32, page_size[1] - 38, view.title)
    for edge in edges:
        if edge.source not in positions or edge.target not in positions:
            continue
        x1, y1 = positions[edge.source]
        x2, y2 = positions[edge.target]
        c.line(x1 + 150, page_size[1] - (y1 + 28), x2, page_size[1] - (y2 + 28))
    for node in nodes:
        x, y = positions.get(node.id, (40, 80))
        r, g, b = _hex_to_rgb(TYPE_COLORS.get(node.type, "#ECECEC"))
        c.setFillColorRGB(r, g, b)
        c.roundRect(x, page_size[1] - y - 56, 150, 56, 6, fill=1, stroke=1)
        c.setFillColorRGB(0.13, 0.13, 0.13)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(x + 9, page_size[1] - y - 22, _clip(node.label, 20))
        c.setFont("Helvetica", 8)
        c.drawString(x + 9, page_size[1] - y - 42, node.type)
    c.save()
    return path


def _write_mermaid(path: Path, view: View, nodes: list[GraphNode], edges: list[GraphEdge]) -> Path:
    lines = ["flowchart LR", f"  %% {view.title}"]
    for node in nodes:
        lines.append(f"  { _mmd_id(node.id) }[\"{node.label} ({node.type})\"]")
    for edge in edges:
        if edge.source in {node.id for node in nodes} and edge.target in {node.id for node in nodes}:
            label = f"|{edge.type}|" if not edge.label else f"|{edge.type}: {edge.label}|"
            lines.append(f"  {_mmd_id(edge.source)} -->{label} {_mmd_id(edge.target)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _mmd_id(value: str) -> str:
    return "n_" + "".join(ch if ch.isalnum() else "_" for ch in value)


def _clip(value: str, length: int) -> str:
    return value if len(value) <= length else value[: max(0, length - 3)] + "..."


def _hex_to_rgb(value: str) -> tuple[float, float, float]:
    value = value.lstrip("#")
    return int(value[0:2], 16) / 255, int(value[2:4], 16) / 255, int(value[4:6], 16) / 255
