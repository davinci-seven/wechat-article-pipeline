#!/usr/bin/env python3
"""把一篇 Markdown 收成一个可以粘贴进公众号的 HTML。

不调用 gzh-design，也不跑 Playwright。默认不写长截图、证据表和隐私报告。
完整流水线仍用 tools/render_wechat.py 或 tools/公众号排版.ps1。

    python tools/paste_wechat.py --md 文章.md --theme laochen-shebao -o out/

用浏览器打开生成的 HTML，点「一键复制到公众号」，再到 mp.weixin.qq.com
新建图文后粘贴。本地图片不会进编辑器，正文里留【插图N】，文件在旁边的
images 文件夹。原因见 docs/paste-images.md。
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
STEPS = "复制 → 打开公众号后台新建图文 → 粘贴 → 检查图片 → 发表"


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


def plain_text(blocks, markers: dict[int, str], account: str) -> str:
    lines: list[str] = []
    if account:
        lines.append(account)
    for index, block in enumerate(blocks):
        if block.kind in {"heading", "paragraph", "quote"}:
            lines.append(inline_plain(block.text))
        elif block.kind == "image":
            if markers.get(index):
                lines.append(markers[index])
                lines.append("在这里插入同名图片，插好后删掉这几行提示")
            if block.alt:
                lines.append(block.alt)
        elif block.kind in {"ul", "ol"}:
            lines.extend(inline_plain(item) for item in (block.items or []))
        elif block.kind == "code":
            lines.append(block.text)
        elif block.kind == "table":
            if block.items:
                lines.append(" ".join(inline_plain(cell) for cell in block.items))
            for row in block.rows or []:
                lines.append(" ".join(inline_plain(cell) for cell in row))
    return "\n\n".join(line for line in lines if line.strip())


def build_page(
    *,
    title: str,
    theme_name: str,
    theme_key: str,
    account: str,
    preview_html: str,
    copy_html: str,
    copy_text: str,
    note: str,
    file_list_html: str,
) -> str:
    label_bits = []
    if account:
        label_bits.append(account)
    if theme_name and theme_name not in label_bits:
        label_bits.append(theme_name)
    label_bits.append(theme_key)
    eyebrow = html.escape(" · ".join(label_bits))
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
body {{ margin:0; background:#e8e4de; color:#1f2933;
  font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  -webkit-text-size-adjust:100%; }}
.paste-bar {{ position:sticky; top:0; z-index:10; background:#ffffff;
  border-bottom:1px solid #e5e1da; padding:16px 16px 14px; }}
.paste-bar .eyebrow {{ margin:0 0 6px; text-align:center; font-size:13px; letter-spacing:1px; color:#6b6258; }}
.paste-bar .steps {{ margin:0 auto 12px; max-width:640px; text-align:center;
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
.files {{ width:min(390px, 100%); margin:0 auto 40px; padding:4px 14px 8px;
  box-sizing:border-box; font-size:14px; line-height:1.7; color:#3f3a34; }}
.files h2 {{ margin:8px 0; font-size:15px; }}
.files ol {{ margin:0; padding-left:1.2em; }}
.files li {{ margin:0 0 6px; }}
.paste-toast {{ position:fixed; left:50%; bottom:20px; transform:translateX(-50%);
  max-width:min(520px, 92vw); padding:12px 16px; border-radius:10px; background:#1a1a1a;
  color:#ffffff; font-size:15px; line-height:1.55; text-align:center; opacity:0;
  pointer-events:none; transition:opacity .2s; }}
.paste-toast.show {{ opacity:1; }}
</style>
</head>
<body>
<header class="paste-bar">
  <p class="eyebrow">{eyebrow}</p>
  <p class="steps">{html.escape(STEPS)}</p>
  <button class="paste-btn" id="paste-btn" type="button">一键复制到公众号</button>
  <p class="paste-note">{html.escape(note)}</p>
</header>
<main>
  <div class="phone" id="preview">
{preview_html}
  </div>
  {file_list_html}
</main>
<textarea id="copy-html" hidden>{html.escape(copy_html)}</textarea>
<textarea id="copy-text" hidden>{html.escape(copy_text)}</textarea>
<div class="paste-toast" id="paste-toast" role="status"></div>
<script>
(function () {{
  var button = document.getElementById("paste-btn");
  var toast = document.getElementById("paste-toast");
  var idle = button.textContent;
  var timer = 0;
  function show(message) {{
    toast.textContent = message;
    toast.className = "paste-toast show";
    clearTimeout(timer);
    timer = setTimeout(function () {{ toast.className = "paste-toast"; }}, 4200);
  }}
  button.addEventListener("click", function () {{
    var markup = document.getElementById("copy-html").value;
    var text = document.getElementById("copy-text").value;
    var done = false;
    function onCopy(event) {{
      if (!event.clipboardData) return;
      event.clipboardData.setData("text/html", markup);
      event.clipboardData.setData("text/plain", text);
      event.preventDefault();
      done = true;
    }}
    document.addEventListener("copy", onCopy);
    var holder = document.createElement("textarea");
    holder.value = text;
    holder.setAttribute("readonly", "");
    holder.style.position = "fixed";
    holder.style.top = "0";
    holder.style.left = "-9999px";
    document.body.appendChild(holder);
    holder.focus();
    holder.select();
    try {{
      document.execCommand("copy");
    }} catch (error) {{
      done = false;
    }} finally {{
      document.removeEventListener("copy", onCopy);
      if (holder.parentNode) holder.parentNode.removeChild(holder);
      button.focus();
    }}
    if (done) {{
      button.textContent = "已复制，去公众号粘贴";
      show("已复制。打开公众号后台，新建图文，在正文里按 Ctrl+V（Mac 用 ⌘+V）。本地图片要按【插图】手动插入。");
      setTimeout(function () {{ button.textContent = idle; }}, 2500);
    }} else {{
      show("没有复制成功。请换 Chrome 或 Edge 打开这个文件，再点一次按钮。");
    }}
  }});
}})();
</script>
<noscript><p class="paste-note">请用浏览器打开这个文件，才能点按钮复制。</p></noscript>
</body>
</html>
"""


