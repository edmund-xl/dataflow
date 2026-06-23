# 中文版本

# 安全说明

## 摘要

本仓库是 Dataflow Project 数据流图智能体的开源工程仓库，不是生产环境数据仓库。仓库只应保存源码、脱敏样例、通用模板和说明文档，不应提交真实生产拓扑、真实导出文件或证据文件。

## 一、不得提交的内容

- 真实 DCP 工作簿、真实服务依赖、真实防火墙规则、真实 IAM / Service Account 明细。
- 原始云平台导出、命令输出、截图、证据目录和最终生成的交付包。
- 私钥、访问令牌、OAuth 凭证、服务账号密钥、数据库连接串和内部控制台地址。
- 未脱敏公网 IP、内部主机名、生产域名、真实人员联系方式和审批记录。

## 二、推荐处理方式

- 真实 DCP 保存在受控内部存储中，不进入 public Git。
- 提交样例前必须脱敏，并确认 `samples/` 只包含演示数据。
- 本地提交前运行：

```bash
scripts/scan_sensitive.sh
```

## 三、漏洞或泄露处理

如果发现敏感信息进入仓库，应立即停止继续传播，删除相关提交中的敏感内容，轮换受影响凭证，并在内部安全流程中记录处置结果。

---

# English Version

# Security Notes

## Abstract

This repository is the open-source engineering repository for the Dataflow Project data-flow agent. It is not a production data repository. It should contain source code, sanitized samples, generic templates, and documentation only.

## 1. Content That Must Not Be Committed

- Real DCP workbooks, real service dependencies, real firewall rules, and real IAM / Service Account details.
- Raw cloud exports, command outputs, screenshots, evidence folders, and generated delivery packages.
- Private keys, access tokens, OAuth credentials, service account keys, database connection strings, and internal console URLs.
- Unsanitized public IPs, internal hostnames, production domains, personal contact details, and approval records.

## 2. Recommended Handling

- Keep real DCPs in controlled internal storage, not in public Git.
- Sanitize samples before committing them, and ensure `samples/` contains demonstration data only.
- Before committing local changes, run:

```bash
scripts/scan_sensitive.sh
```

## 3. Incident Handling

If sensitive information enters the repository, stop further distribution, remove the sensitive content from the affected commits, rotate impacted credentials, and record the handling result through the internal security process.
