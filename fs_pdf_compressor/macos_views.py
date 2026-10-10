# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Daniel Lares
# Modifications Copyright (C) 2026 Kaschief

"""AppKit views used by the main Pdfs by Kash window.

Every colour, border, radius and focus treatment comes from macos_theme, so
the window matches the approved mockups regardless of the system accent.
"""

from __future__ import annotations

import os

import AppKit as AK
import Foundation as FN
import objc
import Quartz

from fs_pdf_compressor import macos_theme as theme
from fs_pdf_compressor.compression_queue import (
    Compressed,
    Compressing,
    Failed,
    Queued,
    Unchanged,
)
from fs_pdf_compressor.core import display_folder, format_file_size
from fs_pdf_compressor.macos_controls import QuietButton, is_focused, keyboard_focus_allowed


class DropCanvas(AK.NSView):
    """Window background: accepts dropped PDFs and draws the empty state."""

    def initWithFrame_controller_(self, frame, controller):
        self = objc.super(DropCanvas, self).initWithFrame_(frame)
        if self is None:
            return None
        self.controller = controller
        self.drag_active = False
        self.registerForDraggedTypes_([AK.NSPasteboardTypeFileURL])
        return self

    def drawRect_(self, dirty_rect):
        bounds = self.bounds()
        theme.WINDOW.setFill()
        AK.NSRectFill(bounds)

        bottom = self.controller.bottom_chrome_height()
        if self.controller.showing_results:
            if self.drag_active:
                list_area = AK.NSMakeRect(0, bottom, bounds.size.width, bounds.size.height - bottom)
                theme.stroke_inside(AK.NSInsetRect(list_area, 6, 6), theme.RADIUS_TILE, theme.ACCENT_RING, 2.0)
            return

        available_height = max(0.0, bounds.size.height - bottom)
        side = min(150.0, bounds.size.width * 0.28, available_height * 0.5)
        target = AK.NSMakeRect(
            (bounds.size.width - side) / 2,
            bottom + (available_height - side) / 2 + 14,
            side,
            side,
        )
        border = theme.rounded(target, 18)
        border.setLineWidth_(1.5)
        border.setLineDash_count_phase_([6.0, 6.0], 2, 0.0)
        (theme.ACCENT_RING if self.drag_active else theme.FAINT).setStroke()
        border.stroke()

        (theme.ACCENT if self.drag_active else theme.FAINT).setStroke()
        cx, cy = AK.NSMidX(target), AK.NSMidY(target)
        arrow = AK.NSBezierPath.bezierPath()
        arrow.setLineWidth_(2.5)
        arrow.setLineCapStyle_(AK.NSLineCapStyleRound)
        arrow.setLineJoinStyle_(AK.NSLineJoinStyleRound)
        arrow.moveToPoint_(AK.NSMakePoint(cx, cy + 26))
        arrow.lineToPoint_(AK.NSMakePoint(cx, cy - 17))
        arrow.moveToPoint_(AK.NSMakePoint(cx - 15, cy - 2))
        arrow.lineToPoint_(AK.NSMakePoint(cx, cy - 19))
        arrow.lineToPoint_(AK.NSMakePoint(cx + 15, cy - 2))
        arrow.stroke()

        _text(
            "Drop PDFs or folders here, or click + to choose files",
            AK.NSMakeRect(0, target.origin.y - 34, bounds.size.width, 18),
            AK.NSFont.systemFontOfSize_(12.5),
            theme.MUTED,
            AK.NSTextAlignmentCenter,
        )

    def draggingEntered_(self, sender):
        self.drag_active = True
        self.setNeedsDisplay_(True)
        return AK.NSDragOperationCopy

    def draggingExited_(self, sender):
        self.drag_active = False
        self.setNeedsDisplay_(True)

    def prepareForDragOperation_(self, sender):
        return True

    def performDragOperation_(self, sender):
        self.drag_active = False
        self.setNeedsDisplay_(True)
        pasteboard = sender.draggingPasteboard()
        urls = pasteboard.readObjectsForClasses_options_(
            [FN.NSURL], {AK.NSPasteboardURLReadingFileURLsOnlyKey: True}
        )
        self.controller.handle_drop_urls(urls or [])
        return bool(urls)


class ChromeView(AK.NSView):
    """The lavender-tinted bottom bar with a single hairline on top.

    While compressing, the hairline doubles as the progress bar (an accent line
    growing left to right), so progress takes no space and nothing reflows.
    """

    progress = None  # None when idle, else 0.0–1.0

    @objc.python_method
    def set_progress(self, value):
        self.progress = value
        self.setNeedsDisplay_(True)

    def drawRect_(self, rect):
        bounds = self.bounds()
        theme.CHROME.setFill()
        AK.NSRectFill(bounds)
        theme.HAIRLINE.setFill()
        AK.NSRectFill(AK.NSMakeRect(0, bounds.size.height - 1, bounds.size.width, 1))
        if self.progress is not None:
            theme.ACCENT.setFill()
            width = bounds.size.width * max(0.02, min(1.0, self.progress))
            AK.NSRectFill(AK.NSMakeRect(0, bounds.size.height - 2, width, 2))


