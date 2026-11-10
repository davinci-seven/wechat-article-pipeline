#!/usr/bin/env python3
"""把一篇 Markdown 收成一个可以粘贴进公众号的 HTML。

不调用 gzh-design，也不跑 Playwright。默认不写长截图、证据表和隐私报告。
完整流水线仍用 tools/render_wechat.py 或 tools/公众号排版.ps1。

    python tools/paste_wechat.py --md 文章.md --theme navy-gazette -o out/

用浏览器打开生成的 HTML。「复制标题」只复制标题，「复制正文」用选区复制
渲染后的正文节点，图片以 data URI 嵌在这个节点里，会跟着进公众号编辑器。
封面和标题不在正文节点里。images 文件夹只是备用原图。
"""

from __future__ import annotations

import argparse
import html
import re
import shutil
import sys
from pathlib import Path

from render_wechat import (
    DEFAULT_THEME,
    THEMES,
    Block,
    ImageView,
    data_uri,
    find_unsupported,
    inline_plain,
    parse_markdown,
    render_blocks,
    resolve_image,
    sha256,
    verify_order,
    visible_fragments,
)

_UNSAFE_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_NUMBERED_FILE = re.compile(r"\d{2}-.+")
_FRONT_MATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?", re.S)
_COVER_NAME = re.compile(r"封面\..+")


def _utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            pass


def safe_filename(name: str) -> str:
    cleaned = _UNSAFE_NAME.sub("_", Path(name).name).strip().strip(".")
    return cleaned or "image"


def html_destination(markdown_path: Path, output: Path) -> tuple[Path, Path]:
    output = output.expanduser()
    if not output.is_absolute():
        output = Path.cwd() / output
    if output.suffix.lower() == ".html":
        return output, output.parent / "images"
    stem = safe_filename(markdown_path.stem)
    return output / f"{stem}.html", output / "images"


def split_front_matter(source: str) -> tuple[dict[str, str], str, int]:
    """读文首 --- 之间的 title 和 cover。返回元数据、剩下的正文、占掉的行数。"""
    matched = _FRONT_MATTER.match(source)
    if not matched:
        return {}, source, 0
    meta: dict[str, str] = {}
    for line in matched.group(1).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        meta[key.strip().lower()] = value.strip().strip("\"'")
    skipped = source[: matched.end()].count("\n")
    return meta, source[matched.end() :], skipped


def take_title(blocks: list[Block], meta: dict[str, str], stem: str) -> tuple[str, list[Block]]:
    """标题单独给公众号标题框。一级标题（没有的话用文首标题或第一处标题）不进正文。"""
    title = (meta.get("title") or "").strip()
    remove_at: int | None = None
    h1_at = next(
        (index for index, block in enumerate(blocks) if block.kind == "heading" and block.level == 1),
        None,
    )
    if h1_at is not None:
        if not title:
            title = inline_plain(blocks[h1_at].text)
        remove_at = h1_at
    elif not title:
        heading_at = next((index for index, block in enumerate(blocks) if block.kind == "heading"), None)
        if heading_at is not None:
            title = inline_plain(blocks[heading_at].text)
            remove_at = heading_at
        else:
            title = stem
    if remove_at is None:
        return title, blocks
    return title, [block for index, block in enumerate(blocks) if index != remove_at]


def build_page(
    *,
    title: str,
    theme_name: str,
    theme_key: str,
    account: str,
    body_html: str,
    note: str,
    steps: str,
    file_list_html: str,
    cover_html: str,
) -> str:
    label_bits = []
    if account:
        label_bits.append(account)
    if theme_name and theme_name not in label_bits:
        label_bits.append(theme_name)
    label_bits.append(theme_key)
    eyebrow = html.escape(" · ".join(label_bits))
    safe_title = html.escape(title)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{safe_title}</title>
<style>
body {{ margin:0; background:#e8e4de; color:#1f2933;
  font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  -webkit-text-size-adjust:100%; }}
