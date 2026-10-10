# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Kaschief

"""Pdfs by Kash design tokens — the single source for colour, shape and motion.

Values mirror the approved mockups (design/settings-v2 on the
settings-design-exploration branch). Every view reads from here; nothing reads
NSColor.controlAccentColor, so the app looks the same whatever accent colour
the user picked in System Settings — like its siblings Geminio and Budget.
"""

from __future__ import annotations

import AppKit as AK
import Quartz  # noqa: F401  (registers CGColorRef so layer colours bridge cleanly)


def _rgb(hex_value: str, alpha: float = 1.0):
    value = hex_value.lstrip("#")
    r, g, b = (int(value[i : i + 2], 16) / 255 for i in (0, 2, 4))
    return AK.NSColor.colorWithSRGBRed_green_blue_alpha_(r, g, b, alpha)


def is_dark(appearance) -> bool:
    if appearance is None:
        appearance = AK.NSApp.effectiveAppearance() if AK.NSApp else None
    if appearance is None:
        return False
    match = appearance.bestMatchFromAppearancesWithNames_(
        [AK.NSAppearanceNameAqua, AK.NSAppearanceNameDarkAqua]
    )
    return match == AK.NSAppearanceNameDarkAqua


def _dynamic(name: str, light, dark):
    return AK.NSColor.colorWithName_dynamicProvider_(
        name, lambda appearance: dark if is_dark(appearance) else light
    )


# -- Colour (light · dark) -----------------------------------------------------------
ACCENT = _dynamic("pbkAccent", _rgb("#5B4EE8"), _rgb("#8F87FF"))
ACCENT_INK = _dynamic("pbkAccentInk", _rgb("#FFFFFF"), _rgb("#12112A"))
ACCENT_SOFT = _dynamic("pbkAccentSoft", _rgb("#EEECFD"), _rgb("#26235C"))
ACCENT_RING = _dynamic("pbkAccentRing", _rgb("#5B4EE8", 0.40), _rgb("#8F87FF", 0.45))
FOCUS_RING = _dynamic("pbkFocus", _rgb("#5B4EE8", 0.55), _rgb("#8F87FF", 0.60))
WARN = _dynamic("pbkWarn", _rgb("#C2620A"), _rgb("#FFB35C"))
WARN_SOFT = _dynamic("pbkWarnSoft", _rgb("#FFF1E0"), _rgb("#3A2A14"))
WARN_RING = _dynamic("pbkWarnRing", _rgb("#C2620A", 0.30), _rgb("#FFB35C", 0.35))
SUCCESS = _dynamic("pbkSuccess", _rgb("#2F8A3C"), _rgb("#8BDC7A"))
FAIL = _dynamic("pbkFail", _rgb("#D1453B"), _rgb("#FF8C7F"))

WINDOW = _dynamic("pbkWindow", _rgb("#FFFFFF"), _rgb("#17162B"))
CHROME = _dynamic("pbkChrome", _rgb("#F7F6FB"), _rgb("#1D1C36"))
CONTROL = _dynamic("pbkControl", _rgb("#FFFFFF"), _rgb("#24234A"))
FLOAT = _dynamic("pbkFloat", _rgb("#FFFFFF"), _rgb("#24234A"))
HAIRLINE = _dynamic("pbkHairline", _rgb("#E8E6F1"), _rgb("#2B2950"))
CONTROL_RING = _dynamic("pbkControlRing", _rgb("#17162B", 0.10), _rgb("#FFFFFF", 0.10))
INK = _dynamic("pbkInk", _rgb("#17162B"), _rgb("#EFEEFE"))
INK_2 = _dynamic("pbkInk2", _rgb("#4A4862"), _rgb("#C9C7E6"))
MUTED = _dynamic("pbkMuted", _rgb("#8A88A3"), _rgb("#9E9CC1"))
FAINT = _dynamic("pbkFaint", _rgb("#B6B4C8"), _rgb("#5F5D85"))
TRACK = _dynamic("pbkTrack", _rgb("#17162B", 0.05), _rgb("#FFFFFF", 0.06))
HOVER = _dynamic("pbkHover", _rgb("#17162B", 0.035), _rgb("#FFFFFF", 0.05))
ROW_SELECTED = _dynamic("pbkRowSelected", _rgb("#5B4EE8", 0.08), _rgb("#8F87FF", 0.14))
BAR = _dynamic("pbkBar", _rgb("#1F1D3A"), _rgb("#EFEEFE"))  # floating selection bar
BAR_INK = _dynamic("pbkBarInk", _rgb("#EFEEFE"), _rgb("#17162B"))

# -- Shape ------------------------------------------------------------------------------
RADIUS_TILE = 10.0
RADIUS_CARD = 9.0
RADIUS_ICON_TILE = 12.0
RADIUS_CONTROL = 8.0
HAIRLINE_WIDTH = 1.0
SELECTED_RING_WIDTH = 1.5
FOCUS_RING_WIDTH = 2.0

# -- Motion -----------------------------------------------------------------------------
HOVER_FADE = 0.12  # seconds
TOOLTIP_DELAY_MS = 1000


def cg(color, appearance=None):
    """Resolve a dynamic colour to a CGColor for layers, under ``appearance``."""
    resolved = []

    def resolve():
        resolved.append(color.CGColor())

    (appearance or AK.NSApp.effectiveAppearance()).performAsCurrentDrawingAppearance_(resolve)
    return resolved[0]


def rounded(rect, radius):
    return AK.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(rect, radius, radius)


def stroke_inside(rect, radius, color, width):
    """Stroke fully inside ``rect`` so 1 px hairlines stay crisp."""
    inset = AK.NSInsetRect(rect, width / 2, width / 2)
    path = rounded(inset, max(0.0, radius - width / 2))
    path.setLineWidth_(width)
    color.setStroke()
    path.stroke()


def draw_focus_ring(rect, radius):
    """Keyboard focus: a thin ring on the control's own edge (never a glow)."""
    stroke_inside(rect, radius, FOCUS_RING, FOCUS_RING_WIDTH)