class IconButton(AK.NSButton):
    """Square control-coloured button with a hairline (the + button)."""

    def initWithSymbol_label_target_action_(self, symbol, label, target, action):
        self = objc.super(IconButton, self).initWithFrame_(AK.NSZeroRect)
        if self is None:
            return None
        self.symbol_image = _symbol(symbol, label, 13, AK.NSFontWeightMedium)
        self.setTitle_("")
        self.setBordered_(False)
        self.setTarget_(target)
        self.setAction_(action)
        self.setFocusRingType_(AK.NSFocusRingTypeNone)
        self.setAccessibilityLabel_(label)
        self.hovered = False
        _hover_tracking(self)
        return self

    def mouseEntered_(self, event):
        self.hovered = True
        self.setNeedsDisplay_(True)

    def mouseExited_(self, event):
        self.hovered = False
        self.setNeedsDisplay_(True)

    def acceptsFirstResponder(self):
        return keyboard_focus_allowed()

    def drawRect_(self, rect):
        bounds = self.bounds()
        theme.CONTROL.setFill()
        theme.rounded(bounds, theme.RADIUS_CONTROL).fill()
        if self.isHighlighted() or self.hovered:
            theme.INK.colorWithAlphaComponent_(0.10 if self.isHighlighted() else 0.05).setFill()
            theme.rounded(bounds, theme.RADIUS_CONTROL).fill()
        theme.stroke_inside(bounds, theme.RADIUS_CONTROL, theme.CONTROL_RING, theme.HAIRLINE_WIDTH)
        _draw_tinted_symbol(self.symbol_image, bounds, theme.INK_2)
        if is_focused(self):
            theme.draw_focus_ring(bounds, theme.RADIUS_CONTROL)


# -- Shared drawing helpers ----------------------------------------------------------


def _symbol(name, description, size=13.0, weight=None):
    image = AK.NSImage.imageWithSystemSymbolName_accessibilityDescription_(name, description)
    if image is None:
        return None
    config = AK.NSImageSymbolConfiguration.configurationWithPointSize_weight_(
        size, weight if weight is not None else AK.NSFontWeightRegular
    )
    return image.imageWithSymbolConfiguration_(config)


def _draw_tinted_symbol(image, rect, color):
    """Draw a template SF Symbol in ``color`` (resolved for the current appearance)."""
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
    target = AK.NSMakeRect(
        rect.origin.x + (rect.size.width - size.width) / 2,
        rect.origin.y + (rect.size.height - size.height) / 2,
        size.width,
        size.height,
    )
    tinted.drawInRect_fromRect_operation_fraction_respectFlipped_hints_(
        target, AK.NSZeroRect, AK.NSCompositingOperationSourceOver, 1.0, True, None
    )


def _text(value, rect, font, color, alignment=AK.NSTextAlignmentLeft):
    style = AK.NSMutableParagraphStyle.alloc().init()
    style.setAlignment_(alignment)
    style.setLineBreakMode_(AK.NSLineBreakByTruncatingMiddle)
    FN.NSString.stringWithString_(value).drawInRect_withAttributes_(
        rect,
        {
            AK.NSFontAttributeName: font,
            AK.NSForegroundColorAttributeName: color,
            AK.NSParagraphStyleAttributeName: style,
        },
    )


def _hover_tracking(view):
    view.addTrackingArea_(
        AK.NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
            AK.NSZeroRect,
            AK.NSTrackingMouseEnteredAndExited
            | AK.NSTrackingActiveInKeyWindow
            | AK.NSTrackingInVisibleRect,
            view,
            None,
        )
    )


# -- Setting tiles (direction A) -----------------------------------------------------


class SettingTile(AK.NSView):
    """Icon + caption + value-in-words; opens an option panel on click.

    Fixed width (set by the window), so a value change never reflows the row.
    ``mode``: "normal", "warn" (Replace) or "off" (not used right now).
    """

    def initWithKind_caption_symbol_owner_(self, kind, caption, symbol, owner):
        self = objc.super(SettingTile, self).initWithFrame_(AK.NSZeroRect)
        if self is None:
            return None
        self.kind = kind
        self.target_controller = owner
        self.caption = caption
        self.symbol = _symbol(symbol, caption, 13.5)
        self.value = ""
        self.mode = "normal"
        self.hovered = False
        self.open = False
        self.setAccessibilityElement_(True)
        self.setAccessibilityRole_(AK.NSAccessibilityPopUpButtonRole)
        _hover_tracking(self)
        return self

    def isFlipped(self):
        return True

    @objc.python_method
    def update(self, value, mode="normal", tooltip=None, symbol=None):
        self.value = value
        self.mode = mode
        if symbol is not None:
            self.symbol = _symbol(symbol, self.caption, 13.5)
        self.setToolTip_(tooltip)
        self.setAccessibilityLabel_(f"{self.caption}: {value}")
        self.setAccessibilityEnabled_(mode != "off")
        self.setNeedsDisplay_(True)

    def acceptsFirstResponder(self):
        return self.mode != "off" and keyboard_focus_allowed()

    def becomeFirstResponder(self):
        self.setNeedsDisplay_(True)
        return True

    def resignFirstResponder(self):
        self.setNeedsDisplay_(True)
        return True

    def accessibilityPerformPress(self):
        self.target_controller.open_setting(self)
        return True

    def keyDown_(self, event):
        if (event.charactersIgnoringModifiers() or "") in (" ", "\r", ""):
            self.target_controller.open_setting(self)
        else:
            objc.super(SettingTile, self).keyDown_(event)

    def mouseEntered_(self, event):
        self.hovered = True
        self.setNeedsDisplay_(True)

    def mouseExited_(self, event):
        self.hovered = False
        self.setNeedsDisplay_(True)

    def mouseDown_(self, event):
        if self.mode != "off":
            self.target_controller.open_setting(self)

    def drawRect_(self, rect):
        bounds = self.bounds()
        off = self.mode == "off"
        if not off:
            theme.CONTROL.setFill()
            theme.rounded(bounds, theme.RADIUS_TILE).fill()
        active = (self.hovered or self.open) and not off
        theme.stroke_inside(
            bounds,
            theme.RADIUS_TILE,
            theme.ACCENT_RING if active else theme.CONTROL_RING,
            theme.HAIRLINE_WIDTH,
        )

        height = bounds.size.height
        chip = AK.NSMakeRect(10, (height - 26) / 2, 26, 26)
        if off:
            chip_fill, glyph = theme.TRACK, theme.FAINT
        elif self.mode == "warn":
            chip_fill, glyph = theme.WARN_SOFT, theme.WARN
        else:
            chip_fill, glyph = theme.ACCENT_SOFT, theme.ACCENT
        chip_fill.setFill()
        theme.rounded(chip, 7).fill()
        _draw_tinted_symbol(self.symbol, chip, glyph)

        text_x = 46
        chevron_space = 0 if off else 22
        text_width = max(10, bounds.size.width - text_x - chevron_space - 6)
        _text(
            self.caption,
            AK.NSMakeRect(text_x, height / 2 - 16, text_width, 14),
            AK.NSFont.systemFontOfSize_(10.5),
            theme.FAINT if off else theme.MUTED,
        )
        _text(
            self.value,
            AK.NSMakeRect(text_x, height / 2 - 2, text_width, 17),
            AK.NSFont.systemFontOfSize_weight_(12.5, AK.NSFontWeightMedium),
            theme.FAINT if off else theme.WARN if self.mode == "warn" else theme.INK,
        )
        if not off:
            chevron = _symbol(
                "chevron.up" if self.open else "chevron.down", "", 9.5, AK.NSFontWeightSemibold
            )
            _draw_tinted_symbol(
                chevron,
                AK.NSMakeRect(bounds.size.width - 24, 0, 14, height),
                theme.ACCENT if self.open else theme.MUTED,
            )
        if is_focused(self):
            theme.draw_focus_ring(bounds, theme.RADIUS_TILE)


