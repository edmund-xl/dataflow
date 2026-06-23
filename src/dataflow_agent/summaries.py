from __future__ import annotations

from pathlib import Path

from .models import Finding
from .pipeline import PipelineState


def write_check_summaries(output_root: Path, state: PipelineState) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    findings = state.validation.findings + state.risks
    blocking = [f for f in findings if f.severity in {"P0", "P1"}]
    pending = [f for f in findings if f.status == "Pending_Confirmation"]
    _write_summary(output_root / "check_summary.md", state, findings, blocking, pending)
    _write_fix_list(output_root / "fix_list.md", findings)


def _write_summary(
    path: Path,
    state: PipelineState,
    findings: list[Finding],
    blocking: list[Finding],
    pending: list[Finding],
) -> None:
    status = "PASS" if not blocking else "NEEDS_FIX"
    lines = [
        "# 中文版本",
        "",
        "# Dataflow Project 采集包自检摘要工程白皮书",
        "",
        "## 摘要",
        "",
        "本文记录当前采集包的智能体自检结果，用于判断采集数据是否具备提交或汇总条件。",
        "",
        "## 一、结果摘要",
        "",
        f"- 状态：{status}",
        f"- 工作簿：`{state.paths.workbook_path}`",
        f"- 产物目录：`{state.paths.package_dir}`",
        f"- 节点数量：{len(state.graph.nodes)}",
        f"- 关系数量：{len(state.graph.edges)}",
        f"- 校验问题数量：{len(state.validation.findings)}",
        f"- 风险问题数量：{len(state.risks)}",
        f"- 阻断问题数量：{len(blocking)}",
        f"- 待确认问题数量：{len(pending)}",
        f"- 丢弃关系数量：{len(state.graph.dropped_edges)}",
        "",
        "## 二、使用结论",
        "",
        "如果状态为 `NEEDS_FIX`，请先阅读修复清单并修改源工作簿，然后重新运行自检脚本。",
        "",
        "## 三、开源授权",
        "",
        "本项目采用 MIT License 开源授权。版权归属 edmund-xl；使用者可以在遵守许可证条款的前提下复制、使用、修改、分发和商用本软件副本。完整授权文本见仓库根目录 `LICENSE` 文件。",
        "",
        "---",
        "",
        "# English Version",
        "",
        "# Dataflow Project Collection Package Check Summary Engineering White Paper",
        "",
        "## Abstract",
        "",
        "This document records the agent self-check result for the current collection package and helps determine whether the data is ready for submission or aggregation.",
        "",
        "## 1. Result Summary",
        "",
        f"- Status: {status}",
        f"- Workbook: `{state.paths.workbook_path}`",
        f"- Package directory: `{state.paths.package_dir}`",
        f"- Graph nodes: {len(state.graph.nodes)}",
        f"- Graph edges: {len(state.graph.edges)}",
        f"- Validation findings: {len(state.validation.findings)}",
        f"- Risk findings: {len(state.risks)}",
        f"- Blocking findings: {len(blocking)}",
        f"- Pending confirmation findings: {len(pending)}",
        f"- Dropped graph edges: {len(state.graph.dropped_edges)}",
        "",
        "## 2. Operational Conclusion",
        "",
        "If the status is `NEEDS_FIX`, read the fix list, correct the source workbook, and run the self-check script again.",
        "",
        "## 3. Open-Source License",
        "",
        "This project is released under the MIT License. Copyright remains with edmund-xl, and users may copy, use, modify, distribute, and use the software commercially subject to the license terms. The full license text is available in the repository root `LICENSE` file.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_fix_list(path: Path, findings: list[Finding]) -> None:
    if not findings:
        path.write_text(
            "# 中文版本\n\n# 修复清单\n\n无校验或风险问题。\n\n## 开源授权\n\n本项目采用 MIT License 开源授权。版权归属 edmund-xl；使用者可以在遵守许可证条款的前提下复制、使用、修改、分发和商用本软件副本。完整授权文本见仓库根目录 `LICENSE` 文件。\n\n---\n\n# English Version\n\n# Fix List\n\nNo validation or risk findings.\n\n## Open-Source License\n\nThis project is released under the MIT License. Copyright remains with edmund-xl, and users may copy, use, modify, distribute, and use the software commercially subject to the license terms. The full license text is available in the repository root `LICENSE` file.\n",
            encoding="utf-8",
        )
        return
    sorted_findings = sorted(findings, key=lambda f: (_severity_order(f.severity), f.sheet, f.row_id, f.field))
    lines = [
        "# 中文版本",
        "",
        "# 修复清单工程白皮书",
        "",
        "## 摘要",
        "",
        "本文列出智能体发现的待修复项。请先处理高严重度问题，再处理待确认和普通风险项。",
        "",
    ]
    for idx, finding in enumerate(sorted_findings, 1):
        lines.extend(
            [
                f"## {idx}. [{finding.severity}] {finding.sheet} {finding.row_id}",
                "",
                f"- 门禁：{_gate_cn(finding.gate)}",
                f"- 字段：{finding.field or '无'}",
                f"- 问题摘要：{_finding_summary_cn(finding)}",
                f"- 状态：{finding.status}",
                "",
            ]
        )
    lines.extend(
        [
            "## 开源授权",
            "",
            "本项目采用 MIT License 开源授权。版权归属 edmund-xl；使用者可以在遵守许可证条款的前提下复制、使用、修改、分发和商用本软件副本。完整授权文本见仓库根目录 `LICENSE` 文件。",
            "",
            "---",
            "",
            "# English Version",
            "",
            "# Fix List Engineering White Paper",
            "",
            "## Abstract",
            "",
            "This document lists findings that require correction. Address higher-severity issues first, then pending confirmations and ordinary risks.",
            "",
            "## Open-Source License",
            "",
            "This project is released under the MIT License. Copyright remains with edmund-xl, and users may copy, use, modify, distribute, and use the software commercially subject to the license terms. The full license text is available in the repository root `LICENSE` file.",
            "",
        ]
    )
    for idx, finding in enumerate(sorted_findings, 1):
        lines.extend(
            [
                f"## {idx}. [{finding.severity}] {finding.sheet} {finding.row_id}",
                "",
                f"- Gate: {finding.gate}",
                f"- Field: {finding.field or 'N/A'}",
                f"- Message: {finding.message}",
                f"- Suggested action: {finding.suggested_action or 'Review and correct the source workbook.'}",
                f"- Status: {finding.status}",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def _severity_order(severity: str) -> int:
    return {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "Info": 4}.get(severity, 9)


def _gate_cn(gate: str) -> str:
    return {
        "Gate 1": "门禁一",
        "Gate 2": "门禁二",
        "Gate 3": "门禁三",
        "Gate 4": "门禁四",
        "Gate 5": "门禁五",
    }.get(gate, gate)


def _finding_summary_cn(finding: Finding) -> str:
    if finding.status == "Pending_Confirmation":
        return "该记录仍处于待确认状态，不能作为最终事实直接验收。"
    if "monitoring" in finding.message.lower():
        return "关键对象缺少监控覆盖记录，需要补充监控、日志或告警信息。"
    if "firewall" in finding.message.lower():
        return "关键依赖缺少防火墙关联或放行原因，需要补充规则或例外说明。"
    if "foreign key" in finding.message.lower() or "does not exist" in finding.message.lower():
        return "引用对象不存在，需要修正标识或补充目标记录。"
    if "required field" in finding.message.lower() or "blank" in finding.message.lower():
        return "必填字段为空，需要在源工作簿中补充。"
    if "duplicate" in finding.message.lower():
        return "主键或记录重复，需要去重或调整标识。"
    return "智能体发现该记录需要复核，请结合机器可读报告查看原始细节。"
