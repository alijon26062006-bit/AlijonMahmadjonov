"""Writes the DARYOB brand SVGs. Geometry matches DaryobMark (Flutter).

The mark lives in a 100×100 box: a map pin tilted 45° (circle centre 42,42,
radius 24, tip at 66,66) whose tip continues as a magnifier handle, with a
four-point spark inside.

    python3 tool/brand/make_svgs.py && node tool/brand/render_icons.js
"""
import math
from pathlib import Path

NAVY = '#101C32'
LIME = '#C9F24B'
HERE = Path(__file__).parent


def spark_points():
    pts = []
    for i in range(8):
        r = 11 if i % 2 == 0 else 3.4
        a = -math.pi / 2 + i * math.pi / 4
        pts.append(f'{42 + math.cos(a) * r:.2f},{42 + math.sin(a) * r:.2f}')
    return ' '.join(pts)


def mark(color):
    return (
        f'<path d="M66 42 A24 24 0 1 0 42 66 L66 66 Z" fill="none" stroke="{color}" '
        f'stroke-width="10" stroke-linejoin="round"/>'
        f'<line x1="68" y1="68" x2="83" y2="83" stroke="{color}" stroke-width="12" '
        f'stroke-linecap="round"/>'
        f'<polygon points="{spark_points()}" fill="{color}"/>'
    )


def placed(color, canvas, scale, cx=54, cy=54):
    """Mark scaled by [scale] with its visual centre (cx, cy) at canvas centre."""
    tx = canvas / 2 - cx * scale
    ty = canvas / 2 - cy * scale
    return f'<g transform="translate({tx:.2f} {ty:.2f}) scale({scale})">{mark(color)}</g>'


def svg(size, body):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
        f'width="{size}" height="{size}">{body}</svg>\n'
    )


files = {
    # Full app icon / store icon: navy rounded square, lime mark.
    'icon.svg': svg(1024, f'<rect width="1024" height="1024" rx="232" fill="{NAVY}"/>'
                          + placed(LIME, 1024, 7.4)),
    # Adaptive icon foreground (108 dp canvas; keep inside the 66 dp circle).
    'adaptive_foreground.svg': svg(108, placed(LIME, 108, 0.64)),
    # Android 12+ splash icon (288 dp canvas; must fit a 192 dp circle).
    'splash_icon.svg': svg(288, placed(LIME, 288, 1.7)),
    # Mark alone, transparent background.
    'mark.svg': svg(100, mark(LIME)),
}

for name, content in files.items():
    (HERE / name).write_text(content)
    print('wrote', name)
