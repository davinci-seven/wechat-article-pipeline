"""五套公开版式的固定骨架。

standard 六套仍走 render_wechat.py 里的原结构。这里每种 layout 是一套
不会随文章变化的骨架：刊头、标题、列表、引用、图片框。配色和刊头文字
来自 Theme，方便以后只加一份 JSON 就复用某种版式。
"""

from __future__ import annotations

import html
from dataclasses import replace

from render_wechat import (
    Block,
    ImageView,
    Theme,
    inline_html,
    leaf,
    placeholder_section,
    resolve_view,
)

SANS = (
    "-apple-system,BlinkMacSystemFont,'PingFang SC','Hiragino Sans GB',"
    "'Microsoft YaHei',sans-serif"
)


def font_of(theme: Theme, which: str) -> str:
    chosen = theme.heading_font if which == "heading" else theme.body_font
    return chosen or SANS


def colored_inline(theme: Theme, text: str, color: str) -> str:
    """标题压在深色底上时，粗体和链接跟着变浅，避免深色字贴在深色底上。"""
    return inline_html(text, replace(theme, strong=color, accent=color))


def root_open(theme: Theme, pad: str = "22px 18px 36px") -> str:
    return (
        '<section style="box-sizing:border-box;width:100%;max-width:100%;margin:0 auto;'
        f"padding:{pad};background:{theme.page_bg};color:{theme.text};"
        f"font-family:{font_of(theme, 'body')};font-size:{theme.font_size};"
        f"line-height:{theme.line_height};letter-spacing:{theme.letter_spacing};"
        'overflow-wrap:break-word;">'
    )


def root_close(theme: Theme, size: str = "13px") -> str:
    footer = ""
    if theme.account:
        footer = (
            f'<p style="margin:32px 0 0;text-align:center;font-size:{size};line-height:1.6;'
            f'letter-spacing:2px;color:{theme.caption};">{leaf("— " + theme.account + " —")}</p>'
        )
    return footer + "</section>"


def masthead(
    theme: Theme,
    *,
    align: str = "left",
    size: str = "13px",
    tag_size: str = "12px",
    color: str = "",
    tracking: str = "2px",
    gap: str = "14px",
) -> str:
    if not theme.account and not theme.tagline:
        return ""
    align_css = "text-align:center;" if align == "center" else ""
    ink = color or theme.accent
    bits: list[str] = []
    if theme.account:
        bits.append(
            f'<p style="margin:0;{align_css}font-size:{size};line-height:1.6;font-weight:700;'
            f'letter-spacing:{tracking};color:{ink};">{leaf(theme.account)}</p>'
        )
    if theme.tagline:
        bits.append(
            f'<p style="margin:3px 0 0;{align_css}font-size:{tag_size};line-height:1.6;'
            f'letter-spacing:1px;color:{theme.caption};">{leaf(theme.tagline)}</p>'
        )
    return f'<section style="margin:0 0 {gap};">{"".join(bits)}</section>'


def seal_mark(theme: Theme) -> str:
    if not theme.seal:
        return ""
    return (
        '<p style="margin:0 0 10px;text-align:center;">'
        f'<span style="display:inline-block;border:1px solid {theme.accent};padding:4px 7px;'
        f"color:{theme.accent};font-size:15px;line-height:1.2;letter-spacing:2px;"
        f"font-family:{font_of(theme, 'heading')};\">{leaf(theme.seal)}</span></p>"
    )


def label_for(section_labels: list[str] | None, chapter: int, fallback: str) -> str:
    labels = section_labels or []
    if 1 <= chapter <= len(labels):
        return labels[chapter - 1]
    return fallback


def paragraph(theme: Theme, block: Block, extra: str = "") -> str:
    return (
        f'<p style="margin:0 0 {theme.para_gap};font-size:{theme.font_size};'
        f"line-height:{theme.line_height};letter-spacing:{theme.letter_spacing};"
        f'color:{theme.text};{extra}">'
        f"{inline_html(block.text, theme)}</p>"
    )


