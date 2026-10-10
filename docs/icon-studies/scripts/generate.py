#!/usr/bin/env python3
"""Pdfs by Kash app icon studies: writes one SVG per concept to ../concepts/.

Every icon is plain SVG geometry (no fonts, no bitmaps), so the files render the same
everywhere. The body matches the other by-kash apps (Geminio, Budget): an 824 px rounded
square at (100, 100) on a 1024 canvas, radius 188, with the same soft drop shadow.

Run:  python3 icon-studies/scripts/generate.py [name ...]
Then: icon-studies/scripts/render.sh
"""
import math
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "concepts"
OUT.mkdir(parents=True, exist_ok=True)

BODY = dict(x=100, y=100, w=824, h=824, rx=188)


def f(n):
    return f"{round(n, 2):g}"


def pts(points):
    return " ".join(f"{f(x)},{f(y)}" for x, y in points)


def grain(id_, op=0.12, freq=1.1, seed=7):
    return (
        f'<filter id="{id_}" x="0" y="0" width="100%" height="100%">'
        f'<feTurbulence type="fractalNoise" baseFrequency="{freq}" numOctaves="2" seed="{seed}"/>'
        f'<feColorMatrix type="matrix" values="0 0 0 0 .5  0 0 0 0 .5  0 0 0 0 .5  0 0 0 {op} 0"/></filter>'
    )


def blur(id_, s):
    return f'<filter id="{id_}" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="{s}"/></filter>'


def drop(id_, dy, sd, color="#000", op=0.35):
    return (
        f'<filter id="{id_}" x="-30%" y="-30%" width="160%" height="170%">'
        f'<feDropShadow dx="0" dy="{dy}" stdDeviation="{sd}" flood-color="{color}" flood-opacity="{op}"/></filter>'
    )


def shell(base, defs="", bg="", inner="", over="", rim=0.22):
    """The shared body: shadowed rounded square, clipped artwork, a hairline light rim on top."""
    b = BODY
    rect = f'x="{b["x"]}" y="{b["y"]}" width="{b["w"]}" height="{b["h"]}" rx="{b["rx"]}"'
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024" width="1024" height="1024">
<defs>
  <clipPath id="body"><rect {rect}/></clipPath>
  <filter id="drop" x="-20%" y="-20%" width="140%" height="150%"><feDropShadow dx="0" dy="16" stdDeviation="16" flood-color="#000" flood-opacity=".38"/></filter>
  <linearGradient id="rim" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity="{rim}"/><stop offset=".35" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".18"/></linearGradient>
  {defs}
</defs>
<g filter="url(#drop)"><rect {rect} fill="{base}"/></g>
<g clip-path="url(#body)">
{bg}
{inner}
{over}
</g>
<rect x="{b["x"] + 1.5}" y="{b["y"] + 1.5}" width="{b["w"] - 3}" height="{b["h"] - 3}" rx="{b["rx"] - 1.5}" fill="none" stroke="url(#rim)" stroke-width="3"/>
</svg>
"""


# ---------------------------------------------------------------- 01 Monoline
def monoline():
    """The family mark: a monoline p, with fainter rings of the bigger file it used to be."""
    cx, cy, R, sw = 548, 448, 150, 58
    stem_x, top, bot = cx - R, cy - R, 798
    rings = "".join(
        f'<circle cx="{cx}" cy="{cy}" r="{f(R * k)}" fill="none" stroke="#fff" stroke-opacity="{op}" stroke-width="{w}"/>'
        for k, op, w in ((2.05, 0.05, 3), (1.68, 0.08, 4), (1.36, 0.13, 5))
    )
    return shell(
        "#0c0b14",
        defs=f"""<radialGradient id="bg" cx=".5" cy=".34" r=".9"><stop offset="0" stop-color="#26213f"/><stop offset="1" stop-color="#0a0910"/></radialGradient>
  <linearGradient id="ring" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ff8a5c"/><stop offset=".5" stop-color="#ff4f7b"/><stop offset="1" stop-color="#9b5cff"/></linearGradient>
  <linearGradient id="stem" gradientUnits="userSpaceOnUse" x1="0" y1="{top}" x2="0" y2="{bot}"><stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#cfc6ff"/></linearGradient>
  {blur("glow", 18)}{grain("grain", 0.10)}""",
        bg='<rect width="1024" height="1024" fill="url(#bg)"/>',
        inner=f"""{rings}
