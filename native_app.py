# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Daniel Lares
# Modifications Copyright (C) 2026 Kaschief
#
# Pdfs by Kash is a modified version of FS PDF Compressor by Daniel Lares
# (https://github.com/gitlares/fs-pdf-compressor), distributed under the
# GNU Affero General Public License v3.0 or later.

import os
import threading
import time
from pathlib import Path

import AppKit as AK
import Foundation as FN
import objc
from PyObjCTools import AppHelper

from fs_pdf_compressor.batch import BatchSummary
from fs_pdf_compressor.compression_queue import (
    CompressionQueue,
    Compressed,
    Compressing,
    Failed,
    state_from_result,
)
from fs_pdf_compressor.core import (
    APP_NAME,
    QUALITY_CONTROL_LABELS,
    QUALITY_PROFILES,
    bundle_contents_dir,
    compress_pdf,
    expand_pdf_paths,
    planned_output_path,
    tilde_path,
)
from fs_pdf_compressor.macos_drop_zone import DropZonePanel
from fs_pdf_compressor.macos_login_item import (
    current_state as login_item_state,
    open_login_items_settings,
    set_enabled as set_login_item_enabled,
)
from fs_pdf_compressor.macos_update_probe import probe_for_update
from fs_pdf_compressor.macos_views import DropCanvas, QueueTableController
from fs_pdf_compressor.version import APP_VERSION

UPSTREAM_NAME = "FS PDF Compressor"
UPSTREAM_URL = "https://github.com/gitlares/fs-pdf-compressor"
REPOSITORY_URL = "https://github.com/kaschief/pdfs-by-kash"
URL_SCHEME = "pdfsbykash"
DROP_ZONE_DEFAULTS_KEY = "DropZoneEnabled"
ORIGINALS_MODE_DEFAULTS_KEY = "OriginalsMode"
QUALITY_DEFAULTS_KEY = "QualityIndex"
OUTPUT_FOLDER_DEFAULTS_KEY = "OutputFolder"
USE_OUTPUT_FOLDER_DEFAULTS_KEY = "UseOutputFolder"
SKIP_REPLACE_CONFIRMATION_DEFAULTS_KEY = "SkipReplaceConfirmation"
SPARKLE_PROBE_LAST_CHECK_KEY = "SparkleLightweightProbeLastCheck"
SPARKLE_PROBE_INTERVAL = 86_400.0
SPARKLE_PROBE_TIMEOUT = 5.0

TAG_ALONGSIDE = 0
TAG_FOLDER = 1
TAG_CHOOSE = 2
TAG_IN_PLACE = 3


def load_sparkle_updater(start: bool = True):
    """Load the bundled Sparkle framework without making it a Python dependency."""
    contents_dir = bundle_contents_dir()
    if contents_dir is None:
        return None
    framework = contents_dir / "Frameworks" / "Sparkle.framework"
    if not framework.is_dir():
        return None
    try:
        objc.loadBundle("Sparkle", globals(), bundle_path=str(framework))
        controller_class = objc.lookUpClass("SPUStandardUpdaterController")
        return controller_class.alloc().initWithStartingUpdater_updaterDelegate_userDriverDelegate_(
            start, None, None
        )
    except Exception:
        return None