class OptionCard(AK.NSView):
    """A choice inside an option panel: icon chip, title, at most one short line."""

    WIDTH = 288.0

    def initWithTitle_detail_symbol_selected_warn_action_(self, title, detail, symbol, selected, warn, action):
        self = objc.super(OptionCard, self).initWithFrame_(AK.NSMakeRect(0, 0, self.WIDTH, 10))
        if self is None:
            return None
        self.title = title
        self.detail = detail or ""
        self.symbol = _symbol(symbol, title, 12.5) if symbol else None
        self.selected = selected
        self.warn = warn
        self.action = action
        self.hovered = False
        self.setAccessibilityElement_(True)
        self.setAccessibilityRole_(AK.NSAccessibilityRadioButtonRole)
        self.setAccessibilityLabel_(title)
        if self.detail:
            self.setAccessibilityHelp_(self.detail)
        _hover_tracking(self)
        self.setFrameSize_(AK.NSMakeSize(self.WIDTH, 52 if self.detail else 40))
        return self

    def isFlipped(self):
        return True

    def accessibilityValue(self):
        return 1 if self.selected else 0

    def accessibilityPerformPress(self):
        self.action()
        return True

    def acceptsFirstResponder(self):
        return keyboard_focus_allowed()

    def becomeFirstResponder(self):
        self.setNeedsDisplay_(True)
        return True

    def resignFirstResponder(self):
        self.setNeedsDisplay_(True)
        return True

    def keyDown_(self, event):
        key = event.charactersIgnoringModifiers() or ""
        if key in (" ", "\r"):
            self.action()
        elif key == "":
            self.window().selectNextKeyView_(self)
        elif key == "":
            self.window().selectPreviousKeyView_(self)
        else:
            objc.super(OptionCard, self).keyDown_(event)

    def mouseEntered_(self, event):
        self.hovered = True
        self.setNeedsDisplay_(True)

    def mouseExited_(self, event):
        self.hovered = False
        self.setNeedsDisplay_(True)

    def mouseDown_(self, event):
        pass

    def mouseUp_(self, event):
        point = self.convertPoint_fromView_(event.locationInWindow(), None)
        if AK.NSPointInRect(point, self.bounds()):
            self.action()

    def drawRect_(self, rect):
        bounds = self.bounds()
        soft, ring, solid = (
            (theme.WARN_SOFT, theme.WARN_RING, theme.WARN)
            if self.warn
            else (theme.ACCENT_SOFT, theme.ACCENT_RING, theme.ACCENT)
        )
        if self.selected:
            soft.setFill()
            theme.rounded(bounds, theme.RADIUS_CARD).fill()
            theme.stroke_inside(bounds, theme.RADIUS_CARD, ring, theme.SELECTED_RING_WIDTH)
        elif self.hovered:
            theme.HOVER.setFill()
            theme.rounded(bounds, theme.RADIUS_CARD).fill()

        chip = AK.NSMakeRect(10, (bounds.size.height - 26) / 2, 26, 26)
        if self.symbol is not None:
            (solid if self.selected else theme.TRACK).setFill()
            theme.rounded(chip, 7).fill()
            _draw_tinted_symbol(
                self.symbol, chip, AK.NSColor.whiteColor() if self.selected else theme.INK_2
            )
        title_y = 9 if self.detail else (bounds.size.height - 17) / 2
        _text(
            self.title,
            AK.NSMakeRect(46, title_y, bounds.size.width - 56, 17),
            AK.NSFont.systemFontOfSize_weight_(13.0, AK.NSFontWeightSemibold),
            theme.INK,
        )
        if self.detail:
            _text(
                self.detail,
                AK.NSMakeRect(46, 27, bounds.size.width - 56, 16),
                AK.NSFont.systemFontOfSize_(11.5),
                theme.MUTED,
            )
        if is_focused(self):
            theme.draw_focus_ring(bounds, theme.RADIUS_CARD)


class _OptionCardView(AK.NSView):
    """The opaque floating card: token surface, hairline, rounded corners."""

    def isFlipped(self):
        return True

    def drawRect_(self, rect):
        bounds = self.bounds()
        theme.FLOAT.setFill()
        theme.rounded(bounds, 12).fill()
        theme.stroke_inside(bounds, 12, theme.CONTROL_RING, theme.HAIRLINE_WIDTH)


