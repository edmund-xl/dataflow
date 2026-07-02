from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dataflow_agent.models import GraphModel, Row, WorkbookData
from dataflow_agent.util import write_csv, write_json

from .indexes import AnalysisIndexes


REPORT_BASENAME = "critical_path_report"
CRITICAL_SERVICES_FIELDS = [
    "rank",
    "service_id",
    "service_name",
    "score",
    "suggested_priority",
    "score_factors",
    "impact_summary",
    "evidence_id",
]
PRIORITY_SCORE = {"P0": 40, "P1": 25, "P2": 10, "P3": 3}
SENSITIVE_LEVELS = {"restricted", "high", "critical"}
INCOMPLETE_MONITORING = {"", "missing", "unknown", "partial"}
HIGH_PRIVILEGE_ROLE_TOKENS = ("owner", "editor", "admin", "*")


@dataclass(frozen=True)
class ScoreFactor:
    name: str
    points: int
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "points": self.points, "reason": self.reason}


@dataclass(frozen=True)
class CriticalServiceImpact:
    rank: int
    service_id: str
    service_name: str
    score: int
    suggested_priority: str
    impact_summary: str
    evidence_id: str
    factors: list[ScoreFactor] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "service_id": self.service_id,
            "service_name": self.service_name,
            "score": self.score,
            "suggested_priority": self.suggested_priority,
            "impact_summary": self.impact_summary,
            "evidence_id": self.evidence_id,
            "score_factors": [factor.as_dict() for factor in self.factors],
        }

    def as_csv_row(self) -> dict[str, str]:
        return {
            "rank": str(self.rank),
            "service_id": self.service_id,
            "service_name": self.service_name,
            "score": str(self.score),
            "suggested_priority": self.suggested_priority,
            "score_factors": "; ".join(f"{factor.name}=+{factor.points}" for factor in self.factors),
            "impact_summary": self.impact_summary,
            "evidence_id": self.evidence_id,
        }


def analyze_critical_paths(
    workbook: WorkbookData,
    graph: GraphModel,
    indexes: AnalysisIndexes,
) -> list[CriticalServiceImpact]:
    del workbook, graph
    scored = [_score_service(service_id, row, indexes) for service_id, row in sorted(indexes.services.items())]
    scored.sort(key=lambda item: (-item.score, item.service_id))
    return [
        CriticalServiceImpact(
            rank=index,
            service_id=item.service_id,
            service_name=item.service_name,
            score=item.score,
            suggested_priority=_suggested_priority(item.score),
            impact_summary=item.impact_summary,
            evidence_id=item.evidence_id,
            factors=item.factors,
        )
        for index, item in enumerate(scored, start=1)
    ]


def write_critical_path_report(output_dir: Path, impacts: list[CriticalServiceImpact]) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    md_path = output / f"{REPORT_BASENAME}.md"
    csv_path = output / "critical_services.csv"
    json_path = output / "service_impact_index.json"

    md_path.write_text(_render_report(impacts), encoding="utf-8")
    write_csv(csv_path, [impact.as_csv_row() for impact in impacts], CRITICAL_SERVICES_FIELDS)
    write_json(
        json_path,
        {
            "summary": {
                "total_services": len(impacts),
                "top_service": impacts[0].service_id if impacts else "",
                "scoring_model": "deterministic_v1",
            },
            "services": [impact.as_dict() for impact in impacts],
        },
    )
    return {"md": md_path, "csv": csv_path, "json": json_path}


@dataclass(frozen=True)
class _ScoredService:
    service_id: str
    service_name: str
    score: int
    impact_summary: str
    evidence_id: str
    factors: list[ScoreFactor]


