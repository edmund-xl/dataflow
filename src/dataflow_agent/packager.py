from __future__ import annotations

import json
import shutil
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from .constants import RuntimePaths, SCHEMA_VERSION, TEMPLATE_VERSION
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
        "schema_version": workbook.metadata.get("Schema_Version") or SCHEMA_VERSION,
        "template_version": workbook.metadata.get("Template_Version") or TEMPLATE_VERSION,
        "input_file": str(paths.workbook_path),
        "input_file_hash": file_sha256(paths.workbook_path),
        "node_count": len(graph.nodes),
        "edge_count": len(graph.edges),
        "dropped_edge_count": len(graph.dropped_edges),
        "validation_finding_count": len(validation_findings),
        "risk_finding_count": len(risk_findings),
        "blocking_validation_finding_count": len([f for f in validation_findings if f.severity in {"P0", "P1"}]),
        "license": "MIT License",
    }
    merge_report = paths.reports_dir / "merge_report.json"
    if merge_report.exists():
        merge_data = json.loads(merge_report.read_text(encoding="utf-8"))
        metadata["merge_duplicate_count"] = merge_data.get("duplicate_count", 0)
        metadata["merge_conflict_count"] = merge_data.get("conflict_count", 0)
    if (paths.reports_dir / "DRAFT_CONFLICTS.md").exists():
        metadata["delivery_status"] = "Draft"
        metadata["draft_reason"] = "Unresolved merge conflicts exist; this package must not be used for final acceptance."
    else:
        metadata["delivery_status"] = "Final"
    (paths.package_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    return metadata


def write_package_readme(paths: RuntimePaths, metadata: dict) -> None:
    lines = [
        "# 中文版本",
        "",
        "# Dataflow Project 数据流图交付包说明",
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
        f"- Schema 版本：{metadata['schema_version']}",
        f"- Template 版本：{metadata['template_version']}",
        f"- 生成时间：{metadata['generated_at']}",
        f"- 输入文件哈希：`{metadata['input_file_hash']}`",
        "",
        "## 二、生成结果",
        "",
        f"- 节点数量：{metadata['node_count']}",
        f"- 关系数量：{metadata['edge_count']}",
        f"- 丢弃关系数量：{metadata['dropped_edge_count']}",
        f"- 校验问题数量：{metadata['validation_finding_count']}",
        f"- 风险问题数量：{metadata['risk_finding_count']}",
        f"- 阻断级校验问题数量：{metadata['blocking_validation_finding_count']}",
        f"- 开源授权：{metadata['license']}",
        f"- 交付状态：{metadata.get('delivery_status', 'Final')}",
        *( [f"- 草稿原因：{metadata['draft_reason']}"] if metadata.get("draft_reason") else [] ),
        "",
        "## 三、图形产物",
        "",
        "每个分层图均同时生成静态图和可编辑源图。SVG、PNG、PDF 用于直接阅读和交付归档，Mermaid 用于轻量审查，draw.io `.drawio` 文件可用 diagrams.net 打开并拖拽调整，GraphML `.graphml` 文件可导入 yEd、Gephi、Cytoscape 等工具。",
        "",
        "总览图和服务依赖图采用编号主数据流视图：图上只保留真实数据流线条，端口、协议和来源记录进入右侧 ledger。其他分层图使用统一的浅色 C4 架构配色，优先保证整体视觉稳定和可交付。",
        "",
        "风险和一致性判断不依赖人工看图。`reports/architecture_findings.md` 会直接分析 Excel/DCP 生成的 graph model、校验结果和风险结果，列出真实数据流链路、问题分组和源表修复位置。",
        "",
        "draw.io 和 GraphML 只用于展示编辑和工具交换，不是新的事实源。若架构关系、边界或数据流需要变更，必须修正源 Excel/DCP 并重新生成交付包。",
        "",
        "## 四、结论",
        "",
        "本交付包中的图、报告和清单均来自同一份结构化工作簿。若产物存在错误，应修正源工作簿并重新运行脚本。",
        "",
        "---",
        "",
        "# English Version",
        "",
        "# Dataflow Project Data Flow Delivery Package Notes",
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
        f"- Schema version: {metadata['schema_version']}",
        f"- Template version: {metadata['template_version']}",
        f"- Generated at: {metadata['generated_at']}",
        f"- Input file hash: `{metadata['input_file_hash']}`",
        "",
        "## 2. Generation Results",
        "",
        f"- Node count: {metadata['node_count']}",
        f"- Edge count: {metadata['edge_count']}",
        f"- Dropped edge count: {metadata['dropped_edge_count']}",
        f"- Validation finding count: {metadata['validation_finding_count']}",
        f"- Risk finding count: {metadata['risk_finding_count']}",
        f"- Blocking validation finding count: {metadata['blocking_validation_finding_count']}",
        f"- Open-source license: {metadata['license']}",
        f"- Delivery status: {metadata.get('delivery_status', 'Final')}",
        *( [f"- Draft reason: {metadata['draft_reason']}"] if metadata.get("draft_reason") else [] ),
        "",
        "## 3. Diagram Artifacts",
        "",
        "Each layered diagram is generated as both static outputs and editable source files. SVG, PNG, and PDF are for direct reading and delivery archiving; Mermaid is for lightweight review; draw.io `.drawio` files can be opened and manually adjusted in diagrams.net; GraphML `.graphml` files can be imported into tools such as yEd, Gephi, and Cytoscape.",
        "",
        "The overview and service dependency diagrams use numbered main-dataflow views: only real dataflow lines stay on the canvas, while ports, protocols, and source records are moved to the right-side ledger. Other layered diagrams use the same light C4 architecture palette to preserve a stable delivery appearance.",
        "",
        "Risk and consistency review does not depend on manually reading diagrams. `reports/architecture_findings.md` directly analyzes the graph model, validation findings, and risk findings generated from the Excel/DCP source, then lists real dataflow paths, finding groups, and source-sheet fix locations.",
        "",
        "draw.io and GraphML are for presentation editing and tool exchange only. They are not new factual sources. If architecture relationships, boundaries, or data flows change, correct the source Excel/DCP and regenerate the delivery package.",
        "",
        "## 4. Conclusion",
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
