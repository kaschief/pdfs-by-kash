# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Daniel Lares
# Modifications Copyright (C) 2026 Kaschief

"""AppKit views used by the main Pdfs by Kash window."""

from __future__ import annotations

import os

import AppKit as AK
import Foundation as FN
import objc

from fs_pdf_compressor.compression_queue import (
    Compressed,
    Compressing,
    Failed,
    Queued,
    Unchanged,
)
from fs_pdf_compressor.core import display_folder, format_file_size


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
        AK.NSColor.windowBackgroundColor().setFill()
        AK.NSBezierPath.fillRect_(bounds)

        bottom = self.controller.bottom_chrome_height()
        if self.controller.showing_results:
            if self.drag_active:
                AK.NSColor.controlAccentColor().colorWithAlphaComponent_(0.6).setStroke()
                ring = AK.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                    AK.NSInsetRect(
                        AK.NSMakeRect(0, bottom, bounds.size.width, bounds.size.height - bottom),
                        4,
                        4,
                    ),
                    10,
                    10,
                )
                ring.setLineWidth_(2.0)
                ring.stroke()
            return

        available_height = max(0.0, bounds.size.height - bottom)
        side = min(160.0, bounds.size.width * 0.3, available_height * 0.5)
        target = AK.NSMakeRect(
            (bounds.size.width - side) / 2,
            bottom + (available_height - side) / 2 + 14,
            side,
            side,
        )

        border_color = (
            AK.NSColor.controlAccentColor().colorWithAlphaComponent_(0.55)
            if self.drag_active
            else AK.NSColor.quaternaryLabelColor()
        )
        border_color.setStroke()
        border = AK.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            target, 19, 19
        )
        border.setLineWidth_(2.0)
        border.setLineDash_count_phase_([7.0, 6.0], 2, 0.0)
        border.stroke()

        arrow_color = (
            AK.NSColor.controlAccentColor().colorWithAlphaComponent_(0.72)
            if self.drag_active
            else AK.NSColor.tertiaryLabelColor()
        )
        arrow_color.setStroke()
        center_x = AK.NSMidX(target)
        center_y = AK.NSMidY(target)
        arrow = AK.NSBezierPath.bezierPath()
        arrow.setLineWidth_(3.0)
        arrow.setLineCapStyle_(AK.NSLineCapStyleRound)
        arrow.setLineJoinStyle_(AK.NSLineJoinStyleRound)
        arrow.moveToPoint_(AK.NSMakePoint(center_x, center_y + 30))
        arrow.lineToPoint_(AK.NSMakePoint(center_x, center_y - 19))
        arrow.moveToPoint_(AK.NSMakePoint(center_x - 18, center_y - 2))
        arrow.lineToPoint_(AK.NSMakePoint(center_x, center_y - 21))
        arrow.lineToPoint_(AK.NSMakePoint(center_x + 18, center_y - 2))
        arrow.stroke()

        style = AK.NSMutableParagraphStyle.alloc().init()
        style.setAlignment_(AK.NSTextAlignmentCenter)
        hint = FN.NSString.stringWithString_(
            "Drop PDFs or folders here, or click + to choose files"
        )
        hint.drawInRect_withAttributes_(
            AK.NSMakeRect(0, target.origin.y - 34, bounds.size.width, 18),
            {
                AK.NSFontAttributeName: AK.NSFont.systemFontOfSize_(12.0),
                AK.NSForegroundColorAttributeName: AK.NSColor.secondaryLabelColor(),
                AK.NSParagraphStyleAttributeName: style,
            },
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
    """Draw a template SF Symbol in ``color`` (works in both appearances)."""
    if image is None:
        return
    tinted = image.copy()
    tinted.lockFocus()
    color.set()
    AK.NSRectFillUsingOperation(
        AK.NSMakeRect(0, 0, tinted.size().width, tinted.size().height),
        AK.NSCompositingOperationSourceAtop,
    )
    tinted.unlockFocus()
    size = image.size()
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


WARN = AK.NSColor.systemOrangeColor
FAIL = AK.NSColor.systemRedColor
OK = AK.NSColor.systemGreenColor


# -- Setting tiles (direction A) -----------------------------------------------------


class SettingTile(AK.NSView):
    """Icon + caption + value-in-words. Opens a popover of option cards on click.

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
        return self.mode != "off"

    def becomeFirstResponder(self):
        self.setNeedsDisplay_(True)
        return True

    def resignFirstResponder(self):
        self.setNeedsDisplay_(True)
        return True

    def drawFocusRingMask(self):
        AK.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(self.bounds(), 10, 10).fill()

    def focusRingMaskBounds(self):
        return self.bounds()

    def accessibilityPerformPress(self):
        self.mouseDown_(None)
        return True

    def keyDown_(self, event):
        if (event.charactersIgnoringModifiers() or "") in (" ", "\r"):
            self.mouseDown_(None)
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
            self.window().makeFirstResponder_(self)
            self.target_controller.open_setting(self)

    def drawRect_(self, rect):
        bounds = AK.NSInsetRect(self.bounds(), 0.5, 0.5)
        off = self.mode == "off"
        card = AK.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(bounds, 10, 10)
        accent = AK.NSColor.controlAccentColor()
        if not off:
            AK.NSColor.controlBackgroundColor().setFill()
            card.fill()
        ring = (
            accent.colorWithAlphaComponent_(0.55)
            if (self.hovered or self.open) and not off
            else AK.NSColor.separatorColor()
        )
        ring.setStroke()
        card.setLineWidth_(1.0)
        card.stroke()

        height = self.bounds().size.height
        chip = AK.NSMakeRect(10, (height - 26) / 2, 26, 26)
        chip_path = AK.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(chip, 7, 7)
        if off:
            AK.NSColor.labelColor().colorWithAlphaComponent_(0.05).setFill()
            glyph = AK.NSColor.tertiaryLabelColor()
        elif self.mode == "warn":
            WARN().colorWithAlphaComponent_(0.14).setFill()
            glyph = WARN()
        else:
            accent.colorWithAlphaComponent_(0.13).setFill()
            glyph = accent
        chip_path.fill()
        _draw_tinted_symbol(self.symbol, chip, glyph)

        text_x = 46
        chevron_space = 0 if off else 22
        text_width = max(10, self.bounds().size.width - text_x - chevron_space - 6)
        _text(
            self.caption,
            AK.NSMakeRect(text_x, height / 2 - 16, text_width, 14),
            AK.NSFont.systemFontOfSize_(10.5),
            AK.NSColor.tertiaryLabelColor() if off else AK.NSColor.secondaryLabelColor(),
        )
        value_color = (
            AK.NSColor.tertiaryLabelColor()
            if off
            else WARN()
            if self.mode == "warn"
            else AK.NSColor.labelColor()
        )
        _text(
            self.value,
            AK.NSMakeRect(text_x, height / 2 - 2, text_width, 17),
            AK.NSFont.systemFontOfSize_weight_(12.5, AK.NSFontWeightMedium),
            value_color,
        )
        if not off:
            chevron = _symbol("chevron.up" if self.open else "chevron.down", "", 9.5, AK.NSFontWeightSemibold)
            _draw_tinted_symbol(
                chevron,
                AK.NSMakeRect(self.bounds().size.width - 24, 0, 14, height),
                accent if self.open else AK.NSColor.tertiaryLabelColor(),
            )


class OptionCard(AK.NSView):
    """A choice inside a settings popover: icon, title, one-line explanation."""

    WIDTH = 300.0

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
        self.setAccessibilityHelp_(self.detail)
        _hover_tracking(self)
        height = 22 + (self._detail_height() if self.detail else 0) + 16
        self.setFrameSize_(AK.NSMakeSize(self.WIDTH, max(42, height)))
        return self

    @objc.python_method
    def _detail_height(self):
        rect = FN.NSString.stringWithString_(self.detail).boundingRectWithSize_options_attributes_(
            AK.NSMakeSize(self.WIDTH - 56, 1000),
            AK.NSStringDrawingUsesLineFragmentOrigin,
            {AK.NSFontAttributeName: AK.NSFont.systemFontOfSize_(11.5)},
        )
        return rect.size.height + 2

    def isFlipped(self):
        return True

    def intrinsicContentSize(self):
        return self.frame().size

    def accessibilityValue(self):
        return 1 if self.selected else 0

    def accessibilityPerformPress(self):
        self.action()
        return True

    def acceptsFirstResponder(self):
        return True

    def keyDown_(self, event):
        if (event.charactersIgnoringModifiers() or "") in (" ", "\r"):
            self.action()
        else:
            objc.super(OptionCard, self).keyDown_(event)

    def drawFocusRingMask(self):
        AK.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(self.bounds(), 9, 9).fill()

    def focusRingMaskBounds(self):
        return self.bounds()

    def mouseEntered_(self, event):
        self.hovered = True
        self.setNeedsDisplay_(True)

    def mouseExited_(self, event):
        self.hovered = False
        self.setNeedsDisplay_(True)

    def mouseUp_(self, event):
        self.action()

    def mouseDown_(self, event):
        pass

    def drawRect_(self, rect):
        bounds = self.bounds()
        path = AK.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(AK.NSInsetRect(bounds, 1, 1), 9, 9)
        tone = WARN() if self.warn else AK.NSColor.controlAccentColor()
        if self.selected:
            tone.colorWithAlphaComponent_(0.11).setFill()
            path.fill()
            tone.colorWithAlphaComponent_(0.45).setStroke()
            path.setLineWidth_(1.5)
            path.stroke()
        elif self.hovered:
            AK.NSColor.labelColor().colorWithAlphaComponent_(0.05).setFill()
            path.fill()

        chip = AK.NSMakeRect(10, 9, 26, 26)
        chip_path = AK.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(chip, 7, 7)
        if self.selected:
            tone.setFill()
            glyph = AK.NSColor.whiteColor()
        else:
            AK.NSColor.labelColor().colorWithAlphaComponent_(0.07).setFill()
            glyph = AK.NSColor.secondaryLabelColor()
        if self.symbol is not None:
            chip_path.fill()
            _draw_tinted_symbol(self.symbol, chip, glyph)

        _text(
            self.title,
            AK.NSMakeRect(46, 9, bounds.size.width - 56, 17),
            AK.NSFont.systemFontOfSize_weight_(13.0, AK.NSFontWeightSemibold),
            AK.NSColor.labelColor(),
        )
        if self.detail:
            style = AK.NSMutableParagraphStyle.alloc().init()
            style.setLineSpacing_(1.0)
            FN.NSString.stringWithString_(self.detail).drawInRect_withAttributes_(
                AK.NSMakeRect(46, 27, bounds.size.width - 56, bounds.size.height - 30),
                {
                    AK.NSFontAttributeName: AK.NSFont.systemFontOfSize_(11.5),
                    AK.NSForegroundColorAttributeName: AK.NSColor.secondaryLabelColor(),
                    AK.NSParagraphStyleAttributeName: style,
                },
            )


class _CallbackViewController(AK.NSViewController):
    def loadView(self):
        pass


def option_popover(cards, delegate):
    """Wrap OptionCards in a transient NSPopover."""
    stack = AK.NSStackView.stackViewWithViews_(cards)
    stack.setOrientation_(AK.NSUserInterfaceLayoutOrientationVertical)
    stack.setSpacing_(4)
    stack.setEdgeInsets_(AK.NSEdgeInsetsMake(8, 8, 8, 8))
    for card in cards:
        card.widthAnchor().constraintEqualToConstant_(OptionCard.WIDTH).setActive_(True)
        card.heightAnchor().constraintEqualToConstant_(card.frame().size.height).setActive_(True)
    stack.setFrameSize_(stack.fittingSize())
    controller = _CallbackViewController.alloc().init()
    controller.setView_(stack)
    popover = AK.NSPopover.alloc().init()
    popover.setBehavior_(AK.NSPopoverBehaviorTransient)
    popover.setAnimates_(True)
    popover.setContentViewController_(controller)
    popover.setContentSize_(stack.fittingSize())
    popover.setDelegate_(delegate)
    return popover


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
        self.buttons = []
        for title, symbol, action in (
            ("Show in Finder", "folder", "revealSelection:"),
            ("Remove", "trash", "removeSelection:"),
            ("Done", None, "clearSelection:"),
        ):
            button = AK.NSButton.buttonWithTitle_target_action_(title, owner, action)
            button.setBordered_(False)
            button.setFont_(AK.NSFont.systemFontOfSize_(12.5))
            if symbol:
                button.setImage_(_symbol(symbol, title, 12))
                button.setImagePosition_(AK.NSImageLeading)
            self.buttons.append(button)
        stack = AK.NSStackView.stackViewWithViews_([self.label] + self.buttons)
        stack.setSpacing_(14)
        stack.setCustomSpacing_afterView_(18, self.label)
        stack.setEdgeInsets_(AK.NSEdgeInsetsMake(0, 16, 0, 14))
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

    def updateLayer(self):
        dark = self.effectiveAppearance().bestMatchFromAppearancesWithNames_(
            [AK.NSAppearanceNameAqua, AK.NSAppearanceNameDarkAqua]
        ) == AK.NSAppearanceNameDarkAqua
        background = AK.NSColor.colorWithSRGBRed_green_blue_alpha_(
            *((0.94, 0.94, 0.99, 1) if dark else (0.12, 0.11, 0.23, 1))
        )
        ink = AK.NSColor.colorWithSRGBRed_green_blue_alpha_(
            *((0.09, 0.09, 0.17, 1) if dark else (0.94, 0.94, 0.99, 1))
        )
        self.layer().setBackgroundColor_(background.CGColor())
        self.label.setTextColor_(ink)
        for button in self.buttons:
            button.setContentTintColor_(ink)
            title = AK.NSAttributedString.alloc().initWithString_attributes_(
                button.title(),
                {AK.NSForegroundColorAttributeName: ink, AK.NSFontAttributeName: button.font()},
            )
            button.setAttributedTitle_(title)

    def wantsUpdateLayer(self):
        return True

    @objc.python_method
    def update(self, count, can_reveal, can_remove):
        self.label.setStringValue_(f"{count} selected")
        self.buttons[0].setEnabled_(can_reveal)
        self.buttons[1].setEnabled_(can_remove)
        self.setNeedsDisplay_(True)
        self.setFrameSize_(AK.NSMakeSize(self.fittingSize().width, 36))


# -- Queue table ---------------------------------------------------------------

COLUMN_FILE = "file"
COLUMN_ORIGINAL = "original"
COLUMN_COMPRESSED = "compressed"
COLUMN_REDUCTION = "reduction"
COLUMN_ACTIONS = "actions"

ROW_HEIGHT = 44.0


class QueueRowView(AK.NSTableRowView):
    """Soft rounded hover/selection, like the family's lists (no system blue bar)."""

    hovered = False

    def drawBackgroundInRect_(self, rect):
        if self.hovered and not self.isSelected():
            AK.NSColor.labelColor().colorWithAlphaComponent_(0.035).setFill()
            AK.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                AK.NSInsetRect(self.bounds(), 4, 1), 8, 8
            ).fill()

    def drawSelectionInRect_(self, rect):
        AK.NSColor.controlAccentColor().colorWithAlphaComponent_(
            0.13 if self.hovered else 0.09
        ).setFill()
        AK.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            AK.NSInsetRect(self.bounds(), 4, 1), 8, 8
        ).fill()

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
            AK.NSColor.controlAccentColor().setFill()
            circle.fill()
            tick = AK.NSBezierPath.bezierPath()
            tick.setLineWidth_(1.7)
            tick.setLineCapStyle_(AK.NSLineCapStyleRound)
            tick.setLineJoinStyle_(AK.NSLineJoinStyleRound)
            tick.moveToPoint_(AK.NSMakePoint(5.4, 9.2))
            tick.lineToPoint_(AK.NSMakePoint(7.9, 6.6))
            tick.lineToPoint_(AK.NSMakePoint(12.8, 11.6))
            AK.NSColor.whiteColor().setStroke()
            tick.stroke()
        else:
            AK.NSColor.controlBackgroundColor().setFill()
            circle.fill()
            AK.NSColor.tertiaryLabelColor().setStroke()
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
        view.hovered = row == self.table.hovered_row
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
                    row_view.hovered = candidate == row
                    row_view.setNeedsDisplay_(True)
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
            Compressed: ("checkmark.circle.fill", OK(), "Completed"),
            Failed: ("exclamationmark.circle.fill", FAIL(), "Failed"),
            Unchanged: ("equal.circle", AK.NSColor.secondaryLabelColor(), "Not smaller"),
            Queued: ("clock", AK.NSColor.tertiaryLabelColor(), "Queued"),
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
        muted = AK.NSColor.secondaryLabelColor()
        if isinstance(state, Compressed):
            if state.output_path == item.path:
                return "Replaced the original", state.output_path, muted
            if os.path.dirname(state.output_path) == os.path.dirname(item.path):
                return "Saved next to the original", state.output_path, muted
            return f"Saved in {display_folder(state.output_path)}", state.output_path, muted
        if isinstance(state, Failed):
            return state.reason, item.path, FAIL()
        if isinstance(state, Unchanged):
            return state.reason, item.path, muted
        planned = self.controller.planned_output_for(item.path)
        if planned == item.path:
            return "Will replace the original", item.path, WARN()
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
        name = self._label(item.name, AK.NSFont.systemFontOfSize_(13.0), AK.NSColor.labelColor())
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
        faint = AK.NSColor.tertiaryLabelColor()
        muted = AK.NSColor.secondaryLabelColor()
        if identifier == COLUMN_ORIGINAL:
            return format_file_size(item.original_size), AK.NSColor.labelColor()
        if identifier == COLUMN_COMPRESSED:
            if isinstance(state, Compressed):
                return format_file_size(state.new_size), AK.NSColor.labelColor()
            if isinstance(state, Compressing):
                return "Compressing…", muted
            if isinstance(state, Queued):
                return "Queued", muted
            if isinstance(state, Unchanged):
                return "Not smaller", muted
            if isinstance(state, Failed):
                return "Failed", FAIL()
            return "—", faint
        if item.reduction is not None:
            return f"↓ {item.reduction:.1f}%", OK()
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
        button = AK.NSButton.buttonWithImage_target_action_(
            _symbol(symbol, description, 13), self, action
        )
        button.setBordered_(False)
        button.setTag_(row)
        button.setToolTip_(description)
        button.setContentTintColor_(AK.NSColor.secondaryLabelColor())
        button.setTranslatesAutoresizingMaskIntoConstraints_(False)
        return button

    @objc.python_method
    def _actions_cell(self, item, row):
        """Row actions appear only on the hovered row, so the list stays quiet."""
        cell = AK.NSTableCellView.alloc().initWithFrame_(AK.NSZeroRect)
        if row != self.table.hovered_row:
            return cell
        stack = AK.NSStackView.stackViewWithViews_([])
        stack.setSpacing_(8)
        stack.setTranslatesAutoresizingMaskIntoConstraints_(False)
        if isinstance(item.state, Compressed):
            stack.addArrangedSubview_(
                self._icon_button(REVEAL_SYMBOL, "Show in Finder", "revealRow:", row)
            )
        if self.controller.can_remove(row):
            stack.addArrangedSubview_(
                self._icon_button("xmark.circle.fill", "Remove from list", "removeRow:", row)
            )
        cell.addSubview_(stack)
        AK.NSLayoutConstraint.activateConstraints_(
            [
                stack.trailingAnchor().constraintEqualToAnchor_constant_(cell.trailingAnchor(), -12),
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
