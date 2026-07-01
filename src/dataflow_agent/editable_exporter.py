from __future__ import annotations

from pathlib import Path

from .models import GraphEdge, GraphNode
from .util import safe_id, xml_escape


def write_editable_outputs(
    base_path: Path,
    title: str,
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    positions: dict[str, tuple[int, int]],
    *,
    node_width: int,
    node_height: int,
) -> list[Path]:
    node_ids = {node.id for node in nodes}
    visible_edges = [edge for edge in edges if edge.source in node_ids and edge.target in node_ids]
    return [
        _write_drawio(base_path.with_suffix(".drawio"), title, nodes, visible_edges, positions, node_width, node_height),
        _write_graphml(base_path.with_suffix(".graphml"), title, nodes, visible_edges),
    ]


def _write_drawio(
    path: Path,
    title: str,
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    positions: dict[str, tuple[int, int]],
    node_width: int,
    node_height: int,
) -> Path:
    lines = [
        '<mxfile host="app.diagrams.net" type="device">',
        f'  <diagram id="{xml_escape(safe_id(path.stem))}" name="{xml_escape(title)}">',
        '    <mxGraphModel dx="1600" dy="1000" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="2200" pageHeight="1400" math="0" shadow="0">',
        "      <root>",
        '        <mxCell id="0"/>',
        '        <mxCell id="1" parent="0"/>',
    ]
    node_cell_ids: dict[str, str] = {}
    for node in nodes:
        cell_id = _cell_id("node", node.id)
        node_cell_ids[node.id] = cell_id
        x, y = positions.get(node.id, (80, 160))
        lines.append(
            "        "
            f'<mxCell id="{cell_id}" value="{xml_escape(_node_value(node))}" style="{_node_style(node)}" vertex="1" parent="1" '
            f'graphNodeId="{xml_escape(node.id)}" nodeType="{xml_escape(node.type)}" status="{xml_escape(node.status)}" '
            f'sourceSheet="{xml_escape(node.sheet)}" layer="{xml_escape(node.layer)}" group="{xml_escape(node.group)}">'
        )
        lines.append(f'          <mxGeometry x="{x}" y="{y}" width="{node_width}" height="{node_height}" as="geometry"/>')
        lines.append("        </mxCell>")
    for edge in edges:
        if edge.source not in node_cell_ids or edge.target not in node_cell_ids:
            continue
        source_sheet = str(edge.metadata.get("source_sheet", "")) if isinstance(edge.metadata, dict) else ""
        record_id = str(edge.metadata.get("record_id", "")) if isinstance(edge.metadata, dict) else ""
        lines.append(
            "        "
            f'<mxCell id="{_cell_id("edge", edge.id)}" value="{xml_escape(_edge_value(edge))}" style="{_edge_style(edge)}" edge="1" parent="1" '
            f'source="{node_cell_ids[edge.source]}" target="{node_cell_ids[edge.target]}" graphEdgeId="{xml_escape(edge.id)}" '
            f'edgeType="{xml_escape(edge.type)}" status="{xml_escape(edge.status)}" sourceNodeId="{xml_escape(edge.source)}" '
            f'targetNodeId="{xml_escape(edge.target)}" sourceSheet="{xml_escape(source_sheet)}" sourceRecord="{xml_escape(record_id)}" '
            f'evidenceId="{xml_escape(edge.evidence_id)}">'
        )
        lines.append('          <mxGeometry relative="1" as="geometry"/>')
        lines.append("        </mxCell>")
    lines.extend(["      </root>", "    </mxGraphModel>", "  </diagram>", "</mxfile>"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_graphml(path: Path, title: str, nodes: list[GraphNode], edges: list[GraphEdge]) -> Path:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
        '  <key id="label" for="all" attr.name="label" attr.type="string"/>',
        '  <key id="type" for="all" attr.name="type" attr.type="string"/>',
        '  <key id="status" for="all" attr.name="status" attr.type="string"/>',
        '  <key id="source_sheet" for="all" attr.name="source_sheet" attr.type="string"/>',
        '  <key id="source_record" for="edge" attr.name="source_record" attr.type="string"/>',
        '  <key id="evidence_id" for="edge" attr.name="evidence_id" attr.type="string"/>',
        f'  <graph id="{xml_escape(safe_id(title))}" edgedefault="directed">',
    ]
    for node in nodes:
        lines.append(f'    <node id="{xml_escape(node.id)}">')
        for key, value in (("label", node.label), ("type", node.type), ("status", node.status), ("source_sheet", node.sheet)):
            lines.append(f'      <data key="{key}">{xml_escape(value)}</data>')
        lines.append("    </node>")
    node_ids = {node.id for node in nodes}
    for edge in edges:
        if edge.source not in node_ids or edge.target not in node_ids:
            continue
        source_sheet = str(edge.metadata.get("source_sheet", "")) if isinstance(edge.metadata, dict) else ""
        record_id = str(edge.metadata.get("record_id", "")) if isinstance(edge.metadata, dict) else ""
        lines.append(f'    <edge id="{xml_escape(edge.id)}" source="{xml_escape(edge.source)}" target="{xml_escape(edge.target)}">')
        for key, value in (
            ("label", edge.label or edge.type),
            ("type", edge.type),
            ("status", edge.status),
            ("source_sheet", source_sheet),
            ("source_record", record_id),
            ("evidence_id", edge.evidence_id),
        ):
            lines.append(f'      <data key="{key}">{xml_escape(value)}</data>')
        lines.append("    </edge>")
    lines.extend(["  </graph>", "</graphml>"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _node_value(node: GraphNode) -> str:
    detail = node.metadata.get("priority") or node.metadata.get("role") or node.metadata.get("coverage") or node.sheet
    return f"{node.label}<br><font style=\"font-size:10px\">{node.type} | {detail}</font>"


def _edge_value(edge: GraphEdge) -> str:
    value = edge.label or edge.type
    if edge.status != "Confirmed":
        value = f"{edge.status}: {value}"
    return value


def _cell_id(prefix: str, value: str) -> str:
    return f"{prefix}_{safe_id(value)}"


def _node_style(node: GraphNode) -> str:
    fill, stroke = _colors_for(node.type)
    return (
        "rounded=1;whiteSpace=wrap;html=1;arcSize=8;"
        f"fillColor={fill};strokeColor={stroke};fontColor=#111827;"
        "spacing=10;fontSize=12;align=left;verticalAlign=middle;"
    )


def _edge_style(edge: GraphEdge) -> str:
    stroke = _edge_color(edge)
    dashed = "dashed=1;dashPattern=8 6;" if edge.type in {"allowed_by", "protected_by", "uses_sa", "has_binding", "monitored_by", "runs_on", "runs_on_runtime", "uses_runtime"} or edge.status in {"Pending_Confirmation", "Auto_Detected", "Accepted_Exception"} else ""
    return (
        "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;"
        f"strokeColor={stroke};fontColor={stroke};strokeWidth=2;endArrow=block;endFill=1;{dashed}"
    )


def _colors_for(node_type: str) -> tuple[str, str]:
    colors = {
        "service": ("#DBEAFE", "#2563EB"),
        "data_asset": ("#F3E8FF", "#9333EA"),
        "external_service": ("#F8FAFC", "#64748B"),
        "runtime": ("#FEF3C7", "#D97706"),
        "server": ("#FEF3C7", "#D97706"),
        "firewall_rule": ("#FEE2E2", "#DC2626"),
        "cloud_armor_policy": ("#FEE2E2", "#DC2626"),
        "service_account": ("#F5F3FF", "#6D28D9"),
        "iam_binding": ("#F5F3FF", "#6D28D9"),
        "monitoring_control": ("#DCFCE7", "#16A34A"),
        "entry_point": ("#F1F5F9", "#475569"),
    }
    return colors.get(node_type, ("#FFFFFF", "#64748B"))


def _edge_color(edge: GraphEdge) -> str:
    if edge.status == "Pending_Confirmation":
        return "#D97706"
    if edge.status == "Accepted_Exception":
        return "#9333EA"
    if edge.type in {"allowed_by", "protected_by"}:
        return "#DC2626"
    if edge.type in {"monitored_by"}:
        return "#16A34A"
    if edge.type in {"uses_sa", "has_binding"}:
        return "#6D28D9"
    if edge.type in {"runs_on", "runs_on_runtime", "uses_runtime"}:
        return "#D97706"
    return "#2563EB"