<circle cx="{cx}" cy="{cy}" r="{R}" fill="none" stroke="url(#ring)" stroke-width="{sw}" opacity=".6" filter="url(#glow)"/>
<circle cx="{cx}" cy="{cy}" r="{R}" fill="none" stroke="url(#ring)" stroke-width="{sw}"/>
<line x1="{stem_x}" y1="{top}" x2="{stem_x}" y2="{bot}" stroke="url(#stem)" stroke-width="{sw}" stroke-linecap="round"/>""",
        over='<rect width="1024" height="1024" filter="url(#grain)"/>',
    )


# ---------------------------------------------------------------- 02 Squish
def squish():
    """Playful: a fat, glossy p squashed flat under a press plate."""
    L, sw = 286, 132  # stem left edge, stem width
    cx, cy, rx, ry = 560, 540, 238, 158  # squashed bowl
    irx, iry = 112, 52
    top = cy - ry
    bowl = (
        f"M{cx - rx},{cy} a{rx},{ry} 0 1,0 {2 * rx},0 a{rx},{ry} 0 1,0 {-2 * rx},0 Z "
        f"M{cx + 14 - irx},{cy} a{irx},{iry} 0 1,1 {2 * irx},0 a{irx},{iry} 0 1,1 {-2 * irx},0 Z"
    )
    stem = f'<rect x="{L}" y="{top}" width="{sw}" height="{830 - top}" rx="56"/>'
    p = f'<path d="{bowl}" fill-rule="evenodd"/>{stem}'
    return shell(
        "#ffb21f",
        defs=f"""<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffe06b"/><stop offset="1" stop-color="#ff9a1f"/></linearGradient>
  <linearGradient id="red" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ff6a4d"/><stop offset="1" stop-color="#e8304a"/></linearGradient>
  <linearGradient id="plate" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#4a3d5c"/><stop offset=".8" stop-color="#2b2238"/><stop offset="1" stop-color="#1c1626"/></linearGradient>
  <linearGradient id="gloss" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".55"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
  <clipPath id="pclip">{p}</clipPath>
  {drop("pshadow", 18, 14, "#a3410d", 0.45)}{grain("grain", 0.08)}""",
        bg='<rect width="1024" height="1024" fill="url(#bg)"/>',
        inner=f"""<g filter="url(#pshadow)" fill="url(#red)">{p}</g>
<g clip-path="url(#pclip)">
  <ellipse cx="{cx - 30}" cy="{top + 46}" rx="{rx - 50}" ry="40" fill="url(#gloss)"/>
  <rect x="{L + 24}" y="{top + 100}" width="26" height="300" rx="13" fill="#fff" opacity=".28"/>
</g>
<g stroke="#c2410c" stroke-width="16" stroke-linecap="round" fill="none" opacity=".55">
  <path d="M{cx + rx + 34},{cy - 60} q22,60 0,120"/><path d="M{cx + rx + 66},{cy - 36} q14,36 0,72"/>
  <path d="M{L - 34},{cy - 60} q-22,60 0,120"/><path d="M{L - 66},{cy - 36} q-14,36 0,72"/>
</g>
<g filter="url(#pshadow)">
  <rect x="232" y="{top - 112}" width="560" height="112" rx="30" fill="url(#plate)"/>
  <rect x="262" y="{top - 104}" width="500" height="10" rx="5" fill="#fff" opacity=".2"/>
</g>
<g stroke="#a3410d" stroke-width="16" stroke-linecap="round" opacity=".45">
  <line x1="380" y1="{top - 210}" x2="380" y2="{top - 160}"/><line x1="512" y1="{top - 226}" x2="512" y2="{top - 160}"/><line x1="644" y1="{top - 210}" x2="644" y2="{top - 160}"/>
