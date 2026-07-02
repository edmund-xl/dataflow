# 中文版本

# 数据处理规则

## 规则

真实数据不进入 public Git。生成产物必须可重复生成；如果图或报告有错误，必须回到源工作簿修正。

## 一、目录规则

- `samples/`：只允许放脱敏演示数据。
- `templates/`：只允许放通用模板和脱敏模板资料。
- `raw_exports/`、`evidence/`、`input/private/`、`agent_check/`、`dist/`：不得提交 Git。
- 最终生成的 `dataflow_package_*.zip` 不提交 Git，应放在受控交付或归档位置。

## 二、真实 DCP 处理

- 真实 DCP 工作簿应存放在内部受控目录或文档系统中。
- 证据文件应按访问控制要求保存，避免无关人员读取生产拓扑和安全配置。
- 提交给仓库的样例必须替换真实项目名、IP、域名、账号、服务名和审批信息。
- 如果图或报告有错误，修正工作簿后重新生成，不手工修改生成产物。

## 三、本地检查

提交前运行：

```bash
scripts/scan_sensitive.sh
python -m pytest -q
```

---

# English Version

# Data Handling Rules

## Rule

Real data must not enter public Git. Generated artifacts must be reproducible; if a diagram or report is wrong, correct the source workbook.

## 1. Directory Rules

- `samples/`: sanitized demonstration data only.
- `templates/`: generic templates and sanitized template material only.
- `raw_exports/`, `evidence/`, `input/private/`, `agent_check/`, `dist/`: must not be committed to Git.
- Generated `dataflow_package_*.zip` files must not be committed to Git; store them in controlled delivery or archive locations.

## 2. Real DCP Handling

- Store real DCP workbooks in controlled internal folders or document systems.
- Store evidence files according to access-control requirements to avoid exposing production topology and security configuration.
- Replace real project names, IPs, domains, accounts, service names, and approval information before committing samples.
- If diagrams or reports are wrong, correct the workbook and regenerate; do not edit generated artifacts manually.

## 3. Local Checks

Before committing, run:

```bash
scripts/scan_sensitive.sh
python -m pytest -q
```
