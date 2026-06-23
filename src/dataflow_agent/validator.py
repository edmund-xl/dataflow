from __future__ import annotations

import ipaddress
from typing import Iterable

from .models import Finding, ValidationResult, WorkbookData
from .util import safe_id, split_multi


def validate_workbook(workbook: WorkbookData, schema: dict) -> ValidationResult:
    result = ValidationResult()
    _validate_sheets_and_headers(workbook, schema, result)
    _validate_required_values(workbook, schema, result)
    _validate_primary_keys(workbook, schema, result)
    _validate_enums(workbook, schema, result)
    _validate_types(workbook, schema, result)
    _validate_foreign_keys(workbook, schema, result)
    _validate_dependency_targets(workbook, result)
    _validate_monitoring_targets(workbook, result)
    _validate_evidence_refs(workbook, result)
    return result


def _validate_sheets_and_headers(workbook: WorkbookData, schema: dict, result: ValidationResult) -> None:
    for sheet in schema["required_sheets"]:
        if sheet not in workbook.sheets:
            result.add(Finding("Gate 1", "P0", sheet, "", "", f"Missing required sheet {sheet}"))
            continue
        expected = schema["sheets"][sheet]["fields"]
        actual = workbook.headers.get(sheet, [])
        missing = [field for field in expected if field not in actual]
        if missing:
            result.add(
                Finding(
                    "Gate 1",
                    "P0",
                    sheet,
                    "",
                    ",".join(missing),
                    f"Missing required fields: {', '.join(missing)}",
                    "Restore the workbook header from the approved template.",
                )
            )


def _validate_required_values(workbook: WorkbookData, schema: dict, result: ValidationResult) -> None:
    for sheet, config in schema["sheets"].items():
        required = config.get("required_fields", [])
        pk = config.get("primary_key", "")
        for row in workbook.sheets.get(sheet, []):
            row_id = row.get("Record_ID") or row.get(pk) or row.get("Field", "")
            if _inactive(row):
                continue
            for field in required:
                if field in workbook.headers.get(sheet, []) and not row.get(field, ""):
                    result.add(
                        Finding(
                            "Gate 1",
                            "P1",
                            sheet,
                            row_id,
                            field,
                            f"Required field {field} is blank.",
                            "Fill the workbook source row or mark it Not_Applicable when valid.",
                        )
                    )


def _validate_primary_keys(workbook: WorkbookData, schema: dict, result: ValidationResult) -> None:
    for sheet, config in schema["sheets"].items():
        pk = config.get("primary_key", "")
        if not pk:
            continue
        seen: dict[str, str] = {}
        for row in workbook.sheets.get(sheet, []):
            if _inactive(row):
                continue
            value = row.get(pk, "")
            row_id = row.get("Record_ID") or value
            if not value:
                continue
            if value in seen:
                result.add(
                    Finding(
                        "Gate 1",
                        "P0",
                        sheet,
                        row_id,
                        pk,
                        f"Duplicate primary key {value}; first seen at {seen[value]}.",
                        "Make primary keys unique before regenerating artifacts.",
                    )
                )
            else:
                seen[value] = row_id


def _validate_enums(workbook: WorkbookData, schema: dict, result: ValidationResult) -> None:
    enum_fields = workbook.enums or schema.get("enum_fields", {})
    for sheet, rows in workbook.sheets.items():
        pk = schema.get("sheets", {}).get(sheet, {}).get("primary_key", "")
        for row in rows:
            if _inactive(row):
                continue
            row_id = row.get("Record_ID") or row.get(pk, "")
            for field, allowed in enum_fields.items():
                if field in row and row[field]:
                    if not _enum_applies(sheet, field):
                        continue
                    values = split_multi(row[field]) if ";" in row[field] else [row[field]]
                    allowed_norm = {item.lower() for item in allowed}
                    for value in values:
                        if value and value.lower() not in allowed_norm:
                            result.add(
                                Finding(
                                    "Gate 1",
                                    "P2",
                                    sheet,
                                    row_id,
                                    field,
                                    f"Unexpected enum value {value}; allowed values are {', '.join(allowed)}.",
                                    "Use a value from 90_Enums or update the approved enum list.",
                                )
                            )


