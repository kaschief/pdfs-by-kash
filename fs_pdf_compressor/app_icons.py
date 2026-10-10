# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Kaschief

"""The eight approved Pdfs by Kash app icons and how the app applies them.

What macOS allows (and what this module therefore does):

* Running app (Dock tile, ⌘-Tab switcher, About panel, alerts):
  ``NSApp.setApplicationIconImage_`` — instant, public, signing-safe.
* Kept-in-Dock tile while the app is *not* running: the bundled
  ``NSDockTilePlugIn`` (macos_dock_tile/) reads the same preference and draws
  the chosen icon. We post a distributed notification so it refreshes at once.
* Finder / Launchpad / Spotlight: deliberately unchanged (always Squish, the
  bundle icon). The only API, ``NSWorkspace setIcon:forFile:``, writes an
  ``Icon\\r`` file into the signed .app, which breaks its code signature and is
  lost on reinstall.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import AppKit as AK
import Foundation as FN

from fs_pdf_compressor.core import bundle_contents_dir

ICON_CHANGED_NOTIFICATION = "com.kaschief.pdfsbykash.AppIconChanged"


@dataclass(frozen=True)
class AppIcon:
    slug: str
    name: str
    note: str


# Order matches the approved icon studies (01–08).
APP_ICONS: tuple[AppIcon, ...] = (
    AppIcon("monoline", "Monoline", "A fine gradient p with echoes of its old size"),
    AppIcon("squish", "Squish", "A glossy p pressed flat"),
    AppIcon("sheet", "Sheet", "A Preview-white page with shrink arrows"),
    AppIcon("accordion", "Accordion", "A page folded into tightening pleats"),
    AppIcon("diamond", "Diamond", "Pressure makes diamonds"),
    AppIcon("didone", "Didone", "An editorial serif p with a red full stop"),
    AppIcon("strata", "Strata", "Colour bands pressed thinner under a bold p"),
    AppIcon("origami", "Origami", "A p folded from one strip of paper"),
)
DEFAULT_ICON = "squish"
_BY_SLUG = {icon.slug: icon for icon in APP_ICONS}


def resolve(slug: str | None) -> AppIcon:
    """Unknown or missing slugs fall back to the default (Squish)."""
    return _BY_SLUG.get(slug or "", _BY_SLUG[DEFAULT_ICON])


def icon_directory() -> Path:
    contents = bundle_contents_dir()
    if contents is not None:
        bundled = contents / "Resources" / "AppIcons"
        if bundled.is_dir():
            return bundled
    return Path(__file__).resolve().parents[1] / "assets" / "app-icons"


def icon_path(slug: str) -> Path:
    return icon_directory() / f"{resolve(slug).slug}.png"


_image_cache: dict[str, object] = {}


def icon_image(slug: str):
    slug = resolve(slug).slug
    if slug not in _image_cache:
        _image_cache[slug] = AK.NSImage.alloc().initWithContentsOfFile_(str(icon_path(slug)))
    return _image_cache[slug]


def apply_icon(slug: str) -> None:
    """Show ``slug`` in the running app's Dock tile and tell the Dock plug-in."""
    image = icon_image(slug)
    if image is not None:
        AK.NSApp.setApplicationIconImage_(image)
    FN.NSDistributedNotificationCenter.defaultCenter().postNotificationName_object_userInfo_deliverImmediately_(
        ICON_CHANGED_NOTIFICATION, None, None, True
    )
