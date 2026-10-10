# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Daniel Lares
# Modifications Copyright (C) 2026 Kaschief

"""AppKit views used by the main Pdfs by Kash window."""

from __future__ import annotations

import AppKit as AK
import Foundation as FN
import objc

from fs_pdf_compressor.compression_queue import (
    Compressed,
    Compressing,
    Failed,
    Pending,
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


# -- Queue table ---------------------------------------------------------------

COLUMN_FILE = "file"
COLUMN_ORIGINAL = "original"
COLUMN_COMPRESSED = "compressed"
COLUMN_REDUCTION = "reduction"
COLUMN_ACTIONS = "actions"

ROW_HEIGHT = 40.0


class QueueTableView(AK.NSTableView):
    """Native table: Delete removes selected rows, Return/double-click reveals."""

    def keyDown_(self, event):
        characters = event.charactersIgnoringModifiers() or ""
        if characters in ("\x7f", ""):  # Backspace / forward Delete
            self.delegate().removeSelectedRows_(self)
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
        self.table.setStyle_(AK.NSTableViewStyleInset)
        self.table.setRowHeight_(ROW_HEIGHT)
        self.table.setUsesAlternatingRowBackgroundColors_(False)
        self.table.setAllowsMultipleSelection_(True)
        self.table.setColumnAutoresizingStyle_(
            AK.NSTableViewFirstColumnOnlyAutoresizingStyle
        )
        self.table.setAccessibilityLabel_("PDF queue")
        for identifier, title, width, alignment in (
            (COLUMN_FILE, "File", 300, AK.NSTextAlignmentLeft),
            (COLUMN_ORIGINAL, "Original", 78, AK.NSTextAlignmentRight),
            (COLUMN_COMPRESSED, "Compressed", 92, AK.NSTextAlignmentRight),
            (COLUMN_REDUCTION, "Reduction", 76, AK.NSTextAlignmentRight),
            (COLUMN_ACTIONS, "", 52, AK.NSTextAlignmentRight),
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

    # -- Data source -------------------------------------------------------------

    def numberOfRowsInTableView_(self, table):
        return len(self.controller.queue)

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

    def tableView_shouldSelectRow_(self, table, row):
        return True

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
    def _status_symbol(self, state):
        if isinstance(state, Compressed):
            return "checkmark.circle.fill", AK.NSColor.systemGreenColor(), "Compressed"
        if isinstance(state, Failed):
            return "exclamationmark.triangle.fill", AK.NSColor.systemRedColor(), "Failed"
        if isinstance(state, Unchanged):
            return "equal.circle", AK.NSColor.secondaryLabelColor(), "Unchanged"
        if isinstance(state, Compressing):
            return "arrow.triangle.2.circlepath", AK.NSColor.controlAccentColor(), "Compressing"
        return "clock", AK.NSColor.tertiaryLabelColor(), "Pending"

    @objc.python_method
    def _detail_for(self, item):
        """Second line under the file name, plus the full-path tooltip."""
        state = item.state
        if isinstance(state, Compressed):
            if state.output_path == item.path:
                return "Replaced original", state.output_path, AK.NSColor.secondaryLabelColor()
            return (
                f"Saved in {display_folder(state.output_path)}",
                state.output_path,
                AK.NSColor.secondaryLabelColor(),
            )
        if isinstance(state, Failed):
            return state.reason, item.path, AK.NSColor.systemRedColor()
        if isinstance(state, Unchanged):
            return state.reason, item.path, AK.NSColor.secondaryLabelColor()
        if isinstance(state, Compressing):
            return "Compressing…", item.path, AK.NSColor.secondaryLabelColor()
        planned = self.controller.planned_output_for(item.path)
        if planned == item.path:
            return "Will replace original", item.path, AK.NSColor.systemOrangeColor()
        return (
            f"Will save to {display_folder(planned)}",
            planned,
            AK.NSColor.secondaryLabelColor(),
        )

    @objc.python_method
    def _file_cell(self, item, row):
        cell = AK.NSTableCellView.alloc().initWithFrame_(AK.NSZeroRect)
        symbol, tint, state_label = self._status_symbol(item.state)
        image = AK.NSImage.imageWithSystemSymbolName_accessibilityDescription_(
            symbol, state_label
        )
        icon = AK.NSImageView.imageViewWithImage_(image)
        icon.setContentTintColor_(tint)
        icon.setSymbolConfiguration_(
            AK.NSImageSymbolConfiguration.configurationWithPointSize_weight_(
                14, AK.NSFontWeightRegular
            )
        )
        icon.setTranslatesAutoresizingMaskIntoConstraints_(False)

        name = self._label(
            item.name, AK.NSFont.systemFontOfSize_(13.0), AK.NSColor.labelColor()
        )
        detail_text, tooltip, detail_color = self._detail_for(item)
        detail = self._label(detail_text, AK.NSFont.systemFontOfSize_(11.0), detail_color)

        for view in (icon, name, detail):
            cell.addSubview_(view)
        cell.setToolTip_(f"{item.path}\n→ {tooltip}" if tooltip != item.path else item.path)
        cell.setAccessibilityLabel_(f"{item.name}, {state_label}. {detail_text}")
        AK.NSLayoutConstraint.activateConstraints_(
            [
                icon.leadingAnchor().constraintEqualToAnchor_constant_(cell.leadingAnchor(), 2),
                icon.centerYAnchor().constraintEqualToAnchor_(cell.centerYAnchor()),
                icon.widthAnchor().constraintEqualToConstant_(18),
                name.leadingAnchor().constraintEqualToAnchor_constant_(icon.trailingAnchor(), 8),
                name.trailingAnchor().constraintLessThanOrEqualToAnchor_(cell.trailingAnchor()),
                name.topAnchor().constraintEqualToAnchor_constant_(cell.topAnchor(), 4),
                detail.leadingAnchor().constraintEqualToAnchor_(name.leadingAnchor()),
                detail.trailingAnchor().constraintLessThanOrEqualToAnchor_(cell.trailingAnchor()),
                detail.topAnchor().constraintEqualToAnchor_constant_(name.bottomAnchor(), 1),
            ]
        )
        return cell

    @objc.python_method
    def _value_text(self, item, identifier):
        state = item.state
        muted = AK.NSColor.secondaryLabelColor()
        if identifier == COLUMN_ORIGINAL:
            return format_file_size(item.original_size), AK.NSColor.labelColor()
        if identifier == COLUMN_COMPRESSED:
            if isinstance(state, Compressed):
                return format_file_size(state.new_size), AK.NSColor.labelColor()
            if isinstance(state, Compressing):
                return "Working…", AK.NSColor.controlAccentColor()
            if isinstance(state, Unchanged):
                return "Not smaller", muted
            if isinstance(state, Failed):
                return "Failed", AK.NSColor.systemRedColor()
            return "Pending", AK.NSColor.tertiaryLabelColor()
        # Reduction
        if item.reduction is not None:
            return f"↓ {item.reduction:.1f}%", AK.NSColor.systemGreenColor()
        return "—", AK.NSColor.tertiaryLabelColor()

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
                label.trailingAnchor().constraintEqualToAnchor_constant_(cell.trailingAnchor(), -2),
                label.leadingAnchor().constraintGreaterThanOrEqualToAnchor_(cell.leadingAnchor()),
                label.centerYAnchor().constraintEqualToAnchor_(cell.centerYAnchor()),
            ]
        )
        return cell

    @objc.python_method
    def _icon_button(self, symbol, description, action, row):
        button = AK.NSButton.buttonWithImage_target_action_(
            AK.NSImage.imageWithSystemSymbolName_accessibilityDescription_(symbol, description),
            self,
            action,
        )
        button.setBordered_(False)
        button.setTag_(row)
        button.setToolTip_(description)
        button.setContentTintColor_(AK.NSColor.secondaryLabelColor())
        button.setTranslatesAutoresizingMaskIntoConstraints_(False)
        return button

    @objc.python_method
    def _actions_cell(self, item, row):
        cell = AK.NSTableCellView.alloc().initWithFrame_(AK.NSZeroRect)
        stack = AK.NSStackView.stackViewWithViews_([])
        stack.setSpacing_(6)
        stack.setTranslatesAutoresizingMaskIntoConstraints_(False)
        if isinstance(item.state, Compressed):
            stack.addArrangedSubview_(
                self._icon_button("magnifyingglass", "Show in Finder", "revealRow:", row)
            )
        if self.controller.can_remove(row):
            stack.addArrangedSubview_(
                self._icon_button("xmark.circle.fill", "Remove from list", "removeRow:", row)
            )
        cell.addSubview_(stack)
        AK.NSLayoutConstraint.activateConstraints_(
            [
                stack.trailingAnchor().constraintEqualToAnchor_constant_(cell.trailingAnchor(), -4),
                stack.centerYAnchor().constraintEqualToAnchor_(cell.centerYAnchor()),
            ]
        )
        return cell

    # -- Actions -------------------------------------------------------------------

    def revealRow_(self, sender):
        self.controller.reveal_rows([sender.tag()])

    def removeRow_(self, sender):
        self.controller.remove_rows([sender.tag()])

    def revealClickedRow_(self, sender):
        row = self.table.clickedRow()
        if row >= 0:
            self.controller.reveal_rows([row])

    @objc.python_method
    def _selected_rows(self):
        rows = []
        indexes = self.table.selectedRowIndexes()
        index = indexes.firstIndex()
        while index != FN.NSNotFound:
            rows.append(index)
            index = indexes.indexGreaterThanIndex_(index)
        return rows

    def removeSelectedRows_(self, sender):
        self.controller.remove_rows(self._selected_rows())

    def revealSelectedRows_(self, sender):
        self.controller.reveal_rows(self._selected_rows())

    @objc.python_method
    def contextMenu(self):
        menu = AK.NSMenu.alloc().initWithTitle_("Queue")
        reveal = menu.addItemWithTitle_action_keyEquivalent_(
            "Show in Finder", "revealSelectedRows:", ""
        )
        reveal.setTarget_(self)
        remove = menu.addItemWithTitle_action_keyEquivalent_(
            "Remove from List", "removeSelectedRows:", ""
        )
        remove.setTarget_(self)
        return menu

    def validateMenuItem_(self, item):
        rows = self._selected_rows()
        if item.action() == "revealSelectedRows:":
            return any(isinstance(self.controller.queue[r].state, Compressed) for r in rows)
        if item.action() == "removeSelectedRows:":
            return any(self.controller.can_remove(r) for r in rows)
        return True

    @objc.python_method
    def reload(self):
        self.table.reloadData()