def themed_picture(theme: Theme, view: ImageView, first: bool) -> str:
    if not view.show:
        return placeholder_section(theme, view, first=first)
    if theme.layout == "kitchen":
        top = "10px" if first else "16px"
    elif first:
        top = "18px"
    else:
        top = "28px"
    cap_size = "15px" if theme.layout == "gazette" else "13px"
    caption = (
        f'<p style="margin:8px 8px 0;text-align:center;font-size:{cap_size};line-height:1.65;'
        f'color:{theme.caption};">{leaf(view.alt)}</p>'
        if view.alt
        else ""
    )
    note = ""
    if view.marker:
        note_size = "16px" if theme.layout == "gazette" else "12px"
        note = (
            f'<p style="margin:4px 8px 0;text-align:center;font-size:{note_size};line-height:1.6;'
            f'font-weight:700;color:{theme.accent};">{leaf(view.marker)}</p>'
        )
    radius = theme.image_radius or "4px"
    width = theme.image_border_width or "1px"
    return (
        f'<section style="margin:{top} 0 0;padding:0;">'
        "<span leaf=\"\">"
        f'<img src="{html.escape(view.src, quote=True)}" alt="{html.escape(view.alt, quote=True)}" '
        'style="display:block;width:100%;max-width:100%;height:auto;margin:0 auto;'
        f"border-radius:{radius};border:{width} solid {theme.image_border};\" />"
        "</span>"
        f"{caption}{note}</section>"
    )


def render_code(
    theme: Theme,
    block: Block,
    *,
    size: str,
    radius: str = "0",
) -> str:
    lines = block.text.split("\n") or [""]
    rendered = [
        f'<p style="margin:0;font-family:Consolas,Monaco,monospace;font-size:{size};'
        f'line-height:1.75;color:{theme.code_text};">{leaf(line or " ")}</p>'
        for line in lines
    ]
    language = ""
    if block.language:
        language = (
            f'<p style="margin:0 0 8px;font-family:Consolas,Monaco,monospace;font-size:{size};'
            f'letter-spacing:1px;color:{theme.code_lang};">{leaf(block.language.upper())}</p>'
        )
    return (
        '<section style="margin:4px 0 22px;padding:14px 16px;overflow-wrap:anywhere;'
        f"background:{theme.code_bg};border-left:4px solid {theme.accent};border-radius:{radius};\">"
        f"{language}{''.join(rendered)}</section>"
    )


def render_table(
    theme: Theme,
    block: Block,
    *,
    size: str,
    header_bg: str,
    header_color: str,
    font: str = "",
) -> str:
    headers = block.items or []
    rows = block.rows or []
    aligns = block.aligns or []
    font_css = f"font-family:{font};" if font else ""

    def align_of(index: int) -> str:
        return aligns[index] if index < len(aligns) else "left"

    def cell(text: str, color: str) -> str:
        if color.lower() in {"#fff", "#ffffff"}:
            return colored_inline(theme, text, color)
        return inline_html(text, theme)

    parts = [
        '<section style="margin:4px 0 22px;overflow-x:auto;max-width:100%;">',
        '<table style="width:100%;border-collapse:collapse;table-layout:fixed;'
        f'font-size:{size};line-height:1.65;color:{theme.text};{font_css}">',
        "<thead><tr>",
    ]
    for position, header in enumerate(headers):
        parts.append(
            f'<th style="padding:10px 8px;text-align:{align_of(position)};vertical-align:top;'
            f"font-weight:700;color:{header_color};background:{header_bg};"
            f"border:1px solid {theme.list_border};overflow-wrap:anywhere;\">"
            f"{cell(header, header_color)}</th>"
        )
    parts.append("</tr></thead><tbody>")
    for row in rows:
        parts.append("<tr>")
        for position, item in enumerate(row):
            parts.append(
                f'<td style="padding:10px 8px;text-align:{align_of(position)};vertical-align:top;'
                f"border:1px solid {theme.list_border};overflow-wrap:anywhere;\">"
                f"{inline_html(item, theme)}</td>"
            )
        parts.append("</tr>")
    parts.append("</tbody></table></section>")
    return "".join(parts)


