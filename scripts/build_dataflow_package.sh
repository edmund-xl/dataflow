#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: scripts/build_dataflow_package.sh <DCP directory or workbook file>" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DCP_INPUT="$1"

if [[ -n "${DATAFLOW_PYTHON:-}" ]]; then
  PYTHON_BIN="${DATAFLOW_PYTHON}"
else
  PYTHON_BIN="python3"
fi

cd "${REPO_ROOT}"
exec "${PYTHON_BIN}" -m dataflow_agent.cli quick-build "${DCP_INPUT}"
