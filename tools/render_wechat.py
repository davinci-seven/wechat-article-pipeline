#!/usr/bin/env python3
"""Render a frozen Markdown article into WeChat-compatible inline HTML."""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import mimetypes
import re
import shutil
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path


IMAGE_RE = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$")
HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$")
ORDERED_RE = re.compile(r"^\s*(\d+)\.\s+(.+)$")
UNORDERED_RE = re.compile(r"^\s*[-*]\s+(.+)$")
HR_RE = re.compile(r"^\s*(?:---+|\*\*\*+)\s*$")
TABLE_SEPARATOR_CELL_RE = re.compile(r"^:?-{3,}:?$")
QUOTE_RE = re.compile(r"^\s*>\s?(.*)$")

# 渲染器只实现公众号排版实际用得上的Markdown子集。不支持的语法必须报错停下，
# 不能默默把星号、大于号留在正文里，或者把行内图片吃掉还报成功。
UNSUPPORTED_RULES: list[tuple[str, re.Pattern[str], str]] = [
    (
        "行内图片",
        re.compile(r"(?<!^)!\[[^\]]*\]\([^)]+\)"),
        "图片必须独占一行，不能夹在句子中间",
    ),
    (
        "嵌套列表",
        re.compile(r"^(?:\s{2,}|\t)+[-*+]\s+\S"),
        "只支持单层列表，请改写成单层或分成多段",
    ),
    (
        "四级及以下标题",
        re.compile(r"^#{4,}\s+\S"),
        "只支持一到三级标题",
    ),
    (
        "HTML标签",
        re.compile(r"^\s*<(?!!--)[a-zA-Z][^>]*>"),
        "不支持在Markdown里直接写HTML",
    ),
]


@dataclass(frozen=True)
class Theme:
    """配色与排印变量。取自 gzh-design 各主题的「设计变量速查表」。"""

    key: str
    name_cn: str
    page_bg: str
    text: str
    heading: str
    accent: str
    accent_soft: str
    h1_bg: str
    h1_text: str
    h2_number: str
    h2_label: str
    h3_bg: str
    h3_text: str
    list_bg: str
    list_border: str
    list_text: str
    code_bg: str
    code_text: str
    code_lang: str
    inline_code_text: str
    inline_code_bg: str
    image_border: str
    caption: str
    hr: str
    strong: str
    font_size: str
    line_height: str
    letter_spacing: str
    para_gap: str
    chapter_gap: str


