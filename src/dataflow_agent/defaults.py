from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from .constants import find_workbook
from .schema import load_schema
from .xlsx_reader import read_workbook


def infer_env_version(input_path: Path) -> tuple[str, str]:
    schema = load_schema()
    workbook_path = find_workbook(input_path.resolve())
    workbook = read_workbook(workbook_path, schema)
    env = workbook.metadata.get("Environment") or "unknown"
    version = workbook.metadata.get("Version") or f"v{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
    return _safe_token(env), _safe_token(version)


def default_check_output(input_path: Path) -> Path:
    resolved = input_path.resolve()
    if resolved.is_file():
        return resolved.parent / "agent_check"
    return resolved / "agent_check"


def default_build_output(input_path: Path) -> Path:
    resolved = input_path.resolve()
    if resolved.is_file():
        return resolved.parent / "dist"
    return resolved / "dist"


def default_merge_output() -> Path:
    return Path.cwd() / "dist"


def _safe_token(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in value.strip()) or "unknown"