def _validate_types(workbook: WorkbookData, schema: dict, result: ValidationResult) -> None:
    for sheet, rows in workbook.sheets.items():
        pk = schema.get("sheets", {}).get(sheet, {}).get("primary_key", "")
        for row in rows:
            if _inactive(row):
                continue
            row_id = row.get("Record_ID") or row.get(pk, "")
            for field in ("Port", "Ports", "Listen_Ports", "Target_Port"):
                if field in row and row[field]:
                    for value in split_multi(row[field]):
                        if "-" in value:
                            start, _, end = value.partition("-")
                            if not (_is_port(start) and _is_port(end)):
                                _type_finding(result, sheet, row_id, field, row[field], "valid port or port range")
                        elif not _is_port(value):
                            _type_finding(result, sheet, row_id, field, row[field], "valid port")
            if row.get("CIDR"):
                try:
                    ipaddress.ip_network(row["CIDR"], strict=False)
                except ValueError:
                    _type_finding(result, sheet, row_id, "CIDR", row["CIDR"], "valid CIDR")
            for field in ("IP_Internal", "IP_External"):
                if row.get(field):
                    try:
                        ipaddress.ip_address(row[field])
                    except ValueError:
                        _type_finding(result, sheet, row_id, field, row[field], "valid IP address")


def _type_finding(result: ValidationResult, sheet: str, row_id: str, field: str, value: str, expected: str) -> None:
    result.add(
        Finding(
            "Gate 1",
            "P1",
            sheet,
            row_id,
            field,
            f"{field} value {value} is not a {expected}.",
            "Correct the field value in the source workbook.",
        )
    )


def _validate_foreign_keys(workbook: WorkbookData, schema: dict, result: ValidationResult) -> None:
    indexes = _indexes(workbook, schema)
    for source_sheet, source_field, target_sheet, target_field, mode in schema.get("foreign_keys", []):
        target_values = indexes.get((target_sheet, target_field), set())
        for row in workbook.sheets.get(source_sheet, []):
            if _inactive(row):
                continue
            row_id = row.get("Record_ID") or row.get(schema["sheets"][source_sheet].get("primary_key", ""), "")
            values = split_multi(row.get(source_field, "")) if mode == "optional_multi" else [row.get(source_field, "")]
            for value in values:
                if not value:
                    if mode == "required":
                        result.add(Finding("Gate 2", "P0", source_sheet, row_id, source_field, f"Required foreign key {source_field} is blank."))
                    continue
                if value not in target_values:
                    result.add(
                        Finding(
                            "Gate 2",
                            "P0" if mode == "required" else "P1",
                            source_sheet,
                            row_id,
                            source_field,
                            f"{source_field}={value} does not exist in {target_sheet}.{target_field}.",
                            "Correct the ID or add the missing target row.",
                        )
                    )