THEMES: dict[str, Theme] = {
    "olive-journal": Theme(
        key="olive-journal", name_cn="橄榄手记",
        page_bg="#fdfdf8", text="#4d4f46", heading="#191919",
        accent="#cf5a22", accent_soft="#e1d7c9",
        h1_bg="#171717", h1_text="#fffdf6",
        h2_number="#cf5a22", h2_label="#9e998f",
        h3_bg="#f4efe7", h3_text="#222",
        list_bg="#f6f1e9", list_border="#e7dfd2", list_text="#3f403a",
        code_bg="#1c1c1c", code_text="#f3ede3", code_lang="#e37a43",
        inline_code_text="#cf5a22", inline_code_bg="#f3eee5",
        image_border="#e7dfd2", caption="#8b877f", hr="#e1d7c9", strong="#181818",
        font_size="14px", line_height="1.9", letter_spacing="0.05px",
        para_gap="18px", chapter_gap="58px",
    ),
    "moyu-green": Theme(
        key="moyu-green", name_cn="摸鱼绿",
        page_bg="#ffffff", text="#374151", heading="#111827",
        accent="#059669", accent_soft="#A7F3D0",
        h1_bg="#111827", h1_text="#ffffff",
        h2_number="#059669", h2_label="#9CA3AF",
        h3_bg="#ECFDF5", h3_text="#111827",
        list_bg="#F0FDF4", list_border="#BBF7D0", list_text="#374151",
        code_bg="#111827", code_text="#F9FAFB", code_lang="#34D399",
        inline_code_text="#059669", inline_code_bg="#F3F4F6",
        image_border="#E5E7EB", caption="#9CA3AF", hr="#D1D5DB", strong="#111827",
        font_size="14px", line_height="1.9", letter_spacing="0.5px",
        para_gap="18px", chapter_gap="58px",
    ),
    "red-white": Theme(
        key="red-white", name_cn="红白色系",
        page_bg="#ffffff", text="#374151", heading="#1C1917",
        accent="#DC2626", accent_soft="#FECACA",
        h1_bg="#1C1917", h1_text="#ffffff",
        h2_number="#DC2626", h2_label="#9CA3AF",
        h3_bg="#FEF2F2", h3_text="#1C1917",
        list_bg="#FEF2F2", list_border="#FEE2E2", list_text="#374151",
        code_bg="#1C1917", code_text="#F5F5F4", code_lang="#FCA5A5",
        inline_code_text="#DC2626", inline_code_bg="#FEF2F2",
        image_border="#E5E7EB", caption="#9CA3AF", hr="#E5E7EB", strong="#1C1917",
        font_size="15px", line_height="1.8", letter_spacing="0.5px",
        para_gap="18px", chapter_gap="58px",
    ),
    "graphite-minimal": Theme(
        key="graphite-minimal", name_cn="石墨极简风",
        page_bg="#ffffff", text="#52525B", heading="#27272A",
        accent="#52525B", accent_soft="#E4E4E7",
        h1_bg="#27272A", h1_text="#ffffff",
        h2_number="#A1A1AA", h2_label="#A1A1AA",
        h3_bg="#FAFAFA", h3_text="#27272A",
        list_bg="#FAFAFA", list_border="#E4E4E7", list_text="#52525B",
        code_bg="#27272A", code_text="#FAFAFA", code_lang="#A1A1AA",
        inline_code_text="#3F3F46", inline_code_bg="#F4F4F5",
        image_border="#E4E4E7", caption="#A1A1AA", hr="#E4E4E7", strong="#27272A",
        font_size="15px", line_height="1.8", letter_spacing="0.3px",
        para_gap="18px", chapter_gap="56px",
    ),
    "zen-whitespace": Theme(
        key="zen-whitespace", name_cn="留白禅意风",
        page_bg="#ffffff", text="#525252", heading="#2B2B2B",
        accent="#4A5D52", accent_soft="#B5C8BC",
        h1_bg="#4A5D52", h1_text="#ffffff",
        h2_number="#B5C8BC", h2_label="#A3A3A3",
        h3_bg="#EEF3F0", h3_text="#2B2B2B",
        list_bg="#EEF3F0", list_border="#E8E8E8", list_text="#525252",
        code_bg="#2B2B2B", code_text="#F5F5F5", code_lang="#B5C8BC",
        inline_code_text="#3D5046", inline_code_bg="#EEF3F0",
        image_border="#E8E8E8", caption="#A3A3A3", hr="#E8E8E8", strong="#2B2B2B",
        font_size="15px", line_height="1.9", letter_spacing="0.3px",
        para_gap="26px", chapter_gap="64px",
    ),
    "moyu-ticket": Theme(
        key="moyu-ticket", name_cn="摸鱼票据风",
        page_bg="#fffef8", text="#555555", heading="#1a1a1a",
        accent="#059669", accent_soft="#A7F3D0",
        h1_bg="#1a1a1a", h1_text="#fffef8",
        h2_number="#059669", h2_label="#888888",
        h3_bg="#F0FDF4", h3_text="#1a1a1a",
        list_bg="#F0FDF4", list_border="#A7F3D0", list_text="#555555",
        code_bg="#1F2937", code_text="#F3F4F6", code_lang="#A7F3D0",
        inline_code_text="#1F2937", inline_code_bg="#F3F4F6",
        image_border="#1a1a1a", caption="#888888", hr="#A7F3D0", strong="#1a1a1a",
        font_size="14px", line_height="1.9", letter_spacing="0.5px",
        para_gap="18px", chapter_gap="32px",
    ),
}

DEFAULT_THEME = "olive-journal"


@dataclass
class Block:
    kind: str
    text: str = ""
    level: int = 0
    items: list[str] | None = None
    language: str = ""
    alt: str = ""
    src: str = ""
    rows: list[list[str]] | None = None
    aligns: list[str] | None = None


