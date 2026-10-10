# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Kaschief

"""The Settings window (⌘,): Appearance and Compression panes.

Native conventions: a toolbar of selectable panes, the window resizes to each
pane, changes apply immediately (no OK/Apply), and the window remembers the
last pane. Compression settings are the *starting* values for each launch.
"""

from __future__ import annotations

from pathlib import Path

import AppKit as AK
import Foundation as FN
import objc

from fs_pdf_compressor import preferences as prefs
from fs_pdf_compressor.app_icons import APP_ICONS, DEFAULT_ICON, apply_icon, icon_image, resolve
from fs_pdf_compressor.core import QUALITY_CONTROL_LABELS, QUALITY_PROFILES, tilde_path

PANE_APPEARANCE = "appearance"
PANE_COMPRESSION = "compression"
LAST_PANE_KEY = "SettingsLastPane"
WIDTH = 560.0
TAG_ALONGSIDE, TAG_FOLDER, TAG_CHOOSE = 0, 1, 2


def apply_theme(theme: str) -> None:
    names = {"light": AK.NSAppearanceNameAqua, "dark": AK.NSAppearanceNameDarkAqua}
    AK.NSApp.setAppearance_(
        AK.NSAppearance.appearanceNamed_(names[theme]) if theme in names else None
    )


def _label(text, size=13.0, color=None, weight=None):
    field = AK.NSTextField.labelWithString_(text)
    field.setFont_(
        AK.NSFont.systemFontOfSize_weight_(size, weight)
        if weight is not None
        else AK.NSFont.systemFontOfSize_(size)
    )
    if color is not None:
        field.setTextColor_(color)
    return field


def _wrapping(text, width, size=11.5):
    field = AK.NSTextField.wrappingLabelWithString_(text)
    field.setFont_(AK.NSFont.systemFontOfSize_(size))
    field.setTextColor_(AK.NSColor.secondaryLabelColor())
    field.setPreferredMaxLayoutWidth_(width)
    return field


def _section_title(text):
    return _label(text, 12.0, AK.NSColor.secondaryLabelColor(), AK.NSFontWeightSemibold)


# -- Icon tile ---------------------------------------------------------------------