def airy_list(theme: Theme, block: Block, *, font: str = "", gap: str = "12px") -> str:
    font_css = f"font-family:{font};" if font else ""
    parts = ['<section style="margin:0 0 22px;">']
    for index, item in enumerate(block.items or [], 1):
        marker = f"{index:02d}" if block.kind == "ol" else "·"
        parts.append(
            f'<section style="margin:0 0 {gap};">'
            f'<span leaf="" style="display:inline-block;min-width:28px;color:{theme.accent};'
            f'font-weight:700;{font_css}">{leaf(marker)}</span>'
            f'<span leaf="" style="color:{theme.list_text};font-size:{theme.font_size};'
            f'line-height:{theme.line_height};{font_css}">'
            f"{inline_html(item, theme)}</span></section>"
        )
    parts.append("</section>")
    return "".join(parts)


def rule(theme: Theme, width: str, height: str, margin: str) -> str:
    return (
        f'<section style="width:{width};height:{height};margin:{margin};'
        f'background:{theme.accent};"></section>'
    )


def h1_text(theme: Theme, block: Block, *, size: str, weight: str, color: str, extra: str = "") -> str:
    painter = colored_inline if color.lower() in {"#fff", "#ffffff"} else inline_html
    # colored_inline always takes a color; inline_html uses the theme as-is.
    inner = painter(theme, block.text, color) if painter is colored_inline else inline_html(block.text, theme)
    return (
        f'<p style="margin:0;font-size:{size};line-height:1.45;font-weight:{weight};'
        f"color:{color};{extra}\">{inner}</p>"
    )


def heading_diary(theme: Theme, block: Block, chapter: int, section_labels: list[str] | None) -> str:
    face = font_of(theme, "heading")
    if block.level == 1:
        return (
            '<section style="margin:4px 0 22px;text-align:center;">'
            + h1_text(
                theme,
                block,
                size="26px",
                weight="600",
                color=theme.h1_text,
                extra=f"font-family:{face};letter-spacing:1px;",
            )
            + rule(theme, "36px", "2px", "14px auto 0")
            + "</section>"
        )
    if block.level == 2:
        label = label_for(section_labels, chapter, "日记")
        return (
            f'<section style="margin:{theme.chapter_gap} 0 18px;">'
            f'<p style="margin:0;font-family:{face};font-size:20px;line-height:1.5;'
            f'font-weight:600;color:{theme.heading};">'
            f'<span leaf="" style="color:{theme.accent};">{leaf(f"{chapter:02d}")}</span>'
            f'<span style="margin-left:8px;">{inline_html(block.text, theme)}</span></p>'
            f'<p style="margin:6px 0 0;font-size:13px;line-height:1.6;letter-spacing:2px;'
            f'color:{theme.caption};">{leaf(label)}</p></section>'
        )
    return (
        '<section style="margin:28px 0 12px;padding:8px 12px;border-radius:8px;'
        f'background:{theme.h3_bg};">'
        f'<p style="margin:0;font-family:{face};font-size:17px;line-height:1.6;font-weight:600;'
        f'color:{theme.h3_text};">{inline_html(block.text, theme)}</p></section>'
    )


