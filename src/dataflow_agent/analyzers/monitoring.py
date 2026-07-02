from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dataflow_agent.models import GraphModel, Row, WorkbookData
from dataflow_agent.util import write_csv

from .indexes import AnalysisIndexes
from .models import AnalysisFinding
from .report_writer import write_analysis_findings


REPORT_BASE_NAME = "monitoring_gap_report"
REPORT_TITLE = "Monitoring Gap Report"
MONITORING_REQUIREMENTS_FIELDS = [
    "finding_id",
    "object_id",
    "object_type",
    "required_control",
    "priority",
    "reason",
    "evidence_id",
    "suggested_action",
]
SUGGESTED_ALERT_FIELDS = [
    "object_id",
    "object_type",
    "required_metric",
    "suggested_alert",
    "priority",
    "reason",
    "evidence_id",
]

CRITICAL_PRIORITIES = {"P0", "P1"}
INCOMPLETE_COVERAGE_VALUES = {"partial", "missing", "unknown", ""}
P1_COVERAGE_VALUES = {"missing", "unknown", ""}
NEGATIVE_COVERAGE_VALUES = {"no", "unknown", ""}
SENSITIVE_VALUES = {"high", "restricted", "critical"}
ASYNC_TOKENS = {"async", "batch", "stream", "publish", "subscribe", "produce", "consume"}


@dataclass(frozen=True)
class _FindingCandidate:
    rule_order: int
    category: str
    severity: str
    object_type: str
    object_id: str
    sheet: str
    row_id: str
    field: str
    message: str
    impact: str
    suggested_action: str
    evidence_id: str

    @property
    def sort_key(self) -> tuple[int, str, str, str, str, str]:
        return (self.rule_order, self.object_type, self.object_id, self.field, self.row_id, self.evidence_id)


def analyze_monitoring_gaps(
    workbook: WorkbookData,
    graph: GraphModel,
    indexes: AnalysisIndexes,
) -> list[AnalysisFinding]:
    candidates: list[_FindingCandidate] = []
    candidates.extend(_service_monitoring_candidates(indexes))
    candidates.extend(_dependency_monitoring_candidates(graph, indexes))
    candidates.extend(_data_asset_monitoring_candidates(indexes))
    return _assign_finding_ids(candidates)


def write_monitoring_gap_report(output_dir: Path, findings: list[AnalysisFinding]) -> dict[str, Path]:
    return write_analysis_findings(Path(output_dir), REPORT_BASE_NAME, findings, REPORT_TITLE)


def monitoring_requirements_rows(findings: list[AnalysisFinding]) -> list[dict[str, str]]:
    return [
        {
            "finding_id": finding.finding_id,
            "object_id": finding.object_id,
            "object_type": finding.object_type,
            "required_control": _required_control(finding),
            "priority": finding.severity,
            "reason": finding.message,
            "evidence_id": finding.evidence_id,
            "suggested_action": finding.suggested_action,
        }
        for finding in _sort_findings(findings)
    ]