class PDFCompressorController(FN.NSObject):
    """Main window: queue PDFs, review settings, then compress on request."""

    FOOTER_HEIGHT = 52.0
    SETTINGS_HEIGHT = 40.0

    def init(self):
        self = objc.super(PDFCompressorController, self).init()
        if self is None:
            return None
        defaults = FN.NSUserDefaults.standardUserDefaults()
        defaults.registerDefaults_(
            {
                ORIGINALS_MODE_DEFAULTS_KEY: "keep",
                QUALITY_DEFAULTS_KEY: 1,
                OUTPUT_FOLDER_DEFAULTS_KEY: "",
                USE_OUTPUT_FOLDER_DEFAULTS_KEY: False,
            }
        )
        self.queue = CompressionQueue()
        self.batch_paths = []
        self.batch_done = 0
        self.processing = False
        self.drop_zone = None
        self.quality_index = max(
            0, min(len(QUALITY_PROFILES) - 1, defaults.integerForKey_(QUALITY_DEFAULTS_KEY))
        )
        self.keep_originals = defaults.stringForKey_(ORIGINALS_MODE_DEFAULTS_KEY) != "replace"
        folder = defaults.stringForKey_(OUTPUT_FOLDER_DEFAULTS_KEY) or ""
        self.output_folder = str(folder) if folder else None
        self.use_output_folder = bool(
            self.output_folder and defaults.boolForKey_(USE_OUTPUT_FOLDER_DEFAULTS_KEY)
        )
        self._build_window()
        self.refresh()
        return self

    # -- Derived state ---------------------------------------------------------------

    @property
    def showing_results(self):
        return len(self.queue) > 0

    @objc.python_method
    def bottom_chrome_height(self):
        return self.FOOTER_HEIGHT + self.SETTINGS_HEIGHT

    @objc.python_method
    def effective_output_dir(self):
        if self.keep_originals and self.use_output_folder and self.output_folder:
            return self.output_folder
        return None

    @objc.python_method
    def planned_output_for(self, path):
        return planned_output_path(path, self.keep_originals, self.effective_output_dir())

    @objc.python_method
    def can_remove(self, row):
        if row < 0 or row >= len(self.queue):
            return False
        item = self.queue[row]
        if isinstance(item.state, Compressing):
            return False
        # Rows waiting in the running batch stay put so the worker's list holds.
        return not (self.processing and item.path in self.batch_paths)

    # -- Window ---------------------------------------------------------------------

    def _build_window(self):
        style = (
            AK.NSWindowStyleMaskTitled
            | AK.NSWindowStyleMaskClosable
            | AK.NSWindowStyleMaskMiniaturizable
            | AK.NSWindowStyleMaskResizable
        )
        self.window = AK.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            AK.NSMakeRect(0, 0, 720, 440), style, AK.NSBackingStoreBuffered, False
        )
        self.window.setTitle_(APP_NAME)
        self.window.setMinSize_(AK.NSMakeSize(660, 380))
        self.window.setReleasedWhenClosed_(False)
        self.window.setDelegate_(self)
        self.window.setFrameAutosaveName_("Pdfs by Kash Main Window")
        self.window.center()

        self.canvas = DropCanvas.alloc().initWithFrame_controller_(
            AK.NSMakeRect(0, 0, 720, 440), self
        )
        self.window.setContentView_(self.canvas)

        self.table_controller = QueueTableController.alloc().initWithController_(self)
        self.results_scroll = AK.NSScrollView.alloc().initWithFrame_(AK.NSZeroRect)
        self.results_scroll.setBorderType_(AK.NSNoBorder)
        self.results_scroll.setHasVerticalScroller_(True)
        self.results_scroll.setAutohidesScrollers_(True)
        self.results_scroll.setDrawsBackground_(False)
        self.results_scroll.setDocumentView_(self.table_controller.table)
        self.canvas.addSubview_(self.results_scroll)

        self._build_settings_bar()
        self._build_footer()
        self.layout_controls()

    @objc.python_method
    def _small_label(self, text):
        label = AK.NSTextField.labelWithString_(text)
        label.setFont_(AK.NSFont.systemFontOfSize_(12.0))
        label.setTextColor_(AK.NSColor.secondaryLabelColor())
        return label

    @objc.python_method
    def _build_settings_bar(self):
        self.settings_bar = AK.NSVisualEffectView.alloc().initWithFrame_(AK.NSZeroRect)
        self.settings_bar.setMaterial_(AK.NSVisualEffectMaterialUnderWindowBackground)
        self.settings_bar.setBlendingMode_(AK.NSVisualEffectBlendingModeWithinWindow)
        self.canvas.addSubview_(self.settings_bar)

        self.settings_separator = AK.NSBox.alloc().initWithFrame_(AK.NSZeroRect)
        self.settings_separator.setBoxType_(AK.NSBoxSeparator)
        self.settings_bar.addSubview_(self.settings_separator)

        self.destination_popup = AK.NSPopUpButton.alloc().initWithFrame_pullsDown_(
            AK.NSZeroRect, False
        )
        self.destination_popup.setControlSize_(AK.NSControlSizeSmall)
        self.destination_popup.setFont_(AK.NSFont.systemFontOfSize_(12.0))
        self.destination_popup.setTarget_(self)
        self.destination_popup.setAction_("selectDestination:")
        self.destination_popup.cell().setLineBreakMode_(AK.NSLineBreakByTruncatingMiddle)
        self.destination_popup.setAccessibilityLabel_("Save compressed PDFs to")

        self.originals_control = AK.NSSegmentedControl.segmentedControlWithLabels_trackingMode_target_action_(
            ["Keep", "Replace"],
            AK.NSSegmentSwitchTrackingSelectOne,
            self,
            "selectOriginalsMode:",
        )
        self.originals_control.setControlSize_(AK.NSControlSizeSmall)
        self.originals_control.setFont_(AK.NSFont.systemFontOfSize_(12.0))
        self.originals_control.setToolTip_forSegment_(
            "Keep the original PDFs untouched and save compressed copies.", 0
        )
        self.originals_control.setToolTip_forSegment_(
            "Overwrite each original with its compressed version once the new file is "
            "verified. The previous version goes to the Trash.",
            1,
        )
        self.originals_control.setAccessibilityLabel_("Original files")

        self.quality_popup = AK.NSPopUpButton.alloc().initWithFrame_pullsDown_(
            AK.NSZeroRect, False
        )
        self.quality_popup.setControlSize_(AK.NSControlSizeSmall)
        self.quality_popup.setFont_(AK.NSFont.systemFontOfSize_(12.0))
        for index, (label, _, description) in enumerate(QUALITY_PROFILES):
            self.quality_popup.addItemWithTitle_(QUALITY_CONTROL_LABELS[index])
            item = self.quality_popup.lastItem()
            item.setToolTip_(f"{label} — {description}")
            item.setTag_(index)
        self.quality_popup.setTarget_(self)
        self.quality_popup.setAction_("selectQuality:")
        self.quality_popup.setAccessibilityLabel_("Compression quality")

        self.save_label = self._small_label("Save to")
        self.originals_label = self._small_label("Originals")
        self.quality_label = self._small_label("Quality")

        self.settings_stack = AK.NSStackView.stackViewWithViews_(
            [
                self.save_label,
                self.destination_popup,
                self.originals_label,
                self.originals_control,
                self.quality_label,
                self.quality_popup,
            ]
        )
        self.settings_stack.setSpacing_(6)
        self.settings_stack.setCustomSpacing_afterView_(18, self.destination_popup)
        self.settings_stack.setCustomSpacing_afterView_(18, self.originals_control)
        self.settings_stack.setAlignment_(AK.NSLayoutAttributeCenterY)
        self.destination_popup.setContentCompressionResistancePriority_forOrientation_(
            AK.NSLayoutPriorityDefaultLow, AK.NSLayoutConstraintOrientationHorizontal
        )
        self.destination_popup.setContentHuggingPriority_forOrientation_(
            AK.NSLayoutPriorityDefaultLow, AK.NSLayoutConstraintOrientationHorizontal
        )
        self.settings_bar.addSubview_(self.settings_stack)
        # Long folder paths truncate in the middle instead of pushing the
        # Originals/Quality controls out of the window; hover shows the full path.
        self.destination_popup.widthAnchor().constraintLessThanOrEqualToConstant_(250).setActive_(True)

    @objc.python_method
    def _build_footer(self):
        self.footer = AK.NSVisualEffectView.alloc().initWithFrame_(AK.NSZeroRect)
        self.footer.setMaterial_(AK.NSVisualEffectMaterialUnderWindowBackground)
        self.footer.setBlendingMode_(AK.NSVisualEffectBlendingModeWithinWindow)
        self.footer.setState_(AK.NSVisualEffectStateFollowsWindowActiveState)
        self.canvas.addSubview_(self.footer)

        self.separator = AK.NSBox.alloc().initWithFrame_(AK.NSZeroRect)
        self.separator.setBoxType_(AK.NSBoxSeparator)
        self.footer.addSubview_(self.separator)

        self.add_button = AK.NSButton.alloc().initWithFrame_(AK.NSZeroRect)
        self.add_button.setBezelStyle_(AK.NSBezelStyleRounded)
        self.add_button.setImage_(
            AK.NSImage.imageWithSystemSymbolName_accessibilityDescription_(
                "plus", "Add PDFs"
            )
        )
        self.add_button.setImagePosition_(AK.NSImageOnly)
        self.add_button.setToolTip_("Add PDFs or folders to the list (⌘O)")
        self.add_button.setTarget_(self)
        self.add_button.setAction_("chooseFiles:")
        self.footer.addSubview_(self.add_button)

        self.status_label = AK.NSTextField.labelWithString_("")
        self.status_label.setFont_(AK.NSFont.systemFontOfSize_(12.0))
        self.status_label.setLineBreakMode_(AK.NSLineBreakByTruncatingTail)
        self.footer.addSubview_(self.status_label)

        self.progress = AK.NSProgressIndicator.alloc().initWithFrame_(AK.NSZeroRect)
        self.progress.setStyle_(AK.NSProgressIndicatorStyleBar)
        self.progress.setIndeterminate_(False)
        self.progress.setMinValue_(0)
        self.progress.setMaxValue_(100)
        self.progress.setHidden_(True)
        self.footer.addSubview_(self.progress)

        self.clear_button = AK.NSButton.buttonWithTitle_target_action_(
            "Clear", self, "clearList:"
        )
        self.clear_button.setBezelStyle_(AK.NSBezelStyleRounded)
        self.clear_button.setToolTip_("Remove all files from the list (files on disk are not touched)")
        self.footer.addSubview_(self.clear_button)

        self.compress_button = AK.NSButton.buttonWithTitle_target_action_(
            "Compress", self, "compress:"
        )
        self.compress_button.setBezelStyle_(AK.NSBezelStyleRounded)
        self.compress_button.setKeyEquivalent_("\r")
        self.footer.addSubview_(self.compress_button)

    def layout_controls(self):
        bounds = self.canvas.bounds()
        width = bounds.size.width
        height = bounds.size.height
        footer_height = self.FOOTER_HEIGHT
        settings_height = self.SETTINGS_HEIGHT
        bottom = footer_height + settings_height

        self.footer.setFrame_(AK.NSMakeRect(0, 0, width, footer_height))
        self.separator.setFrame_(AK.NSMakeRect(0, footer_height - 1, width, 1))
        self.settings_bar.setFrame_(AK.NSMakeRect(0, footer_height, width, settings_height))
        self.settings_separator.setFrame_(AK.NSMakeRect(0, settings_height - 1, width, 1))
        stack_width = width - 28
        self.settings_stack.setFrame_(
            AK.NSMakeRect(14, (settings_height - 24) / 2, stack_width, 24)
        )
        self.results_scroll.setFrame_(AK.NSMakeRect(0, bottom, width, height - bottom))

        control_y = (footer_height - 28) / 2
        self.add_button.setFrame_(AK.NSMakeRect(14, control_y, 34, 28))

        right = width - 14
        self.compress_button.sizeToFit()
        compress_width = max(104, self.compress_button.frame().size.width + 12)
        self.compress_button.setFrame_(
            AK.NSMakeRect(right - compress_width, control_y, compress_width, 28)
        )
        right -= compress_width + 8
        if not self.clear_button.isHidden():
            self.clear_button.setFrame_(AK.NSMakeRect(right - 70, control_y, 70, 28))
            right -= 78
        if not self.progress.isHidden():
            self.progress.setFrame_(
                AK.NSMakeRect(right - 120, (footer_height - 4) / 2, 120, 4)
            )
            right -= 130

        label_x = 58
        label_y = (footer_height - 20) / 2 - 2
        self.status_label.setFrame_(
            AK.NSMakeRect(label_x, label_y, max(90, right - label_x), 20)
        )
        self.canvas.setNeedsDisplay_(True)

    def windowDidResize_(self, notification):
        self.layout_controls()

    # -- Refresh: one place that maps state → controls ---------------------------------

    @objc.python_method
    def refresh(self):
        self._refresh_destination_popup()
        self.originals_control.setSelectedSegment_(0 if self.keep_originals else 1)
        self.quality_popup.selectItemWithTag_(self.quality_index)

        idle = not self.processing
        for control in (self.destination_popup, self.originals_control, self.quality_popup):
            control.setEnabled_(idle)
        self.destination_popup.setEnabled_(idle and self.keep_originals)

        has_pending = self.queue.has_pending
        again = not has_pending and self.queue.has_finished
        self.compress_button.setTitle_("Compress Again" if again else "Compress")
        self.compress_button.setEnabled_(idle and (has_pending or again))
        self.compress_button.setToolTip_(
            "Compress the finished files again with the current settings"
            if again
            else "Compress every pending file in the list (Return)"
        )
        self.clear_button.setHidden_(not (idle and len(self.queue) > 0))
        self.progress.setHidden_(idle)

        if self.processing:
            total = len(self.batch_paths)
            status = f"Compressing {min(self.batch_done + 1, total)} of {total}…"
        else:
            status = self.queue.summary_text()
        self.status_label.setStringValue_(status)
        self.status_label.setToolTip_(status)

        self.results_scroll.setHidden_(not self.showing_results)
        self.table_controller.reload()
        self.layout_controls()

    @objc.python_method
    def _refresh_destination_popup(self):
        popup = self.destination_popup
        popup.removeAllItems()
        if not self.keep_originals:
            popup.addItemWithTitle_("Original files (replaced in place)")
            popup.lastItem().setTag_(TAG_IN_PLACE)
            popup.setToolTip_(
                "Each compressed PDF overwrites its original; the old version goes to the Trash."
            )
            return

        popup.addItemWithTitle_("Same folder as each original")
        popup.lastItem().setTag_(TAG_ALONGSIDE)
        popup.lastItem().setToolTip_("Saved next to the original as “name compressed.pdf”.")
        if self.output_folder:
            popup.addItemWithTitle_(tilde_path(self.output_folder))
            item = popup.lastItem()
            item.setTag_(TAG_FOLDER)
            item.setToolTip_(self.output_folder)
            icon = AK.NSWorkspace.sharedWorkspace().iconForFile_(self.output_folder)
            icon.setSize_(AK.NSMakeSize(16, 16))
            item.setImage_(icon)
        popup.menu().addItem_(AK.NSMenuItem.separatorItem())
        popup.addItemWithTitle_("Choose Folder…")
        popup.lastItem().setTag_(TAG_CHOOSE)

        if self.use_output_folder and self.output_folder:
            popup.selectItemWithTag_(TAG_FOLDER)
            popup.setToolTip_(f"Compressed copies are saved in:\n{self.output_folder}")
        else:
            popup.selectItemWithTag_(TAG_ALONGSIDE)
            popup.setToolTip_(
                "Compressed copies are saved next to each original as “name compressed.pdf”."
            )

    # -- Adding files ------------------------------------------------------------------

    def handle_drop_urls(self, urls):
        self.add_paths([str(url.path()) for url in urls if url.isFileURL()])

    @objc.python_method
    def add_paths(self, paths):
        """Queue PDFs (folders are searched). Never starts compression."""
        if not paths:
            return False
        self.status_label.setStringValue_("Finding PDFs…")
        threading.Thread(target=self._discover_paths, args=(list(paths),), daemon=True).start()
        return True

    @objc.python_method
    def _discover_paths(self, paths):
        try:
            pdfs = expand_pdf_paths(paths)
        except Exception:
            AppHelper.callAfter(self._discovery_finished, [], True)
        else:
            AppHelper.callAfter(self._discovery_finished, pdfs, False)

    @objc.python_method
    def _discovery_finished(self, pdfs, failed):
        # Never disturb rows that are part of the running batch.
        addable = [p for p in pdfs if not (self.processing and p in self.batch_paths)]
        added = self.queue.add(addable)
        self.refresh()
        if not pdfs:
            self.status_label.setStringValue_(
                "Could not read that folder" if failed else "No PDFs found in what you added"
            )
        elif not added:
            self.status_label.setStringValue_("Those PDFs are already in the list")

    @objc.python_method
    def start_drop_zone_paths(self, paths):
        accepted = self.add_paths(paths)
        if accepted:
            self.show_main_window()
        return accepted

    def show_main_window(self):
        self.window.makeKeyAndOrderFront_(None)
        AK.NSApp.activateIgnoringOtherApps_(True)

    def chooseFiles_(self, sender):
        panel = AK.NSOpenPanel.openPanel()
        panel.setCanChooseFiles_(True)
        panel.setCanChooseDirectories_(True)
        panel.setAllowsMultipleSelection_(True)
        panel.setAllowedFileTypes_(["pdf"])
        panel.setPrompt_("Add")
        panel.setMessage_("Choose PDFs or folders to add to the list.")
        if panel.runModal() == AK.NSModalResponseOK:
            self.add_paths([str(url.path()) for url in panel.URLs()])

    # -- Removing / revealing --------------------------------------------------------------

    @objc.python_method
    def remove_rows(self, rows):
        if self.queue.remove(r for r in rows if self.can_remove(r)):
            self.table_controller.table.deselectAll_(None)
            self.refresh()

    def clearList_(self, sender):
        if self.processing:
            return
        self.queue.clear()
        self.refresh()

    @objc.python_method
    def reveal_rows(self, rows):
        urls = []
        for row in rows:
            if 0 <= row < len(self.queue):
                state = self.queue[row].state
                if isinstance(state, Compressed) and os.path.exists(state.output_path):
                    urls.append(FN.NSURL.fileURLWithPath_(state.output_path))
        if urls:
            AK.NSWorkspace.sharedWorkspace().activateFileViewerSelectingURLs_(urls)

    # -- Settings ----------------------------------------------------------------------

    def selectDestination_(self, sender):
        tag = sender.selectedItem().tag()
        if tag == TAG_CHOOSE:
            panel = AK.NSOpenPanel.openPanel()
            panel.setCanChooseFiles_(False)
            panel.setCanChooseDirectories_(True)
            panel.setCanCreateDirectories_(True)
            panel.setPrompt_("Save Here")
            panel.setMessage_("Choose where compressed PDFs should be saved.")
            if self.output_folder:
                panel.setDirectoryURL_(FN.NSURL.fileURLWithPath_(self.output_folder))
            if panel.runModal() == AK.NSModalResponseOK:
                self.output_folder = str(panel.URL().path())
                self.use_output_folder = True
        else:
            self.use_output_folder = tag == TAG_FOLDER
        defaults = FN.NSUserDefaults.standardUserDefaults()
        defaults.setObject_forKey_(self.output_folder or "", OUTPUT_FOLDER_DEFAULTS_KEY)
        defaults.setBool_forKey_(self.use_output_folder, USE_OUTPUT_FOLDER_DEFAULTS_KEY)
        self.refresh()

    def selectOriginalsMode_(self, sender):
        self.keep_originals = sender.selectedSegment() == 0
        FN.NSUserDefaults.standardUserDefaults().setObject_forKey_(
            "keep" if self.keep_originals else "replace", ORIGINALS_MODE_DEFAULTS_KEY
        )
        self.refresh()

    def selectQuality_(self, sender):
        self.quality_index = sender.selectedItem().tag()
        FN.NSUserDefaults.standardUserDefaults().setInteger_forKey_(
            self.quality_index, QUALITY_DEFAULTS_KEY
        )

    # -- Compressing ---------------------------------------------------------------------

    def compress_(self, sender):
        if self.processing:
            return
        if not self.queue.has_pending:
            self.queue.requeue_finished()
        paths = self.queue.pending_paths
        if not paths:
            self.refresh()
            return
        if not self.keep_originals and not self._confirm_replace(len(paths)):
            return
        self.batch_paths = paths
        self.batch_done = 0
        self.processing = True
        self.progress.setDoubleValue_(0)
        self.refresh()

        _, setting, _ = QUALITY_PROFILES[self.quality_index]
        threading.Thread(
            target=self._compress_worker,
            args=(list(paths), setting, self.keep_originals, self.effective_output_dir()),
            daemon=True,
        ).start()

    @objc.python_method
    def _confirm_replace(self, count):
        defaults = FN.NSUserDefaults.standardUserDefaults()
        if defaults.boolForKey_(SKIP_REPLACE_CONFIRMATION_DEFAULTS_KEY):
            return True
        alert = AK.NSAlert.alloc().init()
        noun = "PDF" if count == 1 else f"{count} PDFs"
        alert.setMessageText_(f"Replace {noun} with compressed versions?")
        alert.setInformativeText_(
            "Each original is only replaced after its compressed version has been "
            "created and verified. The previous versions are moved to the Trash."
        )
        alert.addButtonWithTitle_("Replace Originals")
        alert.addButtonWithTitle_("Cancel")
        alert.setShowsSuppressionButton_(True)
        alert.suppressionButton().setTitle_("Don’t ask again")
        response = alert.runModal()
        if alert.suppressionButton().state() == AK.NSControlStateValueOn:
            defaults.setBool_forKey_(True, SKIP_REPLACE_CONFIRMATION_DEFAULTS_KEY)
        return response == AK.NSAlertFirstButtonReturn

    @objc.python_method
    def _compress_worker(self, paths, setting, keep_original, output_dir):
        try:
            for path in paths:
                AppHelper.callAfter(self._mark_compressing, path)
                try:
                    status, metrics = compress_pdf(path, setting, keep_original, output_dir)
                except Exception:
                    status, metrics = f"{Path(path).name} — compression failed", None
                AppHelper.callAfter(self._update_result, path, status, metrics)
        finally:
            AppHelper.callAfter(self._finish_compression)

    @objc.python_method
    def _mark_compressing(self, path):
        self.queue.set_state(path, Compressing())
        self.refresh()

    @objc.python_method
    def _update_result(self, path, status, metrics):
        self.queue.set_state(path, state_from_result(status, metrics))
        self.batch_done += 1
        total = len(self.batch_paths)
        self.progress.setDoubleValue_(self.batch_done / total * 100 if total else 100)
        if self.drop_zone is not None:
            self.drop_zone.batch_progress(self.batch_done, total)
        self.refresh()

    @objc.python_method
    def _finish_compression(self):
        self.processing = False
        # Anything still marked Compressing (e.g. an unexpected worker crash) failed.
        for path in self.batch_paths:
            index = self.queue.index_of(path)
            if index is not None and isinstance(self.queue[index].state, Compressing):
                self.queue.set_state(path, Failed("Compression was interrupted"))
        batch = set(self.batch_paths)
        metrics = [
            {
                "original_size": item.original_size,
                "saved_size": item.original_size - item.state.new_size,
            }
            for item in self.queue.items
            if item.path in batch and isinstance(item.state, Compressed)
        ]
        self.batch_paths = []
        self.refresh()
        if self.drop_zone is not None:
            self.drop_zone.batch_finished(BatchSummary.from_metrics(metrics))