def heading_gazette(theme: Theme, block: Block, chapter: int, section_labels: list[str] | None) -> str:
    if block.level == 1:
        return (
            '<section style="margin:0 0 20px;padding:18px 16px;'
            f'background:{theme.h1_bg};">'
            + h1_text(theme, block, size="26px", weight="800", color=theme.h1_text)
            + "</section>"
        )
    if block.level == 2:
        custom = label_for(section_labels, chapter, "")
        prefix = f"{chapter:02d}" if not custom else f"{chapter:02d} {custom}"
        return (
            f'<section style="margin:{theme.chapter_gap} 0 16px;padding:12px 14px;'
            f'background:{theme.accent};">'
            f'<p style="margin:0;font-size:20px;line-height:1.45;font-weight:800;color:#ffffff;">'
            f'<span leaf="">{leaf(prefix)}</span>'
            f'<span style="margin-left:8px;">{colored_inline(theme, block.text, "#ffffff")}</span>'
            "</p></section>"
        )
    return (
        '<section style="margin:26px 0 12px;padding:10px 12px;'
        f"background:{theme.h3_bg};border-left:6px solid {theme.accent};\">"
        f'<p style="margin:0;font-size:18px;line-height:1.55;font-weight:800;color:{theme.h3_text};">'
        f"{inline_html(block.text, theme)}</p></section>"
    )


def heading_memo(theme: Theme, block: Block, chapter: int, section_labels: list[str] | None) -> str:
    if block.level == 1:
        return (
            '<section style="margin:16px 0 16px;">'
            + h1_text(theme, block, size="22px", weight="700", color=theme.h1_text)
            + "</section>"
        )
    if block.level == 2:
        label = label_for(section_labels, chapter, "条款")
        return (
            f'<section style="margin:{theme.chapter_gap} 0 12px;padding:0 0 8px;'
            f"border-bottom:1px solid {theme.accent};\">"
            f'<p style="margin:0 0 4px;font-size:13px;line-height:1.5;letter-spacing:1px;'
            f'color:{theme.accent};">{leaf(f"{chapter:02d}  {label}")}</p>'
            f'<p style="margin:0;font-size:18px;line-height:1.5;font-weight:700;color:{theme.heading};">'
            f"{inline_html(block.text, theme)}</p></section>"
        )
    return (
        f'<p style="margin:22px 0 8px;font-size:16px;line-height:1.5;font-weight:700;'
        f'color:{theme.accent};">{inline_html(block.text, theme)}</p>'
    )


def heading_archive(theme: Theme, block: Block, chapter: int, section_labels: list[str] | None) -> str:
    face = font_of(theme, "heading")
    if block.level == 1:
        return (
            '<section style="margin:2px 0 20px;text-align:center;">'
            + h1_text(
                theme,
                block,
                size="26px",
                weight="700",
                color=theme.h1_text,
                extra=f"font-family:{face};letter-spacing:2px;",
            )
            + "</section>"
        )
    if block.level == 2:
        label = label_for(section_labels, chapter, "篇")
        return (
            f'<section style="margin:{theme.chapter_gap} 0 16px;text-align:center;">'
            f'<p style="margin:0;font-size:13px;line-height:1.6;letter-spacing:3px;color:{theme.accent};">'
            f"{leaf(f'{chapter:02d}  {label}')}</p>"
            f'<p style="margin:8px 0 0;font-family:{face};font-size:20px;line-height:1.5;'
            f'font-weight:700;color:{theme.heading};">{inline_html(block.text, theme)}</p>'
            f'<p style="margin:8px 0 0;font-size:12px;letter-spacing:6px;color:{theme.accent};">'
            f"{leaf('· · ·')}</p></section>"
        )
    return (
        f'<p style="margin:26px 0 12px;text-align:center;font-family:{face};font-size:17px;'
        f'line-height:1.6;font-weight:700;color:{theme.h3_text};">{inline_html(block.text, theme)}</p>'
    )