</g>""",
        over='<rect width="1024" height="1024" filter="url(#grain)"/>',
    )


# ---------------------------------------------------------------- 03 Sheet
def sheet():
    """macOS-native: a Preview-white page, its old larger outline behind, the system 'shrink' arrows."""
    x0, y0, x1, y1, dog = 312, 236, 712, 788, 104
    page = pts([(x0, y0), (x1 - dog, y0), (x1, y0 + dog), (x1, y1), (x0, y1)])
    gx0, gy0, gx1, gy1 = 236, 168, 788, 856
    cxp, cyp = (x0 + x1) / 2, (y0 + y1) / 2 + 24

    s = 66  # half-length of each arrow's travel
    g = 26  # gap from centre
    # Top-left arrow points down-right to the centre; bottom-right points up-left.
    tl_tip = (cxp - g, cyp - g)
    br_tip = (cxp + g, cyp + g)
    head = 92
    arrows = (
        f'<path d="M{f(tl_tip[0] - s * 1.6)},{f(tl_tip[1] - s * 1.6)} L{f(tl_tip[0])},{f(tl_tip[1])} '
        f'M{f(tl_tip[0] - head)},{f(tl_tip[1])} L{f(tl_tip[0])},{f(tl_tip[1])} L{f(tl_tip[0])},{f(tl_tip[1] - head)}"/>'
        f'<path d="M{f(br_tip[0] + s * 1.6)},{f(br_tip[1] + s * 1.6)} L{f(br_tip[0])},{f(br_tip[1])} '
        f'M{f(br_tip[0] + head)},{f(br_tip[1])} L{f(br_tip[0])},{f(br_tip[1])} L{f(br_tip[0])},{f(br_tip[1] + head)}"/>'
    )
    return shell(
        "#2f8bff",
        defs=f"""<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#6fc3ff"/><stop offset="1" stop-color="#1468f0"/></linearGradient>
  <linearGradient id="paper" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#e9eef6"/></linearGradient>
  <linearGradient id="fold" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="#c9d3e3"/><stop offset="1" stop-color="#ffffff"/></linearGradient>
  <linearGradient id="ink" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#2a8cff"/><stop offset="1" stop-color="#0a5ce0"/></linearGradient>
  {drop("pshadow", 22, 22, "#06307a", 0.45)}""",
        bg='<rect width="1024" height="1024" fill="url(#bg)"/>',
        inner=f"""<rect x="{gx0}" y="{gy0}" width="{gx1 - gx0}" height="{gy1 - gy0}" rx="26" fill="#fff" fill-opacity=".10" stroke="#fff" stroke-opacity=".55" stroke-width="7" stroke-dasharray="26 20"/>
<g filter="url(#pshadow)"><polygon points="{page}" fill="url(#paper)"/></g>
<polygon points="{pts([(x1 - dog, y0), (x1 - dog, y0 + dog), (x1, y0 + dog)])}" fill="url(#fold)"/>
<g fill="none" stroke="url(#ink)" stroke-width="56" stroke-linecap="round" stroke-linejoin="round">{arrows}</g>""",
        over="",
        rim=0.35,
    )


# ---------------------------------------------------------------- 04 Accordion
def accordion():
    """Abstract: one sheet folded into bellows, the folds tightening left to right."""
    n = 7
    x_start, x_end = 214, 812
    # Panel widths shrink geometrically: wide and calm on the left, dense on the right.
    ws = [1.0 * (0.66 ** i) for i in range(n)]
    k = (x_end - x_start) / sum(ws)
    ws = [w * k for w in ws]
    xs = [x_start]
    for w in ws:
        xs.append(xs[-1] + w)
    top, bot = 352, 712
    panels = ""
    for i in range(n):
        # Each fold rises more as the panel narrows (the paper is pushed together).
        d0 = 0 if i % 2 == 0 else None
        lift = lambda j: (0 if j % 2 == 0 else 1) * (10 + 120 * (1 - ws[min(j, n - 1)] / ws[0]))
        a, b = xs[i], xs[i + 1]
        la, lb = lift(i), lift(i + 1)
        poly = [(a, top - la), (b, top - lb), (b, bot - lb), (a, bot - la)]
        fill = "url(#lit)" if i % 2 == 0 else "url(#shade)"
        panels += f'<polygon points="{pts(poly)}" fill="{fill}"/>'
        if i == 0:
            continue
        panels += f'<line x1="{f(a)}" y1="{f(top - la)}" x2="{f(a)}" y2="{f(bot - la)}" stroke="#fff" stroke-opacity="{0.55 if i % 2 == 0 else 0.15}" stroke-width="3"/>'
    # The first, still-flat panel shows the page's text; the rest is already folded away.
    a, b = xs[0], xs[1]
    lines = "".join(
        f'<line x1="{f(a + 46)}" y1="{y}" x2="{f(a + 46 + (b - a - 100) * wf)}" y2="{y}"/>'
        for y, wf in ((top + 70, 0.55), (top + 128, 1), (top + 172, 0.92), (top + 216, 1), (top + 260, 0.7))
    )
    return shell(
        "#0d3a3c",
        defs=f"""<radialGradient id="bg" cx=".4" cy=".3" r=".95"><stop offset="0" stop-color="#1c6a68"/><stop offset="1" stop-color="#062426"/></radialGradient>
  <linearGradient id="lit" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fffaf0"/><stop offset="1" stop-color="#efe5d2"/></linearGradient>
  <linearGradient id="shade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#c3ae8a"/><stop offset="1" stop-color="#9c8763"/></linearGradient>
  <linearGradient id="red" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#ff7a59"/><stop offset="1" stop-color="#ff4d6d"/></linearGradient>
  {drop("pshadow", 26, 22, "#00110f", 0.55)}{grain("grain", 0.10)}""",
        bg='<rect width="1024" height="1024" fill="url(#bg)"/>',
        inner=f"""<g filter="url(#pshadow)">{panels}</g>
