#!/usr/bin/env python3
"""Contact sheet of rendered trailer shots: one row per shot, a frame every STEP seconds.

    trailer_sheet.py <out.jpg> <shot dir>... [--step 0.5] [--width 320]

Each shot dir is build/trailer/shots/<id> (frame########.png at 30 fps); each thumbnail is
labelled with the shot id and its time in the shot.
"""
import argparse
import os

from PIL import Image, ImageDraw

FPS = 30


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("shots", nargs="+")
    ap.add_argument("--step", type=float, default=0.5)
    ap.add_argument("--width", type=int, default=320)
    a = ap.parse_args()
    rows = []
    for d in a.shots:
        frames = sorted(n for n in os.listdir(d) if n.startswith("frame") and n.endswith(".png"))
        picks = list(range(0, len(frames), max(1, round(a.step * FPS))))
        rows.append((os.path.basename(d.rstrip("/")), [(i, os.path.join(d, frames[i])) for i in picks]))
    tw, th = a.width, a.width * 9 // 16
    cols = max(len(r[1]) for r in rows)
    sheet = Image.new("RGB", (cols * (tw + 4) + 4, len(rows) * (th + 4) + 4), (24, 24, 24))
    draw = ImageDraw.Draw(sheet)
    for ri, (name, picks) in enumerate(rows):
        for ci, (i, path) in enumerate(picks):
            with Image.open(path) as im:
                thumb = im.convert("RGB").resize((tw, th), Image.LANCZOS)
            x, y = 4 + ci * (tw + 4), 4 + ri * (th + 4)
            sheet.paste(thumb, (x, y))
            label = "%s %.1fs" % (name, i / FPS)
            draw.rectangle((x, y, x + 7 * len(label) + 6, y + 14), fill=(0, 0, 0))
            draw.text((x + 3, y + 2), label, fill=(255, 255, 255))
    sheet.save(a.out, quality=88)
    print("trailer_sheet: %s (%d shots)" % (a.out, len(rows)))


if __name__ == "__main__":
    main()
