# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Kaschief

"""Small custom controls drawn from the design tokens (macos_theme).

Shared rule: focus is shown only for keyboard navigation. Controls refuse
first-responder status during mouse events, so clicking never paints a ring,
while Tab still reaches them and draws a thin token-coloured ring.
"""

from __future__ import annotations

from math import ceil

import AppKit as AK
import Foundation as FN
import objc

from fs_pdf_compressor import macos_theme as theme

_MOUSE_EVENTS = {
    AK.NSEventTypeLeftMouseDown,
    AK.NSEventTypeLeftMouseUp,
    AK.NSEventTypeRightMouseDown,
    AK.NSEventTypeOtherMouseDown,
}


def bring_app_forward() -> None:
    """Activate the app for a user action — but never during automated checks.

    PDFS_BY_KASH_BACKGROUND=1 (set by the UI test harnesses) keeps every window
    behind whatever the person is working in, so test runs never steal focus.
    """
    import os

    if os.environ.get("PDFS_BY_KASH_BACKGROUND") != "1":
        AK.NSApp.activateIgnoringOtherApps_(True)


def keyboard_focus_allowed() -> bool:
    event = AK.NSApp.currentEvent()
    return event is None or event.type() not in _MOUSE_EVENTS


def is_focused(view) -> bool:
    window = view.window()
    return window is not None and window.isKeyWindow() and window.firstResponder() is view


def draw_text(value, rect, font, color, alignment=AK.NSTextAlignmentCenter):
    style = AK.NSMutableParagraphStyle.alloc().init()
    style.setAlignment_(alignment)
    style.setLineBreakMode_(AK.NSLineBreakByTruncatingTail)
    attributes = {
        AK.NSFontAttributeName: font,
        AK.NSForegroundColorAttributeName: color,
        AK.NSParagraphStyleAttributeName: style,
    }
    string = FN.NSString.stringWithString_(value)
    height = string.sizeWithAttributes_(attributes).height
    string.drawInRect_withAttributes_(
        AK.NSMakeRect(rect.origin.x, rect.origin.y + (rect.size.height - height) / 2, rect.size.width, height),
        attributes,
    )


class PrimaryButton(AK.NSButton):
    """The indigo Compress button from the mockups (fixed width set by layout)."""

    def initWithTitle_target_action_(self, title, target, action):
        self = objc.super(PrimaryButton, self).initWithFrame_(AK.NSZeroRect)
        if self is None:
            return None
        self.setTitle_(title)
        self.setTarget_(target)
        self.setAction_(action)
        self.setBordered_(False)
        self.setFocusRingType_(AK.NSFocusRingTypeNone)
        self.hovered = False
        self.addTrackingArea_(
            AK.NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
                AK.NSZeroRect,
                AK.NSTrackingMouseEnteredAndExited | AK.NSTrackingActiveInActiveApp | AK.NSTrackingInVisibleRect,
                self,
                None,
            )
        )
        return self

    def mouseEntered_(self, event):
        self.hovered = True
        self.setNeedsDisplay_(True)

    def mouseExited_(self, event):
        self.hovered = False
        self.setNeedsDisplay_(True)

    def setEnabled_(self, value):
        objc.super(PrimaryButton, self).setEnabled_(value)
        self.setNeedsDisplay_(True)

    def acceptsFirstResponder(self):
        return keyboard_focus_allowed()

    def becomeFirstResponder(self):
        self.setNeedsDisplay_(True)
        return True

    def resignFirstResponder(self):
        self.setNeedsDisplay_(True)
        return True

    def drawRect_(self, rect):
        bounds = self.bounds()
        enabled = self.isEnabled()
        pressed = self.isHighlighted()
        fill = theme.ACCENT if enabled else theme.ACCENT.colorWithAlphaComponent_(0.32)
        theme.rounded(bounds, theme.RADIUS_CONTROL).addClip()
        fill.setFill()
        AK.NSRectFill(bounds)
        if pressed:
            AK.NSColor.blackColor().colorWithAlphaComponent_(0.14).setFill()
            AK.NSRectFillUsingOperation(bounds, AK.NSCompositingOperationSourceOver)
        elif enabled and self.hovered:
            AK.NSColor.whiteColor().colorWithAlphaComponent_(0.10).setFill()
            AK.NSRectFillUsingOperation(bounds, AK.NSCompositingOperationSourceOver)
        draw_text(
            self.title(),
            bounds,
            AK.NSFont.systemFontOfSize_weight_(13.0, AK.NSFontWeightSemibold),
            theme.ACCENT_INK if enabled else theme.ACCENT_INK.colorWithAlphaComponent_(0.85),
        )
        if is_focused(self):
            theme.draw_focus_ring(bounds, theme.RADIUS_CONTROL)


