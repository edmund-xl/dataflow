# 中文版本

# 样例数据说明

## 用途

`samples/` 目录只保存脱敏演示数据，用于验证脚本、自检、建图、报告和打包流程。这里不得包含真实生产环境信息。

## 使用规则

- 可以提交脱敏的演示 DCP。
- 不得提交真实生产 DCP、真实证据、真实导出文件或生成的交付包。
- 如果需要复现生产问题，应先在内部环境脱敏，再复制到样例目录。

## 样例目录

- `DCP_clean_v0.1/`：干净通过样例，适合首次安装、自检、打包和合并验证。
- `DCP_v0.1/`：风险演示样例，适合查看 `fix_list.md`、风险规则和待确认项效果。

---

# English Version

# Sample Data Notes

## Purpose

The `samples/` directory stores sanitized demonstration data only. Use it to validate scripts, self-checks, graph generation, reporting, and packaging. It must not contain real production information.

## Usage Rules

- Sanitized demonstration DCPs may be committed.
- Real production DCPs, real evidence, raw exports, and generated delivery packages must not be committed.
- To reproduce a production issue, sanitize it in an internal environment before copying it into the sample directory.

## Sample Directories

- `DCP_clean_v0.1/`: clean passing sample for first-run setup, self-check, package, and merge validation.
- `DCP_v0.1/`: risk-demo sample for reviewing `fix_list.md`, risk rules, and pending-confirmation behavior.