<g stroke="#8b7a5c" stroke-opacity=".55" stroke-width="14" stroke-linecap="round">{lines}</g>
""",
        over='<rect width="1024" height="1024" filter="url(#grain)"/>',
    )


# ---------------------------------------------------------------- 05 Diamond
def diamond():
    """Elegant: pressure makes diamonds. A small, bright, cut stone on midnight."""
    cx = 512
    ty, gy, cy_ = 318, 440, 790  # table, girdle, culet
    tw, gw = 300, 540
    tl, tr = cx - tw / 2, cx + tw / 2
    gl, gr = cx - gw / 2, cx + gw / 2
    # crown: table + triangles between table corners and girdle
    gm = [gl + gw * t for t in (0, 0.25, 0.5, 0.75, 1)]
    tm = [tl + tw * t for t in (0, 0.5, 1)]
    crown = [
        ([(tl, ty), (gm[0], gy), (gm[1], gy)], "#d9e6ff"),
        ([(tl, ty), (gm[1], gy), (tm[1], ty)], "#f6f9ff"),
        ([(tm[1], ty), (gm[1], gy), (gm[2], gy)], "#bcd0ff"),
        ([(tm[1], ty), (gm[2], gy), (gm[3], gy)], "#e8efff"),
        ([(tm[1], ty), (gm[3], gy), (tr, ty)], "#cfdcff"),
        ([(tr, ty), (gm[3], gy), (gm[4], gy)], "#a9bdf5"),
    ]
    culet = (cx, cy_)
    pav = [
        ([(gm[0], gy), (gm[1], gy), culet], "#9fb6f2"),
        ([(gm[1], gy), (gm[2], gy), culet], "#e3ebff"),
        ([(gm[2], gy), (gm[3], gy), culet], "#c3d3ff"),
        ([(gm[3], gy), (gm[4], gy), culet], "#7f97de"),
    ]
    inner_lines = (
        f'<path d="M{f(gm[1])},{gy} L{f(cx - 50)},{cy_ - 120} M{f(gm[3])},{gy} L{f(cx + 50)},{cy_ - 120}" '
        f'stroke="#fff" stroke-opacity=".35" stroke-width="3" fill="none"/>'
    )
    facets = "".join(f'<polygon points="{pts(p)}" fill="{c}"/>' for p, c in crown + pav)
    edges = "".join(
        f'<polygon points="{pts(p)}" fill="none" stroke="#ffffff" stroke-opacity=".7" stroke-width="3" stroke-linejoin="round"/>'
        for p, _ in crown + pav
    )
    outline = pts([(tl, ty), (tr, ty), (gr, gy), culet, (gl, gy)])

    def star(x, y, r, op):
        return (
            f'<path d="M{x},{y - r} Q{x},{y} {x + r},{y} Q{x},{y} {x},{y + r} Q{x},{y} {x - r},{y} Q{x},{y} {x},{y - r} Z" fill="#fff" opacity="{op}"/>'
        )

    return shell(
        "#0b1030",
        defs=f"""<radialGradient id="bg" cx=".5" cy=".42" r=".75"><stop offset="0" stop-color="#2b3a86"/><stop offset=".55" stop-color="#141c4d"/><stop offset="1" stop-color="#080b22"/></radialGradient>
  <linearGradient id="tint" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ff9ad5" stop-opacity=".35"/><stop offset=".5" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#7ef0ff" stop-opacity=".35"/></linearGradient>
  <clipPath id="gem"><polygon points="{outline}"/></clipPath>
  {blur("glow", 40)}{drop("gshadow", 30, 26, "#000", 0.5)}{grain("grain", 0.08)}""",
        bg='<rect width="1024" height="1024" fill="url(#bg)"/>',
        inner=f"""<ellipse cx="{cx}" cy="{(ty + cy_) / 2}" rx="260" ry="250" fill="#6f8cff" opacity=".35" filter="url(#glow)"/>
