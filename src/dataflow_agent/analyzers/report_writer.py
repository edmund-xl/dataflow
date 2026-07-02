from __future__ import annotations

from pathlib import Path

from dataflow_agent.util import write_csv, write_json

from .models import AnalysisFinding, AnalysisReportSummary


ANALYSIS_FINDING_FIELDS = [
    "finding_id",
    "domain",
    "severity",
    "category",
    "object_type",
    "object_id",
    "sheet",
    "row_id",
    "field",
    "message",
    "impact",
    "suggested_action",
    "evidence_id",
    "confidence",
    "source",
]


def write_analysis_findings_md(
    output_dir: Path,
    base_name: str,
    findings: list[AnalysisFinding],
    title: str,
) -> Path:
    path = output_dir / f"{base_name}.md"
    rows = [_finding_row(finding) for finding in _sorted_findings(findings)]
    summary = AnalysisReportSummary.from_findings(title, _sorted_findings(findings))
    lines = [
        f"# {title}",
        "",
        f"- Total findings: {summary.total_findings}",
        f"- Severity counts: {_format_counts(summary.severity_counts)}",
        f"- Domain counts: {_format_counts(summary.domain_counts)}",
        "",
        "| " + " | ".join(ANALYSIS_FINDING_FIELDS) + " |",
        "| " + " | ".join(["---"] * len(ANALYSIS_FINDING_FIELDS)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_md_cell(row[field]) for field in ANALYSIS_FINDING_FIELDS) + " |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_analysis_findings_json(
    output_dir: Path,
    base_name: str,
    findings: list[AnalysisFinding],
    title: str,
) -> Path:
    path = output_dir / f"{base_name}.json"
    sorted_findings = _sorted_findings(findings)
    payload = {
        "summary": AnalysisReportSummary.from_findings(title, sorted_findings).as_dict(),
        "findings": [finding.as_dict() for finding in sorted_findings],
    }
    write_json(path, payload)
    return path


def write_analysis_findings_csv(
    output_dir: Path,
    base_name: str,
    findings: list[AnalysisFinding],
    title: str,
) -> Path:
    path = output_dir / f"{base_name}.csv"
    write_csv(path, [_finding_row(finding) for finding in _sorted_findings(findings)], ANALYSIS_FINDING_FIELDS)
    return path


def write_analysis_findings(
    output_dir: Path,
    base_name: str,
    findings: list[AnalysisFinding],
    title: str,
) -> dict[str, Path]:
    return {
        "md": write_analysis_findings_md(output_dir, base_name, findings, title),
        "json": write_analysis_findings_json(output_dir, base_name, findings, title),
        "csv": write_analysis_findings_csv(output_dir, base_name, findings, title),
    }


def _sorted_findings(findings: list[AnalysisFinding]) -> list[AnalysisFinding]:
    return sorted(
        findings,
        key=lambda finding: (
            finding.severity,
            finding.domain,
            finding.category,
            finding.object_type,
            finding.object_id,
            finding.finding_id,
        ),
    )


def _finding_row(finding: AnalysisFinding) -> dict[str, str]:
    return finding.as_dict()


def _format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


def _md_cell(value: str) -> str:
    return (value or "").replace("|", "\\|").replace("\n", "<br>")
