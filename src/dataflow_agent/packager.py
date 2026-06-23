from __future__ import annotations

import json
import shutil
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from .constants import RuntimePaths
from .models import Finding, GraphModel, WorkbookData
from .util import file_sha256


def write_package_metadata(
    paths: RuntimePaths,
    workbook: WorkbookData,
    graph: GraphModel,
    validation_findings: list[Finding],
    risk_findings: list[Finding],
    env: str,
    version: str,
) -> dict:
    metadata = {
        "project": workbook.metadata.get("Project_Name", "Dataflow Project Data Flow Diagram"),
        "environment": env,
        "version": version,
        "generated_at": datetime.now(UTC).isoformat(),
        "generated_by": "dataflow-agent",
        "input_file": str(paths.workbook_path),
        "input_file_hash": file_sha256(paths.workbook_path),
        "node_count": len(graph.nodes),
        "edge_count": len(graph.edges),
        "validation_finding_count": len(validation_findings),
        "risk_finding_count": len(risk_findings),
        "blocking_validation_finding_count": len([f for f in validation_findings if f.severity in {"P0", "P1"}]),
        "license": "Proprietary; all rights reserved by edmund-xl",
    }
    (paths.package_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    return metadata


def write_package_readme(paths: RuntimePaths, metadata: dict) -> None:
    lines = [
        "# 中文版本",
        "",
        "# Dataflow Project 数据流图交付包工程白皮书",
        "",
        "## 摘要",
        "",
        "本文说明本次 Dataflow Project 数据流图交付包的生成范围、输入依据、处理结果和验收口径。交付包由智能体根据数据采集工作簿自动生成，包含归一化数据、图模型、分层图、验证报告、问题台账、验收清单和元数据。",
        "",
        "## 关键词",
        "",
        "数据流图；交付包；图模型；自动校验；问题台账；可重复生成。",
        "",
        "## 一、生成元数据",
        "",
        f"- 环境：{metadata['environment']}",
        f"- 版本：{metadata['version']}",
        f"- 生成时间：{metadata['generated_at']}",
        f"- 输入文件哈希：`{metadata['input_file_hash']}`",
        "",
        "## 二、生成结果",
        "",
        f"- 节点数量：{metadata['node_count']}",
        f"- 关系数量：{metadata['edge_count']}",
        f"- 校验问题数量：{metadata['validation_finding_count']}",
        f"- 风险问题数量：{metadata['risk_finding_count']}",
        f"- 阻断级校验问题数量：{metadata['blocking_validation_finding_count']}",
        f"- 版权与授权：{metadata['license']}",
        "",
        "## 三、结论",
        "",
        "本交付包中的图、报告和清单均来自同一份结构化工作簿。若产物存在错误，应修正源工作簿并重新运行脚本。",
        "",
        "---",
        "",
        "# English Version",
        "",
        "# Dataflow Project Data Flow Delivery Package Engineering White Paper",
        "",
        "## Abstract",
        "",
        "This document describes the generation scope, input basis, processing results, and acceptance criteria of this Dataflow Project data-flow delivery package. The package is generated automatically by the agent from the collection workbook and includes normalized data, graph models, layered diagrams, validation reports, issue registers, acceptance checklists, and metadata.",
        "",
        "## Keywords",
        "",
        "Data flow diagram; delivery package; graph model; automated validation; issue register; reproducible generation.",
        "",
        "## 1. Generation Metadata",
        "",
        f"- Environment: {metadata['environment']}",
        f"- Version: {metadata['version']}",
        f"- Generated at: {metadata['generated_at']}",
        f"- Input file hash: `{metadata['input_file_hash']}`",
        "",
        "## 2. Generation Results",
        "",
        f"- Node count: {metadata['node_count']}",
        f"- Edge count: {metadata['edge_count']}",
        f"- Validation finding count: {metadata['validation_finding_count']}",
        f"- Risk finding count: {metadata['risk_finding_count']}",
        f"- Blocking validation finding count: {metadata['blocking_validation_finding_count']}",
        f"- Copyright and license: {metadata['license']}",
        "",
        "## 3. Conclusion",
        "",
        "The diagrams, reports, and checklists in this package are derived from the same structured workbook. If an artifact is wrong, correct the source workbook and rerun the script.",
        "",
    ]
    (paths.package_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def assemble_package(paths: RuntimePaths) -> Path:
    input_dir = paths.package_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(paths.workbook_path, input_dir / paths.workbook_path.name)
    _copy_optional(paths.input_dir / "raw_exports", paths.package_dir / "evidence" / "raw_exports")
    _copy_optional(paths.input_dir / "evidence", paths.package_dir / "evidence")
    _copy_optional(paths.input_dir / "notes", paths.package_dir / "notes")
    _copy_optional(Path(__file__).resolve().parents[2] / "LICENSE", paths.package_dir / "LICENSE")
    zip_path = paths.output_root / f"{paths.package_dir.name}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file in sorted(paths.package_dir.rglob("*")):
            if file.is_file():
                zf.write(file, file.relative_to(paths.output_root))
    return zip_path


def _copy_optional(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    if src.is_dir():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
