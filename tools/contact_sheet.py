"""Tiles renders into a labelled contact sheet (visual QA: fp_preview, crowd_shot...).

  python tools/contact_sheet.py OUT.webp DIR [DIR2] [--cols 6] [--width 320] [--only a,b,c]

One DIR: every PNG in it, by name. Two DIRs (before / after): each name's two renders side by
side, the second's label marked "after". --only picks and orders names (no extension).
"""
from __future__ import annotations

import argparse
import pathlib

from PIL import Image, ImageDraw, ImageFont


def _font(size: int):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",):
        if pathlib.Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--cols", type=int, default=6)
    ap.add_argument("--width", type=int, default=320)
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    dirs = [pathlib.Path(d) for d in a.dirs]
    names = [n for n in a.only.split(",") if n] or sorted(p.stem for p in dirs[0].glob("*.png"))
    cells = []
    for n in names:
        for k, d in enumerate(dirs):
            f = d / f"{n}.png"
            if f.exists():
                cells.append((n + (" (after)" if k and len(dirs) > 1 else ""), f))
    if not cells:
        raise SystemExit("contact_sheet: no images")
    w = a.width
    im0 = Image.open(cells[0][1])
    h = round(im0.height * w / im0.width)
    lab = 18
    cols = a.cols - (a.cols % len(dirs)) if len(dirs) > 1 else a.cols
    rows = (len(cells) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w, rows * (h + lab)), (24, 24, 24))
    draw = ImageDraw.Draw(sheet)
    font = _font(13)
    for i, (label, f) in enumerate(cells):
        x, y = (i % cols) * w, (i // cols) * (h + lab)
        sheet.paste(Image.open(f).convert("RGB").resize((w, h), Image.LANCZOS), (x, y + lab))
        draw.text((x + 4, y + 2), label, fill=(235, 235, 235), font=font)
    sheet.save(a.out, quality=80)
    print(f"contact_sheet: {len(cells)} images -> {a.out} ({sheet.width}x{sheet.height})")


if __name__ == "__main__":
    main()
