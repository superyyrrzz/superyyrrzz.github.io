#!/usr/bin/env python3
"""Render a 1200x630 OG image for a blog post.

Usage:
    python tools/og.py "<title>" <output.png>
    python tools/og.py --default <output.png>     # site default (no title)
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630
BG_TOP = (15, 23, 42)        # slate-900
BG_BOTTOM = (30, 41, 59)     # slate-800
ACCENT = (250, 204, 21)      # amber-400 — guitar/jazz nod, ties to favicon
FG = (248, 250, 252)         # slate-50
MUTED = (148, 163, 184)      # slate-400

SEGOE_BOLD = r"C:\Windows\Fonts\segoeuib.ttf"
SEGOE_REG = r"C:\Windows\Fonts\segoeui.ttf"
CONSOLAS_BOLD = r"C:\Windows\Fonts\consolab.ttf"


def gradient(img):
    px = img.load()
    for y in range(H):
        t = y / H
        r = int(BG_TOP[0] * (1 - t) + BG_BOTTOM[0] * t)
        g = int(BG_TOP[1] * (1 - t) + BG_BOTTOM[1] * t)
        b = int(BG_TOP[2] * (1 - t) + BG_BOTTOM[2] * t)
        for x in range(W):
            px[x, y] = (r, g, b)


def wrap(draw, text, font, max_w):
    words = text.split()
    lines, cur = [], ""
    for word in words:
        trial = (cur + " " + word).strip()
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def render(title, out_path):
    img = Image.new("RGB", (W, H))
    gradient(img)
    draw = ImageDraw.Draw(img)

    # Accent bar on the left
    draw.rectangle([(0, 0), (12, H)], fill=ACCENT)

    # Site name (top-left, monospace)
    site_font = ImageFont.truetype(CONSOLAS_BOLD, 28)
    draw.text((60, 56), "Renze Yu", font=site_font, fill=ACCENT)

    # URL (top-right, muted)
    url_font = ImageFont.truetype(SEGOE_REG, 24)
    url = "superyyrrzz.github.io"
    url_w = draw.textlength(url, font=url_font)
    draw.text((W - 60 - url_w, 60), url, font=url_font, fill=MUTED)

    # Title (centered vertically-ish, large)
    if title:
        size = 44
        tfont = ImageFont.truetype(SEGOE_BOLD, size)
        lines = wrap(draw, title, tfont, W - 140)
        for trial in (72, 64, 56, 50, 44):
            tfont = ImageFont.truetype(SEGOE_BOLD, trial)
            lines = wrap(draw, title, tfont, W - 140)
            if len(lines) <= 4:
                size = trial
                break
        line_h = int(size * 1.18)
        total_h = line_h * len(lines)
        y = (H - total_h) // 2 - 10
        for line in lines:
            draw.text((60, y), line, font=tfont, fill=FG)
            y += line_h
    else:
        tag_font = ImageFont.truetype(SEGOE_BOLD, 84)
        draw.text((60, 240), "Renze Yu", font=tag_font, fill=FG)
        sub_font = ImageFont.truetype(SEGOE_REG, 36)
        draw.text((60, 350), "engineering notes", font=sub_font, fill=MUTED)

    # Footer hairline
    draw.rectangle([(60, H - 80), (W - 60, H - 79)], fill=MUTED)

    img.save(out_path, "PNG", optimize=True)
    print(f"wrote {out_path}")


def main():
    args = sys.argv[1:]
    if len(args) == 2 and args[0] == "--default":
        render(None, Path(args[1]))
    elif len(args) == 2:
        render(args[0], Path(args[1]))
    else:
        print(__doc__, file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
