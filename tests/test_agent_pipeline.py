from __future__ import annotations

import json
import shutil
import subprocess
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from docx import Document

from dataflow_agent.diagram_renderer import VIEWS, render_diagrams
from dataflow_agent.graph_builder import build_graph
from dataflow_agent.normalizer import normalize_workbook
from dataflow_agent.pipeline import run_all
from dataflow_agent.risk_checker import check_risks
from dataflow_agent.schema import load_schema
from dataflow_agent.validator import validate_workbook
from dataflow_agent.xlsx_reader import read_workbook
from dataflow_agent.merge import merge_dcps


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DCP = ROOT / "samples" / "DCP_v0.1"
SAMPLE_WORKBOOK = SAMPLE_DCP / "dataflow_collection_template_v0.1.xlsx"


def test_full_run_outputs_package(tmp_path: Path) -> None:
    state = run_all(SAMPLE_DCP, tmp_path, "testnetv2", "v0.1-demo")

    package_dir = tmp_path / "dataflow_package_v0.1-demo"
    assert (tmp_path / "dataflow_package_v0.1-demo.zip").exists()
    assert (package_dir / "normalized" / "nodes.csv").exists()
    assert (package_dir / "normalized" / "edges.csv").exists()
    assert (package_dir / "normalized" / "dataflow_graph.json").exists()
    assert (package_dir / "normalized" / "dataflow_graph.yaml").exists()
    assert (package_dir / "reports" / "validation_report.xlsx").exists()
    assert (package_dir / "reports" / "logic_mapping_validation_report.docx").exists()
    assert (package_dir / "reports" / "issue_risk_register.xlsx").exists()
    assert (package_dir / "reports" / "acceptance_checklist.xlsx").exists()
    assert (package_dir / "metadata.json").exists()
    assert state.zip_path and state.zip_path.exists()

    metadata = json.loads((package_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["environment"] == "testnetv2"
    assert metadata["version"] == "v0.1-demo"
    assert metadata["input_file_hash"]


def test_sample_validates_and_builds_expected_edges() -> None:
    schema = load_schema()
    workbook = normalize_workbook(read_workbook(SAMPLE_WORKBOOK, schema), schema)
    validation = validate_workbook(workbook, schema)
    graph = build_graph(workbook)

    assert validation.findings == []
    edge_types = {edge.type for edge in graph.edges}
    assert {"runs_on", "calls", "calls_external", "reads_from", "uses_sa", "monitored_by"}.issubset(edge_types)


def test_duplicate_primary_key_is_validation_error() -> None:
    schema = load_schema()
    workbook = normalize_workbook(read_workbook(SAMPLE_WORKBOOK, schema), schema)
    workbook.sheets["04_Services"].append(dict(workbook.sheets["04_Services"][0]))

    validation = validate_workbook(workbook, schema)

    assert any(f.sheet == "04_Services" and "Duplicate primary key" in f.message for f in validation.findings)


def test_broken_foreign_key_is_validation_error() -> None:
    schema = load_schema()
    workbook = normalize_workbook(read_workbook(SAMPLE_WORKBOOK, schema), schema)
    workbook.sheets["04_Services"][0]["Running_On_Instance_ID"] = "missing-instance"

    validation = validate_workbook(workbook, schema)

    assert any(f.gate == "Gate 2" and f.field == "Running_On_Instance_ID" and f.severity == "P0" for f in validation.findings)


def test_rejected_rows_do_not_enter_graph_and_pending_rows_enter_risk_register() -> None:
    schema = load_schema()
    workbook = read_workbook(SAMPLE_WORKBOOK, schema)
    workbook.sheets["04_Services"][0]["Confirmation_Status"] = "Rejected"
    normalized = normalize_workbook(workbook, schema)
    graph = build_graph(normalized)
    risks = check_risks(normalized, graph)

    assert "svc-nginx-entry" not in graph.nodes
    assert any(f.status == "Pending_Confirmation" for f in risks)


def test_all_diagram_views_render_nonempty_files(tmp_path: Path) -> None:
    schema = load_schema()
    workbook = normalize_workbook(read_workbook(SAMPLE_WORKBOOK, schema), schema)
    graph = build_graph(workbook)

    outputs = render_diagrams(graph, tmp_path)

    expected_count = len(VIEWS) * 4
    assert len(outputs) == expected_count
    for path in outputs:
        assert path.exists()
        assert path.stat().st_size > 100


def test_cli_input_can_be_copied_to_fresh_dcp(tmp_path: Path) -> None:
    dcp = tmp_path / "DCP_v0.1"
    dcp.mkdir()
    shutil.copy2(SAMPLE_WORKBOOK, dcp / SAMPLE_WORKBOOK.name)

    state = run_all(dcp, tmp_path / "out", "testnetv2", "v0.1-demo")

    assert state.validation.findings == []
    assert state.zip_path and state.zip_path.exists()


def test_merge_identical_dcp_deduplicates_rows(tmp_path: Path) -> None:
    result = merge_dcps([SAMPLE_DCP, SAMPLE_DCP], tmp_path, "v0.1-demo")

    assert result.workbook_path.exists()
    assert (result.merged_dcp / "merge_report.xlsx").exists()
    assert (result.merged_dcp / "merge_report.json").exists()
    assert result.duplicate_count > 0
    assert result.conflict_count == 0


def test_script_check_dcp_runs_with_defaults() -> None:
    subprocess.run(["scripts/check_dcp.sh", "samples/DCP_v0.1"], cwd=ROOT, check=True)

    check_dir = SAMPLE_DCP / "agent_check"
    assert (check_dir / "check_summary.md").exists()
    assert (check_dir / "fix_list.md").exists()


def test_script_build_package_runs_with_defaults() -> None:
    subprocess.run(["scripts/build_dataflow_package.sh", "samples/DCP_v0.1"], cwd=ROOT, check=True)

    dist_dir = SAMPLE_DCP / "dist"
    assert any(path.name.startswith("dataflow_package_") and path.suffix == ".zip" for path in dist_dir.iterdir())


def test_script_merge_dcp_runs_with_defaults() -> None:
    subprocess.run(["scripts/merge_dcp.sh", "samples/DCP_v0.1", "samples/DCP_v0.1"], cwd=ROOT, check=True)

    merge_reports = list((ROOT / "dist").glob("merged_dcp_*/merge_report.xlsx"))
    package_zips = list((ROOT / "dist").glob("dataflow_package_*.zip"))
    assert merge_reports
    assert package_zips


def test_repository_docs_are_chinese_first_then_english() -> None:
    docs = [
        ROOT / "README.md",
        ROOT / "docs" / "collector_quick_check_guide.md",
        ROOT / "docs" / "aggregation_operator_guide.md",
        ROOT / "docs" / "dataflow_agent_input_contract_v0.1.md",
    ]
    for path in docs:
        text = path.read_text(encoding="utf-8")
        assert "# 中文版本" in text
        assert "# English Version" in text
        assert text.index("# 中文版本") < text.index("# English Version")


def test_generated_docs_are_chinese_first_then_english(tmp_path: Path) -> None:
    state = run_all(SAMPLE_DCP, tmp_path, "testnetv2", "v0.1-demo")
    package_dir = tmp_path / "dataflow_package_v0.1-demo"
    package_readme = (package_dir / "README.md").read_text(encoding="utf-8")
    assert package_readme.index("# 中文版本") < package_readme.index("# English Version")

    doc = Document(package_dir / "reports" / "logic_mapping_validation_report.docx")
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    assert paragraphs[0] == "中文版本"
    assert "English Version" in paragraphs
    assert paragraphs.index("中文版本") < paragraphs.index("English Version")


def test_role_terms_are_neutral_in_docs_and_generated_templates() -> None:
    docs_and_templates = [
        ROOT / "README.md",
        ROOT / "docs" / "collector_quick_check_guide.md",
        ROOT / "docs" / "aggregation_operator_guide.md",
        ROOT / "docs" / "dataflow_agent_input_contract_v0.1.md",
        ROOT / "src" / "dataflow_agent" / "packager.py",
        ROOT / "src" / "dataflow_agent" / "report_generator.py",
        ROOT / "src" / "dataflow_agent" / "summaries.py",
        ROOT / "src" / "dataflow_agent" / "cli.py",
    ]
    forbidden_terms = [
        "devops",
        "dev ops",
        "sre",
        "collector",
        "collectors",
        "operator",
        "operators",
        "colleague",
        "colleagues",
        "同事",
        "团队",
        "岗位",
        "采集者",
        "运维",
    ]

    for path in docs_and_templates:
        text = path.read_text(encoding="utf-8").lower()
        for term in forbidden_terms:
            assert term not in text, f"{path.relative_to(ROOT)} contains role term {term!r}"

    with ZipFile(SAMPLE_WORKBOOK) as workbook:
        for name in workbook.namelist():
            if name.endswith((".xml", ".rels")):
                data = workbook.read(name).decode("utf-8", errors="ignore").lower()
                for term in forbidden_terms:
                    assert term not in data, f"{SAMPLE_WORKBOOK.relative_to(ROOT)}:{name} contains role term {term!r}"

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "信息采集人员填写工作簿" in readme
    assert "数据汇总负责人收集多份 DCP" in readme


def test_license_and_generic_naming_are_enforced() -> None:
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert license_text.startswith("Proprietary License")
    assert "Copyright (c) 2026 edmund-xl. All rights reserved." in license_text
    assert "No permission is granted" in license_text
    assert 'license = "LicenseRef-Proprietary"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    legacy = "mega" + "eth"
    text_paths = [
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and ".git" not in path.parts
        and "dist" not in path.parts
        and "agent_check" not in path.parts
        and "__pycache__" not in path.parts
        and path.suffix.lower() in {".md", ".py", ".toml", ".sh", ".txt"}
    ]
    for path in text_paths:
        assert legacy not in path.name.lower()
        assert legacy not in path.read_text(encoding="utf-8").lower()

    with ZipFile(SAMPLE_WORKBOOK) as workbook:
        for name in workbook.namelist():
            if name.endswith((".xml", ".rels")):
                data = workbook.read(name).decode("utf-8", errors="ignore").lower()
                assert legacy not in data


def test_template_package_has_no_legacy_project_name() -> None:
    legacy_patterns = ["mega" + "eth", "mega" + " eth", "mega" + "-eth"]
    template_root = ROOT / "templates" / "dataflow_v1.0"
    expected_files = {
        "README.md",
        "dataflow_agent_io_contract_v1.0.md",
        "dataflow_collection_filling_guide_v1.0.docx",
        "dataflow_collection_template_bundle_v1.0.zip",
        "dataflow_data_dictionary_v1.0.xlsx",
        "dataflow_main_collection_template_v1.0.xlsx",
        "dataflow_overview_demo_v1.0.png",
        "dataflow_project_final_plan_v1.0.docx",
        "dataflow_sample_input_v1.0.xlsx",
        "dataflow_service_dependency_drilldown_demo_v1.0.png",
        "dataflow_task_collection_mapping_v1.0.xlsx",
    }

    assert template_root.exists()
    assert {path.name for path in template_root.iterdir() if path.is_file()} == expected_files

    def assert_no_legacy(text: str, label: str) -> None:
        lowered = text.lower()
        for pattern in legacy_patterns:
            assert pattern not in lowered, f"{label} contains legacy project name pattern {pattern!r}"

    def scan_zip_bytes(data: bytes, label: str) -> None:
        with ZipFile(BytesIO(data)) as archive:
            for name in archive.namelist():
                assert_no_legacy(name, f"{label}:{name}")
                payload = archive.read(name)
                lower_name = name.lower()
                if lower_name.endswith((".docx", ".xlsx", ".zip")):
                    scan_zip_bytes(payload, f"{label}:{name}")
                elif lower_name.endswith((".xml", ".rels", ".md", ".txt", ".json", ".csv")):
                    assert_no_legacy(payload.decode("utf-8", errors="ignore"), f"{label}:{name}")

    for path in template_root.rglob("*"):
        assert_no_legacy(str(path.relative_to(ROOT)), str(path.relative_to(ROOT)))
        if not path.is_file():
            continue
        lower_name = path.name.lower()
        if lower_name.endswith((".docx", ".xlsx", ".zip")):
            scan_zip_bytes(path.read_bytes(), str(path.relative_to(ROOT)))
        elif lower_name.endswith((".md", ".txt", ".json", ".csv")):
            assert_no_legacy(path.read_text(encoding="utf-8"), str(path.relative_to(ROOT)))
