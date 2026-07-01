from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from .artifacts import write_graph_artifacts, write_normalized_snapshot
from .constants import RuntimePaths, make_runtime_paths
from .diagram_renderer import render_diagrams, render_service_drilldown
from .graph_builder import build_graph
from .models import Finding, GraphModel, ValidationResult, WorkbookData
from .normalizer import normalize_workbook
from .packager import assemble_package, write_package_metadata, write_package_readme
from .report_generator import generate_reports
from .risk_checker import check_risks
from .schema import load_schema
from .util import ensure_dirs
from .validator import validate_workbook
from .xlsx_reader import read_workbook


@dataclass
class PipelineState:
    paths: RuntimePaths
    schema: dict
    workbook: WorkbookData
    normalized_workbook: WorkbookData
    validation: ValidationResult
    graph: GraphModel
    risks: list[Finding]
    zip_path: Path | None = None


def load_state(input_dir: Path, output_root: Path, env: str, version: str, clean_output: bool = False) -> PipelineState:
    schema = load_schema()
    paths = make_runtime_paths(input_dir, output_root, version)
    if clean_output and paths.package_dir.exists():
        shutil.rmtree(paths.package_dir)
    ensure_dirs(paths.package_dir, paths.normalized_dir, paths.diagrams_dir, paths.reports_dir)
    workbook = read_workbook(paths.workbook_path, schema)
    normalized = normalize_workbook(workbook, schema)
    validation = validate_workbook(normalized, schema)
    graph = build_graph(normalized)
    risks = check_risks(normalized, graph)
    return PipelineState(paths, schema, workbook, normalized, validation, graph, risks)


def run_validate(state: PipelineState) -> None:
    from .artifacts import write_findings_workbook, write_validation_json

    write_findings_workbook(state.paths.reports_dir / "validation_report.xlsx", "Validation", state.validation.findings)
    write_validation_json(state.validation.findings, state.paths.reports_dir)


def run_normalize(state: PipelineState) -> None:
    write_normalized_snapshot(state.normalized_workbook, state.paths.normalized_dir)


def run_build(state: PipelineState) -> None:
    write_graph_artifacts(state.graph, state.paths.normalized_dir)


def run_risk(state: PipelineState) -> None:
    from .artifacts import write_findings_workbook, write_logic_check_results

    write_findings_workbook(state.paths.reports_dir / "issue_risk_register.xlsx", "Issues_Risks", state.validation.findings + state.risks)
    write_logic_check_results(state.paths.reports_dir / "logic_check_results.json", state.risks)


def run_render(state: PipelineState) -> None:
    render_diagrams(state.graph, state.paths.diagrams_dir, findings=state.validation.findings + state.risks)


def run_service_drilldown(
    state: PipelineState,
    service_id: str,
    output_dir: Path,
    depth: int = 1,
    direction: str = "both",
    theme: str = "auto",
    risk_focus: bool = False,
) -> list[Path]:
    return render_service_drilldown(state.graph, service_id, output_dir, depth=depth, direction=direction, theme=theme, risk_focus=risk_focus)


def run_report(state: PipelineState, env: str, version: str) -> None:
    generate_reports(
        state.normalized_workbook,
        state.graph,
        state.validation.findings,
        state.risks,
        state.paths.reports_dir,
        env,
        version,
    )


def run_package(state: PipelineState, env: str, version: str) -> Path:
    metadata = write_package_metadata(
        state.paths,
        state.normalized_workbook,
        state.graph,
        state.validation.findings,
        state.risks,
        env,
        version,
    )
    write_package_readme(state.paths, metadata)
    state.zip_path = assemble_package(state.paths)
    return state.zip_path


def run_all(input_dir: Path, output_root: Path, env: str, version: str, clean_output: bool = True) -> PipelineState:
    state = load_state(input_dir, output_root, env, version, clean_output=clean_output)
    run_validate(state)
    run_normalize(state)
    run_build(state)
    run_risk(state)
    run_render(state)
    run_report(state, env, version)
    run_package(state, env, version)
    return state


def run_check(input_dir: Path, output_root: Path, env: str, version: str, clean_output: bool = True) -> PipelineState:
    from .summaries import write_check_summaries

    state = load_state(input_dir, output_root, env, version, clean_output=clean_output)
    run_validate(state)
    run_normalize(state)
    run_build(state)
    run_risk(state)
    run_report(state, env, version)
    write_check_summaries(output_root, state)
    return state
