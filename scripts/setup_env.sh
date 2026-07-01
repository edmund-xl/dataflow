#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${DATAFLOW_VENV:-${REPO_ROOT}/.venv}"

if [[ -n "${DATAFLOW_PYTHON:-}" ]]; then
  PYTHON_BIN="${DATAFLOW_PYTHON}"
else
  PYTHON_BIN="python3"
fi

cd "${REPO_ROOT}"
"${PYTHON_BIN}" -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/python" -m pip install --upgrade pip
"${VENV_DIR}/bin/python" -m pip install -e ".[dev]"

if command -v npm >/dev/null 2>&1; then
  npm ci --no-audit --no-fund
  echo "ELK diagram layout dependencies are ready."
else
  echo "WARN: npm is not available; overview diagrams will fall back to the built-in deterministic layout."
fi

echo "Dataflow Agent environment is ready."
echo "Use this Python for scripts:"
echo "  export DATAFLOW_PYTHON=\"${VENV_DIR}/bin/python\""
echo "Verify with:"
echo "  DATAFLOW_PYTHON=\"${VENV_DIR}/bin/python\" scripts/doctor.sh"