<g filter="url(#gshadow)">{facets}</g>
<g clip-path="url(#gem)"><rect width="1024" height="1024" fill="url(#tint)"/>{inner_lines}</g>
{edges}
{star(684, 300, 46, 0.95)}{star(330, 742, 26, 0.6)}""",
        over='<rect width="1024" height="1024" filter="url(#grain)"/>',
    )


# ---------------------------------------------------------------- 06 Didone
def didone():
    """Editorial: a Didot-style p in ink on warm paper; the text rules beneath set tighter and tighter."""
    ink = "#1d1a2b"
    # Stem
    sx0, sx1, stop, sbot = 356, 436, 300, 790
    # Bowl: outer ellipse, inner offset left -> thick right, hairline top & bottom (vertical stress)
    cx, cy, orx, ory = 540, 482, 182, 182
    icx, irx, iry = 516, 118, 170
    bowl = (
        f"M{cx - orx},{cy} a{orx},{ory} 0 1,0 {2 * orx},0 a{orx},{ory} 0 1,0 {-2 * orx},0 Z "
        f"M{icx - irx},{cy} a{irx},{iry} 0 1,1 {2 * irx},0 a{irx},{iry} 0 1,1 {-2 * irx},0 Z"
    )
    # Hairline serifs: the top-left flag and the foot of the descender.
    serifs = (
        f'<path d="M{sx0},{stop} L{sx0 - 62},{stop + 18} L{sx0 - 62},{stop + 26} L{sx0},{stop + 22} Z"/>'
        f'<rect x="{sx0 - 58}" y="{sbot - 7}" width="{sx1 - sx0 + 116}" height="7"/>'
    )
    rules = ""
    y, gap = 214, 46
    while y < 900:
        rules += f'<line x1="100" y1="{f(y)}" x2="924" y2="{f(y)}"/>'
        y += gap
        gap = max(9, gap * 0.86)
    return shell(
        "#f3ecdf",
        defs=f"""<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fbf6ec"/><stop offset="1" stop-color="#ebe1cf"/></linearGradient>
  {grain("grain", 0.14, 0.9)}""",
        bg=f'<rect width="1024" height="1024" fill="url(#bg)"/><g stroke="#8a6f4a" stroke-opacity=".16" stroke-width="2">{rules}</g>',
        inner=f"""<g fill="{ink}">
  <path d="{bowl}" fill-rule="evenodd"/>
  <rect x="{sx0}" y="{stop}" width="{sx1 - sx0}" height="{sbot - stop}"/>
  {serifs}