class OptionPanel(AK.NSPanel):
    """An opaque option card anchored above a setting tile.

    Replaces NSPopover, whose see-through material picked up the desktop behind
    the window and made the selected option unreadable. Closes on a click
    elsewhere, Esc, or picking an option.
    """

    def initWithCards_onClose_(self, cards, on_close):
        padding, spacing = 6.0, 4.0
        height = padding * 2 + sum(c.frame().size.height for c in cards) + spacing * (len(cards) - 1)
        width = OptionCard.WIDTH + padding * 2
        self = objc.super(OptionPanel, self).initWithContentRect_styleMask_backing_defer_(
            AK.NSMakeRect(0, 0, width, height),
            AK.NSWindowStyleMaskBorderless,
            AK.NSBackingStoreBuffered,
            False,
        )
        if self is None:
            return None
        self.on_close = on_close
        self.closing = False
        self.setOpaque_(False)
        self.setBackgroundColor_(AK.NSColor.clearColor())
        self.setHasShadow_(True)
        self.setReleasedWhenClosed_(False)
        content = _OptionCardView.alloc().initWithFrame_(AK.NSMakeRect(0, 0, width, height))
        content.setWantsLayer_(True)
        content.layer().setCornerRadius_(12)
        content.layer().setMasksToBounds_(True)
        y = padding
        for card in cards:
            card.setFrameOrigin_(AK.NSMakePoint(padding, y))
            content.addSubview_(card)
            y += card.frame().size.height + spacing
        for current, following in zip(cards, cards[1:] + cards[:1]):
            current.setNextKeyView_(following)
        self.setContentView_(content)
        self.cards = cards
        return self

    def canBecomeKeyWindow(self):
        return True

    @objc.python_method
    def show_above(self, tile):
        parent = tile.window()
        tile_in_window = tile.convertRect_toView_(tile.bounds(), None)
        tile_on_screen = parent.convertRectToScreen_(tile_in_window)
        frame = self.frame()
        origin = AK.NSMakePoint(
            tile_on_screen.origin.x,
            tile_on_screen.origin.y + tile_on_screen.size.height + 6,
        )
        self.setFrameOrigin_(origin)
        self.setAppearance_(parent.effectiveAppearance())
        parent.addChildWindow_ordered_(self, AK.NSWindowAbove)
        self.makeKeyAndOrderFront_(None)
        return frame

    def resignKeyWindow(self):
        objc.super(OptionPanel, self).resignKeyWindow()
        self.dismiss()

    def cancelOperation_(self, sender):
        self.dismiss()

    @objc.python_method
    def dismiss(self):
        if self.closing:
            return
        self.closing = True
        parent = self.parentWindow()
        if parent is not None:
            parent.removeChildWindow_(self)
            parent.makeKeyWindow()
        self.orderOut_(None)
        self.on_close()


# -- Floating selection bar ------------------------------------------------------------


class SelectionBar(AK.NSView):
    """“2 selected · Show in Finder · Remove · Done”. Overlays the list, never pushes it."""

    def initWithOwner_(self, owner):
        self = objc.super(SelectionBar, self).initWithFrame_(AK.NSMakeRect(0, 0, 360, 36))
        if self is None:
            return None
        self.owner = owner
        self.setWantsLayer_(True)
        self.layer().setCornerRadius_(11)
        self.layer().setShadowOpacity_(0.28)
        self.layer().setShadowRadius_(14)
        self.layer().setShadowOffset_(AK.NSMakeSize(0, -6))
        self.label = AK.NSTextField.labelWithString_("")
        self.label.setFont_(AK.NSFont.systemFontOfSize_weight_(12.5, AK.NSFontWeightSemibold))
        self.reveal_button = QuietButton.alloc().initWithTitle_symbol_style_target_action_(
            "Show in Finder", "finder", "bar", owner, "revealSelection:"
        )
        # "from List" makes it plain that nothing is deleted from disk.
        self.remove_button = QuietButton.alloc().initWithTitle_symbol_style_target_action_(
            "Remove from List", "minus.circle", "bar", owner, "removeSelection:"
        )
        self.deselect_button = QuietButton.alloc().initWithTitle_symbol_style_target_action_(
            None, "xmark", "bar", owner, "clearSelection:"
        )
        self.deselect_button.setToolTip_("Deselect (Esc)")
        self.deselect_button.setAccessibilityLabel_("Deselect")
        self.deselect_button.widthAnchor().constraintEqualToConstant_(28).setActive_(True)
        self.buttons = [self.reveal_button, self.remove_button, self.deselect_button]
        for button in self.buttons:
            button.heightAnchor().constraintEqualToConstant_(28).setActive_(True)
        stack = AK.NSStackView.stackViewWithViews_([self.label] + self.buttons)
        stack.setSpacing_(2)
        stack.setCustomSpacing_afterView_(12, self.label)
        stack.setCustomSpacing_afterView_(8, self.remove_button)
        stack.setEdgeInsets_(AK.NSEdgeInsetsMake(0, 16, 0, 4))
        stack.setTranslatesAutoresizingMaskIntoConstraints_(False)
        self.addSubview_(stack)
        AK.NSLayoutConstraint.activateConstraints_(
            [
                stack.leadingAnchor().constraintEqualToAnchor_(self.leadingAnchor()),
                stack.trailingAnchor().constraintEqualToAnchor_(self.trailingAnchor()),
                stack.centerYAnchor().constraintEqualToAnchor_(self.centerYAnchor()),
            ]
        )
        self.setAccessibilityRole_(AK.NSAccessibilityToolbarRole)
        self.setAccessibilityLabel_("Selection actions")
        return self

    def wantsUpdateLayer(self):
        return True

    def updateLayer(self):
        appearance = self.effectiveAppearance()
        self.layer().setBackgroundColor_(theme.cg(theme.BAR, appearance))
        self.label.setTextColor_(theme.BAR_INK)
        for button in self.buttons:
            button.setNeedsDisplay_(True)

    @objc.python_method
    def update(self, count, can_reveal, can_remove):
        self.label.setStringValue_(f"{count} selected")
        self.reveal_button.setEnabled_(can_reveal)
        self.remove_button.setEnabled_(can_remove)
        self.setNeedsDisplay_(True)
        self.setFrameSize_(AK.NSMakeSize(self.fittingSize().width, 36))
        self.setNeedsLayout_(True)