def heading_kitchen(theme: Theme, block: Block, chapter: int, section_labels: list[str] | None) -> str:
    if block.level == 1:
        return (
            '<section style="margin:2px 0 18px;">'
            + h1_text(theme, block, size="26px", weight="800", color=theme.heading)
            + rule(theme, "52px", "4px", "10px 0 0")
            + "</section>"
        )
    if block.level == 2:
        custom = label_for(section_labels, chapter, "")
        prefix = ""
        if custom:
            prefix = (
                f'<p style="margin:0 0 4px;font-size:13px;line-height:1.5;letter-spacing:1px;'
                f'color:{theme.accent};">{leaf(custom)}</p>'
            )
        return (
            f'<section style="margin:{theme.chapter_gap} 0 14px;">'
            f"{prefix}"
            f'<p style="margin:0;font-size:20px;line-height:1.45;font-weight:800;color:{theme.h2_label};">'
            f"{inline_html(block.text, theme)}</p>"
            + rule(theme, "48px", "4px", "8px 0 0")
            + "</section>"
        )
    return (
        f'<p style="margin:22px 0 10px;font-size:18px;line-height:1.5;font-weight:800;'
        f'color:{theme.h2_label};">{inline_html(block.text, theme)}</p>'
    )


def quote_block(
    theme: Theme,
    block: Block,
    *,
    label: str,
    box: str,
    text_style: str,
    label_size: str = "13px",
) -> str:
    label_html = ""
    if label:
        label_html = (
            f'<p style="margin:0 0 8px;font-size:{label_size};line-height:1.5;font-weight:700;'
            f'letter-spacing:2px;color:{theme.accent};">{leaf(label)}</p>'
        )
    return (
        f'<section style="margin:6px 0 {theme.para_gap};{box}">'
        f"{label_html}"
        f'<p style="margin:0;{text_style}">{inline_html(block.text, theme)}</p></section>'
    )


def list_gazette(theme: Theme, block: Block) -> str:
    label = theme.list_label if block.kind == "ul" else (theme.step_label or theme.list_label)
    parts = [
        '<section style="margin:4px 0 22px;padding:14px 14px 4px;'
        f"background:{theme.list_bg};border:2px solid {theme.accent};\">"
    ]
    if label:
        parts.append(
            f'<p style="margin:0 0 10px;font-size:16px;line-height:1.5;font-weight:800;'
            f'letter-spacing:1px;color:{theme.accent};">{leaf(label)}</p>'
        )
    for index, item in enumerate(block.items or [], 1):
        if block.kind == "ol":
            marker = (
                f'<span leaf="" style="display:inline-block;min-width:36px;font-size:22px;'
                f'font-weight:800;color:{theme.accent};">{leaf(f"{index:02d}")}</span>'
            )
        else:
            marker = (
                f'<span leaf="" style="display:inline-block;min-width:22px;font-size:16px;'
                f'font-weight:800;color:{theme.accent};">{leaf("●")}</span>'
            )
        parts.append(
            '<section style="margin:0 0 10px;padding:0 0 8px;'
            f'border-bottom:1px solid {theme.accent};">'
            f"{marker}"
            f'<span leaf="" style="font-size:{theme.font_size};line-height:1.7;color:{theme.list_text};">'
            f"{inline_html(item, theme)}</span></section>"
        )
    parts.append("</section>")
    return "".join(parts)


def list_memo(theme: Theme, block: Block) -> str:
    label = theme.list_label if block.kind == "ul" else (theme.step_label or theme.list_label)
    parts = ['<section style="margin:2px 0 18px;">']
    if label:
        parts.append(
            f'<p style="margin:0 0 4px;font-size:13px;line-height:1.5;letter-spacing:1px;'
            f'color:{theme.accent};">{leaf(label)}</p>'
        )
    for index, item in enumerate(block.items or [], 1):
        marker = f"{index}." if block.kind == "ol" else "–"
        parts.append(
            '<section style="margin:0;padding:7px 0;'
            f"border-bottom:1px solid {theme.list_border};\">"
            f'<span leaf="" style="display:inline-block;min-width:26px;color:{theme.accent};'
            f'font-weight:700;">{leaf(marker)}</span>'
            f'<span leaf="" style="color:{theme.list_text};font-size:{theme.font_size};'
            f'line-height:1.7;">{inline_html(item, theme)}</span></section>'
        )
    parts.append("</section>")
    return "".join(parts)