class AppDelegate(FN.NSObject):
    def init(self):
        self = objc.super(AppDelegate, self).init()
        if self is None:
            return None
        self.controller = None
        self.updater_controller = None
        self._update_probe_thread = None
        self._update_probe_timer = None
        self._pending_quick_action_paths = []
        return self

    def applicationDidFinishLaunching_(self, notification):
        self.drop_zone_panel = None
        self._build_main_menu()
        self.controller = PDFCompressorController.alloc().init()
        if FN.NSUserDefaults.standardUserDefaults().boolForKey_(
            DROP_ZONE_DEFAULTS_KEY
        ):
            self._set_drop_zone_enabled(True)
        self.controller.window.makeKeyAndOrderFront_(None)
        AK.NSApp.activateIgnoringOtherApps_(True)
        if self._pending_quick_action_paths:
            self.controller.add_paths(self._pending_quick_action_paths)
            self._pending_quick_action_paths = []
        self._schedule_automatic_update_probe()

    def _sparkle_feed_url(self):
        feed_url = FN.NSBundle.mainBundle().objectForInfoDictionaryKey_("SUFeedURL")
        return str(feed_url) if feed_url else None

    def _ensure_sparkle_updater(self):
        if self.updater_controller is None:
            self.updater_controller = load_sparkle_updater()
        return self.updater_controller

    def _schedule_automatic_update_probe(self):
        if self._sparkle_feed_url() is None:
            return
        self._update_probe_timer = (
            FN.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                SPARKLE_PROBE_INTERVAL,
                self,
                "runAutomaticUpdateProbe:",
                None,
                True,
            )
        )
        self._start_automatic_update_probe_if_due()

    def runAutomaticUpdateProbe_(self, timer):
        self._start_automatic_update_probe_if_due()

    def _start_automatic_update_probe_if_due(self):
        if self.updater_controller is not None or self._update_probe_thread is not None:
            return
        feed_url = self._sparkle_feed_url()
        if feed_url is None:
            return
        defaults = FN.NSUserDefaults.standardUserDefaults()
        last_check = defaults.doubleForKey_(SPARKLE_PROBE_LAST_CHECK_KEY)
        if last_check and time.time() - last_check < SPARKLE_PROBE_INTERVAL:
            return
        self._update_probe_thread = threading.Thread(
            target=self._automatic_update_probe_worker,
            args=(feed_url,),
            daemon=True,
        )
        self._update_probe_thread.start()

    def _automatic_update_probe_worker(self, feed_url):
        result = probe_for_update(
            feed_url,
            APP_VERSION,
            timeout=SPARKLE_PROBE_TIMEOUT,
        )
        AppHelper.callAfter(self._finish_automatic_update_probe, result)

    def _finish_automatic_update_probe(self, result):
        self._update_probe_thread = None
        if result is None:
            return
        FN.NSUserDefaults.standardUserDefaults().setDouble_forKey_(
            time.time(), SPARKLE_PROBE_LAST_CHECK_KEY
        )
        if not result:
            return
        updater_controller = self._ensure_sparkle_updater()
        if updater_controller is None:
            return
        try:
            updater = updater_controller.updater()
            if updater.automaticallyChecksForUpdates():
                updater.checkForUpdatesInBackground()
        except Exception:
            pass

    def application_openURLs_(self, application, urls):
        """Queue PDF selections sent by the Finder Quick Action (never auto-compresses)."""
        paths = []
        for url in urls:
            if url.isFileURL():
                paths.append(str(url.path()))
                continue
            if url.scheme() != URL_SCHEME or url.host() != "compress":
                continue
            components = FN.NSURLComponents.componentsWithURL_resolvingAgainstBaseURL_(
                url, False
            )
            for item in components.queryItems() or []:
                if item.name() != "bookmark" or not item.value():
                    continue
                bookmark = FN.NSData.alloc().initWithBase64EncodedString_options_(
                    item.value(), 0
                )
                if bookmark is None:
                    continue
                resolved_url, _stale, error = (
                    FN.NSURL.URLByResolvingBookmarkData_options_relativeToURL_bookmarkDataIsStale_error_(
                        bookmark, 0, None, None, None
                    )
                )
                if resolved_url is not None and error is None and resolved_url.isFileURL():
                    paths.append(str(resolved_url.path()))
        if self.controller is None:
            self._pending_quick_action_paths.extend(paths)
            return
        self.controller.show_main_window()
        self.controller.add_paths(paths)

    def _build_main_menu(self):
        main_menu = AK.NSMenu.alloc().init()
        application_item = AK.NSMenuItem.alloc().init()
        main_menu.addItem_(application_item)

        application_menu = AK.NSMenu.alloc().initWithTitle_(APP_NAME)
        about_item = AK.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            f"About {APP_NAME}", "showAbout:", ""
        )
        about_item.setTarget_(self)
        application_menu.addItem_(about_item)

        application_menu.addItem_(AK.NSMenuItem.separatorItem())

        self.drop_zone_item = AK.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Show Drop Zone", "toggleDropZone:", ""
        )
        self.drop_zone_item.setTarget_(self)
        self.drop_zone_item.setState_(
            AK.NSControlStateValueOn
            if FN.NSUserDefaults.standardUserDefaults().boolForKey_(
                DROP_ZONE_DEFAULTS_KEY
            )
            else AK.NSControlStateValueOff
        )
        application_menu.addItem_(self.drop_zone_item)

        self.launch_at_login_item = (
            AK.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "Launch at Login", "toggleLaunchAtLogin:", ""
            )
        )
        self.launch_at_login_item.setTarget_(self)
        self._refresh_launch_at_login_item()
        application_menu.addItem_(self.launch_at_login_item)
        application_menu.addItem_(AK.NSMenuItem.separatorItem())

        hide_item = AK.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            f"Hide {APP_NAME}", "hide:", "h"
        )
        application_menu.addItem_(hide_item)
        application_menu.addItem_(AK.NSMenuItem.separatorItem())

        quit_item = AK.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            f"Quit {APP_NAME}", "terminate:", "q"
        )
        application_menu.addItem_(quit_item)
        application_item.setSubmenu_(application_menu)

        file_item = AK.NSMenuItem.alloc().init()
        main_menu.addItem_(file_item)
        file_menu = AK.NSMenu.alloc().initWithTitle_("File")
        add_item = file_menu.addItemWithTitle_action_keyEquivalent_(
            "Add PDFs…", "chooseFiles:", "o"
        )
        add_item.setTarget_(self.controller)
        compress_item = file_menu.addItemWithTitle_action_keyEquivalent_(
            "Compress", "compress:", "\r"
        )
        compress_item.setTarget_(self.controller)
        file_menu.addItem_(AK.NSMenuItem.separatorItem())
        clear_item = file_menu.addItemWithTitle_action_keyEquivalent_(
            "Clear List", "clearList:", ""
        )
        clear_item.setTarget_(self.controller)
        file_menu.addItem_(AK.NSMenuItem.separatorItem())
        file_menu.addItemWithTitle_action_keyEquivalent_("Close Window", "performClose:", "w")
        file_item.setSubmenu_(file_menu)

        edit_item = AK.NSMenuItem.alloc().init()
        main_menu.addItem_(edit_item)
        edit_menu = AK.NSMenu.alloc().initWithTitle_("Edit")
        edit_menu.addItemWithTitle_action_keyEquivalent_("Select All", "selectAll:", "a")
        edit_item.setSubmenu_(edit_menu)
        AK.NSApp.setMainMenu_(main_menu)

    def showAbout_(self, sender):
        text = (
            "Queue PDFs, review, then compress — locally, with Ghostscript.\n\n"
            f"Based on {UPSTREAM_NAME} by Daniel Lares.\n"
            "Modified by Kaschief.\n\n"
            "No warranty · GNU AGPL v3\n"
            f"Source  ·  Original project\n"
            "Ghostscript"
        )
        credits = FN.NSMutableAttributedString.alloc().initWithString_(text)
        full_range = FN.NSMakeRange(0, len(text))
        credits.addAttribute_value_range_(
            AK.NSFontAttributeName, AK.NSFont.systemFontOfSize_(11.5), full_range
        )
        credits.addAttribute_value_range_(
            AK.NSForegroundColorAttributeName,
            AK.NSColor.secondaryLabelColor(),
            full_range,
        )

        paragraph = AK.NSMutableParagraphStyle.alloc().init()
        paragraph.setAlignment_(AK.NSTextAlignmentCenter)
        paragraph.setLineSpacing_(2.0)
        credits.addAttribute_value_range_(
            AK.NSParagraphStyleAttributeName, paragraph, full_range
        )

        links = {
            "Source": REPOSITORY_URL,
            "Original project": UPSTREAM_URL,
            "Ghostscript": "https://ghostscript.com/licensing/",
            "GNU AGPL v3": "https://www.gnu.org/licenses/agpl-3.0.html",
        }
        for label, url in links.items():
            start = text.rindex(label)
            link_range = FN.NSMakeRange(start, len(label))
            credits.addAttribute_value_range_(
                AK.NSLinkAttributeName, FN.NSURL.URLWithString_(url), link_range
            )
            credits.addAttribute_value_range_(
                AK.NSForegroundColorAttributeName, AK.NSColor.linkColor(), link_range
            )

        AK.NSApp.orderFrontStandardAboutPanelWithOptions_(
            {
                AK.NSAboutPanelOptionApplicationName: APP_NAME,
                AK.NSAboutPanelOptionApplicationVersion: APP_VERSION,
                AK.NSAboutPanelOptionVersion: "",
                AK.NSAboutPanelOptionCredits: credits,
            }
        )

    def toggleDropZone_(self, sender):
        enabled = sender.state() != AK.NSControlStateValueOn
        self._set_drop_zone_enabled(enabled)
        FN.NSUserDefaults.standardUserDefaults().setBool_forKey_(
            enabled, DROP_ZONE_DEFAULTS_KEY
        )

    def toggleLaunchAtLogin_(self, sender):
        enabled = not login_item_state().enabled
        success, error = set_login_item_enabled(enabled)
        self._refresh_launch_at_login_item()
        if not success:
            alert = AK.NSAlert.alloc().init()
            alert.setMessageText_("Could not change Launch at Login")
            alert.setInformativeText_(error or "macOS rejected the change.")
            alert.runModal()
            return
        if login_item_state().requires_approval:
            alert = AK.NSAlert.alloc().init()
            alert.setMessageText_("Approve Launch at Login")
            alert.setInformativeText_(
                "macOS requires your approval in System Settings before "
                f"{APP_NAME} can open automatically."
            )
            alert.addButtonWithTitle_("Open System Settings")
            alert.addButtonWithTitle_("Later")
            if alert.runModal() == AK.NSAlertFirstButtonReturn:
                open_login_items_settings()

    def _refresh_launch_at_login_item(self):
        state = login_item_state()
        self.launch_at_login_item.setState_(
            AK.NSControlStateValueOn
            if state.enabled
            else AK.NSControlStateValueOff
        )

    def _set_drop_zone_enabled(self, enabled):
        self.drop_zone_item.setState_(
            AK.NSControlStateValueOn
            if enabled
            else AK.NSControlStateValueOff
        )
        if enabled:
            if self.drop_zone_panel is None:
                self.drop_zone_panel = DropZonePanel.alloc().initWithController_(
                    self.controller
                )
            self.controller.drop_zone = self.drop_zone_panel
            self.drop_zone_panel.show_panel()
            return

        self.controller.drop_zone = None
        if self.drop_zone_panel is not None:
            self.drop_zone_panel.orderOut_(None)
        if not self.controller.window.isVisible():
            self.controller.show_main_window()

    def applicationShouldTerminateAfterLastWindowClosed_(self, application):
        return not FN.NSUserDefaults.standardUserDefaults().boolForKey_(
            DROP_ZONE_DEFAULTS_KEY
        )

    def applicationShouldTerminate_(self, application):
        if self.controller.processing:
            alert = AK.NSAlert.alloc().init()
            alert.setMessageText_("Compression is still running")
            alert.setInformativeText_("Please wait for the current batch to finish before quitting.")
            alert.addButtonWithTitle_("Continue compressing")
            alert.runModal()
            return AK.NSTerminateCancel
        return AK.NSTerminateNow


def main():
    application = AK.NSApplication.sharedApplication()
    application.setActivationPolicy_(AK.NSApplicationActivationPolicyRegular)
    delegate = AppDelegate.alloc().init()
    application.setDelegate_(delegate)
    AppHelper.runEventLoop()


if __name__ == "__main__":
    main()