def column_aligns(separator_line: str) -> list[str]:
    """把 :---: / ---: / :--- 读成 center / right / left。"""
    aligns: list[str] = []
    for cell in split_table_row(separator_line):
        left = cell.startswith(":")
        right = cell.endswith(":")
        if left and right:
            aligns.append("center")
        elif right:
            aligns.append("right")
        else:
            aligns.append("left")
    return aligns


def split_table_row(line: str) -> list[str]:
    """Split a simple GFM table row while preserving escaped pipes."""
    value = line.strip()
    if value.startswith("|"):
        value = value[1:]
    if value.endswith("|") and not value.endswith(r"\|"):
        value = value[:-1]
    cells = re.split(r"(?<!\\)\|", value)
    return [cell.strip().replace(r"\|", "|") for cell in cells]


def is_table_separator(line: str) -> bool:
    cells = split_table_row(line)
    return len(cells) > 0 and all(
        TABLE_SEPARATOR_CELL_RE.fullmatch(cell) for cell in cells
    )


def find_unsupported(source: str) -> list[dict]:
    """扫描不支持的Markdown语法，返回行号和原因。"""
    findings: list[dict] = []
    in_code = False
    for number, line in enumerate(source.replace("\r\n", "\n").split("\n"), 1):
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        for name, pattern, hint in UNSUPPORTED_RULES:
            if pattern.search(line):
                findings.append(
                    {"line": number, "syntax": name, "hint": hint, "text": line.strip()[:120]}
                )
    return findings


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_markdown(source: str) -> list[Block]:
    lines = source.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: list[Block] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue

        if line.startswith("```"):
            language = line[3:].strip()
            code_lines: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].startswith("```"):
                code_lines.append(lines[index])
                index += 1
            if index < len(lines):
                index += 1
            blocks.append(Block("code", "\n".join(code_lines), language=language))
            continue

        if (
            "|" in line
            and index + 1 < len(lines)
            and is_table_separator(lines[index + 1])
        ):
            header = split_table_row(line)
            aligns = column_aligns(lines[index + 1])
            table_rows: list[list[str]] = []
            index += 2
            while index < len(lines) and lines[index].strip() and "|" in lines[index]:
                row = split_table_row(lines[index])
                if len(row) != len(header):
                    break
                table_rows.append(row)
                index += 1
            blocks.append(Block("table", items=header, rows=table_rows, aligns=aligns))
            continue

        image_match = IMAGE_RE.match(line)
        if image_match:
            blocks.append(Block("image", alt=image_match.group(1), src=image_match.group(2)))
            index += 1
            continue

        heading_match = HEADING_RE.match(line)
        if heading_match:
            blocks.append(
                Block("heading", heading_match.group(2), level=len(heading_match.group(1)))
            )
            index += 1
            continue

        if HR_RE.match(line):
            blocks.append(Block("hr"))
            index += 1
            continue

        quote_match = QUOTE_RE.match(line)
        if quote_match:
            quote_lines = [quote_match.group(1).strip()]
            index += 1
            while index < len(lines):
                following = QUOTE_RE.match(lines[index])
                if not following:
                    break
                quote_lines.append(following.group(1).strip())
                index += 1
            blocks.append(Block("quote", " ".join(x for x in quote_lines if x)))
            continue

        ordered_match = ORDERED_RE.match(line)
        if ordered_match:
            items: list[str] = []
            while index < len(lines):
                match = ORDERED_RE.match(lines[index])
                if not match:
                    break
                items.append(match.group(2))
                index += 1
            blocks.append(Block("ol", items=items))
            continue

        unordered_match = UNORDERED_RE.match(line)
        if unordered_match:
            items = []
            while index < len(lines):
                match = UNORDERED_RE.match(lines[index])
                if not match:
                    break
                items.append(match.group(1))
                index += 1
            blocks.append(Block("ul", items=items))
            continue

        paragraph_lines = [line.strip()]
        index += 1
        while index < len(lines):
            candidate = lines[index]
            if not candidate.strip():
                break
            if (
                candidate.startswith("```")
                or IMAGE_RE.match(candidate)
                or HEADING_RE.match(candidate)
                or HR_RE.match(candidate)
                or ORDERED_RE.match(candidate)
                or UNORDERED_RE.match(candidate)
            ):
                break
            paragraph_lines.append(candidate.strip())
            index += 1
        blocks.append(Block("paragraph", " ".join(paragraph_lines)))
    return blocks


