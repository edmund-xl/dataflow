from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


BUSINESS_SHEETS = [
    "00_Metadata",
    "01_Projects",
    "02_Networks",
    "03_Servers",
    "04_Services",
    "05_Dependencies",
    "06_Data_Assets",
    "07_Firewalls",
    "08_Cloud_Armor",
    "09_IAM_SA",
    "10_Monitoring",
    "11_CICD",
    "12_External_Services",
    "13_Issues_Exceptions",
    "14_Evidence_Index",
    "90_Enums",
]

WORKBOOK_CANDIDATES = [
    "dataflow_collection_template_v0.1.xlsx",
    "dataflow_collection_template_v1.0.xlsx",
    "dataflow_sample_input_v0.1.xlsx",
]

CONFIRMED_STATUSES = {"Confirmed", "Auto_Detected", "Pending_Confirmation"}
EXCLUDED_STATUSES = {"Rejected", "Not_Applicable"}

OUTPUT_PACKAGE_PREFIX = "dataflow_package"


@dataclass(frozen=True)
class RuntimePaths:
    input_dir: Path
    workbook_path: Path
    output_root: Path
    package_dir: Path
    normalized_dir: Path
    diagrams_dir: Path
    reports_dir: Path


def make_runtime_paths(input_dir: Path, output_root: Path, version: str) -> RuntimePaths:
    package_name = f"{OUTPUT_PACKAGE_PREFIX}_{version}"
    package_dir = output_root / package_name
    return RuntimePaths(
        input_dir=input_dir,
        workbook_path=find_workbook(input_dir),
        output_root=output_root,
        package_dir=package_dir,
        normalized_dir=package_dir / "normalized",
        diagrams_dir=package_dir / "diagrams",
        reports_dir=package_dir / "reports",
    )


def find_workbook(input_dir: Path) -> Path:
    if input_dir.is_file() and input_dir.suffix.lower() == ".xlsx":
        return input_dir
    if input_dir.exists() and not input_dir.is_dir():
        raise FileNotFoundError(f"Input path is not an .xlsx workbook or DCP directory: {input_dir}")
    if not input_dir.exists():
        raise FileNotFoundError(f"Input path does not exist: {input_dir}")
    for name in WORKBOOK_CANDIDATES:
        candidate = input_dir / name
        if candidate.exists():
            return candidate
    matches = sorted(input_dir.glob("*.xlsx"))
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        names = ", ".join(path.name for path in matches)
        raise FileNotFoundError(
            "Multiple workbook files found but no standard workbook name was present. "
            f"Use one of {', '.join(WORKBOOK_CANDIDATES)} or pass the workbook file explicitly. Found: {names}"
        )
    raise FileNotFoundError(f"No workbook found in {input_dir}")
