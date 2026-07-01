from __future__ import annotations

from pathlib import Path

from .architecture_findings import write_architecture_findings
from .models import Finding
from .pipeline import PipelineState


def write_check_summaries(output_root: Path, state: PipelineState) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    findings = state.validation.findings + state.risks
    blocking = [f for f in findings if f.severity in {"P0", "P1"}]
    pending = [f for f in findings if f.status == "Pending_Confirmation"]
    _write_summary(output_root / "check_summary.md", state, findings, blocking, pending)
    _write_fix_list(output_root / "fix_list.md", findings)
    write_architecture_findings(output_root / "architecture_findings.md", state.normalized_workbook, state.graph, state.validation.findings, state.risks)


def _write_summary(
    path: Path,
    state: PipelineState,
    findings: list[Finding],
    blocking: list[Finding],
    pending: list[Finding],
) -> None:
    status = "PASS" if not blocking else "NEEDS_FIX"
    submit_cn = "可以提交给数据汇总负责人。" if status == "PASS" else "暂不建议提交；请先处理 P0/P1 或阻断级问题。"
    submit_en = "Ready to submit to the data aggregation owner." if status == "PASS" else "Do not submit yet; resolve P0/P1 or blocking findings first."
    lines = [
        "# 中文版本",
        "",
        "# Dataflow Project 采集包自检摘要",
        "",
        "## 结论",
        "",
        f"- 自检状态：`{status}`",
        f"- 提交判断：{submit_cn}",
        f"- 下一步：{'可进入汇总或出包流程。' if status == 'PASS' else '打开 `fix_list.md`，修改源工作簿后重新运行 `scripts/check_dcp.sh`。'}",
        "",
        "## 关键指标",
        "",
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
        "## 处理规则",
        "",
        "所有问题都应回到源工作簿修正。不要手工修改生成的报告、图或压缩包。",
        "",
        "## 开源授权",
        "",
        "本项目采用 MIT License 开源授权。版权归属 edmund-xl；使用者可以在遵守许可证条款的前提下复制、使用、修改、分发和商用本软件副本。完整授权文本见仓库根目录 `LICENSE` 文件。",
        "",
        "---",
        "",
        "# English Version",
        "",
        "# Dataflow Project Collection Package Check Summary",
        "",
        "## Conclusion",
        "",
        f"- Check status: `{status}`",
        f"- Submission decision: {submit_en}",
        f"- Next step: {'Proceed to aggregation or package generation.' if status == 'PASS' else 'Open `fix_list.md`, correct the source workbook, and rerun `scripts/check_dcp.sh`.'}",
        "",
        "## Key Metrics",
        "",
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
        "## Handling Rule",
        "",
        "Correct every issue in the source workbook. Do not manually edit generated reports, diagrams, or archives.",
        "",
        "## Open-Source License",
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
    blocking_count = len([finding for finding in sorted_findings if finding.severity in {"P0", "P1"}])
    lines = [
        "# 中文版本",
        "",
        "# 修复清单",
        "",
        "## 处理结论",
        "",
        f"- 发现问题：{len(sorted_findings)}",
        f"- 阻断或高优先级问题：{blocking_count}",
        "- 处理方式：只修改源工作簿，然后重新运行自检脚本。",
        "- 建议顺序：先处理 P0/P1，再处理 Pending_Confirmation 和 P2/P3。",
        "",
    ]
    _append_finding_groups_cn(lines, sorted_findings)
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
            "# Fix List",
            "",
            "## Operational Conclusion",
            "",
            f"- Findings: {len(sorted_findings)}",
            f"- Blocking or high-priority findings: {blocking_count}",
            "- Handling: edit only the source workbook, then rerun the self-check script.",
            "- Recommended order: resolve P0/P1 first, then Pending_Confirmation and P2/P3.",
            "",
        ]
    )
    _append_finding_groups_en(lines, sorted_findings)
    lines.extend(
        [
            "## Open-Source License",
            "",
            "This project is released under the MIT License. Copyright remains with edmund-xl, and users may copy, use, modify, distribute, and use the software commercially subject to the license terms. The full license text is available in the repository root `LICENSE` file.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _append_finding_groups_cn(lines: list[str], findings: list[Finding]) -> None:
    current_group = ""
    for idx, finding in enumerate(findings, 1):
        group = f"{finding.severity} / {finding.sheet}"
        if group != current_group:
            current_group = group
            lines.extend([f"## {group}", ""])
        lines.extend(
            [
                f"### {idx}. {finding.row_id or '未指定主键'}",
                "",
                f"- 字段：{finding.field or '无'}",
                f"- 门禁：{_gate_cn(finding.gate)}",
                f"- 状态：{finding.status}",
                f"- 问题：{_finding_summary_cn(finding)}",
                f"- 修复建议：{_finding_action_cn(finding)}",
                f"- 证据：{finding.evidence_id or '无'}",
                "",
            ]
        )


def _append_finding_groups_en(lines: list[str], findings: list[Finding]) -> None:
    current_group = ""
    for idx, finding in enumerate(findings, 1):
        group = f"{finding.severity} / {finding.sheet}"
        if group != current_group:
            current_group = group
            lines.extend([f"## {group}", ""])
        lines.extend(
            [
                f"### {idx}. {finding.row_id or 'No row id'}",
                "",
                f"- Field: {finding.field or 'N/A'}",
                f"- Gate: {finding.gate}",
                f"- Status: {finding.status}",
                f"- Message: {finding.message}",
                f"- Suggested action: {finding.suggested_action or 'Review and correct the source workbook.'}",
                f"- Evidence: {finding.evidence_id or 'N/A'}",
                "",
            ]
        )


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


def _finding_action_cn(finding: Finding) -> str:
    if finding.suggested_action:
        return _translate_action_cn(finding.suggested_action)
    if finding.status == "Pending_Confirmation":
        return "确认该记录，或在源表中改成已接受例外后再提交。"
    return "复核该行并在源工作簿中修正。"


def _translate_action_cn(action: str) -> str:
    lowered = action.lower()
    if "monitoring" in lowered or "dashboard" in lowered or "alert" in lowered:
        return "在 `10_Monitoring` 中补充对应对象的监控、日志、告警或仪表盘记录。"
    if "firewall" in lowered:
        return "在 `07_Firewalls` 中补充关联规则，或在源表中记录已接受例外。"
    if "confirm the row" in lowered:
        return "确认该记录后把 `Confirmation_Status` 改为 `Confirmed`，或按流程记录例外。"
    if "correct the id" in lowered or "missing target" in lowered:
        return "修正引用 ID，或补充被引用的目标记录。"
    if "fill" in lowered:
        return "补齐源工作簿中的必填字段。"
    return action