def inline_plain(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"~~(.+?)~~", r"\1", text)
    text = re.sub(r"(?<!\*)\*(?!\*)([^*\n]+)\*(?!\*)", r"\1", text)
    text = text.replace("**", "").replace("`", "")
    return html.unescape(text)


def leaf(text: str) -> str:
    return f'<span leaf="">{html.escape(text, quote=False)}</span>'


def inline_html(text: str, theme: Theme) -> str:
    token_re = re.compile(
        r"(`[^`]+`"           # 行内代码
        r"|\*\*.+?\*\*"        # 粗体
        r"|~~.+?~~"            # 删除线
        r"|(?<!\*)\*(?!\*)[^*\n]+\*(?!\*)"  # 斜体，避开粗体的星号
        r"|\[[^\]]+\]\([^)]+\))"            # 链接
    )
    cursor = 0
    output: list[str] = []
    for match in token_re.finditer(text):
        if match.start() > cursor:
            output.append(leaf(text[cursor : match.start()]))
        token = match.group(0)
        if token.startswith("`"):
            output.append(
                '<code style="font-family:Consolas,Monaco,monospace;font-size:0.92em;'
                f'color:{theme.inline_code_text};background:{theme.inline_code_bg};'
                'padding:2px 5px;border-radius:3px;">'
                f"{leaf(token[1:-1])}</code>"
            )
        elif token.startswith("**"):
            output.append(
                f'<strong style="font-weight:700;color:{theme.strong};">'
                f"{leaf(token[2:-2])}</strong>"
            )
        elif token.startswith("~~"):
            output.append(
                '<span style="text-decoration:line-through;opacity:0.7;">'
                f"{leaf(token[2:-2])}</span>"
            )
        elif token.startswith("*"):
            output.append(
                '<span style="font-style:italic;">'
                f"{leaf(token[1:-1])}</span>"
            )
        else:
            link_match = re.match(r"\[([^\]]+)\]\(([^)]+)\)", token)
            assert link_match
            label, url = link_match.groups()
            output.append(
                f'<a href="{html.escape(url, quote=True)}" '
                f'style="color:{theme.accent};text-decoration:none;'
                f'border-bottom:1px solid {theme.accent};">'
                f"{leaf(label)}</a>"
            )
        cursor = match.end()
    if cursor < len(text):
        output.append(leaf(text[cursor:]))
    return "".join(output)


def resolve_image(article_dir: Path, raw_src: str) -> Path | None:
    if re.match(r"^https?://", raw_src, re.I):
        return None
    candidate = Path(raw_src)
    if not candidate.is_absolute():
        candidate = article_dir / candidate
    return candidate.resolve()


def data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def image_section(src: str, alt: str, theme: Theme, first: bool = False) -> str:
    top = "18px" if first else "30px"
    caption = (
        '<p style="margin:8px 8px 0;text-align:center;font-size:12px;line-height:1.65;'
        f'color:{theme.caption};">{leaf(alt)}</p>'
        if alt
        else ""
    )
    return (
        f'<section style="margin:{top} 0 0;padding:0;">'
        '<span leaf="">'
        f'<img src="{html.escape(src, quote=True)}" alt="{html.escape(alt, quote=True)}" '
        'style="display:block;width:100%;max-width:100%;height:auto;margin:0 auto;'
        f'border-radius:4px;border:1px solid {theme.image_border};" />'
        "</span>"
        f"{caption}</section>"
    )