class IconTile(AK.NSView):
    """One selectable icon: preview + name. Keyboard and VoiceOver friendly."""

    SIZE = AK.NSMakeSize(112, 118)

    def initWithIcon_owner_(self, icon, owner):
        self = objc.super(IconTile, self).initWithFrame_(
            AK.NSMakeRect(0, 0, self.SIZE.width, self.SIZE.height)
        )
        if self is None:
            return None
        self.icon = icon
        self.owner = owner
        self.selected = False
        self.hovered = False
        self.setToolTip_(icon.note)
        self.setAccessibilityElement_(True)
        self.setAccessibilityRole_(AK.NSAccessibilityRadioButtonRole)
        self.setAccessibilityLabel_(f"{icon.name} icon")
        self.setAccessibilityHelp_(icon.note)
        area = AK.NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
            AK.NSZeroRect,
            AK.NSTrackingMouseEnteredAndExited
            | AK.NSTrackingActiveInKeyWindow
            | AK.NSTrackingInVisibleRect,
            self,
            None,
        )
        self.addTrackingArea_(area)
        return self

    def isFlipped(self):
        return True

    def intrinsicContentSize(self):
        return self.SIZE

    def acceptsFirstResponder(self):
        return True

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

    def mouseEntered_(self, event):
        self.hovered = True
        self.setNeedsDisplay_(True)

    def mouseExited_(self, event):
        self.hovered = False
        self.setNeedsDisplay_(True)

    def mouseDown_(self, event):
        self.window().makeFirstResponder_(self)
        self.owner.chooseIcon_(self.icon.slug)

    def keyDown_(self, event):
        key = event.charactersIgnoringModifiers() or ""
        if key in (" ", "\r"):
            self.owner.chooseIcon_(self.icon.slug)
        elif key in ("", "", "", ""):
            self.owner.moveFocusFrom_key_(self, key)
        else:
            objc.super(IconTile, self).keyDown_(event)

    def drawFocusRingMask(self):
        AK.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            AK.NSInsetRect(self.bounds(), 2, 2), 12, 12
        ).fill()

    def focusRingMaskBounds(self):
        return self.bounds()

    def drawRect_(self, rect):
        card = AK.NSInsetRect(self.bounds(), 3, 3)
        path = AK.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(card, 12, 12)
        accent = AK.NSColor.controlAccentColor()
        if self.selected:
            accent.colorWithAlphaComponent_(0.12).setFill()
            path.fill()
            accent.setStroke()
            path.setLineWidth_(2.0)
            path.stroke()
        elif self.hovered:
            AK.NSColor.labelColor().colorWithAlphaComponent_(0.05).setFill()
            path.fill()

        image = icon_image(self.icon.slug)
        if image is not None:
            side = 72.0
            image.drawInRect_fromRect_operation_fraction_respectFlipped_hints_(
                AK.NSMakeRect((self.bounds().size.width - side) / 2, 10, side, side),
                AK.NSZeroRect,
                AK.NSCompositingOperationSourceOver,
                1.0,
                True,
                {AK.NSImageHintInterpolation: AK.NSImageInterpolationHigh},
            )
        style = AK.NSMutableParagraphStyle.alloc().init()
        style.setAlignment_(AK.NSTextAlignmentCenter)
        title = self.icon.name + (" · Default" if self.icon.slug == DEFAULT_ICON else "")
        FN.NSString.stringWithString_(title).drawInRect_withAttributes_(
            AK.NSMakeRect(0, 88, self.bounds().size.width, 18),
            {
                AK.NSFontAttributeName: AK.NSFont.systemFontOfSize_weight_(
                    12.0, AK.NSFontWeightSemibold if self.selected else AK.NSFontWeightRegular
                ),
                AK.NSForegroundColorAttributeName: AK.NSColor.labelColor()
                if self.selected
                else AK.NSColor.secondaryLabelColor(),
                AK.NSParagraphStyleAttributeName: style,
            },
        )


# -- Window ------------------------------------------------------------------------