class ChipControl(AK.NSView):
    """Segmented choice as a soft track with a raised chip (Theme, Quality…)."""

    HEIGHT = 26.0

    def initWithLabels_onChange_(self, labels, on_change):
        self = objc.super(ChipControl, self).initWithFrame_(AK.NSZeroRect)
        if self is None:
            return None
        self.labels = list(labels)
        self.selected = 0
        self.on_change = on_change
        self.setAccessibilityElement_(True)
        self.setAccessibilityRole_(AK.NSAccessibilityRadioGroupRole)
        return self

    def isFlipped(self):
        return True

    def intrinsicContentSize(self):
        font = AK.NSFont.systemFontOfSize_weight_(12.0, AK.NSFontWeightSemibold)
        widest = max(
            FN.NSString.stringWithString_(label).sizeWithAttributes_({AK.NSFontAttributeName: font}).width
            for label in self.labels
        )
        return AK.NSMakeSize(6 + len(self.labels) * (widest + 26), self.HEIGHT)

    @objc.python_method
    def select(self, index, notify=False):
        index = max(0, min(len(self.labels) - 1, index))
        changed = index != self.selected
        self.selected = index
        self.setAccessibilityValue_(self.labels[index])
        self.setNeedsDisplay_(True)
        if changed and notify:
            self.on_change(index)

    @objc.python_method
    def _segment_rect(self, index):
        width = (self.bounds().size.width - 6) / len(self.labels)
        return AK.NSMakeRect(3 + index * width, 3, width, self.bounds().size.height - 6)

    def acceptsFirstResponder(self):
        return keyboard_focus_allowed()

    def becomeFirstResponder(self):
        self.setNeedsDisplay_(True)
        return True

    def resignFirstResponder(self):
        self.setNeedsDisplay_(True)
        return True

    def mouseDown_(self, event):
        point = self.convertPoint_fromView_(event.locationInWindow(), None)
        for index in range(len(self.labels)):
            if AK.NSPointInRect(point, self._segment_rect(index)):
                self.select(index, notify=True)
                return

    def keyDown_(self, event):
        key = event.charactersIgnoringModifiers() or ""
        if key == "":
            self.select(self.selected - 1, notify=True)
        elif key == "":
            self.select(self.selected + 1, notify=True)
        else:
            objc.super(ChipControl, self).keyDown_(event)

    def drawRect_(self, rect):
        bounds = self.bounds()
        theme.TRACK.setFill()
        theme.rounded(bounds, theme.RADIUS_CARD).fill()
        chip = self._segment_rect(self.selected)
        shadow = AK.NSShadow.alloc().init()
        shadow.setShadowColor_(AK.NSColor.blackColor().colorWithAlphaComponent_(0.10))
        shadow.setShadowOffset_(AK.NSMakeSize(0, -1))
        shadow.setShadowBlurRadius_(2)
        AK.NSGraphicsContext.saveGraphicsState()
        shadow.set()
        theme.CONTROL.setFill()
        theme.rounded(chip, 7).fill()
        AK.NSGraphicsContext.restoreGraphicsState()
        theme.stroke_inside(chip, 7, theme.CONTROL_RING, theme.HAIRLINE_WIDTH)
        for index, label in enumerate(self.labels):
            chosen = index == self.selected
            draw_text(
                label,
                self._segment_rect(index),
                AK.NSFont.systemFontOfSize_weight_(
                    12.0, AK.NSFontWeightSemibold if chosen else AK.NSFontWeightRegular
                ),
                theme.INK if chosen else theme.INK_2,
            )
        if is_focused(self):
            theme.draw_focus_ring(bounds, theme.RADIUS_CARD)


