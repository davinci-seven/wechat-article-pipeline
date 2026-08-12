#!/usr/bin/env python3
"""Sanitize generated reports before they are shared or committed publicly."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

SANITIZE_SUFFIXES = {".json", ".md", ".txt"}
SCAN_SUFFIXES = SANITIZE_SUFFIXES | {".html", ".htm"}


def read_text_any_encoding(path: Path) -> tuple[str, str]:
    """按BOM识别编码读取。

    Windows PowerShell 5.1 的 Tee-Object 默认写 UTF-16LE。以前这里一律按
    UTF-8 读，UTF-16 日志会被读成乱码，正则匹配不到绝对路径，清理静默失效，
    结果就是"隐私检查0 ERROR"但仓库里真的躺着本机路径。
    """
    raw = path.read_bytes()
    for bom, encoding in (
        (b"\xff\xfe\x00\x00", "utf-32"),
        (b"\x00\x00\xfe\xff", "utf-32"),
        (b"\xff\xfe", "utf-16"),
        (b"\xfe\xff", "utf-16"),
        (b"\xef\xbb\xbf", "utf-8-sig"),
    ):
        if raw.startswith(bom):
            return raw.decode(encoding, errors="replace"), encoding
    return raw.decode("utf-8", errors="replace"), "utf-8"

HIGH_RISK_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("OpenAI API key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\b")),
    ("GitHub token", re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{20,}\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b")),
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    (
        "secret assignment",
        re.compile(
            r"(?im)^\s*(?:APPSECRET|APP_SECRET|API_KEY|TOKEN|PASSWORD|SECRET)\s*[:=]\s*[^\s#]{8,}\s*$"
        ),
    ),
]

WARNING_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("email", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
    ("UUID", re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b", re.I)),
    ("private IPv4", re.compile(r"\b(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})\b")),
]

ABSOLUTE_PATH_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Windows absolute path", re.compile(r'(?<![A-Za-z0-9])[A-Za-z]:(?:\\{1,2})[^"\r\n<>|]+')),
    ("Unix user path", re.compile(r'/(?:Users|home)/[^/\s"\']+(?:/[^\s"\']*)?')),
]


def path_variants(path: Path) -> set[str]:
    text = str(path)
    return {
        text,
        text.replace("\\", "/"),
        text.replace("\\", "\\\\"),
    }


def replacement_pairs(article_dir: Path, layout_root: Path) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    entries: list[tuple[Path, str]] = [
        (layout_root, "<LAYOUT_ROOT>"),
        (article_dir, "<ARTICLE_DIR>"),
    ]

    homes: set[Path] = {Path.home().resolve()}
    for name in ("USERPROFILE", "HOME"):
        value = os.environ.get(name)
        if value:
            homes.add(Path(value).expanduser().resolve())
    entries.extend((home, "<USER_HOME>") for home in homes)

    entries.sort(key=lambda item: len(str(item[0])), reverse=True)
    for path, placeholder in entries:
        for variant in sorted(path_variants(path), key=len, reverse=True):
            pairs.append((variant, placeholder))
    return pairs


def sanitize_text(text: str, pairs: list[tuple[str, str]]) -> tuple[str, bool]:
    original = text
    for needle, replacement in pairs:
        if needle and needle in text:
            text = text.replace(needle, replacement)

    text = ABSOLUTE_PATH_PATTERNS[0][1].sub("<ABSOLUTE_PATH>", text)
    text = ABSOLUTE_PATH_PATTERNS[1][1].sub("<USER_PATH>", text)
    return text, text != original


def finding_rows(
    path: Path,
    text: str,
    *,
    absolute_paths_are_errors: bool,
) -> tuple[list[dict], list[dict]]:
    errors: list[dict] = []
    warnings: list[dict] = []

    for label, pattern in HIGH_RISK_PATTERNS:
        if pattern.search(text):
            errors.append({"file": str(path), "type": label})

    for label, pattern in ABSOLUTE_PATH_PATTERNS:
        matches = pattern.findall(text)
        if not matches:
            continue
        row = {"file": str(path), "type": label, "count": len(matches)}
        if absolute_paths_are_errors:
            errors.append(row)
        else:
            warnings.append(row)

    for label, pattern in WARNING_PATTERNS:
        matches = pattern.findall(text)
        if matches:
            warnings.append({"file": str(path), "type": label, "count": len(matches)})

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--article-dir", required=True)
    parser.add_argument("--layout-root", required=True)
    args = parser.parse_args()

    article_dir = Path(args.article_dir).resolve()
    layout_root = Path(args.layout_root).resolve()
    if not layout_root.is_dir():
        parser.error(f"输出目录不存在：{layout_root}")

    pairs = replacement_pairs(article_dir, layout_root)
    changed_files: list[str] = []
    errors: list[dict] = []
    warnings: list[dict] = []

    audit_path = layout_root / "privacy-audit.json"
    for path in sorted(layout_root.rglob("*")):
        suffix = path.suffix.lower()
        if not path.is_file() or path == audit_path or suffix not in SCAN_SUFFIXES:
            continue
        text, encoding = read_text_any_encoding(path)
        inspected = text
        if suffix in SANITIZE_SUFFIXES:
            inspected, changed = sanitize_text(text, pairs)
            # 非UTF-8的日志即使内容没变也重写一遍，统一成UTF-8，
            # 免得下次扫描又因为编码问题漏检。
            if changed or encoding != "utf-8":
                path.write_text(inspected, encoding="utf-8")
                if changed:
                    changed_files.append(str(path.relative_to(layout_root)))
        file_errors, file_warnings = finding_rows(
            path.relative_to(layout_root),
            inspected,
            absolute_paths_are_errors=suffix in SANITIZE_SUFFIXES,
        )
        errors.extend(file_errors)
        warnings.extend(file_warnings)

    result = {
        "ok": not errors,
        "changed_files": changed_files,
        "errors": errors,
        "warnings": warnings,
        "note": "warnings需要人工判断；errors处理完成前不要公开输出目录。",
    }
    audit_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