def _validate_dependency_targets(workbook: WorkbookData, result: ValidationResult) -> None:
    indexes = _dependency_target_indexes(workbook)
    for row in workbook.sheets.get("05_Dependencies", []):
        if _inactive(row):
            continue
        row_id = row.get("Record_ID") or row.get("Dependency_ID", "")
        target_type = row.get("Target_Type", "")
        target_id = row.get("Target_ID", "")
        if target_type or target_id:
            if not target_type:
                result.add(Finding("Gate 2", "P1", "05_Dependencies", row_id, "Target_Type", "Target_ID is populated but Target_Type is blank.", "Fill Target_Type so the dependency can be resolved deterministically."))
                continue
            if not target_id:
                result.add(Finding("Gate 2", "P1", "05_Dependencies", row_id, "Target_ID", "Target_Type is populated but Target_ID is blank.", "Fill Target_ID or remove Target_Type."))
                continue
            normalized_type = _normalize_target_type(target_type)
            if normalized_type not in indexes:
                result.add(Finding("Gate 2", "P1", "05_Dependencies", row_id, "Target_Type", f"Unsupported dependency Target_Type={target_type}.", "Use an approved Target_Type value or update the schema."))
                continue
            if target_id not in indexes[normalized_type]:
                result.add(
                    Finding(
                        "Gate 2",
                        "P1",
                        "05_Dependencies",
                        row_id,
                        "Target_ID",
                        f"Target_ID={target_id} does not exist for Target_Type={target_type}.",
                        "Correct Target_ID, Target_Type, or add the missing target row.",
                    )
                )
            _validate_interaction_mode(row, row_id, normalized_type, result)
            continue
        targets = [row.get("Target_Service_ID", ""), row.get("Target_External_ID", ""), row.get("Target_Data_Asset_ID", "")]
        if not any(targets):
            result.add(
                Finding(
                    "Gate 2",
                    "P0",
                    "05_Dependencies",
                    row_id,
                    "Target_*",
                    "Dependency has no target service, external service, or data asset.",
                    "Populate exactly the target field that represents this dependency.",
                )
            )
        _validate_interaction_mode(row, row_id, _legacy_target_type(row), result)


def _dependency_target_indexes(workbook: WorkbookData) -> dict[str, set[str]]:
    runtime_ids = {
        row.get("Runtime_ID") or f"runtime:{safe_id(row.get('Service_ID', ''))}"
        for row in workbook.sheets.get("04_Services", [])
        if not _inactive(row) and (row.get("Runtime_Type") or row.get("Runtime_ID")) and row.get("Service_ID")
    }
    return {
        "service": {row.get("Service_ID", "") for row in workbook.sheets.get("04_Services", []) if row.get("Service_ID") and not _inactive(row)},
        "external_service": {row.get("External_ID", "") for row in workbook.sheets.get("12_External_Services", []) if row.get("External_ID") and not _inactive(row)},
        "data_asset": {row.get("Data_Asset_ID", "") for row in workbook.sheets.get("06_Data_Assets", []) if row.get("Data_Asset_ID") and not _inactive(row)},
        "runtime": {value for value in runtime_ids if value},
        "firewall_rule": {row.get("Firewall_ID", "") for row in workbook.sheets.get("07_Firewalls", []) if row.get("Firewall_ID") and not _inactive(row)},
        "monitoring_control": {row.get("Monitoring_ID", "") for row in workbook.sheets.get("10_Monitoring", []) if row.get("Monitoring_ID") and not _inactive(row)},
    }


def _normalize_target_type(value: str) -> str:
    lowered = value.lower()
    if lowered in {"service", "internal_service"}:
        return "service"
    if lowered in {"external", "external_service"}:
        return "external_service"
    if lowered in {"data_asset", "data", "storage", "database"}:
        return "data_asset"
    if lowered in {"runtime", "kubernetes", "cloudrun", "cloud_run"}:
        return "runtime"
    if lowered in {"firewall", "firewall_rule", "security_control"}:
        return "firewall_rule"
    if lowered in {"monitoring", "monitoring_control"}:
        return "monitoring_control"
    return lowered


def _legacy_target_type(row: dict[str, str]) -> str:
    if row.get("Target_Data_Asset_ID"):
        return "data_asset"
    if row.get("Target_External_ID"):
        return "external_service"
    if row.get("Target_Service_ID"):
        return "service"
    return ""


def _validate_interaction_mode(row: dict[str, str], row_id: str, target_type: str, result: ValidationResult) -> None:
    mode = row.get("Interaction_Mode", "").lower()
    if not mode:
        return
    if mode in {"read", "write", "produce", "publish"} and target_type not in {"data_asset", "external_service"}:
        result.add(
            Finding(
                "Gate 2",
                "P2",
                "05_Dependencies",
                row_id,
                "Interaction_Mode",
                f"Interaction_Mode={row.get('Interaction_Mode')} usually targets data_asset or external_service, but target type is {target_type}.",
                "Confirm the interaction mode and target type.",
            )
        )
    if mode in {"sync", "async", "stream"} and target_type == "data_asset":
        result.add(
            Finding(
                "Gate 2",
                "P2",
                "05_Dependencies",
                row_id,
                "Interaction_Mode",
                f"Interaction_Mode={row.get('Interaction_Mode')} on a data_asset target may be ambiguous.",
                "Use read/write/batch where possible or document the reason.",
            )
        )