def list_kitchen(theme: Theme, block: Block) -> str:
    if block.kind == "ol":
        label = theme.step_label or "做法"
        parts = ['<section style="margin:4px 0 22px;">']
        parts.append(
            f'<p style="margin:0 0 10px;font-size:15px;line-height:1.5;font-weight:800;'
            f'letter-spacing:1px;color:{theme.accent};">{leaf(label)}</p>'
        )
        for index, item in enumerate(block.items or [], 1):
            parts.append(
                '<section style="margin:0 0 10px;padding:12px 14px;'
                f"background:{theme.list_bg};border:1px solid {theme.list_border};"
                'border-radius:12px;">'
                '<p style="margin:0;font-size:16px;line-height:1.75;color:'
                f'{theme.list_text};">'
                f'<span leaf="" style="display:inline-block;min-width:26px;padding:0 7px;'
                f"line-height:26px;text-align:center;background:{theme.accent};color:#ffffff;"
                f'font-weight:800;border-radius:13px;margin-right:8px;">{leaf(str(index))}</span>'
                f"<span>{inline_html(item, theme)}</span></p></section>"
            )
        parts.append("</section>")
        return "".join(parts)

    label = theme.list_label or "用料"
    parts = [
        '<section style="margin:4px 0 22px;padding:12px 14px 4px;'
        f"background:{theme.list_bg};border:1px solid {theme.list_border};border-radius:12px;\">"
        f'<p style="margin:0 0 8px;font-size:15px;line-height:1.5;font-weight:800;'
        f'letter-spacing:1px;color:{theme.h2_label};">{leaf(label)}</p>'
    ]
    for item in block.items or []:
        parts.append(
            '<section style="margin:0;padding:7px 0;border-top:1px solid '
            f'{theme.list_border};">'
            f'<span leaf="" style="display:inline-block;min-width:18px;color:{theme.h2_label};'
            f'font-weight:700;">{leaf("·")}</span>'
            f'<span leaf="" style="color:{theme.list_text};font-size:{theme.font_size};'
            f'line-height:1.7;">{inline_html(item, theme)}</span></section>'
        )
    parts.append("</section>")
    return "".join(parts)


def hr_diary(theme: Theme) -> str:
    return (
        '<section style="margin:28px auto;width:48px;height:1px;'
        f'background:{theme.hr};"></section>'
    )


def hr_gazette(theme: Theme) -> str:
    return f'<section style="margin:28px 0;height:2px;background:{theme.hr};"></section>'


def hr_memo(theme: Theme) -> str:
    return f'<section style="margin:22px 0;height:1px;background:{theme.hr};"></section>'


def hr_archive(theme: Theme) -> str:
    return (
        f'<p style="margin:28px 0;text-align:center;font-size:12px;letter-spacing:8px;'
        f'color:{theme.accent};">{leaf("· · ·")}</p>'
    )


def hr_kitchen(theme: Theme) -> str:
    return rule(theme, "48px", "3px", "26px auto")


def open_diary(theme: Theme) -> str:
    return root_open(theme, "28px 22px 42px") + masthead(
        theme, align="center", tracking="3px", gap="18px"
    )


def open_gazette(theme: Theme) -> str:
    return root_open(theme, "18px 16px 32px") + masthead(
        theme, size="16px", tag_size="15px", gap="12px"
    )


def open_memo(theme: Theme) -> str:
    rules = (
        f'<section style="height:2px;background:{theme.accent};"></section>'
        f'<section style="height:1px;margin-top:3px;background:{theme.accent};"></section>'
    )
    return (
        root_open(theme, "20px 18px 32px")
        + masthead(theme, size="14px", tag_size="13px", gap="8px")
        + rules
    )


def open_archive(theme: Theme) -> str:
    return (
        root_open(theme, "26px 20px 40px")
        + seal_mark(theme)
        + masthead(theme, align="center", size="14px", tracking="3px", gap="16px")
    )


def open_kitchen(theme: Theme) -> str:
    return root_open(theme, "18px 16px 32px") + masthead(
        theme, size="14px", color=theme.h2_label, tracking="2px", gap="12px"
    )


