from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AnalysisFinding:
    finding_id: str
    domain: str
    severity: str
    category: str
    object_type: str
    object_id: str
    sheet: str
    row_id: str
    field: str
    message: str
    impact: str
    suggested_action: str
    evidence_id: str = ""
    confidence: str = "High"
    source: str = "analysis"

    def as_dict(self) -> dict[str, str]:
        return {
            "finding_id": self.finding_id,
            "domain": self.domain,
            "severity": self.severity,
            "category": self.category,
            "object_type": self.object_type,
            "object_id": self.object_id,
            "sheet": self.sheet,
            "row_id": self.row_id,
            "field": self.field,
            "message": self.message,
            "impact": self.impact,
            "suggested_action": self.suggested_action,
            "evidence_id": self.evidence_id,
            "confidence": self.confidence,
            "source": self.source,
        }


@dataclass(frozen=True)
class AnalysisReportSummary:
    title: str
    total_findings: int
    severity_counts: dict[str, int] = field(default_factory=dict)
    domain_counts: dict[str, int] = field(default_factory=dict)
    source: str = "analysis"

    def as_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "total_findings": self.total_findings,
            "severity_counts": dict(sorted(self.severity_counts.items())),
            "domain_counts": dict(sorted(self.domain_counts.items())),
            "source": self.source,
        }

    @classmethod
    def from_findings(cls, title: str, findings: list[AnalysisFinding]) -> "AnalysisReportSummary":
        severity_counts: dict[str, int] = {}
        domain_counts: dict[str, int] = {}
        for finding in findings:
            severity_counts[finding.severity] = severity_counts.get(finding.severity, 0) + 1
            domain_counts[finding.domain] = domain_counts.get(finding.domain, 0) + 1
        return cls(
            title=title,
            total_findings=len(findings),
            severity_counts=severity_counts,
            domain_counts=domain_counts,
        )
