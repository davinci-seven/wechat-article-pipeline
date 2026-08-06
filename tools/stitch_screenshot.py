#!/usr/bin/env python3
"""Stitch browser viewport captures at known CSS scroll positions."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--page-height", required=True, type=int)
    parser.add_argument("--positions", required=True)
    parser.add_argument("segments", nargs="+")
    args = parser.parse_args()

    positions = [int(value) for value in args.positions.split(",")]
    if len(positions) != len(args.segments):
        raise SystemExit("positions and segments count differ")

    images = [Image.open(path).convert("RGB") for path in args.segments]
    width, viewport_height = images[0].size
    if any(image.size != (width, viewport_height) for image in images):
        raise SystemExit("viewport segment dimensions differ")

    canvas = Image.new("RGB", (width, args.page_height), "#eef0f2")
    for position, image in zip(positions, images):
        remaining = args.page_height - position
        if remaining <= 0:
            continue
        if remaining < viewport_height:
            image = image.crop((0, viewport_height - remaining, width, viewport_height))
            canvas.paste(image, (0, position))
        else:
            canvas.paste(image, (0, position))

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, format="PNG", optimize=True)
    print(f"{output}\t{canvas.width}x{canvas.height}")


if __name__ == "__main__":
    main()