def assemble(blocks, image_sources, theme, section_labels, image_views, spec: dict) -> str:
    parts: list[str] = [spec["open"](theme)]
    chapter = 0
    image_index = 0
    for block_index, block in enumerate(blocks):
        if block.kind == "heading":
            if block.level == 2:
                chapter += 1
            parts.append(spec["heading"](theme, block, chapter, section_labels))
        elif block.kind == "paragraph":
            parts.append(spec["paragraph"](theme, block))
        elif block.kind == "image":
            view = resolve_view(block_index, block, image_sources, image_views)
            parts.append(spec["image"](theme, view, image_index == 0))
            image_index += 1
        elif block.kind in {"ul", "ol"}:
            parts.append(spec["items"](theme, block))
        elif block.kind == "code":
            parts.append(spec["code"](theme, block))
        elif block.kind == "quote":
            parts.append(spec["quote"](theme, block))
        elif block.kind == "table":
            parts.append(spec["table"](theme, block))
        elif block.kind == "hr":
            parts.append(spec["hr"](theme))
        else:
            raise RuntimeError(f"未知块类型：{block.kind}")
    parts.append(spec["close"](theme))
    return "\n".join(parts)


def _spec_diary() -> dict:
    def paragraph_diary(theme: Theme, block: Block) -> str:
        return paragraph(
            theme,
            block,
            extra=f"text-indent:2em;font-family:{font_of(theme, 'body')};",
        )

    def quote_diary(theme: Theme, block: Block) -> str:
        return quote_block(
            theme,
            block,
            label=theme.quote_label or "旁注",
            box=f"padding:2px 0 2px 14px;border-left:2px solid {theme.accent_soft};",
            text_style=(
                f"font-size:{theme.font_size};line-height:{theme.line_height};color:{theme.text};"
            ),
        )

    def table_diary(theme: Theme, block: Block) -> str:
        return render_table(
            theme,
            block,
            size="14px",
            header_bg=theme.h3_bg,
            header_color=theme.heading,
        )

    return {
        "open": open_diary,
        "close": lambda theme: root_close(theme),
        "heading": heading_diary,
        "paragraph": paragraph_diary,
        "image": themed_picture,
        "items": lambda theme, block: airy_list(theme, block, gap="12px"),
        "code": lambda theme, block: render_code(theme, block, size="13px", radius="8px"),
        "quote": quote_diary,
        "table": table_diary,
        "hr": hr_diary,
    }


def _spec_gazette() -> dict:
    def quote_gazette(theme: Theme, block: Block) -> str:
        label = theme.takeaway_label or theme.quote_label or "记住"
        return quote_block(
            theme,
            block,
            label=label,
            label_size="16px",
            box=(
                f"padding:14px 16px;background:{theme.h3_bg};"
                f"border:2px solid {theme.accent};"
            ),
            text_style=(
                f"font-size:{theme.font_size};line-height:{theme.line_height};"
                f"font-weight:700;color:{theme.heading};"
            ),
        )

    def table_gazette(theme: Theme, block: Block) -> str:
        return render_table(
            theme,
            block,
            size="16px",
            header_bg=theme.accent,
            header_color="#ffffff",
        )

    return {
        "open": open_gazette,
        "close": lambda theme: root_close(theme, size="15px"),
        "heading": heading_gazette,
        "paragraph": lambda theme, block: paragraph(theme, block),
        "image": themed_picture,
        "items": list_gazette,
        "code": lambda theme, block: render_code(theme, block, size="16px"),
        "quote": quote_gazette,
        "table": table_gazette,
        "hr": hr_gazette,
    }