# -- Queue table ---------------------------------------------------------------

COLUMN_FILE = "file"
COLUMN_ORIGINAL = "original"
COLUMN_COMPRESSED = "compressed"
COLUMN_REDUCTION = "reduction"
COLUMN_ACTIONS = "actions"

ROW_HEIGHT = 44.0


class QueueHeaderView(AK.NSTableHeaderView):
    """Column titles in the mockup's style: muted 11.5 pt on the window colour."""

    def drawRect_(self, rect):
        bounds = self.bounds()
        theme.WINDOW.setFill()
        AK.NSRectFill(bounds)
        theme.HAIRLINE.setFill()
        AK.NSRectFill(AK.NSMakeRect(0, bounds.size.height - 1, bounds.size.width, 1))
        table = self.tableView()
        if table is None:
            return
        for index, column in enumerate(table.tableColumns()):
            title = column.title()
            if not title:
                continue
            frame = self.headerRectOfColumn_(index)
            right = column.headerCell().alignment() == AK.NSTextAlignmentRight
            inset = 4 if right else 42 if index == 0 else 8  # 42: aligns with file names
            _text(
                title,
                AK.NSMakeRect(frame.origin.x + (0 if right else inset), (bounds.size.height - 15) / 2,
                              frame.size.width - inset, 15),
                AK.NSFont.systemFontOfSize_(11.5),
                theme.MUTED,
                AK.NSTextAlignmentRight if right else AK.NSTextAlignmentLeft,
            )

    def isFlipped(self):
        return True


class QueueRowView(AK.NSTableRowView):
    """Soft rounded hover/selection pill that fades (no system blue bar)."""

    def initWithFrame_(self, frame):
        self = objc.super(QueueRowView, self).initWithFrame_(frame)
        if self is None:
            return None
        self._hovered = False
        self.setWantsLayer_(True)
        self.pill = Quartz.CALayer.layer()
        self.pill.setCornerRadius_(8)
        self.layer().addSublayer_(self.pill)
        return self

    @objc.python_method
    def set_hovered(self, value, animated=True):
        self._hovered = value
        self._update_pill(animated)

    def setSelected_(self, value):
        objc.super(QueueRowView, self).setSelected_(value)
        self._update_pill(True)

    @objc.python_method
    def _update_pill(self, animated):
        if self.isSelected():
            color = theme.ROW_SELECTED
        elif self._hovered:
            color = theme.HOVER
        else:
            color = AK.NSColor.clearColor()
        Quartz.CATransaction.begin()
        Quartz.CATransaction.setAnimationDuration_(theme.HOVER_FADE if animated else 0)
        self.pill.setBackgroundColor_(theme.cg(color, self.effectiveAppearance()))
        Quartz.CATransaction.commit()

    def layout(self):
        objc.super(QueueRowView, self).layout()
        Quartz.CATransaction.begin()
        Quartz.CATransaction.setDisableActions_(True)
        self.pill.setFrame_(AK.NSInsetRect(self.bounds(), 6, 1))
        Quartz.CATransaction.commit()

    def viewDidChangeEffectiveAppearance(self):
        self._update_pill(False)

    def drawBackgroundInRect_(self, rect):
        pass

    def drawSelectionInRect_(self, rect):
        pass

    def isEmphasized(self):
        return False

    def interiorBackgroundStyle(self):
        return AK.NSBackgroundStyleNormal


class CheckCircle(AK.NSView):
    """Additive selection: click toggles this row without ⌘/⇧."""

    def initWithRow_checked_owner_(self, row, checked, owner):
        self = objc.super(CheckCircle, self).initWithFrame_(AK.NSMakeRect(0, 0, 18, 18))
        if self is None:
            return None
        self.row = row
        self.checked = checked
        self.owner = owner
        self.setAccessibilityElement_(True)
        self.setAccessibilityRole_(AK.NSAccessibilityCheckBoxRole)
        self.setAccessibilityLabel_("Select")
        return self

    def accessibilityValue(self):
        return 1 if self.checked else 0

    def accessibilityPerformPress(self):
        self.owner.toggleRow_(self.row)
        return True

    def mouseDown_(self, event):
        self.owner.toggleRow_(self.row)

    def drawRect_(self, rect):
        circle = AK.NSBezierPath.bezierPathWithOvalInRect_(AK.NSInsetRect(self.bounds(), 1.5, 1.5))
        if self.checked:
            theme.ACCENT.setFill()
            circle.fill()
            tick = AK.NSBezierPath.bezierPath()
            tick.setLineWidth_(1.7)
            tick.setLineCapStyle_(AK.NSLineCapStyleRound)
            tick.setLineJoinStyle_(AK.NSLineJoinStyleRound)
            tick.moveToPoint_(AK.NSMakePoint(5.4, 9.2))
            tick.lineToPoint_(AK.NSMakePoint(7.9, 6.6))
            tick.lineToPoint_(AK.NSMakePoint(12.8, 11.6))
            theme.ACCENT_INK.setStroke()
            tick.stroke()
        else:
            theme.CONTROL.setFill()
            circle.fill()
            theme.FAINT.setStroke()
            circle.setLineWidth_(1.3)
            circle.stroke()


