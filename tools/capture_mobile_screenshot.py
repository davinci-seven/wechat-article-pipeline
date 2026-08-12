#!/usr/bin/env python3
"""在390px视口打开手机截图页，输出完整长截图。

依赖Playwright。没装时以退出码3退出，由调用方如实标记"未运行"，
不允许用截图页或占位图冒充已生成。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Chromium单张截图的高度上限，超过就分段截再拼。
MAX_SINGLE_SHOT_HEIGHT = 16000


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--page", required=True, help="手机截图页HTML")
    parser.add_argument("--output", required=True, help="输出PNG路径")
    parser.add_argument("--width", type=int, default=390)
    parser.add_argument("--scale", type=int, default=2)
    parser.add_argument("--wait", type=int, default=1200, help="等待渲染的毫秒数")
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "未安装Playwright，无法生成长截图。\n"
            "安装：pip install playwright && python -m playwright install chromium",
            file=sys.stderr,
        )
        return 3

    page_path = Path(args.page).resolve()
    if not page_path.is_file():
        print(f"手机截图页不存在：{page_path}", file=sys.stderr)
        return 2

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(
                viewport={"width": args.width, "height": 900},
                device_scale_factor=args.scale,
            )
            page.goto(page_path.as_uri())
            page.wait_for_timeout(args.wait)

            page_height = page.evaluate("document.body.scrollHeight")
            overflow = page.evaluate(
                f"document.documentElement.scrollWidth > {args.width}"
            )
            broken = page.evaluate(
                "[...document.images].filter("
                "i => !i.complete || i.naturalWidth === 0).length"
            )

            if page_height <= MAX_SINGLE_SHOT_HEIGHT:
                page.screenshot(path=str(output_path), full_page=True)
            else:
                _capture_in_segments(page, output_path, args, page_height)

            browser.close()
    except Exception as error:  # noqa: BLE001 - 交给调用方判断是否致命
        print(f"截图失败：{error}", file=sys.stderr)
        return 4

    print(
        f"{output_path}\t页面高度={page_height}px\t"
        f"横向溢出={'是' if overflow else '否'}\t破图={broken}张"
    )
    return 0


def _capture_in_segments(page, output_path: Path, args, page_height: int) -> None:
    """超高页面分段截取后拼接，避免单张截图被浏览器截断。"""
    from PIL import Image

    viewport_height = 900
    positions = list(range(0, page_height, viewport_height))
    segments = []
    for index, top in enumerate(positions):
        page.evaluate(f"window.scrollTo(0, {top})")
        page.wait_for_timeout(150)
        segment_path = output_path.parent / f".segment-{index:03d}.png"
        page.screenshot(path=str(segment_path))
        segments.append(segment_path)

    images = [Image.open(path).convert("RGB") for path in segments]
    width, height = images[0].size
    canvas = Image.new("RGB", (width, page_height * args.scale), "#eef0f2")
    for top, image in zip(positions, images):
        remaining = page_height * args.scale - top * args.scale
        if remaining <= 0:
            continue
        if remaining < height:
            image = image.crop((0, height - remaining, width, height))
        canvas.paste(image, (0, top * args.scale))
    canvas.save(output_path, format="PNG", optimize=True)

    for path in segments:
        path.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