def file_list(records: list[dict]) -> str:
    local = [item for item in records if item["kind"] == "local"]
    remote = [item for item in records if item["kind"] == "remote"]
    if not records:
        return ""
    items: list[str] = []
    for item in records:
        alt = html.escape(item["alt"] or "（无图注）")
        if item["kind"] == "local":
            items.append(
                f"<li><b>{html.escape(item['export_name'])}</b>　{html.escape(item['marker'])}　{alt}</li>"
            )
        else:
            items.append(f"<li>外链图片，粘贴时由公众号尝试自动保存　{alt}</li>")
    title = "要手动插入的图片" if local else "文中的网络图片"
    extra = ""
    if local and remote:
        extra = "<p>网络图片没有对应文件，粘贴后确认它们是否出现。</p>"
    return (
        '<section class="files">'
        f"<h2>{title}</h2><ol>{''.join(items)}</ol>{extra}</section>"
    )


def note_for(records: list[dict]) -> str:
    local = any(item["kind"] == "local" for item in records)
    remote = any(item["kind"] == "remote" for item in records)
    if not records:
        return "这篇没有配图。点按钮复制，到公众号粘贴后通读一遍再发表。请点按钮，不要自己全选页面。"
    if local and remote:
        return (
            "预览里能看到图，但本地图片粘贴不过去，正文会留下【插图】。"
            "请按旁边 images 文件夹里的同名文件插入，插好后删掉提示。"
            "网络图片由公众号在粘贴时尝试自动保存。请点按钮复制，不要自己全选页面。"
        )
    if local:
        return (
            "预览里能看到图，粘贴到公众号时本地图片不会跟着过去。"
            "正文【插图1】的位置，用旁边 images 文件夹里的同名文件插入，插好后删掉提示。"
            "请点按钮，不要自己全选页面。"
        )
    return "配图是网络地址。粘贴后确认图片是否出现；没出现就在公众号里重新上传。请点按钮复制，不要自己全选页面。"


