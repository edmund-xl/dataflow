#!/usr/bin/env bash
set -euo pipefail

if [[ $# -gt 1 ]]; then
  echo "Usage: scripts/doctor.sh [DCP directory or workbook file]" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DCP_INPUT="${1:-samples/DCP_clean_v0.1}"

if [[ -n "${DATAFLOW_PYTHON:-}" ]]; then
  PYTHON_BIN="${DATAFLOW_PYTHON}"
else
  PYTHON_BIN="python3"
fi

cd "${REPO_ROOT}"
PYTHONPATH="${REPO_ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}" exec "${PYTHON_BIN}" - "${DCP_INPUT}" <<'PY'
from __future__ import annotations

import importlib
import sys
from pathlib import Path


repo_root = Path.cwd()
input_path = Path(sys.argv[1]).resolve()
ready: list[str] = []
warn: list[str] = []
missing: list[str] = []


def add(target: list[str], message: str) -> None:
    target.append(message)


def section(title: str, items: list[str]) -> None:
    print(title)
    if not items:
        print("- none")
        return
    for item in items:
        print(f"- {item}")


print("Dataflow Agent Doctor")
print(f"Repository: {repo_root}")
print(f"Input: {input_path}")
print(f"Python: {sys.executable}")

if sys.version_info >= (3, 11):
    add(ready, f"Python version is {sys.version.split()[0]}")
else:
    add(missing, f"Python 3.11 or newer is required; current version is {sys.version.split()[0]}")

required_modules = {
    "openpyxl": "Excel workbook read/write",
    "docx": "Word report generation",
    "PIL": "PNG rendering",
    "reportlab": "PDF rendering",
}
for module_name, purpose in required_modules.items():
    try:
        importlib.import_module(module_name)
        add(ready, f"{module_name} is available for {purpose}")
    except Exception as exc:
        add(missing, f"{module_name} is missing for {purpose}: {exc}")

try:
    importlib.import_module("pytest")
    add(ready, "pytest is available for developer regression tests")
except Exception:
    add(warn, "pytest is not installed; daily scripts still work, but developer regression tests need the dev extra")

try:
    from dataflow_agent.constants import find_workbook
    from dataflow_agent.graph_builder import build_graph
    from dataflow_agent.normalizer import normalize_workbook
    from dataflow_agent.schema import load_schema
    from dataflow_agent.validator import validate_workbook
    from dataflow_agent.xlsx_reader import read_workbook

    add(ready, "dataflow_agent package is importable")
    schema = load_schema()
    workbook_path = find_workbook(input_path)
    add(ready, f"Workbook detected: {workbook_path}")
    workbook = read_workbook(workbook_path, schema)
    missing_sheets = [sheet for sheet in schema["required_sheets"] if sheet not in workbook.sheets]
    if missing_sheets:
        add(missing, f"Workbook is missing required sheets: {', '.join(missing_sheets)}")
    else:
        add(ready, "Workbook contains all required sheet names")
    validation = validate_workbook(workbook, schema)
    if validation.findings:
        add(warn, f"Workbook has {len(validation.findings)} validation findings; run scripts/check_dcp.sh for the fix list")
    else:
        add(ready, "Workbook validation has no findings")
    graph = build_graph(normalize_workbook(workbook, schema))
    add(ready, f"Graph builder works: {len(graph.nodes)} nodes, {len(graph.edges)} edges")
except Exception as exc:
    add(missing, f"Agent smoke test failed: {exc}")

for script_name in [
    "doctor.sh",
    "check_dcp.sh",
    "build_dataflow_package.sh",
    "merge_dcp.sh",
    "build_service_drilldown.sh",
    "query_service_ports.sh",
    "setup_env.sh",
]:
    script_path = repo_root / "scripts" / script_name
    if script_path.exists() and script_path.stat().st_mode & 0o111:
        add(ready, f"{script_name} exists and is executable")
    else:
        add(missing, f"{script_name} is missing or not executable")

print()
section("READY", ready)
section("WARN", warn)
section("MISSING", missing)
if missing:
    print()
    print("Suggested setup:")
    print("- Run scripts/setup_env.sh from the repository root.")
    print("- Then run: export DATAFLOW_PYTHON=\"$(pwd)/.venv/bin/python\"")
    print("- Recheck with: scripts/doctor.sh")
print()
print(f"Summary: ready={len(ready)} warn={len(warn)} missing={len(missing)}")
raise SystemExit(1 if missing else 0)
PY
