from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_schema(path: Path | None = None) -> dict[str, Any]:
    schema_path = path or project_root() / "schemas" / "workbook_schema.json"
    return json.loads(schema_path.read_text(encoding="utf-8"))