def clear_stale_images(image_dir: Path, written: set[str]) -> None:
    if not image_dir.is_dir():
        return
    for existing in image_dir.iterdir():
        if existing.is_file() and _NUMBERED_FILE.fullmatch(existing.name) and existing.name not in written:
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
    unsupported = find_unsupported(source)
    if unsupported and not args.allow_unsupported:
        print("这篇 Markdown 有排版器不支持的写法，已停止：", file=sys.stderr)
        for item in unsupported:
            print(
                f"第 {item['line']} 行 {item['syntax']}：{item['hint']}",
                file=sys.stderr,
            )
        print("改原稿，或加上 --allow-unsupported 接受降级。", file=sys.stderr)
        return 4

    blocks = parse_markdown(source)
    article_dir = markdown_path.parent
    html_path, image_dir = html_destination(markdown_path, Path(args.output))

    preview_views: dict[int, ImageView] = {}
    copy_views: dict[int, ImageView] = {}
    markers: dict[int, str] = {}
    records: list[dict] = []
    missing: list[str] = []
    written: set[str] = set()
    local_number = 0

    for block_index, block in enumerate(blocks):
        if block.kind != "image":
            continue
        resolved = resolve_image(article_dir, block.src)
        if resolved is None:
            view = ImageView(src=block.src, alt=block.alt, show=True)
            preview_views[block_index] = view
            copy_views[block_index] = view
            records.append({"kind": "remote", "alt": block.alt, "marker": "", "export_name": ""})
            continue
        if not resolved.is_file():
            missing.append(str(resolved))
            continue
        local_number += 1
        export_name = f"{local_number:02d}-{safe_filename(resolved.name)}"
        marker = f"【插图{local_number}：{export_name}】"
        image_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(resolved, image_dir / export_name)
        written.add(export_name)
        markers[block_index] = marker
        preview_views[block_index] = ImageView(
            src=data_uri(resolved), alt=block.alt, marker=marker, show=True
        )
        copy_views[block_index] = ImageView(src="", alt=block.alt, marker=marker, show=False)
        records.append(
            {
                "kind": "local",
                "alt": block.alt,
                "marker": marker,
                "export_name": export_name,
            }
        )

    if missing:
        print("缺少图片，已停止，没有生成 HTML：", file=sys.stderr)
        for item in missing:
            print(f"- {item}", file=sys.stderr)
        return 2

    clear_stale_images(image_dir, written)
    preview_html = render_blocks(blocks, {}, theme, image_views=preview_views)
    copy_html = render_blocks(blocks, {}, theme, image_views=copy_views)
    fragments = visible_fragments(blocks)
    preview_ok, preview_missing = verify_order(preview_html, fragments)
    copy_ok, copy_missing = verify_order(copy_html, fragments)
    after_hash = sha256(markdown_path)
    if re.search(r'src="data:image', copy_html) or re.search(r"<script", copy_html, re.I):
        print("复制用的正文里出现了不能粘贴进公众号的内容，已停止。", file=sys.stderr)
        return 3
    if not (preview_ok and copy_ok and before_hash == after_hash):
        print("正文顺序校验没通过，没有写出 HTML。", file=sys.stderr)
        for item in preview_missing + copy_missing:
            print(f"- {item}", file=sys.stderr)
        return 3

    title_text = next(
        (block.text for block in blocks if block.kind == "heading" and block.level == 1),
        markdown_path.stem,
    )
    page_title = f"{title_text} · {theme.account or theme.name_cn}"
    page = build_page(
        title=page_title,
        theme_name=theme.name_cn,
        theme_key=theme.key,
        account=theme.account,
        preview_html=preview_html,
        copy_html=copy_html,
        copy_text=plain_text(blocks, markers, theme.account),
        note=note_for(records),
        file_list_html=file_list(records),
    )
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(page, encoding="utf-8")

    print(f"已生成：{html_path}")
    print(f"主题：{theme.name_cn}（{theme.key}）")
    print("用浏览器打开这个文件，点「一键复制到公众号」。")
    if written:
        print(f"本地配图 {len(written)} 张，在 {image_dir} ，按【插图】的文件名手动插入。")
    elif records:
        print("这篇只有网络图片，粘贴后请确认公众号有没有把它们自动保存下来。")
    else:
        print("这篇没有配图。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
