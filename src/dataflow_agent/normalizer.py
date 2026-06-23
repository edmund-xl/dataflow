from __future__ import annotations

from .models import Row, WorkbookData
from .util import clean


def normalize_workbook(workbook: WorkbookData, schema: dict) -> WorkbookData:
    normalized_sheets: dict[str, list[Row]] = {}
    for sheet, rows in workbook.sheets.items():
        normalized_sheets[sheet] = [_normalize_row(row) for row in rows if not _is_rejected(row)]
    metadata = {key: clean(value) for key, value in workbook.metadata.items()}
    return WorkbookData(
        path=workbook.path,
        sheets=normalized_sheets,
        headers=workbook.headers,
        metadata=metadata,
        enums=workbook.enums,
    )


def active_rows(workbook: WorkbookData, sheet: str) -> list[Row]:
    return [row for row in workbook.sheets.get(sheet, []) if row.get("Confirmation_Status") not in {"Rejected", "Not_Applicable"}]


def formal_rows(workbook: WorkbookData, sheet: str) -> list[Row]:
    return [row for row in active_rows(workbook, sheet) if row.get("Confirmation_Status") in {"Confirmed", "Auto_Detected", ""}]


def _normalize_row(row: Row) -> Row:
    result = {key: clean(value) for key, value in row.items()}
    if result.get("Protocol"):
        result["Protocol"] = result["Protocol"].upper()
    if result.get("Target_Port_Protocol"):
        result["Target_Port_Protocol"] = result["Target_Port_Protocol"].upper()
    if not result.get("Confirmation_Status") and "Confirmation_Status" in result:
        result["Confirmation_Status"] = "Pending_Confirmation"
    return result


def _is_rejected(row: Row) -> bool:
    return row.get("Confirmation_Status") == "Rejected"

