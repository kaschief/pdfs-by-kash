# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Kaschief

"""Small custom controls drawn from the design tokens (macos_theme).

Shared rule: focus is shown only for keyboard navigation. Controls refuse
first-responder status during mouse events, so clicking never paints a ring,
while Tab still reaches them and draws a thin token-coloured ring.
"""

from __future__ import annotations

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
        return self

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
            AK.NSColor.blackColor().colorWithAlphaComponent_(0.12).setFill()
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