class QueueTableView(AK.NSTableView):
    """Hover tracking, Delete/Esc keys and a context menu on top of NSTableView."""

    hovered_row = -1

    def updateTrackingAreas(self):
        objc.super(QueueTableView, self).updateTrackingAreas()
        for area in list(self.trackingAreas()):
            if area.owner() is self and area.userInfo() is None:
                self.removeTrackingArea_(area)
        self.addTrackingArea_(
            AK.NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
                AK.NSZeroRect,
                AK.NSTrackingMouseMoved
                | AK.NSTrackingMouseEnteredAndExited
                | AK.NSTrackingActiveInKeyWindow
                | AK.NSTrackingInVisibleRect,
                self,
                None,
            )
        )

    def mouseMoved_(self, event):
        point = self.convertPoint_fromView_(event.locationInWindow(), None)
        self.delegate().setHoveredRow_(self.rowAtPoint_(point))

    def mouseExited_(self, event):
        self.delegate().setHoveredRow_(-1)

    def keyDown_(self, event):
        characters = event.charactersIgnoringModifiers() or ""
        if characters in ("\x7f", ""):
            self.delegate().removeSelectedRows_(self)
            return
        if characters == "\x1b":
            self.deselectAll_(None)
            return
        objc.super(QueueTableView, self).keyDown_(event)

    def menuForEvent_(self, event):
        point = self.convertPoint_fromView_(event.locationInWindow(), None)
        row = self.rowAtPoint_(point)
        if row >= 0 and not self.isRowSelected_(row):
            self.selectRowIndexes_byExtendingSelection_(
                FN.NSIndexSet.indexSetWithIndex_(row), False
            )
        return self.delegate().contextMenu()


