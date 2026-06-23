#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: scripts/check_dcp.sh <DCP directory or workbook file>" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DCP_INPUT="$1"

if [[ -n "${DATAFLOW_PYTHON:-}" ]]; then
  PYTHON_BIN="${DATAFLOW_PYTHON}"
elif [[ -x "/Users/xinglei/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3" ]]; then
  PYTHON_BIN="/Users/xinglei/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
else
  PYTHON_BIN="python3"
fi

cd "${REPO_ROOT}"
exec "${PYTHON_BIN}" -m dataflow_agent.cli check "${DCP_INPUT}"