def _spec_memo() -> dict:
    def quote_memo(theme: Theme, block: Block) -> str:
        return quote_block(
            theme,
            block,
            label=theme.quote_label or "说明",
            box=f"padding:2px 0 2px 12px;border-left:3px solid {theme.accent};",
            text_style=(
                f"font-size:{theme.font_size};line-height:{theme.line_height};color:{theme.text};"
            ),
        )

    def table_memo(theme: Theme, block: Block) -> str:
        return render_table(
            theme,
            block,
            size="14px",
            header_bg=theme.h3_bg,
            header_color=theme.heading,
        )

    return {
        "open": open_memo,
        "close": lambda theme: root_close(theme),
        "heading": heading_memo,
        "paragraph": lambda theme, block: paragraph(theme, block),
        "image": themed_picture,
        "items": list_memo,
        "code": lambda theme, block: render_code(theme, block, size="14px"),
        "quote": quote_memo,
        "table": table_memo,
        "hr": hr_memo,
    }


def _spec_archive() -> dict:
    def paragraph_archive(theme: Theme, block: Block) -> str:
        return paragraph(
            theme,
            block,
            extra=f"text-indent:2em;font-family:{font_of(theme, 'heading')};",
        )

    def quote_archive(theme: Theme, block: Block) -> str:
        face = font_of(theme, "heading")
        label = theme.quote_label or "原文"
        return (
            f'<section style="margin:6px 0 {theme.para_gap};padding:6px;'
            f'border:1px solid {theme.accent};">'
            f'<section style="padding:14px 16px;background:{theme.h3_bg};">'
            f'<p style="margin:0 0 8px;font-size:13px;line-height:1.5;font-weight:700;'
            f'letter-spacing:2px;color:{theme.accent};">{leaf(label)}</p>'
            f'<p style="margin:0;font-family:{face};font-size:17px;line-height:2.05;'
            f'color:{theme.heading};">{inline_html(block.text, theme)}</p>'
            "</section></section>"
        )

    def table_archive(theme: Theme, block: Block) -> str:
        return render_table(
            theme,
            block,
            size="15px",
            header_bg=theme.h3_bg,
            header_color=theme.heading,
            font=font_of(theme, "heading"),
        )

    return {
        "open": open_archive,
        "close": lambda theme: root_close(theme),
        "heading": heading_archive,
        "paragraph": paragraph_archive,
        "image": themed_picture,
        "items": lambda theme, block: airy_list(
            theme, block, font=font_of(theme, "heading"), gap="10px"
        ),
        "code": lambda theme, block: render_code(theme, block, size="13px"),
        "quote": quote_archive,
        "table": table_archive,
        "hr": hr_archive,
    }


def _spec_kitchen() -> dict:
    def quote_kitchen(theme: Theme, block: Block) -> str:
        return quote_block(
            theme,
            block,
            label=theme.quote_label or "小记",
            box=(
                f"padding:12px 14px;background:{theme.list_bg};"
                f"border-left:4px solid {theme.accent};border-radius:10px;"
            ),
            text_style=(
                f"font-size:{theme.font_size};line-height:{theme.line_height};color:{theme.text};"
            ),
        )

    def table_kitchen(theme: Theme, block: Block) -> str:
        return render_table(
            theme,
            block,
            size="15px",
            header_bg=theme.h2_label,
            header_color="#ffffff",
        )

    return {
        "open": open_kitchen,
        "close": lambda theme: root_close(theme),
        "heading": heading_kitchen,
        "paragraph": lambda theme, block: paragraph(theme, block),
        "image": themed_picture,
        "items": list_kitchen,
        "code": lambda theme, block: render_code(theme, block, size="13px", radius="8px"),
        "quote": quote_kitchen,
        "table": table_kitchen,
        "hr": hr_kitchen,
    }


SPECS = {
    "diary": _spec_diary(),
    "gazette": _spec_gazette(),
    "memo": _spec_memo(),
    "archive": _spec_archive(),
    "kitchen": _spec_kitchen(),
}


def render_themed(blocks, image_sources, theme, section_labels, image_views) -> str:
    spec = SPECS.get(theme.layout)
    if spec is None:
        raise ValueError(f"布局 {theme.layout} 没有对应的排版")
    return assemble(blocks, image_sources, theme, section_labels, image_views, spec)