class QueueTableController(FN.NSObject):
    """Data source + delegate translating the CompressionQueue into rows."""

    def initWithController_(self, controller):
        self = objc.super(QueueTableController, self).init()
        if self is None:
            return None
        self.controller = controller
        self.table = QueueTableView.alloc().initWithFrame_(AK.NSZeroRect)
        self.table.setStyle_(AK.NSTableViewStyleFullWidth)
        self.table.setRowHeight_(ROW_HEIGHT)
        self.table.setIntercellSpacing_(AK.NSMakeSize(0, 0))
        self.table.setBackgroundColor_(AK.NSColor.clearColor())
        self.table.setAllowsMultipleSelection_(True)
        self.table.setGridStyleMask_(AK.NSTableViewGridNone)
        self.table.setColumnAutoresizingStyle_(AK.NSTableViewFirstColumnOnlyAutoresizingStyle)
        self.table.setAccessibilityLabel_("PDF list")
        # Fixed numeric columns (values never outgrow them); File takes the rest
        # and grows with the window. No user resizing: nothing would gain from it.
        self.table.setAllowsColumnResizing_(False)
        self.table.setAllowsColumnReordering_(False)
        self.table.setHeaderView_(QueueHeaderView.alloc().initWithFrame_(AK.NSMakeRect(0, 0, 720, 30)))
        for identifier, title, width, alignment in (
            (COLUMN_FILE, "File", 300, AK.NSTextAlignmentLeft),
            (COLUMN_ORIGINAL, "Original", 80, AK.NSTextAlignmentRight),
            (COLUMN_COMPRESSED, "Compressed", 96, AK.NSTextAlignmentRight),
            (COLUMN_REDUCTION, "Reduction", 78, AK.NSTextAlignmentRight),
            (COLUMN_ACTIONS, "", 64, AK.NSTextAlignmentRight),
        ):
            column = AK.NSTableColumn.alloc().initWithIdentifier_(identifier)
            column.setTitle_(title)
            column.setWidth_(width)
            column.headerCell().setAlignment_(alignment)
            if identifier == COLUMN_FILE:
                column.setMinWidth_(160)
                column.setResizingMask_(AK.NSTableColumnAutoresizingMask)
            else:
                column.setMinWidth_(width)
                column.setMaxWidth_(width)
                column.setResizingMask_(AK.NSTableColumnNoResizing)
            self.table.addTableColumn_(column)
        self.table.setDataSource_(self)
        self.table.setDelegate_(self)
        self.table.setTarget_(self)
        self.table.setDoubleAction_("revealClickedRow:")
        return self

    # -- Data source / delegate -----------------------------------------------------

    def numberOfRowsInTableView_(self, table):
        return len(self.controller.queue)

    def tableView_rowViewForRow_(self, table, row):
        view = QueueRowView.alloc().initWithFrame_(AK.NSZeroRect)
        view.set_hovered(row == self.table.hovered_row, animated=False)
        return view

    def tableView_viewForTableColumn_row_(self, table, column, row):
        if row >= len(self.controller.queue):
            return None
        item = self.controller.queue[row]
        identifier = column.identifier()
        if identifier == COLUMN_FILE:
            return self._file_cell(item, row)
        if identifier == COLUMN_ACTIONS:
            return self._actions_cell(item, row)
        return self._value_cell(item, identifier)

    def tableViewSelectionDidChange_(self, notification):
        self.controller.selection_changed()

    def setHoveredRow_(self, row):
        old = self.table.hovered_row
        if row == old:
            return
        self.table.hovered_row = row
        rows = FN.NSMutableIndexSet.indexSet()
        for candidate in (old, row):
            if 0 <= candidate < self.table.numberOfRows():
                rows.addIndex_(candidate)
                row_view = self.table.rowViewAtRow_makeIfNecessary_(candidate, False)
                if row_view is not None:
                    row_view.set_hovered(candidate == row)
        if rows.count():
            self.table.reloadDataForRowIndexes_columnIndexes_(
                rows, FN.NSIndexSet.indexSetWithIndexesInRange_(FN.NSMakeRange(0, 5))
            )

    # -- Cells -------------------------------------------------------------------

    @objc.python_method
    def _label(self, text, font, color, alignment=AK.NSTextAlignmentLeft):
        label = AK.NSTextField.labelWithString_(text)
        label.setFont_(font)
        label.setTextColor_(color)
        label.setAlignment_(alignment)
        label.setLineBreakMode_(AK.NSLineBreakByTruncatingMiddle)
        label.setTranslatesAutoresizingMaskIntoConstraints_(False)
        return label

    @objc.python_method
    def _status_view(self, state):
        if isinstance(state, Compressing):
            spinner = AK.NSProgressIndicator.alloc().initWithFrame_(AK.NSMakeRect(0, 0, 14, 14))
            spinner.setStyle_(AK.NSProgressIndicatorStyleSpinning)
            spinner.setControlSize_(AK.NSControlSizeSmall)
            spinner.startAnimation_(None)
            return spinner, "Compressing"
        symbol = {
            Compressed: ("checkmark.circle.fill", theme.SUCCESS, "Completed"),
            Failed: ("exclamationmark.circle.fill", theme.FAIL, "Failed"),
            Unchanged: ("equal.circle", theme.MUTED, "Not smaller"),
            Queued: ("clock", theme.FAINT, "Queued"),
        }.get(type(state))
        if symbol is None:
            return None, "Ready"
        name, tint, label = symbol
        view = AK.NSImageView.imageViewWithImage_(_symbol(name, label, 14))
        view.setContentTintColor_(tint)
        return view, label

    @objc.python_method
    def _detail_for(self, item):
        """Line under the file name + the full path for its tooltip."""
        state = item.state
        muted = theme.MUTED
        if isinstance(state, Compressed):
            if state.output_path == item.path:
                return "Replaced the original", state.output_path, muted
            if os.path.dirname(state.output_path) == os.path.dirname(item.path):
                return "Saved next to the original", state.output_path, muted
            return f"Saved in {display_folder(state.output_path)}", state.output_path, muted
        if isinstance(state, Failed):
            return state.reason, item.path, theme.FAIL
        if isinstance(state, Unchanged):
            return state.reason, item.path, muted
        planned = self.controller.planned_output_for(item.path)
        if planned == item.path:
            return "Will replace the original", item.path, theme.MUTED
        if os.path.dirname(planned) == os.path.dirname(item.path):
            return "Will save next to the original", planned, muted
        return f"Will save to {display_folder(planned)}", planned, muted

    @objc.python_method
    def _file_cell(self, item, row):
        cell = AK.NSTableCellView.alloc().initWithFrame_(AK.NSZeroRect)
        status, state_label = self._status_view(item.state)
        selected = self.table.isRowSelected_(row)
        show_check = self.controller.can_select(row) and (
            selected or row == self.table.hovered_row or self.controller.selection_active()
        )
        lead = (
            CheckCircle.alloc().initWithRow_checked_owner_(row, selected, self)
            if show_check
            else status
        )
        name = self._label(item.name, AK.NSFont.systemFontOfSize_(13.0), theme.INK)
        views = [name]
        if isinstance(item.state, Compressing):
            bar = AK.NSProgressIndicator.alloc().initWithFrame_(AK.NSZeroRect)
            bar.setStyle_(AK.NSProgressIndicatorStyleBar)
            bar.setIndeterminate_(True)
            bar.setControlSize_(AK.NSControlSizeSmall)
            bar.startAnimation_(None)
            bar.setTranslatesAutoresizingMaskIntoConstraints_(False)
            second = bar
            detail_text, tooltip = "Compressing", item.path
        else:
            detail_text, tooltip, color = self._detail_for(item)
            second = self._label(detail_text, AK.NSFont.systemFontOfSize_(11.0), color)
        views.append(second)
        if lead is not None:
            lead.setTranslatesAutoresizingMaskIntoConstraints_(False)
            cell.addSubview_(lead)
        for view in views:
            cell.addSubview_(view)
        cell.setToolTip_(tooltip)
        cell.setAccessibilityLabel_(f"{item.name}, {state_label}. {detail_text}")
        constraints = [
            name.leadingAnchor().constraintEqualToAnchor_constant_(cell.leadingAnchor(), 36),
            name.trailingAnchor().constraintLessThanOrEqualToAnchor_(cell.trailingAnchor()),
            name.topAnchor().constraintEqualToAnchor_constant_(cell.topAnchor(), 6),
            second.leadingAnchor().constraintEqualToAnchor_(name.leadingAnchor()),
            second.topAnchor().constraintEqualToAnchor_constant_(name.bottomAnchor(), 2),
        ]
        if isinstance(item.state, Compressing):
            constraints.append(second.widthAnchor().constraintEqualToConstant_(160))
        else:
            constraints.append(
                second.trailingAnchor().constraintLessThanOrEqualToAnchor_(cell.trailingAnchor())
            )
        if lead is not None:
            constraints += [
                lead.centerXAnchor().constraintEqualToAnchor_constant_(cell.leadingAnchor(), 22),
                lead.centerYAnchor().constraintEqualToAnchor_(cell.centerYAnchor()),
                lead.widthAnchor().constraintEqualToConstant_(18),
                lead.heightAnchor().constraintEqualToConstant_(18),
            ]
        AK.NSLayoutConstraint.activateConstraints_(constraints)
        return cell

    @objc.python_method
    def _value_text(self, item, identifier):
        state = item.state
        faint = theme.FAINT
        muted = theme.MUTED
        if identifier == COLUMN_ORIGINAL:
            return format_file_size(item.original_size), theme.INK
        if identifier == COLUMN_COMPRESSED:
            if isinstance(state, Compressed):
                return format_file_size(state.new_size), theme.INK
            if isinstance(state, Compressing):
                return "Compressing…", muted
            if isinstance(state, Queued):
                return "Queued", muted
            if isinstance(state, Unchanged):
                return "Not smaller", muted
            if isinstance(state, Failed):
                return "Failed", theme.FAIL
            return "—", faint
        if item.reduction is not None:
            return f"↓ {item.reduction:.1f}%", theme.SUCCESS
        return "", faint

    @objc.python_method
    def _value_cell(self, item, identifier):
        cell = AK.NSTableCellView.alloc().initWithFrame_(AK.NSZeroRect)
        text, color = self._value_text(item, identifier)
        label = self._label(
            text,
            AK.NSFont.monospacedDigitSystemFontOfSize_weight_(12.5, AK.NSFontWeightRegular),
            color,
            AK.NSTextAlignmentRight,
        )
        cell.addSubview_(label)
        AK.NSLayoutConstraint.activateConstraints_(
            [
                label.trailingAnchor().constraintEqualToAnchor_constant_(cell.trailingAnchor(), -4),
                label.leadingAnchor().constraintGreaterThanOrEqualToAnchor_(cell.leadingAnchor()),
                label.centerYAnchor().constraintEqualToAnchor_(cell.centerYAnchor()),
            ]
        )
        return cell

    @objc.python_method
    def _icon_button(self, symbol, description, action, row):
        button = QuietButton.alloc().initWithTitle_symbol_style_target_action_(
            None, symbol, "icon", self, action
        )
        button.setTag_(row)
        button.setToolTip_(description)
        button.setAccessibilityLabel_(description)
        button.setTranslatesAutoresizingMaskIntoConstraints_(False)
        button.widthAnchor().constraintEqualToConstant_(24).setActive_(True)
        button.heightAnchor().constraintEqualToConstant_(24).setActive_(True)
        return button

    @objc.python_method
    def _actions_cell(self, item, row):
        """Row actions appear only on the hovered row, so the list stays quiet."""
        cell = AK.NSTableCellView.alloc().initWithFrame_(AK.NSZeroRect)
        if row != self.table.hovered_row:
            return cell
        stack = AK.NSStackView.stackViewWithViews_([])
        stack.setSpacing_(2)
        stack.setTranslatesAutoresizingMaskIntoConstraints_(False)
        if isinstance(item.state, Compressed):
            stack.addArrangedSubview_(
                self._icon_button(REVEAL_SYMBOL, "Show in Finder", "revealRow:", row)
            )
        if self.controller.can_remove(row):
            stack.addArrangedSubview_(
                self._icon_button("xmark", "Remove from list", "removeRow:", row)
            )
        cell.addSubview_(stack)
        AK.NSLayoutConstraint.activateConstraints_(
            [
                stack.trailingAnchor().constraintEqualToAnchor_constant_(cell.trailingAnchor(), -10),
                stack.centerYAnchor().constraintEqualToAnchor_(cell.centerYAnchor()),
            ]
        )
        return cell

    # -- Actions -------------------------------------------------------------------

    def toggleRow_(self, row):
        if self.table.isRowSelected_(row):
            self.table.deselectRow_(row)
        else:
            self.table.selectRowIndexes_byExtendingSelection_(
                FN.NSIndexSet.indexSetWithIndex_(row), True
            )

    def revealRow_(self, sender):
        self.controller.reveal_rows([sender.tag()])

    def removeRow_(self, sender):
        self.controller.remove_rows([sender.tag()])

    def revealClickedRow_(self, sender):
        row = self.table.clickedRow()
        if row >= 0:
            self.controller.reveal_rows([row])

    @objc.python_method
    def selected_rows(self):
        rows = []
        indexes = self.table.selectedRowIndexes()
        index = indexes.firstIndex()
        while index != FN.NSNotFound:
            rows.append(index)
            index = indexes.indexGreaterThanIndex_(index)
        return rows

    def removeSelectedRows_(self, sender):
        self.controller.remove_rows(self.selected_rows())

    def revealSelectedRows_(self, sender):
        self.controller.reveal_rows(self.selected_rows())

    def openSelectedRows_(self, sender):
        self.controller.open_rows(self.selected_rows())

    def copySelectedPaths_(self, sender):
        self.controller.copy_paths(self.selected_rows())

    @objc.python_method
    def contextMenu(self):
        menu = AK.NSMenu.alloc().initWithTitle_("PDF")
        for title, action, key, symbol in (
            ("Show in Finder", "revealSelectedRows:", "r", REVEAL_SYMBOL),
            ("Open", "openSelectedRows:", "", "arrow.up.forward.app"),
            ("Copy Path", "copySelectedPaths:", "", "doc.on.doc"),
            (None, None, None, None),
            ("Remove from List", "removeSelectedRows:", "\x08", "trash"),
        ):
            if title is None:
                menu.addItem_(AK.NSMenuItem.separatorItem())
                continue
            item = menu.addItemWithTitle_action_keyEquivalent_(title, action, key)
            item.setTarget_(self)
            item.setImage_(_symbol(symbol, title, 13))
        return menu

    def validateMenuItem_(self, item):
        rows = self.selected_rows()
        action = item.action()
        if action == "removeSelectedRows:":
            return any(self.controller.can_remove(r) for r in rows)
        return bool(rows)

    @objc.python_method
    def reload(self):
        self.table.reloadData()


# Finder's own face where the system has it; a plain folder otherwise.
REVEAL_SYMBOL = (
    "finder"
    if AK.NSImage.imageWithSystemSymbolName_accessibilityDescription_("finder", None) is not None
    else "folder"
)