class SettingsWindowController(FN.NSObject):
    def initWithOnChange_(self, on_change):
        """``on_change(kind)`` is called after a setting changes ("compression"/"icon")."""
        self = objc.super(SettingsWindowController, self).init()
        if self is None:
            return None
        self.on_change = on_change
        self.window = AK.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            AK.NSMakeRect(0, 0, WIDTH, 300),
            AK.NSWindowStyleMaskTitled | AK.NSWindowStyleMaskClosable,
            AK.NSBackingStoreBuffered,
            False,
        )
        self.window.setReleasedWhenClosed_(False)
        self.window.setToolbarStyle_(AK.NSWindowToolbarStylePreference)
        toolbar = AK.NSToolbar.alloc().initWithIdentifier_("PdfsByKashSettings")
        toolbar.setDelegate_(self)
        toolbar.setAllowsUserCustomization_(False)
        toolbar.setDisplayMode_(AK.NSToolbarDisplayModeIconAndLabel)
        self.window.setToolbar_(toolbar)
        self.panes = {
            PANE_APPEARANCE: self._build_appearance(),
            PANE_COMPRESSION: self._build_compression(),
        }
        last = FN.NSUserDefaults.standardUserDefaults().stringForKey_(LAST_PANE_KEY)
        self.show_pane(str(last) if last in self.panes else PANE_APPEARANCE, animate=False)
        self.window.center()
        return self

    @objc.python_method
    def show(self):
        self.refresh()
        self.window.makeKeyAndOrderFront_(None)
        AK.NSApp.activateIgnoringOtherApps_(True)

    # Toolbar ----------------------------------------------------------------

    def toolbarAllowedItemIdentifiers_(self, toolbar):
        return [PANE_APPEARANCE, PANE_COMPRESSION]

    def toolbarDefaultItemIdentifiers_(self, toolbar):
        return [PANE_APPEARANCE, PANE_COMPRESSION]

    def toolbarSelectableItemIdentifiers_(self, toolbar):
        return [PANE_APPEARANCE, PANE_COMPRESSION]

    def toolbar_itemForItemIdentifier_willBeInsertedIntoToolbar_(self, toolbar, identifier, flag):
        item = AK.NSToolbarItem.alloc().initWithItemIdentifier_(identifier)
        title, symbol = {
            PANE_APPEARANCE: ("Appearance", "paintpalette"),
            PANE_COMPRESSION: ("Compression", "arrow.down.right.and.arrow.up.left"),
        }[str(identifier)]
        item.setLabel_(title)
        item.setImage_(AK.NSImage.imageWithSystemSymbolName_accessibilityDescription_(symbol, title))
        item.setTarget_(self)
        item.setAction_("selectPane:")
        return item

    def selectPane_(self, sender):
        self.show_pane(str(sender.itemIdentifier()))

    @objc.python_method
    def show_pane(self, identifier, animate=True):
        view = self.panes[identifier]
        self.window.toolbar().setSelectedItemIdentifier_(identifier)
        self.window.setTitle_("Appearance" if identifier == PANE_APPEARANCE else "Compression")
        FN.NSUserDefaults.standardUserDefaults().setObject_forKey_(identifier, LAST_PANE_KEY)
        size = view.fittingSize()
        content = self.window.contentRectForFrameRect_(self.window.frame())
        new_content = AK.NSMakeRect(
            content.origin.x, content.origin.y + content.size.height - size.height, WIDTH, size.height
        )
        frame = self.window.frameRectForContentRect_(new_content)
        self.window.setContentView_(AK.NSView.alloc().initWithFrame_(AK.NSZeroRect))
        self.window.setFrame_display_animate_(frame, True, animate and self.window.isVisible())
        self.window.setContentView_(view)

    # Appearance pane ---------------------------------------------------------------

    @objc.python_method
    def _build_appearance(self):
        self.icon_tiles = [IconTile.alloc().initWithIcon_owner_(icon, self) for icon in APP_ICONS]
        rows = [self.icon_tiles[i : i + 4] for i in range(0, len(self.icon_tiles), 4)]
        grid = AK.NSGridView.gridViewWithViews_(rows)
        grid.setRowSpacing_(6)
        grid.setColumnSpacing_(10)

        note = _wrapping(
            "Changes the icon in the Dock and the app switcher right away, and on the "
            "Dock tile while the app is closed. Finder and Launchpad always show Squish: "
            "macOS doesn’t let a signed app change its own file icon.",
            WIDTH - 64,
        )

        self.theme_control = AK.NSSegmentedControl.segmentedControlWithLabels_trackingMode_target_action_(
            ["System", "Light", "Dark"], AK.NSSegmentSwitchTrackingSelectOne, self, "selectTheme:"
        )
        self.theme_control.setAccessibilityLabel_("Theme")
        theme_row = AK.NSStackView.stackViewWithViews_([_label("Theme"), self.theme_control])
        theme_row.setSpacing_(12)

        return self._pane(
            [
                _section_title("App Icon"),
                grid,
                note,
                self._separator(),
                theme_row,
            ],
            custom_spacing={grid: 10, note: 16},
        )

    def chooseIcon_(self, slug):
        prefs.set_app_icon(resolve(slug).slug)
        apply_icon(slug)
        self.refresh()
        self.on_change("icon")

    def moveFocusFrom_key_(self, tile, key):
        index = self.icon_tiles.index(tile)
        delta = {"": -1, "": 1, "": -4, "": 4}[key]
        target = index + delta
        if 0 <= target < len(self.icon_tiles):
            self.window.makeFirstResponder_(self.icon_tiles[target])

    def selectTheme_(self, sender):
        theme = prefs.THEMES[sender.selectedSegment()]
        prefs.set_theme(theme)
        apply_theme(theme)

    # Compression pane ------------------------------------------------------------

    @objc.python_method
    def _build_compression(self):
        self.quality_control = AK.NSSegmentedControl.segmentedControlWithLabels_trackingMode_target_action_(
            list(QUALITY_CONTROL_LABELS), AK.NSSegmentSwitchTrackingSelectOne, self, "changeCompression:"
        )
        self.quality_control.setAccessibilityLabel_("Default quality")
        self.quality_hint = _wrapping("", 300)

        self.destination_popup = AK.NSPopUpButton.alloc().initWithFrame_pullsDown_(AK.NSZeroRect, False)
        self.destination_popup.setTarget_(self)
        self.destination_popup.setAction_("changeDestination:")
        self.destination_popup.setAccessibilityLabel_("Default save location")
        self.destination_popup.widthAnchor().constraintEqualToConstant_(300).setActive_(True)
        self.destination_popup.cell().setLineBreakMode_(AK.NSLineBreakByTruncatingMiddle)

        self.keep_radio = AK.NSButton.radioButtonWithTitle_target_action_(
            "Keep originals", self, "changeCompression:"
        )
        self.replace_radio = AK.NSButton.radioButtonWithTitle_target_action_(
            "Replace originals", self, "changeCompression:"
        )
        keep_hint = _wrapping("Saves a compressed copy. Your files are never touched.", 300)
        replace_hint = _wrapping(
            "Overwrites each file once its smaller version checks out. Old versions go to the Trash.",
            300,
        )
        originals = AK.NSStackView.stackViewWithViews_(
            [self.keep_radio, self._indented(keep_hint), self.replace_radio, self._indented(replace_hint)]
        )
        originals.setOrientation_(AK.NSUserInterfaceLayoutOrientationVertical)
        originals.setAlignment_(AK.NSLayoutAttributeLeading)
        originals.setSpacing_(2)
        originals.setCustomSpacing_afterView_(8, originals.arrangedSubviews()[1])

        self.reveal_checkbox = AK.NSButton.checkboxWithTitle_target_action_(
            "Show compressed files in Finder", self, "changeCompression:"
        )

        quality = AK.NSStackView.stackViewWithViews_([self.quality_control, self.quality_hint])
        quality.setOrientation_(AK.NSUserInterfaceLayoutOrientationVertical)
        quality.setAlignment_(AK.NSLayoutAttributeLeading)
        quality.setSpacing_(4)

        grid = AK.NSGridView.gridViewWithViews_(
            [
                [_label("Quality:"), quality],
                [_label("Save to:"), self.destination_popup],
                [_label("Originals:"), originals],
                [_label("When done:"), self.reveal_checkbox],
            ]
        )
        grid.setRowSpacing_(14)
        grid.setColumnSpacing_(10)
        grid.columnAtIndex_(0).setXPlacement_(AK.NSGridCellPlacementTrailing)
        for row in range(grid.numberOfRows()):
            grid.rowAtIndex_(row).setRowAlignment_(AK.NSGridRowAlignmentFirstBaseline)

        note = _wrapping(
            "Pdfs by Kash starts with these settings each time it opens. Changing them in "
            "the main window only affects the current session.",
            WIDTH - 64,
        )
        return self._pane([grid, self._separator(), note], custom_spacing={grid: 18})

    @objc.python_method
    def _indented(self, view):
        wrapper = AK.NSStackView.stackViewWithViews_([view])
        wrapper.setEdgeInsets_(AK.NSEdgeInsetsMake(0, 18, 0, 0))
        return wrapper

    @objc.python_method
    def _current(self):
        return prefs.compression_defaults()

    def changeCompression_(self, sender):
        current = self._current()
        keep = current.keep_originals
        if sender is self.keep_radio:
            keep = True
        elif sender is self.replace_radio:
            keep = False
        prefs.save_compression_defaults(
            prefs.CompressionDefaults(
                quality_index=self.quality_control.selectedSegment(),
                keep_originals=keep,
                output_folder=current.output_folder,
                use_output_folder=current.use_output_folder,
                reveal_when_done=self.reveal_checkbox.state() == AK.NSControlStateValueOn,
            )
        )
        self.refresh()
        self.on_change("compression")

    def changeDestination_(self, sender):
        current = self._current()
        folder, use_folder = current.output_folder, current.use_output_folder
        tag = sender.selectedItem().tag()
        if tag == TAG_CHOOSE:
            panel = AK.NSOpenPanel.openPanel()
            panel.setCanChooseFiles_(False)
            panel.setCanChooseDirectories_(True)
            panel.setCanCreateDirectories_(True)
            panel.setPrompt_("Choose")
            panel.setMessage_("Choose the default folder for compressed PDFs.")
            if panel.runModal() == AK.NSModalResponseOK:
                folder, use_folder = str(panel.URL().path()), True
        else:
            use_folder = tag == TAG_FOLDER
        prefs.save_compression_defaults(
            prefs.CompressionDefaults(
                current.quality_index, current.keep_originals, folder, use_folder, current.reveal_when_done
            )
        )
        self.refresh()
        self.on_change("compression")

    # Shared --------------------------------------------------------------------------

    @objc.python_method
    def _separator(self):
        box = AK.NSBox.alloc().initWithFrame_(AK.NSZeroRect)
        box.setBoxType_(AK.NSBoxSeparator)
        box.widthAnchor().constraintEqualToConstant_(WIDTH - 64).setActive_(True)
        return box

    @objc.python_method
    def _pane(self, views, custom_spacing=None):
        stack = AK.NSStackView.stackViewWithViews_(views)
        stack.setOrientation_(AK.NSUserInterfaceLayoutOrientationVertical)
        stack.setAlignment_(AK.NSLayoutAttributeLeading)
        stack.setSpacing_(12)
        stack.setEdgeInsets_(AK.NSEdgeInsetsMake(20, 32, 24, 32))
        for view, spacing in (custom_spacing or {}).items():
            stack.setCustomSpacing_afterView_(spacing, view)
        stack.widthAnchor().constraintEqualToConstant_(WIDTH).setActive_(True)
        return stack

    @objc.python_method
    def refresh(self):
        chosen = prefs.app_icon()
        for tile in self.icon_tiles:
            tile.selected = tile.icon.slug == resolve(chosen).slug
            tile.setNeedsDisplay_(True)
        self.theme_control.setSelectedSegment_(prefs.THEMES.index(prefs.theme()))

        current = self._current()
        self.quality_control.setSelectedSegment_(current.quality_index)
        _, _, description = QUALITY_PROFILES[current.quality_index]
        self.quality_hint.setStringValue_(description)
        self.keep_radio.setState_(AK.NSControlStateValueOn if current.keep_originals else AK.NSControlStateValueOff)
        self.replace_radio.setState_(AK.NSControlStateValueOff if current.keep_originals else AK.NSControlStateValueOn)
        self.reveal_checkbox.setState_(
            AK.NSControlStateValueOn if current.reveal_when_done else AK.NSControlStateValueOff
        )

        popup = self.destination_popup
        popup.removeAllItems()
        popup.addItemWithTitle_("Next to each original")
        popup.lastItem().setTag_(TAG_ALONGSIDE)
        if current.output_folder:
            popup.addItemWithTitle_(tilde_path(current.output_folder))
            item = popup.lastItem()
            item.setTag_(TAG_FOLDER)
            icon = AK.NSWorkspace.sharedWorkspace().iconForFile_(current.output_folder)
            icon.setSize_(AK.NSMakeSize(16, 16))
            item.setImage_(icon)
        popup.menu().addItem_(AK.NSMenuItem.separatorItem())
        popup.addItemWithTitle_("Choose Folder…")
        popup.lastItem().setTag_(TAG_CHOOSE)
        popup.selectItemWithTag_(TAG_FOLDER if current.use_output_folder else TAG_ALONGSIDE)
        popup.setEnabled_(current.keep_originals)
