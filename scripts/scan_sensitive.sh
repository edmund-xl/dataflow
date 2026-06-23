#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"

python3 - <<'PY'
from __future__ import annotations

import ipaddress
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode("utf-8").split("\0")
tracked = [item for item in tracked if item]

forbidden_path_patterns = (
    re.compile(r"(^|/)raw_exports/"),
    re.compile(r"(^|/)evidence/"),
    re.compile(r"(^|/)input/private/"),
    re.compile(r"(^|/)agent_check/"),
    re.compile(r"(^|/)dist/"),
    re.compile(r"(^|/)dataflow_package_[^/]*\.zip$"),
)
private_key_patterns = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r'"private_key"\s*:'),
)
service_account_pattern = re.compile(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.iam\.gserviceaccount\.com", re.I)
ipv4_pattern = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

text_suffixes = {".md", ".py", ".toml", ".sh", ".txt", ".json", ".csv", ".yml", ".yaml"}
excluded_content_roots = ("samples/", "templates/")
findings: list[str] = []

for rel in tracked:
    for pattern in forbidden_path_patterns:
        if pattern.search(rel):
            findings.append(f"forbidden tracked path: {rel}")
            break

for rel in tracked:
    if rel.startswith(excluded_content_roots):
        continue
    path = ROOT / rel
    if path.suffix.lower() not in text_suffixes:
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    for pattern in private_key_patterns:
        if pattern.search(text):
            findings.append(f"private key marker: {rel}")
            break
    if service_account_pattern.search(text):
        findings.append(f"service account email: {rel}")
    for match in ipv4_pattern.finditer(text):
        value = match.group(0)
        try:
            ip = ipaddress.ip_address(value)
        except ValueError:
            continue
        if ip.is_global:
            findings.append(f"public IPv4 address {value}: {rel}")

if findings:
    print("Sensitive data scan failed:", file=sys.stderr)
    for finding in findings:
        print(f"- {finding}", file=sys.stderr)
    sys.exit(1)

print("Sensitive data scan passed.")
PY