class QuietButton(AK.NSButton):
    """One button family with consistent states across the app.

    Styles:
      "secondary" — control surface + hairline (Clear List)
      "bar"       — on the dark selection bar: transparent, soft light hover
      "icon"      — row icons: transparent, round hover chip
    States: hover (soft overlay), pressed (stronger), disabled (40 %),
    keyboard focus (thin ring). No animation beyond the system's own redraw.
    """

    def initWithTitle_symbol_style_target_action_(self, title, symbol, style, target, action):
        self = objc.super(QuietButton, self).initWithFrame_(AK.NSZeroRect)
        if self is None:
            return None
        self.label = title or ""
        self.style = style
        self.hovered = False
        self.symbol_image = None
        if symbol:
            image = AK.NSImage.imageWithSystemSymbolName_accessibilityDescription_(symbol, title)
            if image is not None:
                size = 13.0 if style == "icon" else 12.0
                self.symbol_image = image.imageWithSymbolConfiguration_(
                    AK.NSImageSymbolConfiguration.configurationWithPointSize_weight_(
                        size, AK.NSFontWeightMedium
                    )
                )
        self.setTitle_(title or "")
        self.setBordered_(False)
        self.setTarget_(target)
        self.setAction_(action)
        self.setFocusRingType_(AK.NSFocusRingTypeNone)
        if title:
            self.setAccessibilityLabel_(title)
        self.addTrackingArea_(
            AK.NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
                AK.NSZeroRect,
                AK.NSTrackingMouseEnteredAndExited
                | AK.NSTrackingActiveInActiveApp
                | AK.NSTrackingInVisibleRect,
                self,
                None,
            )
        )
        return self

    @objc.python_method
    def _font(self):
        return AK.NSFont.systemFontOfSize_weight_(
            12.5 if self.style == "bar" else 13.0, AK.NSFontWeightMedium
        )

    def intrinsicContentSize(self):
        if self.style == "icon":
            return AK.NSMakeSize(24, 24)
        text = FN.NSString.stringWithString_(self.label).sizeWithAttributes_(
            {AK.NSFontAttributeName: self._font()}
        ).width
        icon = 18 if self.symbol_image is not None else 0
        return AK.NSMakeSize(ceil(text) + icon + 22, 28)

    def acceptsFirstResponder(self):
        return keyboard_focus_allowed()

    def becomeFirstResponder(self):
        self.setNeedsDisplay_(True)
        return True

    def resignFirstResponder(self):
        self.setNeedsDisplay_(True)
        return True

    def mouseEntered_(self, event):
        self.hovered = True
        self.setNeedsDisplay_(True)

    def mouseExited_(self, event):
        self.hovered = False
        self.setNeedsDisplay_(True)

    def setEnabled_(self, value):
        objc.super(QuietButton, self).setEnabled_(value)
        self.setNeedsDisplay_(True)

    def drawRect_(self, rect):
        bounds = self.bounds()
        enabled = self.isEnabled()
        pressed = self.isHighlighted() and enabled
        hovered = self.hovered and enabled
        on_bar = self.style == "bar"
        ink = theme.BAR_INK if on_bar else theme.INK if (hovered or pressed) else theme.INK_2
        radius = bounds.size.height / 2 if self.style == "icon" else theme.RADIUS_CONTROL

        if self.style == "secondary":
            theme.CONTROL.setFill()
            theme.rounded(bounds, radius).fill()
        if hovered or pressed:
            overlay = theme.BAR_INK if on_bar else theme.INK
            overlay.colorWithAlphaComponent_(
                (0.20 if pressed else 0.12) if on_bar else (0.10 if pressed else 0.05)
            ).setFill()
            theme.rounded(bounds, radius).fill()
        if self.style == "secondary":
            theme.stroke_inside(bounds, radius, theme.CONTROL_RING, theme.HAIRLINE_WIDTH)

        alpha = 1.0 if enabled else 0.4
        color = ink.colorWithAlphaComponent_(alpha)
        if self.style == "icon":
            _draw_symbol(self.symbol_image, bounds, color)
        else:
            font = self._font()
            text_w = FN.NSString.stringWithString_(self.label).sizeWithAttributes_(
                {AK.NSFontAttributeName: font}
            ).width
            icon_w = 18 if self.symbol_image is not None else 0
            x = (bounds.size.width - text_w - icon_w) / 2
            if self.symbol_image is not None:
                _draw_symbol(self.symbol_image, AK.NSMakeRect(x, 0, 14, bounds.size.height), color)
            draw_text(
                self.label,
                AK.NSMakeRect(x + icon_w, 0, text_w + 2, bounds.size.height),
                font,
                color,
                AK.NSTextAlignmentLeft,
            )
        if is_focused(self):
            theme.draw_focus_ring(bounds, radius)


def _draw_symbol(image, rect, color):
    if image is None:
        return
    size = image.size()
    tinted = AK.NSImage.imageWithSize_flipped_drawingHandler_(
        size,
        False,
        lambda dst: (
            image.drawInRect_(dst),
            color.set(),
            AK.NSRectFillUsingOperation(dst, AK.NSCompositingOperationSourceAtop),
            True,
        )[-1],
    )
    tinted.drawInRect_fromRect_operation_fraction_respectFlipped_hints_(
        AK.NSMakeRect(
            rect.origin.x + (rect.size.width - size.width) / 2,
            rect.origin.y + (rect.size.height - size.height) / 2,
            size.width,
            size.height,
        ),
        AK.NSZeroRect,
        AK.NSCompositingOperationSourceOver,
        1.0,
        True,
        None,
    )