</g>
<circle cx="{cx + orx + 52}" cy="{cy + ory - 26}" r="30" fill="#e2412f"/>""",
        over='<rect width="1024" height="1024" filter="url(#grain)"/>',
        rim=0.5,
    )


# ---------------------------------------------------------------- 07 Strata
def strata():
    """Modern: bands of colour pressed thinner toward the bottom, a heavy white p on top."""
    heights = [0.78 ** i for i in range(14)]
    k = 824 / sum(heights)
    cols = ["#ff8a4c", "#ff6a52", "#ff4f6a", "#f43f86", "#d93ba0", "#b63db6", "#8f3fc4", "#6c40cc",
            "#5139c0", "#3f31aa", "#30298f", "#262276", "#1e1c60", "#18174d"]
    y, bands = 100.0, ""
    for h, c in zip(heights, cols):
        bands += f'<rect x="0" y="{f(y)}" width="1024" height="{f(h * k + 1)}" fill="{c}"/>'
        y += h * k
    # Heavy geometric p (Avenir Heavy proportions)
    cx, cy, R, w = 566, 442, 192, 128
    stem_l = cx - R
    p = (
        f'<circle cx="{cx}" cy="{cy}" r="{R - w / 2}" fill="none" stroke="#fff" stroke-width="{w}"/>'
        f'<rect x="{stem_l}" y="{cy - R}" width="{w}" height="{820 - (cy - R)}" rx="18" fill="#fff"/>'
    )
    return shell(
        "#ff6a52",
        defs=f"""<linearGradient id="sheen" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity=".12"/><stop offset=".5" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".12"/></linearGradient>
  {drop("pshadow", 20, 18, "#1a0a3a", 0.45)}{grain("grain", 0.10)}""",
        bg=bands + '<rect width="1024" height="1024" fill="url(#sheen)"/>',
        inner=f'<g filter="url(#pshadow)">{p}</g>',
        over='<rect width="1024" height="1024" filter="url(#grain)"/>',
    )


# ---------------------------------------------------------------- 08 Origami
def origami():
    """A p folded from one strip of two-sided paper: making something smaller without losing any of it."""
    L, R, T, B, w, foot = 322, 714, 246, 598, 124, 812
    stem = [(L, T), (L + w, T + w), (L + w, foot - 70), (L, foot)]
    flap = [(L, foot), (L + w, foot - 70), (L + w, foot - 6)]  # the coral back of the paper, turned up at the foot
    topbar = [(L, T), (R, T), (R - w, T + w), (L + w, T + w)]
    right = [(R, T), (R, B), (R - w, B - w), (R - w, T + w)]
    bottom = [(L + w, B - w), (R - w, B - w), (R, B), (L + w, B)]
    return shell(
        "#23264f",
        defs=f"""<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ff8a66"/><stop offset=".55" stop-color="#f0506a"/><stop offset="1" stop-color="#b8326a"/></linearGradient>
  <linearGradient id="s" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#f1eef4"/></linearGradient>
  <linearGradient id="t" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#ece7f0"/><stop offset="1" stop-color="#fdfbff"/></linearGradient>
  <linearGradient id="r" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e2dcea"/><stop offset="1" stop-color="#cfc7da"/></linearGradient>
  <linearGradient id="b" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#bdb3cc"/><stop offset="1" stop-color="#d6cfe0"/></linearGradient>
  <linearGradient id="flap" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="#2c2f6e"/><stop offset="1" stop-color="#4b4fa8"/></linearGradient>
  {drop("pshadow", 26, 20, "#5a0f2e", 0.5)}{grain("grain", 0.09)}""",
        bg='<rect width="1024" height="1024" fill="url(#bg)"/>',
        inner=f"""<g filter="url(#pshadow)">
  <polygon points="{pts(stem)}" fill="url(#s)"/>
  <polygon points="{pts(flap)}" fill="url(#flap)"/>
  <polygon points="{pts(topbar)}" fill="url(#t)"/>
  <polygon points="{pts(right)}" fill="url(#r)"/>
  <polygon points="{pts(bottom)}" fill="url(#b)"/>
</g>
<g stroke="#4a2a5a" stroke-opacity=".14" stroke-width="2.5">
  <line x1="{L}" y1="{T}" x2="{L + w}" y2="{T + w}"/><line x1="{R}" y1="{T}" x2="{R - w}" y2="{T + w}"/><line x1="{R}" y1="{B}" x2="{R - w}" y2="{B - w}"/>
</g>""",
        over='<rect width="1024" height="1024" filter="url(#grain)"/>',
    )


CONCEPTS = [
    ("01-monoline", monoline),
    ("02-squish", squish),
    ("03-sheet", sheet),
    ("04-accordion", accordion),
    ("05-diamond", diamond),
    ("06-didone", didone),
    ("07-strata", strata),
    ("08-origami", origami),
]

if __name__ == "__main__":
    want = set(sys.argv[1:])
    for name, fn in CONCEPTS:
        if want and not any(w in name for w in want):
            continue
        (OUT / f"{name}.svg").write_text(fn())
        print("wrote", OUT / f"{name}.svg")