def render_blocks(
    blocks: list[Block],
    image_sources: dict[int, str],
    theme: Theme,
    section_labels: list[str] | None = None,
) -> str:
    parts: list[str] = [
        '<section style="box-sizing:border-box;width:100%;max-width:100%;margin:0 auto;'
        f'padding:20px 16px 34px;background:{theme.page_bg};color:{theme.text};'
        'font-family:-apple-system,BlinkMacSystemFont,&quot;Segoe UI&quot;,'
        '&quot;Microsoft YaHei&quot;,Arial,sans-serif;'
        f'font-size:{theme.font_size};line-height:{theme.line_height};">'
    ]
    chapter = 0
    image_index = 0
    for block_index, block in enumerate(blocks):
        if block.kind == "heading" and block.level == 1:
            parts.append(
                f'<section style="margin:0;padding:23px 20px 20px;background:{theme.h1_bg};'
                f'border-top:5px solid {theme.accent};border-radius:3px;">'
                '<p style="margin:0;font-size:25px;line-height:1.35;font-weight:800;'
                f'letter-spacing:-0.5px;color:{theme.h1_text};">'
                f'{inline_html(block.text, theme)}</p>'
                "</section>"
            )
        elif block.kind == "heading" and block.level == 2:
            chapter += 1
            labels = section_labels or []
            label = labels[chapter - 1] if chapter <= len(labels) else "CHAPTER"
            heading_font_size = "17px" if len(block.text) >= 19 else "19px"
            parts.append(
                f'<section style="margin:{theme.chapter_gap} 0 22px;padding:0;">'
                '<section style="display:block;margin:0 0 7px;">'
                '<span leaf="" style="font-size:33px;line-height:1;font-weight:800;'
                f'color:{theme.h2_number};">'
                f"{chapter:02d}</span>"
                f'<span leaf="" style="margin-left:10px;font-size:10px;letter-spacing:2px;'
                f'color:{theme.h2_label};">{label}</span></section>'
                f'<p style="margin:0;font-size:{heading_font_size};line-height:1.5;font-weight:800;'
                f'color:{theme.heading};">{inline_html(block.text, theme)}</p>'
                f'<section style="width:42px;height:3px;margin-top:12px;'
                f'background:{theme.accent};"></section>'
                "</section>"
            )
        elif block.kind == "heading":
            parts.append(
                '<section style="margin:34px 0 14px;padding:10px 12px;'
                f'border-left:4px solid {theme.accent};background:{theme.h3_bg};">'
                f'<p style="margin:0;font-size:17px;line-height:1.55;font-weight:700;'
                f'color:{theme.h3_text};">{inline_html(block.text, theme)}</p></section>'
            )
        elif block.kind == "paragraph":
            parts.append(
                f'<p style="margin:0 0 {theme.para_gap};font-size:{theme.font_size};'
                f'line-height:{theme.line_height};'
                f'letter-spacing:{theme.letter_spacing};color:{theme.text};">'
                f'{inline_html(block.text, theme)}</p>'
            )
        elif block.kind == "image":
            src = image_sources[block_index]
            parts.append(image_section(src, block.alt, theme, first=image_index == 0))
            image_index += 1
        elif block.kind in {"ul", "ol"}:
            items = block.items or []
            list_parts: list[str] = [
                '<section style="margin:2px 0 20px;padding:14px 15px;'
                f'background:{theme.list_bg};border:1px solid {theme.list_border};'
                'border-radius:3px;">'
            ]
            for idx, item in enumerate(items, 1):
                marker = f"{idx:02d}" if block.kind == "ol" else "•"
                list_parts.append(
                    '<section style="margin:0 0 9px;padding:0;">'
                    f'<span leaf="" style="display:inline-block;min-width:28px;'
                    f'color:{theme.accent};'
                    f'font-weight:700;">{marker}</span>'
                    f'<span leaf="" style="display:inline;color:{theme.list_text};">'
                    f"{inline_html(item, theme)}</span></section>"
                )
            list_parts.append("</section>")
            parts.append("".join(list_parts))
        elif block.kind == "code":
            code_lines = block.text.split("\n") or [""]
            rendered_lines = []
            for code_line in code_lines:
                rendered_lines.append(
                    f'<p style="margin:0;font-family:Consolas,Monaco,monospace;'
                    f'font-size:12px;line-height:1.75;color:{theme.code_text};">'
                    f'{leaf(code_line or " ")}</p>'
                )
            language = (
                f'<p style="margin:0 0 8px;font-family:Consolas,Monaco,monospace;'
                f'font-size:10px;letter-spacing:1px;color:{theme.code_lang};">'
                f'{leaf(block.language.upper())}</p>'
                if block.language
                else ""
            )
            parts.append(
                '<section style="margin:4px 0 22px;padding:14px 16px;overflow-wrap:anywhere;'
                f'background:{theme.code_bg};border-left:4px solid {theme.accent};'
                'border-radius:3px;">'
                f"{language}{''.join(rendered_lines)}</section>"
            )
        elif block.kind == "table":
            headers = block.items or []
            rows = block.rows or []
            aligns = block.aligns or []
            align_of = lambda i: aligns[i] if i < len(aligns) else "left"
            table_parts = [
                '<section style="margin:4px 0 22px;overflow-x:auto;max-width:100%;">',
                '<table style="width:100%;border-collapse:collapse;table-layout:fixed;'
                f'font-size:13px;line-height:1.65;color:{theme.text};">',
                "<thead><tr>",
            ]
            for position, header in enumerate(headers):
                table_parts.append(
                    f'<th style="padding:10px 8px;text-align:{align_of(position)};'
                    'vertical-align:top;'
                    f'font-weight:700;color:{theme.heading};background:{theme.list_bg};'
                    f'border:1px solid {theme.list_border};overflow-wrap:anywhere;">'
                    f'{inline_html(header, theme)}</th>'
                )
            table_parts.append("</tr></thead><tbody>")
            for row in rows:
                table_parts.append("<tr>")
                for position, cell in enumerate(row):
                    table_parts.append(
                        f'<td style="padding:10px 8px;text-align:{align_of(position)};'
                        'vertical-align:top;'
                        f'border:1px solid {theme.list_border};overflow-wrap:anywhere;">'
                        f'{inline_html(cell, theme)}</td>'
                    )
                table_parts.append("</tr>")
            table_parts.append("</tbody></table></section>")
            parts.append("".join(table_parts))
        elif block.kind == "quote":
            parts.append(
                f'<section style="margin:6px 0 {theme.para_gap};padding:12px 14px;'
                f'border-left:4px solid {theme.accent_soft};background:{theme.h3_bg};">'
                f'<p style="margin:0;font-size:{theme.font_size};'
                f'line-height:{theme.line_height};color:{theme.text};">'
                f'{inline_html(block.text, theme)}</p></section>'
            )
        elif block.kind == "hr":
            parts.append(
                '<section style="margin:34px auto;width:100%;height:1px;'
                f'background:{theme.hr};"></section>'
            )
    parts.append("</section>")
    return "\n".join(parts)