def suggested_alerts_rows(findings: list[AnalysisFinding]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for finding in _sort_findings(findings):
        for metric, alert in _alert_recommendations(finding):
            dedupe_key = (finding.object_type, finding.object_id, metric)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            rows.append(
                {
                    "object_id": finding.object_id,
                    "object_type": finding.object_type,
                    "required_metric": metric,
                    "suggested_alert": alert,
                    "priority": finding.severity,
                    "reason": finding.message,
                    "evidence_id": finding.evidence_id,
                }
            )
    return sorted(rows, key=lambda row: (row["object_type"], row["object_id"], row["required_metric"]))


def write_monitoring_requirements_csv(output_dir: Path, findings: list[AnalysisFinding]) -> Path:
    path = Path(output_dir) / "monitoring_requirements.csv"
    write_csv(path, monitoring_requirements_rows(findings), MONITORING_REQUIREMENTS_FIELDS)
    return path


def write_suggested_alerts_csv(output_dir: Path, findings: list[AnalysisFinding]) -> Path:
    path = Path(output_dir) / "suggested_alerts.csv"
    write_csv(path, suggested_alerts_rows(findings), SUGGESTED_ALERT_FIELDS)
    return path


def _service_monitoring_candidates(indexes: AnalysisIndexes) -> list[_FindingCandidate]:
    candidates: list[_FindingCandidate] = []
    for service_id, row in sorted(indexes.services.items()):
        priority = row.get("Service_Priority", "")
        if priority not in CRITICAL_PRIORITIES:
            continue
        monitoring_rows = _monitoring_rows(indexes, "service", service_id)
        if not monitoring_rows:
            candidates.append(
                _candidate(
                    10,
                    "missing_service_monitoring",
                    "P1",
                    "service",
                    service_id,
                    "04_Services",
                    row,
                    "Service_ID",
                    f"{priority} service {service_id} has no monitoring row keyed by service.",
                    "Critical services can fail without dashboard, alert, logging, or XDR coverage evidence.",
                    "Add a 10_Monitoring row keyed by Object_Type=service and Object_ID for this service.",
                )
            )
            continue
        if priority == "P0":
            for monitoring_row in monitoring_rows:
                incomplete_fields = _incomplete_monitoring_fields(monitoring_row)
                if not incomplete_fields:
                    continue
                coverage_status = _normalized(monitoring_row.get("Coverage_Status", ""))
                severity = "P1" if coverage_status in P1_COVERAGE_VALUES else "P2"
                monitoring_id = monitoring_row.get("Monitoring_ID", "")
                candidates.append(
                    _candidate(
                        20,
                        "incomplete_p0_service_monitoring",
                        severity,
                        "service",
                        service_id,
                        "10_Monitoring",
                        monitoring_row,
                        ",".join(incomplete_fields),
                        f"P0 service {service_id} has incomplete monitoring evidence in {monitoring_id or _row_id(monitoring_row)}.",
                        "P0 service incidents may be detected late or lack investigation evidence.",
                        "Complete dashboard, alert rule, logging, XDR, and coverage status evidence.",
                    )
                )
    return candidates


def _dependency_monitoring_candidates(graph: GraphModel, indexes: AnalysisIndexes) -> list[_FindingCandidate]:
    candidates: list[_FindingCandidate] = []
    calls_external_dependency_ids = _calls_external_dependency_ids(graph)
    for dependency_id, row in sorted(indexes.dependencies.items()):
        criticality = row.get("Dependency_Criticality", "")
        monitoring_rows = _monitoring_rows(indexes, "dependency", dependency_id)
        missing_monitoring = not monitoring_rows
        if criticality in CRITICAL_PRIORITIES and missing_monitoring:
            candidates.append(
                _candidate(
                    30,
                    "missing_dependency_monitoring",
                    "P2",
                    "dependency",
                    dependency_id,
                    "05_Dependencies",
                    row,
                    "Dependency_ID",
                    f"{criticality} dependency {dependency_id} has no monitoring row keyed by dependency.",
                    "Critical dependency degradation may not be visible independently from service health.",
                    "Add a 10_Monitoring row keyed by Object_Type=dependency and Object_ID for this dependency.",
                )
            )
        if missing_monitoring and _is_external_dependency(row, indexes, calls_external_dependency_ids):
            candidates.append(
                _candidate(
                    40,
                    "external_dependency_monitoring_recommendation",
                    "P2",
                    "dependency",
                    dependency_id,
                    "05_Dependencies",
                    row,
                    "Target_External_ID",
                    f"External dependency {dependency_id} has no dependency-level monitoring recommendation.",
                    "External calls need timeout, error rate, latency, and fallback visibility.",
                    "Add monitoring recommendations for timeout, error_rate, latency, and fallback behavior.",
                )
            )
        if missing_monitoring and _is_async_dependency(row):
            candidates.append(
                _candidate(
                    50,
                    "async_dependency_monitoring_recommendation",
                    "P2",
                    "dependency",
                    dependency_id,
                    "05_Dependencies",
                    row,
                    "Call_Description",
                    f"Async or queue-like dependency {dependency_id} has no dependency-level monitoring recommendation.",
                    "Async flows can silently accumulate backlog, lag, retries, or dead-letter failures.",
                    "Add queue or async monitoring recommendations for queue depth, consumer lag, retry, and dead-letter signals.",
                )
            )
    return candidates


def _data_asset_monitoring_candidates(indexes: AnalysisIndexes) -> list[_FindingCandidate]:
    candidates: list[_FindingCandidate] = []
    for asset_id, row in sorted(indexes.data_assets.items()):
        if _normalized(row.get("Sensitivity", "")) not in SENSITIVE_VALUES:
            continue
        if _monitoring_rows(indexes, "data_asset", asset_id):
            continue
        candidates.append(
            _candidate(
                60,
                "missing_sensitive_data_asset_monitoring",
                "P1",
                "data_asset",
                asset_id,
                "06_Data_Assets",
                row,
                "Data_Asset_ID",
                f"Sensitive data asset {asset_id} has no monitoring row keyed by data_asset.",
                "Sensitive data access or availability problems may lack direct detection evidence.",
                "Add a 10_Monitoring row keyed by Object_Type=data_asset and Object_ID for this asset.",
            )
        )
    return candidates


def _assign_finding_ids(candidates: list[_FindingCandidate]) -> list[AnalysisFinding]:
    findings: list[AnalysisFinding] = []
    for index, candidate in enumerate(sorted(candidates, key=lambda item: item.sort_key), start=1):
        findings.append(
            AnalysisFinding(
                finding_id=f"MON-{index:04d}",
                domain="Monitoring",
                severity=candidate.severity,
                category=candidate.category,
                object_type=candidate.object_type,
                object_id=candidate.object_id,
                sheet=candidate.sheet,
                row_id=candidate.row_id,
                field=candidate.field,
                message=candidate.message,
                impact=candidate.impact,
                suggested_action=candidate.suggested_action,
                evidence_id=candidate.evidence_id,
            )
        )
    return findings


def _candidate(
    rule_order: int,
    category: str,
    severity: str,
    object_type: str,
    object_id: str,
    sheet: str,
    row: Row,
    field: str,
    message: str,
    impact: str,
    suggested_action: str,
) -> _FindingCandidate:
    return _FindingCandidate(
        rule_order=rule_order,
        category=category,
        severity=severity,
        object_type=object_type,
        object_id=object_id,
        sheet=sheet,
        row_id=_row_id(row),
        field=field,
        message=message,
        impact=impact,
        suggested_action=suggested_action,
        evidence_id=row.get("Evidence_ID", "") or row.get("Related_Evidence_ID", ""),
    )


def _monitoring_rows(indexes: AnalysisIndexes, object_type: str, object_id: str) -> list[Row]:
    rows: list[Row] = []
    for (indexed_type, indexed_id), indexed_rows in indexes.monitoring_by_object.items():
        if _normalized(indexed_type) == object_type and indexed_id == object_id:
            rows.extend(indexed_rows)
    return sorted(rows, key=lambda row: (_row_id(row), row.get("Monitoring_ID", ""), row.get("Evidence_ID", "")))


def _incomplete_monitoring_fields(row: Row) -> list[str]:
    fields: list[str] = []
    for field in ("Dashboard_URL", "Alert_Rule"):
        if not row.get(field, "").strip():
            fields.append(field)
    for field in ("Logging_Coverage", "XDR_Coverage"):
        if _normalized(row.get(field, "")) in NEGATIVE_COVERAGE_VALUES:
            fields.append(field)
    if _normalized(row.get("Coverage_Status", "")) in INCOMPLETE_COVERAGE_VALUES:
        fields.append("Coverage_Status")
    return fields


def _calls_external_dependency_ids(graph: GraphModel) -> set[str]:
    dependency_ids: set[str] = set()
    for edge in graph.edges:
        if edge.type != "calls_external":
            continue
        dependency_id = str(edge.metadata.get("dependency_id", ""))
        if dependency_id:
            dependency_ids.add(dependency_id)
    return dependency_ids


def _is_external_dependency(row: Row, indexes: AnalysisIndexes, calls_external_dependency_ids: set[str]) -> bool:
    dependency_id = row.get("Dependency_ID", "")
    if dependency_id in calls_external_dependency_ids:
        return True
    if row.get("Target_External_ID"):
        return True
    if _normalized(row.get("Target_Type", "")) in {"external", "external_service"}:
        return True
    target_id = row.get("Target_ID", "")
    return bool(target_id and target_id in indexes.external_services)


def _is_async_dependency(row: Row) -> bool:
    text = " ".join(
        row.get(field, "")
        for field in (
            "Dependency_ID",
            "Direction",
            "Call_Description",
            "Target_Path",
            "Target_Port_Protocol",
            "Target_Type",
            "Interaction_Mode",
            "Notes",
        )
    ).lower()
    return any(token in text for token in ASYNC_TOKENS)


def _required_control(finding: AnalysisFinding) -> str:
    controls = {
        "missing_service_monitoring": "service monitoring row",
        "incomplete_p0_service_monitoring": "complete P0 service monitoring evidence",
        "missing_dependency_monitoring": "dependency monitoring row",
        "external_dependency_monitoring_recommendation": "external dependency monitoring recommendation",
        "async_dependency_monitoring_recommendation": "queue or async monitoring recommendation",
        "missing_sensitive_data_asset_monitoring": "sensitive data asset monitoring row",
    }
    return controls.get(finding.category, "monitoring requirement")


def _alert_recommendations(finding: AnalysisFinding) -> list[tuple[str, str]]:
    if finding.category == "external_dependency_monitoring_recommendation":
        return [
            ("timeout", "Alert when external dependency timeout count or timeout rate exceeds the agreed threshold."),
            ("error_rate", "Alert when external dependency errors exceed the agreed rate threshold."),
            ("latency", "Alert when external dependency latency exceeds the agreed percentile threshold."),
            ("fallback", "Alert when fallback path usage or fallback failures exceed the agreed threshold."),
        ]
    if finding.category == "async_dependency_monitoring_recommendation":
        return [
            ("queue_depth", "Alert when queue depth exceeds the agreed backlog threshold."),
            ("consumer_lag", "Alert when consumer lag exceeds the agreed freshness threshold."),
            ("retry_rate", "Alert when retry rate exceeds the agreed failure threshold."),
            ("dead_letter", "Alert when dead-letter messages are produced."),
        ]
    if finding.category == "missing_sensitive_data_asset_monitoring":
        return [
            ("availability", "Alert when the data asset is unavailable or rejects health checks."),
            ("access_error_rate", "Alert when data asset access errors exceed the agreed threshold."),
            ("unauthorized_access", "Alert when unauthorized or anomalous sensitive data access is detected."),
        ]
    if finding.category in {"missing_dependency_monitoring", "missing_service_monitoring", "incomplete_p0_service_monitoring"}:
        return [
            ("availability", "Alert when the monitored object is unavailable or unhealthy."),
            ("error_rate", "Alert when errors exceed the agreed rate threshold."),
            ("latency", "Alert when latency exceeds the agreed percentile threshold."),
        ]
    return []


def _sort_findings(findings: list[AnalysisFinding]) -> list[AnalysisFinding]:
    return sorted(findings, key=lambda finding: finding.finding_id)


def _row_id(row: Row) -> str:
    for field in (
        "Record_ID",
        "Monitoring_ID",
        "Dependency_ID",
        "Service_ID",
        "Data_Asset_ID",
        "External_ID",
        "Evidence_ID",
    ):
        if row.get(field):
            return row[field]
    return ""


def _normalized(value: str) -> str:
    return (value or "").strip().lower()