def _validate_monitoring_targets(workbook: WorkbookData, result: ValidationResult) -> None:
    target_map = {
        "project": ("01_Projects", "Project_ID"),
        "network": ("02_Networks", "Network_ID"),
        "server": ("03_Servers", "Instance_ID"),
        "instance": ("03_Servers", "Instance_ID"),
        "service": ("04_Services", "Service_ID"),
        "dependency": ("05_Dependencies", "Dependency_ID"),
        "data_asset": ("06_Data_Assets", "Data_Asset_ID"),
        "firewall_rule": ("07_Firewalls", "Firewall_ID"),
        "external_service": ("12_External_Services", "External_ID"),
    }
    indexes = {
        key: {row.get(field, "") for row in workbook.sheets.get(sheet, []) if row.get(field, "") and not _inactive(row)}
        for key, (sheet, field) in target_map.items()
    }
    for row in workbook.sheets.get("10_Monitoring", []):
        if _inactive(row):
            continue
        obj_type = row.get("Object_Type", "").lower()
        obj_id = row.get("Object_ID", "")
        if obj_type in indexes and obj_id and obj_id not in indexes[obj_type]:
            result.add(
                Finding(
                    "Gate 2",
                    "P1",
                    "10_Monitoring",
                    row.get("Record_ID") or row.get("Monitoring_ID", ""),
                    "Object_ID",
                    f"Monitoring object {obj_id} does not exist for Object_Type={row.get('Object_Type')}.",
                    "Correct Object_ID or Object_Type in the monitoring row.",
                )
            )


def _validate_evidence_refs(workbook: WorkbookData, result: ValidationResult) -> None:
    evidence_ids = {row.get("Evidence_ID", "") for row in workbook.sheets.get("14_Evidence_Index", []) if row.get("Evidence_ID")}
    for sheet, rows in workbook.sheets.items():
        if sheet == "14_Evidence_Index":
            continue
        for row in rows:
            if _inactive(row):
                continue
            row_id = row.get("Record_ID") or row.get("Issue_ID") or row.get("Field", "")
            for field in ("Evidence_ID", "Related_Evidence_ID"):
                for evidence_id in split_multi(row.get(field, "")):
                    if evidence_id and evidence_id not in evidence_ids:
                        result.add(
                            Finding(
                                "Gate 2",
                                "P1",
                                sheet,
                                row_id,
                                field,
                                f"Evidence reference {evidence_id} is missing from 14_Evidence_Index.",
                                "Add the evidence row or correct the reference.",
                            )
                        )


def _indexes(workbook: WorkbookData, schema: dict) -> dict[tuple[str, str], set[str]]:
    result: dict[tuple[str, str], set[str]] = {}
    for sheet, config in schema["sheets"].items():
        pk = config.get("primary_key", "")
        if pk:
            result[(sheet, pk)] = {row.get(pk, "") for row in workbook.sheets.get(sheet, []) if row.get(pk, "") and not _inactive(row)}
    return result


def _is_port(value: str) -> bool:
    return value.isdigit() and 0 < int(value) <= 65535


def _inactive(row: dict[str, str]) -> bool:
    return row.get("Confirmation_Status") in {"Rejected", "Not_Applicable"}


def _enum_applies(sheet: str, field: str) -> bool:
    if field == "Status" and sheet != "13_Issues_Exceptions":
        return False
    return True


def merge_findings(*groups: Iterable[Finding]) -> list[Finding]:
    findings: list[Finding] = []
    for group in groups:
        findings.extend(group)
    return findings