def visible_fragments(blocks: list[Block]) -> list[str]:
    fragments: list[str] = []
    for block in blocks:
        if block.kind in {"heading", "paragraph", "quote"}:
            fragments.append(inline_plain(block.text))
        elif block.kind == "image" and block.alt:
            fragments.append(block.alt)
        elif block.kind in {"ul", "ol"}:
            fragments.extend(inline_plain(item) for item in (block.items or []))
        elif block.kind == "code":
            fragments.extend(block.text.split("\n"))
        elif block.kind == "table":
            fragments.extend(inline_plain(cell) for cell in (block.items or []))
            for row in block.rows or []:
                fragments.extend(inline_plain(cell) for cell in row)
    return [re.sub(r"\s+", " ", item).strip() for item in fragments if item.strip()]


def verify_order(rendered: str, fragments: list[str]) -> tuple[bool, list[str]]:
    parser = TextExtractor()
    parser.feed(rendered)
    # Inline Markdown is rendered as adjacent leaf spans. Joining parser events with
    # an artificial space would make an unchanged sentence look modified.
    haystack = re.sub(r"\s+", " ", html.unescape("".join(parser.parts))).strip()
    cursor = 0
    missing: list[str] = []
    for fragment in fragments:
        normalized = re.sub(r"\s+", " ", fragment).strip()
        found = haystack.find(normalized, cursor)
        if found < 0:
            missing.append(normalized[:120])
        else:
            cursor = found + len(normalized)
    return not missing, missing


def nearest_heading(blocks: list[Block], position: int) -> str:
    title = "文章开头"
    for block in blocks[: position + 1]:
        if block.kind == "heading":
            title = block.text
    return title