.paste-bar {{ position:sticky; top:0; z-index:10; background:#ffffff;
  border-bottom:1px solid #e5e1da; padding:16px 16px 14px; }}
.paste-bar .eyebrow {{ margin:0 0 6px; text-align:center; font-size:13px; letter-spacing:1px; color:#6b6258; }}
.paste-bar .steps {{ margin:0 auto 12px; max-width:680px; text-align:center;
  font-size:16px; line-height:1.6; font-weight:700; color:#1a1a1a; }}
.paste-btn {{ display:block; width:min(520px, 100%); margin:0 auto; padding:16px 18px;
  background:#07c160; color:#ffffff; border:0; border-radius:14px; cursor:pointer;
  font-size:22px; line-height:1.3; font-weight:800; letter-spacing:1px; }}
.paste-btn:hover {{ background:#06ad56; }}
.paste-btn:focus-visible {{ outline:3px solid #10243f; outline-offset:2px; }}
.paste-note {{ max-width:640px; margin:10px auto 0; text-align:center;
  font-size:14px; line-height:1.7; color:#3f3a34; }}
.phone {{ width:min(390px, 100%); margin:18px auto 8px; background:#ffffff;
  box-shadow:0 10px 28px rgba(40,32,24,.12); }}
.cover-card, .title-card {{ box-sizing:border-box; padding:16px 16px 8px; background:#ffffff; }}
.cover-card img {{ display:block; width:100%; height:auto; }}
.cover-label, .title-kicker {{ margin:0 0 8px; font-size:13px; line-height:1.5;
  font-weight:700; letter-spacing:1px; color:#6b6258; }}
.cover-download {{ display:inline-block; margin:8px 0 4px; font-size:14px; color:#1B4F8A; }}
.title-card {{ padding-bottom:14px; border-bottom:1px solid #e5e1da; }}
.article-title {{ margin:0; font-size:22px; line-height:1.45; font-weight:800; color:#1a1a1a; }}
.title-btn {{ display:inline-block; margin:10px 0 0; padding:6px 12px; font-size:14px;
  font-weight:700; color:#1f2933; background:#ffffff; border:1px solid #c9c3ba;
  border-radius:8px; cursor:pointer; }}
.title-btn:hover {{ background:#f6f4f1; }}
.files {{ width:min(390px, 100%); margin:0 auto 40px; padding:4px 14px 8px;
  box-sizing:border-box; font-size:14px; line-height:1.7; color:#3f3a34; }}
.files h2 {{ margin:8px 0; font-size:15px; }}
.files ol {{ margin:0; padding-left:1.2em; }}
.files li {{ margin:0 0 6px; }}
.paste-toast {{ position:fixed; left:50%; bottom:20px; transform:translateX(-50%);
  max-width:min(520px, 92vw); padding:12px 16px; border-radius:10px; background:#1a1a1a;
  color:#ffffff; font-size:15px; line-height:1.55; text-align:center; opacity:0;
  pointer-events:none; transition:opacity .2s; z-index:20; }}
.paste-toast.show {{ opacity:1; }}
</style>
</head>
<body>
<header class="paste-bar">
  <p class="eyebrow">{eyebrow}</p>
  <p class="steps">{html.escape(steps)}</p>
  <button class="paste-btn" id="paste-btn" type="button">复制正文</button>
  <p class="paste-note">{html.escape(note)}</p>
</header>
<main>
  <div class="phone">
    {cover_html}
    <section class="title-card">
      <p class="title-kicker">标题（填到公众号标题框，不会进正文）</p>
      <p class="article-title" id="article-title">{safe_title}</p>
      <button class="title-btn" id="copy-title" type="button">复制标题</button>
    </section>
    <div id="paste-body">
{body_html}
    </div>
  </div>
  {file_list_html}
</main>
<div class="paste-toast" id="paste-toast" role="status"></div>
<script>
(function () {{
  var toast = document.getElementById("paste-toast");
  var timer = 0;
  function show(message) {{
    toast.textContent = message;
    toast.className = "paste-toast show";
    clearTimeout(timer);
    timer = setTimeout(function () {{ toast.className = "paste-toast"; }}, 4200);
  }}
  function fallbackCopy(el) {{
    var markup = el.innerHTML;
    var text = el.innerText || el.textContent || "";
    if (navigator.clipboard && window.ClipboardItem && navigator.clipboard.write) {{
      try {{
        return navigator.clipboard.write([
          new ClipboardItem({{
            "text/html": new Blob([markup], {{ type: "text/html" }}),
            "text/plain": new Blob([text], {{ type: "text/plain" }})
          }})
        ]);
      }} catch (error) {{
        return Promise.reject(error);
      }}
    }}
    if (navigator.clipboard && navigator.clipboard.writeText) {{
      return navigator.clipboard.writeText(text);
    }}
    return Promise.reject(new Error("no clipboard"));
  }}
  function copyElement(el) {{
    var range = document.createRange();
    range.selectNodeContents(el);
    var selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    var ok = false;
    try {{
      ok = document.execCommand("copy");
    }} catch (error) {{
      ok = false;
    }}
    selection.removeAllRanges();
    if (ok) return Promise.resolve("selection");
    return fallbackCopy(el);
  }}
  document.getElementById("paste-btn").addEventListener("click", function () {{
    var button = document.getElementById("paste-btn");
    var idle = "复制正文";
    copyElement(document.getElementById("paste-body")).then(function () {{
      button.textContent = "正文已复制";
      show("正文已复制。到公众号正文里粘贴，图片会一起过去。");
      setTimeout(function () {{ button.textContent = idle; }}, 2500);
    }}, function () {{
      show("没有复制成功。请换 Chrome、Edge 或手机浏览器打开这个文件，再点一次。");
    }});
  }});
  document.getElementById("copy-title").addEventListener("click", function () {{
    var button = document.getElementById("copy-title");
    copyElement(document.getElementById("article-title")).then(function () {{
      button.textContent = "标题已复制";
      show("标题已复制。填进公众号的标题框，不要贴进正文。");
      setTimeout(function () {{ button.textContent = "复制标题"; }}, 2500);
    }}, function () {{
      show("标题没有复制成功。请再点一次「复制标题」。");
    }});
  }});
}})();
</script>
<noscript><p class="paste-note">请用浏览器打开这个文件，才能点按钮复制。</p></noscript>
</body>
</html>
"""


def file_list(records: list[dict]) -> str:
    local = [item for item in records if item["kind"] == "local"]
    if not local:
        return ""
    items = []
    for item in local:
        alt = html.escape(item["alt"] or "（无图注）")
        items.append(f"<li><b>{html.escape(item['export_name'])}</b>　{alt}</li>")
    return (
        '<section class="files">'
        "<h2>备用原图</h2>"
        "<p>正文里的图会跟着「复制正文」一起过去。只有粘贴后缺了图，才按这个顺序从 images 文件夹补。</p>"
        f"<ol>{''.join(items)}</ol></section>"
    )


def locate_local(article_dir: Path, raw: str, *, also_cwd: bool) -> Path | None:
    """本地文件返回路径；http(s) 返回 None。找不到时返回解析后的路径，调用方再判断是否存在。"""
    if re.match(r"^https?://", raw, re.I):
        return None
    raw_path = Path(raw)
    candidates: list[Path] = []
    if raw_path.is_absolute():
        candidates.append(raw_path)
    else:
        if also_cwd:
            candidates.append(Path.cwd() / raw_path)
        candidates.append(article_dir / raw_path)
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return candidates[-1].resolve()


def cover_html(src: str, download_href: str, download_name: str) -> str:
    return (
        '<section class="cover-card">'
        '<p class="cover-label">封面（在后台单独上传）</p>'
        f'<img src="{html.escape(src, quote=True)}" alt="封面">'
        f'<a class="cover-download" href="{html.escape(download_href, quote=True)}" '
        f'download="{html.escape(download_name, quote=True)}">下载封面</a>'
        "</section>"
    )


def note_for(has_images: bool, has_cover: bool) -> str:
    parts = ["点「复制正文」，不要自己全选页面，否则标题和按钮也会被复制。"]
    if has_images:
        parts.append("正文里的图片会跟着过去。")
    if has_cover:
        parts.append("封面用上面的下载链接保存，到公众号后台单独上传，不要贴进正文。")
    return "".join(parts)


def steps_for(has_cover: bool) -> str:
    steps = "复制标题 → 打开公众号后台新建图文，填进标题框 → 复制正文 → 粘贴到正文 → 检查图片"
    if has_cover:
        steps += " → 封面单独上传"
    return steps + " → 发表"


def clear_stale_images(image_dir: Path, written: set[str]) -> None:
    if not image_dir.is_dir():
        return
    for existing in image_dir.iterdir():
        if not existing.is_file() or existing.name in written:
            continue
        if _NUMBERED_FILE.fullmatch(existing.name) or _COVER_NAME.fullmatch(existing.name):
            existing.unlink()


def print_themes() -> None:
    for theme in THEMES.values():
        marker = "（默认）" if theme.key == DEFAULT_THEME else ""
        account = f"  {theme.account}" if theme.account else ""
        print(
            f"{theme.key:<18}{theme.name_cn}  {theme.layout:<10}"
            f"主色 {theme.accent}{account}{marker}"
        )


def main(argv: list[str] | None = None) -> int:
    _utf8_stdio()
    parser = argparse.ArgumentParser(
        description="把 Markdown 收成一个可粘贴进公众号的 HTML。不生成长截图和检查报告。"
    )
    parser.add_argument("--md", "--markdown", dest="markdown", help="文章 Markdown 路径")
    parser.add_argument(
        "--theme",
        default=DEFAULT_THEME,
        choices=sorted(THEMES),
        help=f"视觉主题，默认 {DEFAULT_THEME}。可用 --list-themes 查看",
    )
    parser.add_argument("-o", "--output", dest="output", help="输出目录，或一个 .html 文件路径")
    parser.add_argument(
        "--cover",
        help="封面图路径。只显示在页面上并提供下载，不进正文。也可写在文首 cover:",
    )
    parser.add_argument("--list-themes", action="store_true", help="列出全部主题后退出")
    parser.add_argument(
        "--allow-unsupported",
        action="store_true",
        help="接受渲染器不支持的 Markdown 语法被降级，默认遇到就停",
    )
    args = parser.parse_args(argv)

    if args.list_themes:
        print_themes()
        return 0
    if not args.markdown or not args.output:
        parser.error("--md 和 -o 为必填（除非使用 --list-themes）")

    markdown_path = Path(args.markdown).expanduser()
    if not markdown_path.is_absolute():
        markdown_path = Path.cwd() / markdown_path
    markdown_path = markdown_path.resolve()
    if not markdown_path.is_file():
        print(f"找不到 Markdown：{markdown_path}", file=sys.stderr)
        return 2

    theme = THEMES[args.theme]
    source = markdown_path.read_text(encoding="utf-8-sig")
    before_hash = sha256(markdown_path)
    meta, body, skipped_lines = split_front_matter(source)
    unsupported = find_unsupported(body)
    for item in unsupported:
        item["line"] += skipped_lines
    if unsupported and not args.allow_unsupported:
        print("这篇 Markdown 有排版器不支持的写法，已停止：", file=sys.stderr)
        for item in unsupported:
            print(
                f"第 {item['line']} 行 {item['syntax']}：{item['hint']}",
                file=sys.stderr,
            )
        print("改原稿，或加上 --allow-unsupported 接受降级。", file=sys.stderr)
        return 4

    parsed = parse_markdown(body)
    title_text, blocks = take_title(parsed, meta, markdown_path.stem)
    article_dir = markdown_path.parent
    html_path, image_dir = html_destination(markdown_path, Path(args.output))

    image_views: dict[int, ImageView] = {}
    records: list[dict] = []
    missing: list[str] = []
    written: set[str] = set()
    local_number = 0

    for block_index, block in enumerate(blocks):
        if block.kind != "image":
            continue
        resolved = resolve_image(article_dir, block.src)
        if resolved is None:
            image_views[block_index] = ImageView(src=block.src, alt=block.alt, show=True)
            records.append({"kind": "remote", "alt": block.alt, "export_name": ""})
            continue
        if not resolved.is_file():
            missing.append(str(resolved))
            continue
        local_number += 1
        export_name = f"{local_number:02d}-{safe_filename(resolved.name)}"
        image_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(resolved, image_dir / export_name)
        written.add(export_name)
        image_views[block_index] = ImageView(
            src=data_uri(resolved), alt=block.alt, show=True
        )
        records.append({"kind": "local", "alt": block.alt, "export_name": export_name})

    cover_raw = (args.cover or meta.get("cover") or "").strip()
    cover_block = ""
    if cover_raw:
        resolved_cover = locate_local(article_dir, cover_raw, also_cwd=bool(args.cover))
        if resolved_cover is None:
            cover_block = cover_html(cover_raw, cover_raw, "封面")
        elif not resolved_cover.is_file():
            missing.append(str(resolved_cover))
        else:
            suffix = resolved_cover.suffix.lower() or ".jpg"
            cover_name = f"封面{suffix}"
            image_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(resolved_cover, image_dir / cover_name)
            written.add(cover_name)
            cover_block = cover_html(
                data_uri(resolved_cover),
                f"images/{cover_name}",
                cover_name,
            )

    if missing:
        print("缺少图片，已停止，没有生成 HTML：", file=sys.stderr)
        for item in missing:
            print(f"- {item}", file=sys.stderr)
        return 2

    clear_stale_images(image_dir, written)
    body_html = render_blocks(blocks, {}, theme, image_views=image_views)
    fragments = visible_fragments(blocks)
    body_ok, body_missing = verify_order(body_html, fragments)
    after_hash = sha256(markdown_path)
    if "<script" in body_html.lower():
        print("正文里出现了脚本，已停止。", file=sys.stderr)
        return 3
    if not (body_ok and before_hash == after_hash):
        print("正文顺序校验没通过，没有写出 HTML。", file=sys.stderr)
        for item in body_missing:
            print(f"- {item}", file=sys.stderr)
        return 3

    has_local = any(item["kind"] == "local" for item in records)
    page = build_page(
        title=title_text,
        theme_name=theme.name_cn,
        theme_key=theme.key,
        account=theme.account,
        body_html=body_html,
        note=note_for(has_local or any(item["kind"] == "remote" for item in records), bool(cover_block)),
        steps=steps_for(bool(cover_block)),
        file_list_html=file_list(records),
        cover_html=cover_block,
    )
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(page, encoding="utf-8")

    print(f"已生成：{html_path}")
    print(f"主题：{theme.name_cn}（{theme.key}）")
    print(f"标题单独复制：{title_text}")
    print("用浏览器打开这个文件，点「复制正文」。图片嵌在正文里，会跟着粘贴过去。")
    if written:
        print(f"备用原图在 {image_dir} 。封面如果有，用页面上的下载链接，到后台单独上传。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
