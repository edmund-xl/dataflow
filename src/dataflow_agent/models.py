from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


Row = dict[str, str]


@dataclass
class WorkbookData:
    path: Path
    sheets: dict[str, list[Row]]
    headers: dict[str, list[str]]
    metadata: dict[str, str]
    enums: dict[str, list[str]]


@dataclass
class Finding:
    gate: str
    severity: str
    sheet: str
    row_id: str
    field: str
    message: str
    suggested_action: str = ""
    status: str = "Open"
    owner: str = ""
    due_date: str = ""
    exception_decision: str = ""
    evidence_id: str = ""

    def as_row(self) -> dict[str, str]:
        return {
            "Gate": self.gate,
            "Severity": self.severity,
            "Sheet": self.sheet,
            "Row_ID": self.row_id,
            "Field": self.field,
            "Message": self.message,
            "Suggested_Action": self.suggested_action,
            "Status": self.status,
            "Owner": self.owner,
            "Due_Date": self.due_date,
            "Exception_Decision": self.exception_decision,
            "Evidence_ID": self.evidence_id,
        }


@dataclass
class ValidationResult:
    findings: list[Finding] = field(default_factory=list)

    @property
    def blocking_findings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity in {"P0", "P1"}]

    @property
    def ok(self) -> bool:
        return not self.blocking_findings

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)


@dataclass
class GraphNode:
    id: str
    type: str
    label: str
    sheet: str
    status: str = "Confirmed"
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "label": self.label,
            "sheet": self.sheet,
            "status": self.status,
            "metadata": self.metadata,
        }


@dataclass
class GraphEdge:
    id: str
    type: str
    source: str
    target: str
    label: str = ""
    status: str = "Confirmed"
    evidence_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "source": self.source,
            "target": self.target,
            "label": self.label,
            "status": self.status,
            "evidence_id": self.evidence_id,
            "metadata": self.metadata,
        }


@dataclass
class GraphModel:
    nodes: dict[str, GraphNode] = field(default_factory=dict)
    edges: list[GraphEdge] = field(default_factory=list)

    def add_node(self, node: GraphNode) -> None:
        if node.id and node.id not in self.nodes:
            self.nodes[node.id] = node

    def add_edge(self, edge: GraphEdge) -> None:
        if edge.source and edge.target and edge.source in self.nodes and edge.target in self.nodes:
            self.edges.append(edge)

    def as_dict(self) -> dict[str, Any]:
        return {
            "nodes": [node.as_dict() for node in self.nodes.values()],
            "edges": [edge.as_dict() for edge in self.edges],
        }