def write_xiaowan_documents(
    article_dir: Path,
    output_root: Path,
    markdown_path: Path,
    blocks: list[Block],
    image_rows: list[dict],
    theme: Theme,
) -> None:
    title = next((b.text for b in blocks if b.kind == "heading" and b.level == 1), markdown_path.stem)
    chapters = [b.text for b in blocks if b.kind == "heading" and b.level == 2]
    task = f"""# 公众号排版任务卡

- 文章：{title}
- 原稿：{markdown_path}
- 状态：正文冻结；仅允许排版、图片复制、路径稳定化和兼容性修复
- 手机端目标：390px 宽；一屏一个重点
- 视觉主题：{theme.name_cn}（{theme.key}），主色 {theme.accent}
- 正文排印：{theme.font_size} / 行高 {theme.line_height} / 字间距 {theme.letter_spacing}
- 图片规则：严格保持原稿顺序与原图注，不增删、不重排
- 发布规则：本脚本只生成与校验，绝不创建公众号草稿
"""
    (output_root / "排版任务卡.md").write_text(task, encoding="utf-8")

    evidence = [
        "# 图片证据表",
        "",
        "| 序号 | 图注 | 原始路径 | 所属章节 | 排版用途 |",
        "|---:|---|---|---|---|",
    ]
    for row in image_rows:
        evidence.append(
            f"| {row['index']} | {row['alt'].replace('|', '｜')} | "
            f"`{row['raw_src']}` | {row['section'].replace('|', '｜')} | "
            f"证明或展示“{row['alt'].replace('|', '｜')}” |"
        )
    (output_root / "图片证据表.md").write_text("\n".join(evidence) + "\n", encoding="utf-8")

    structure = [
        "# 手机端结构脚本",
        "",
        f"- 首屏：标题块“{title}”",
        "- 阅读宽度：390px；正文安全边距 16px",
        f"- 正文字号：{theme.font_size}；行高 {theme.line_height}；段间距 {theme.para_gap}",
        f"- 章节间距：{theme.chapter_gap}；章节标题控制孤行和短尾",
        "- 图片：100% 容器宽度，自适应高度，原图注居中显示",
        "- 强调预算：只保留原稿粗体、链接和代码强调，不自动给全文加下划线",
        "",
        "## 章节顺序",
        "",
    ]
    structure.extend(f"{idx}. {chapter}" for idx, chapter in enumerate(chapters, 1))
    structure.extend(
        [
            "",
            "## 手机端检查重点",
            "",
            "- 标题是否在 390px 下产生两三个字的孤行",
            "- 图片是否超出正文宽度或被拉伸",
            "- 代码块是否横向溢出",
            "- 列表序号、正文和留白是否对齐",
            "- 末尾作者信息和 CTA 是否保持原文",
        ]
    )
    (output_root / "手机端结构脚本.md").write_text("\n".join(structure) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    # 不用 required=True：--list-themes 是纯查询，不该被迫传文章路径。
    parser.add_argument("--markdown")
    parser.add_argument("--output-root")
    parser.add_argument(
        "--theme",
        default=DEFAULT_THEME,
        choices=sorted(THEMES),
        help=f"视觉主题，默认 {DEFAULT_THEME}",
    )
    parser.add_argument(
        "--section-labels",
        default="",
        help="二级标题旁的英文小标签，逗号分隔；缺省或用完后统一为 CHAPTER",
    )
    parser.add_argument(
        "--allow-unsupported",
        action="store_true",
        help="明确接受不支持语法被降级渲染，默认遇到就停",
    )
    parser.add_argument(
        "--list-themes",
        action="store_true",
        help="列出全部可用主题后退出",
    )
    args = parser.parse_args()

    if args.list_themes:
        for theme in THEMES.values():
            marker = "（默认）" if theme.key == DEFAULT_THEME else ""
            print(f"{theme.key:<18}{theme.name_cn:<8}主色 {theme.accent}{marker}")
        return 0

    if not args.markdown or not args.output_root:
        parser.error("--markdown 和 --output-root 为必填（除非使用 --list-themes）")

    theme = THEMES[args.theme]
    section_labels = [item.strip() for item in args.section_labels.split(",") if item.strip()]
    markdown_path = Path(args.markdown).resolve()
    article_dir = markdown_path.parent
    output_root = Path(args.output_root).resolve()
    output_dir = output_root / "output"
    assets_dir = output_dir / "assets"
    output_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)

    source = markdown_path.read_text(encoding="utf-8-sig")
    before_hash = sha256(markdown_path)

    unsupported = find_unsupported(source)
    if unsupported and not args.allow_unsupported:
        print(
            json.dumps(
                {
                    "ok": False,
                    "reason": "存在本渲染器不支持的Markdown语法",
                    "unsupported": unsupported,
                    "hint": "改写原稿，或加 --allow-unsupported 明确接受降级渲染",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 4
    blocks = parse_markdown(source)
    image_rows: list[dict] = []
    clean_sources: dict[int, str] = {}
    stable_sources: dict[int, str] = {}
    missing_images: list[str] = []
    used_names: set[str] = set()
    image_number = 0

    for block_index, block in enumerate(blocks):
        if block.kind != "image":
            continue
        image_number += 1
        resolved = resolve_image(article_dir, block.src)
        if resolved is None:
            clean_sources[block_index] = block.src
            stable_sources[block_index] = block.src
            status = "external"
            resolved_text = block.src
        elif not resolved.is_file():
            missing_images.append(str(resolved))
            clean_sources[block_index] = block.src
            stable_sources[block_index] = block.src
            status = "missing"
            resolved_text = str(resolved)
        else:
            filename = resolved.name
            if filename.lower() in used_names:
                filename = f"{image_number:02d}-{filename}"
            used_names.add(filename.lower())
            copied = assets_dir / filename
            shutil.copy2(resolved, copied)
            clean_sources[block_index] = f"assets/{filename}"
            stable_sources[block_index] = data_uri(resolved)
            status = "ok"
            resolved_text = str(resolved)
        image_rows.append(
            {
                "index": image_number,
                "alt": block.alt,
                "raw_src": block.src,
                "resolved": resolved_text,
                "section": nearest_heading(blocks, block_index),
                "status": status,
                "clean_src": clean_sources[block_index],
            }
        )

    if missing_images:
        print(json.dumps({"ok": False, "missing_images": missing_images}, ensure_ascii=False, indent=2))
        return 2

    clean_html = render_blocks(blocks, clean_sources, theme, section_labels)
    stable_html = render_blocks(blocks, stable_sources, theme, section_labels)
    fragments = visible_fragments(blocks)
    clean_ok, clean_missing = verify_order(clean_html, fragments)
    stable_ok, stable_missing = verify_order(stable_html, fragments)

    stem = markdown_path.stem
    tag = f"{stem}_排版_{theme.name_cn}({theme.key})"
    clean_path = output_dir / f"{tag}.html"
    stable_path = output_dir / f"{tag}_发布稳定版.html"
    mobile_page_path = output_dir / f"{tag}_手机截图页.html"
    clean_path.write_text(clean_html, encoding="utf-8")
    stable_path.write_text(stable_html, encoding="utf-8")
    mobile_page_path.write_text(
        """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>390px 手机端排版检查</title>
<style>
html,body{margin:0;padding:0;background:#eef0f2;-webkit-text-size-adjust:100%}
main{box-sizing:border-box;width:100%;max-width:390px;margin:0 auto;padding:8px;background:#eef0f2}
</style>
</head>
<body><main>"""
        + stable_html
        + "</main></body></html>",
        encoding="utf-8",
    )

    write_xiaowan_documents(article_dir, output_root, markdown_path, blocks, image_rows, theme)
    after_hash = sha256(markdown_path)
    report = {
        "ok": clean_ok and stable_ok and before_hash == after_hash,
        "markdown": str(markdown_path),
        "theme": theme.key,
        "theme_name": theme.name_cn,
        "unsupported_syntax": unsupported,
        "source_sha256_before": before_hash,
        "source_sha256_after": after_hash,
        "source_unchanged": before_hash == after_hash,
        "block_count": len(blocks),
        "image_count": image_number,
        "missing_image_count": 0,
        "images": image_rows,
        "content_order_clean_ok": clean_ok,
        "content_order_stable_ok": stable_ok,
        "clean_missing_fragments": clean_missing,
        "stable_missing_fragments": stable_missing,
        "clean_html": str(clean_path),
        "stable_html": str(stable_path),
        "mobile_screenshot_page": str(mobile_page_path),
    }
    report_path = output_root / "source-integrity.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_root / "image-map.json").write_text(
        json.dumps(image_rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 3


if __name__ == "__main__":
    sys.exit(main())
