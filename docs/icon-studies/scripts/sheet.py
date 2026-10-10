#!/usr/bin/env python3
"""Contact sheet (png/sheet.png): each concept at 256, then 128/64/32/16 at true pixel size,
on a dark and a light strip, so legibility can be judged from one image."""
from pathlib import Path
from PIL import Image

here = Path(__file__).resolve().parent.parent
names = sorted(p.stem for p in (here / "concepts").glob("*.svg"))
cols, cw, ch = 4, 300, 420
sheet = Image.new("RGB", (cols * cw, ((len(names) + cols - 1) // cols) * ch), (24, 23, 30))
for i, n in enumerate(names):
    x, y = (i % cols) * cw, (i // cols) * ch
    big = Image.open(here / "png" / f"{n}-256.png").convert("RGBA")
    sheet.paste(big, (x + 22, y + 10), big)
    for row, bgc in enumerate([(30, 30, 36), (236, 236, 240)]):
        ry = y + 280 + row * 66
        sheet.paste(Image.new("RGB", (cw - 20, 62), bgc), (x + 10, ry))
        sx = x + 18
        for s in (128, 64, 32, 16):
            if s == 128:
                continue
            im = Image.open(here / "png" / f"{n}-{s}.png").convert("RGBA")
            sheet.paste(im, (sx, ry + (62 - s) // 2), im)
            sx += s + 24
sheet.save(here / "png" / "sheet.png")
print("wrote", here / "png" / "sheet.png")
