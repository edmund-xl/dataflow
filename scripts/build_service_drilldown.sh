#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: scripts/build_service_drilldown.sh <DCP directory or workbook file> <Service_ID> [--depth N] [--direction upstream|downstream|both] [--theme auto|light|dark|security] [--risk-focus]" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DCP_INPUT="$1"
SERVICE_ID="$2"
shift 2

if [[ -n "${DATAFLOW_PYTHON:-}" ]]; then
  PYTHON_BIN="${DATAFLOW_PYTHON}"
else
  PYTHON_BIN="python3"
fi

cd "${REPO_ROOT}"
exec "${PYTHON_BIN}" -m dataflow_agent.cli drilldown --input "${DCP_INPUT}" --service-id "${SERVICE_ID}" "$@"
