# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Kaschief

"""The Settings window (⌘,): the app icon and the theme — nothing else.

Everything about compressing lives on the main screen. Built to
design/settings-v2 (settings-design-exploration branch): no tabs, no prose,
no tooltips, no hover reaction on the icons; selection is the soft accent ring
and tint; focus is a thin ring for keyboard navigation only.
"""

from __future__ import annotations

import os

import AppKit as AK
import objc

from fs_pdf_compressor import macos_theme as theme
from fs_pdf_compressor import preferences as prefs
from fs_pdf_compressor.app_icons import APP_ICONS, apply_icon, icon_image, resolve
from fs_pdf_compressor.macos_controls import (
    ChipControl,
    bring_app_forward,
    draw_text,
    is_focused,
    keyboard_focus_allowed,
)

WIDTH = 460.0
COLUMNS = 4
THEME_LABELS = ("System", "Light", "Dark")


def apply_theme(value: str) -> None:
    names = {"light": AK.NSAppearanceNameAqua, "dark": AK.NSAppearanceNameDarkAqua}
    AK.NSApp.setAppearance_(
        AK.NSAppearance.appearanceNamed_(names[value]) if value in names else None
    )


class IconTile(AK.NSView):
    """One selectable icon: preview + name. Static on hover by design."""

    SIZE = AK.NSMakeSize(96, 100)

    def initWithIcon_owner_(self, icon, owner):
        self = objc.super(IconTile, self).initWithFrame_(
            AK.NSMakeRect(0, 0, self.SIZE.width, self.SIZE.height)
        )
        if self is None:
            return None
        self.icon = icon
        self.owner = owner
        self.selected = False
        self.setAccessibilityElement_(True)
        self.setAccessibilityRole_(AK.NSAccessibilityRadioButtonRole)
        self.setAccessibilityLabel_(icon.name)
        return self

    def isFlipped(self):
        return True

    def intrinsicContentSize(self):
        return self.SIZE

    def acceptsFirstResponder(self):
        return keyboard_focus_allowed()

    def becomeFirstResponder(self):
        self.setNeedsDisplay_(True)
        return True

    def resignFirstResponder(self):
        self.setNeedsDisplay_(True)
        return True

    def accessibilityValue(self):
        return 1 if self.selected else 0

    def accessibilityPerformPress(self):
        self.owner.chooseIcon_(self.icon.slug)
        return True

    def mouseDown_(self, event):
        self.owner.chooseIcon_(self.icon.slug)

    def keyDown_(self, event):
        key = event.charactersIgnoringModifiers() or ""
        if key in (" ", "\r"):
            self.owner.chooseIcon_(self.icon.slug)
        elif key in ("", "", "", ""):
            self.owner.moveFocusFrom_key_(self, key)
        else:
            objc.super(IconTile, self).keyDown_(event)

    def drawRect_(self, rect):
        bounds = self.bounds()
        if self.selected:
            theme.ACCENT_SOFT.setFill()
            theme.rounded(bounds, theme.RADIUS_ICON_TILE).fill()
            theme.stroke_inside(bounds, theme.RADIUS_ICON_TILE, theme.ACCENT_RING, theme.SELECTED_RING_WIDTH)
        if is_focused(self):
            theme.draw_focus_ring(bounds, theme.RADIUS_ICON_TILE)
        image = icon_image(self.icon.slug)
        if image is not None:
            side = 60.0
            image.drawInRect_fromRect_operation_fraction_respectFlipped_hints_(
                AK.NSMakeRect((bounds.size.width - side) / 2, 10, side, side),
                AK.NSZeroRect,
                AK.NSCompositingOperationSourceOver,
                1.0,
                True,
                {AK.NSImageHintInterpolation: AK.NSImageInterpolationHigh},
            )
        draw_text(
            self.icon.name,
            AK.NSMakeRect(0, 74, bounds.size.width, 18),
            AK.NSFont.systemFontOfSize_weight_(
                11.5, AK.NSFontWeightSemibold if self.selected else AK.NSFontWeightRegular
            ),
            theme.INK if self.selected else theme.INK_2,
        )


class _Pane(AK.NSView):
    def isFlipped(self):
        return True

    def drawRect_(self, rect):
        theme.WINDOW.setFill()
        AK.NSRectFill(rect)


