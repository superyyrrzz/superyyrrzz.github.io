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
# Safe zone: keep all text inside x=[SAFE_X, W-SAFE_X], y=[SAFE_Y, H-SAFE_Y].
# Social platforms (and our own blog grid on narrow viewports) may center-crop
# to non-1.91:1 aspect ratios. Anything outside the safe zone can be clipped.
SAFE_X = 170
SAFE_Y = 90
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

    # Accent bar on the left (decorative; safe to clip)
    draw.rectangle([(0, 0), (12, H)], fill=ACCENT)

    inner_w = W - 2 * SAFE_X

    # Site name (top-left of safe zone, monospace)
    site_font = ImageFont.truetype(CONSOLAS_BOLD, 28)
    draw.text((SAFE_X, SAFE_Y), "Renze Yu", font=site_font, fill=ACCENT)

    # URL (top-right of safe zone, muted)
    url_font = ImageFont.truetype(SEGOE_REG, 24)
    url = "superyyrrzz.github.io"
    url_w = draw.textlength(url, font=url_font)
    draw.text((W - SAFE_X - url_w, SAFE_Y + 4), url, font=url_font, fill=MUTED)

    # Title (vertically centered, wrapped within safe zone)
    if title:
        size = 40
        tfont = ImageFont.truetype(SEGOE_BOLD, size)
        lines = wrap(draw, title, tfont, inner_w)
        for trial in (64, 56, 50, 44, 40):
            tfont = ImageFont.truetype(SEGOE_BOLD, trial)
            lines = wrap(draw, title, tfont, inner_w)
            if len(lines) <= 4:
                size = trial
                break
        line_h = int(size * 1.18)
        total_h = line_h * len(lines)
        y = (H - total_h) // 2 - 10
        for line in lines:
            draw.text((SAFE_X, y), line, font=tfont, fill=FG)
            y += line_h
    else:
        tag_font = ImageFont.truetype(SEGOE_BOLD, 84)
        draw.text((SAFE_X, 240), "Renze Yu", font=tag_font, fill=FG)
        sub_font = ImageFont.truetype(SEGOE_REG, 36)
        draw.text((SAFE_X, 350), "engineering notes", font=sub_font, fill=MUTED)

    # Footer hairline (inside safe zone)
    draw.rectangle([(SAFE_X, H - SAFE_Y - 10), (W - SAFE_X, H - SAFE_Y - 9)], fill=MUTED)

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