def _score_service(service_id: str, row: Row, indexes: AnalysisIndexes) -> _ScoredService:
    factors: list[ScoreFactor] = []
    priority = row.get("Service_Priority", "")
    _add_factor(factors, "service_priority", PRIORITY_SCORE.get(priority, 0), f"Service_Priority={priority or 'N/A'}")

    upstream = len(indexes.upstream.get(service_id, set()))
    downstream = len(indexes.downstream.get(service_id, set()))
    _add_factor(factors, "upstream_services", min(upstream * 3, 18), f"{upstream} upstream graph nodes")
    _add_factor(factors, "downstream_services", min(downstream * 4, 24), f"{downstream} downstream graph nodes")

    sensitive_assets = _sensitive_assets(indexes, service_id)
    _add_factor(factors, "sensitive_data_assets", min(len(sensitive_assets) * 10, 30), _ids_reason(sensitive_assets, "Data_Asset_ID"))

    external_services = indexes.external_by_service.get(service_id, [])
    _add_factor(factors, "external_dependencies", min(len(external_services) * 6, 24), _ids_reason(external_services, "External_ID"))

    high_privilege = _high_privilege_rows(indexes, service_id)
    _add_factor(factors, "high_privilege_iam", min(len(high_privilege) * 8, 24), _ids_reason(high_privilege, "IAM_Binding_ID"))

    monitoring_rows = indexes.monitoring_by_object.get(("service", service_id), [])
    if not monitoring_rows:
        _add_factor(factors, "monitoring_gap", 12, "no service monitoring row")
    elif any(_is_incomplete_monitoring(row) for row in monitoring_rows):
        _add_factor(factors, "monitoring_gap", 6, "service monitoring is not fully covered")

    total = sum(factor.points for factor in factors)
    return _ScoredService(
        service_id=service_id,
        service_name=row.get("Service_Name", "") or service_id,
        score=total,
        impact_summary=_impact_summary(service_id, factors),
        evidence_id=row.get("Evidence_ID", ""),
        factors=factors,
    )


def _add_factor(factors: list[ScoreFactor], name: str, points: int, reason: str) -> None:
    if points <= 0:
        return
    factors.append(ScoreFactor(name=name, points=points, reason=reason))


def _sensitive_assets(indexes: AnalysisIndexes, service_id: str) -> list[Row]:
    return [
        row
        for row in indexes.data_assets_by_service.get(service_id, [])
        if row.get("Sensitivity", "").strip().lower() in SENSITIVE_LEVELS
    ]


def _high_privilege_rows(indexes: AnalysisIndexes, service_id: str) -> list[Row]:
    rows: list[Row] = []
    for row in indexes.iam_by_service.get(service_id, []):
        role = row.get("Role", "").strip().lower()
        high = row.get("Is_High_Privilege", "").strip().lower() == "yes"
        if high or any(token in role for token in HIGH_PRIVILEGE_ROLE_TOKENS):
            rows.append(row)
    return rows


def _is_incomplete_monitoring(row: Row) -> bool:
    return row.get("Coverage_Status", "").strip().lower() in INCOMPLETE_MONITORING


def _ids_reason(rows: list[Row], id_field: str) -> str:
    ids = [row.get(id_field, "") for row in rows if row.get(id_field, "")]
    return ", ".join(ids) if ids else "none"


def _impact_summary(service_id: str, factors: list[ScoreFactor]) -> str:
    if not factors:
        return f"{service_id} has no current critical-path signal in the collected workbook graph."
    names = ", ".join(factor.name for factor in factors)
    return f"{service_id} impact score is driven by {names}."


def _suggested_priority(score: int) -> str:
    if score >= 75:
        return "P0"
    if score >= 45:
        return "P1"
    if score >= 20:
        return "P2"
    return "Review"


def _render_report(impacts: list[CriticalServiceImpact]) -> str:
    lines = [
        "# Critical Path Report",
        "",
        "This branch-only report ranks services using deterministic signals from the collected workbook and generated graph. It does not infer relationships that are not present in source data.",
        "",
        "| rank | service_id | score | suggested_priority | score_factors | impact_summary | evidence_id |",
        "| --- | --- | ---: | --- | --- | --- | --- |",
    ]
    for impact in impacts:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(impact.rank),
                    _md(impact.service_id),
                    str(impact.score),
                    _md(impact.suggested_priority),
                    _md("; ".join(f"{factor.name}=+{factor.points}" for factor in impact.factors)),
                    _md(impact.impact_summary),
                    _md(impact.evidence_id),
                ]
            )
            + " |"
        )
    if not impacts:
        lines.append("")
        lines.append("No services were present in the collected workbook.")
    return "\n".join(lines) + "\n"


def _md(value: str) -> str:
    return (value or "").replace("|", "\\|").replace("\n", "<br>")