class SettingsWindowController(AK.NSObject):
    def init(self):
        self = objc.super(SettingsWindowController, self).init()
        if self is None:
            return None
        self.window = AK.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            AK.NSMakeRect(0, 0, WIDTH, 300),
            AK.NSWindowStyleMaskTitled | AK.NSWindowStyleMaskClosable,
            AK.NSBackingStoreBuffered,
            False,
        )
        self.window.setTitle_("Settings")
        self.window.setReleasedWhenClosed_(False)
        pane = self._build()
        self.window.setContentSize_(pane.frame().size)
        self.window.setContentView_(pane)
        self.window.center()
        self.refresh()
        return self

    @objc.python_method
    def show(self):
        self.refresh()
        if os.environ.get("PDFS_BY_KASH_BACKGROUND") == "1":
            self.window.orderBack_(None)
        else:
            self.window.makeKeyAndOrderFront_(None)
        self.window.makeFirstResponder_(None)  # no focus ring until the user Tabs
        bring_app_forward()

    @objc.python_method
    def _build(self):
        pad_x, top = 26.0, 20.0
        tile_w, tile_h = IconTile.SIZE.width, IconTile.SIZE.height
        gap = (WIDTH - 2 * pad_x - COLUMNS * tile_w) / (COLUMNS - 1)
        rows = (len(APP_ICONS) + COLUMNS - 1) // COLUMNS
        grid_top = top + 24
        grid_bottom = grid_top + rows * tile_h + (rows - 1) * 6
        divider_y = grid_bottom + 16
        theme_y = divider_y + 14
        height = theme_y + ChipControl.HEIGHT + 22

        pane = _Pane.alloc().initWithFrame_(AK.NSMakeRect(0, 0, WIDTH, height))

        title = AK.NSTextField.labelWithString_("App Icon")
        title.setFont_(AK.NSFont.systemFontOfSize_weight_(11.5, AK.NSFontWeightSemibold))
        title.setTextColor_(theme.MUTED)
        title.setFrame_(AK.NSMakeRect(pad_x + 2, top, 200, 16))
        pane.addSubview_(title)

        self.icon_tiles = []
        for index, icon in enumerate(APP_ICONS):
            row, column = divmod(index, COLUMNS)
            tile = IconTile.alloc().initWithIcon_owner_(icon, self)
            tile.setFrame_(
                AK.NSMakeRect(pad_x + column * (tile_w + gap), grid_top + row * (tile_h + 6), tile_w, tile_h)
            )
            pane.addSubview_(tile)
            self.icon_tiles.append(tile)

        divider = AK.NSBox.alloc().initWithFrame_(AK.NSMakeRect(pad_x, divider_y, WIDTH - 2 * pad_x, 1))
        divider.setBoxType_(AK.NSBoxCustom)
        divider.setBorderWidth_(0)
        divider.setFillColor_(theme.HAIRLINE)
        pane.addSubview_(divider)

        label = AK.NSTextField.labelWithString_("Theme")
        label.setFont_(AK.NSFont.systemFontOfSize_(13.0))
        label.setTextColor_(theme.INK)
        label.setFrame_(AK.NSMakeRect(pad_x + 2, theme_y + 4, 120, 18))
        pane.addSubview_(label)

        self.theme_control = ChipControl.alloc().initWithLabels_onChange_(THEME_LABELS, self._theme_changed)
        size = self.theme_control.intrinsicContentSize()
        self.theme_control.setFrame_(
            AK.NSMakeRect(WIDTH - pad_x - size.width, theme_y, size.width, ChipControl.HEIGHT)
        )
        self.theme_control.setAccessibilityLabel_("Theme")
        pane.addSubview_(self.theme_control)

        # Keyboard order: icons left→right, top→bottom, then the theme control.
        for current, following in zip(self.icon_tiles, self.icon_tiles[1:] + [self.theme_control]):
            current.setNextKeyView_(following)
        self.theme_control.setNextKeyView_(self.icon_tiles[0])
        return pane

    def chooseIcon_(self, slug):
        prefs.set_app_icon(resolve(slug).slug)
        apply_icon(slug)
        self.refresh()

    def moveFocusFrom_key_(self, tile, key):
        index = self.icon_tiles.index(tile)
        target = index + {"": -1, "": 1, "": -COLUMNS, "": COLUMNS}[key]
        if 0 <= target < len(self.icon_tiles):
            self.window.makeFirstResponder_(self.icon_tiles[target])

    @objc.python_method
    def _theme_changed(self, index):
        value = prefs.THEMES[index]
        prefs.set_theme(value)
        apply_theme(value)

    @objc.python_method
    def refresh(self):
        chosen = resolve(prefs.app_icon()).slug
        for tile in self.icon_tiles:
            tile.selected = tile.icon.slug == chosen
            tile.setNeedsDisplay_(True)
        self.theme_control.select(prefs.THEMES.index(prefs.theme()))
