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
    IN_FLIGHT_STATES,
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
from fs_pdf_compressor import preferences as prefs
from fs_pdf_compressor.app_icons import apply_icon
from fs_pdf_compressor.macos_drop_zone import DropZonePanel
from fs_pdf_compressor.macos_settings import SettingsWindowController, apply_theme
from fs_pdf_compressor.macos_login_item import (
    current_state as login_item_state,
    open_login_items_settings,
    set_enabled as set_login_item_enabled,
)
from fs_pdf_compressor.macos_update_probe import probe_for_update
from fs_pdf_compressor import macos_theme as theme
from fs_pdf_compressor.macos_controls import PrimaryButton, QuietButton, bring_app_forward
from fs_pdf_compressor.macos_views import (
    ChromeView,
    DropCanvas,
    IconButton,
    OptionCard,
    OptionPanel,
    QueueTableController,
    SelectionBar,
    SettingTile,
)
from fs_pdf_compressor.version import APP_VERSION

# One short line per quality option card (the long upstream descriptions are
# kept in core.QUALITY_PROFILES for the other platforms).
QUALITY_HINTS = (
    "Print quality, smallest savings.",
    "Sharp on screen, much smaller.",
    "Smallest files, visible softening.",
)
UPSTREAM_NAME = "FS PDF Compressor"
UPSTREAM_URL = "https://github.com/gitlares/fs-pdf-compressor"
REPOSITORY_URL = "https://github.com/kaschief/pdfs-by-kash"
URL_SCHEME = "pdfsbykash"
DROP_ZONE_DEFAULTS_KEY = "DropZoneEnabled"
SPARKLE_PROBE_LAST_CHECK_KEY = "SparkleLightweightProbeLastCheck"
SPARKLE_PROBE_INTERVAL = 86_400.0
SPARKLE_PROBE_TIMEOUT = 5.0



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
    """Main window: add PDFs, review settings, then compress on request."""

    FOOTER_HEIGHT = 52.0
    TILES_HEIGHT = 56.0  # 44 pt tiles + 12 pt top padding
    COMPRESS_WIDTH = 128.0

    def init(self):
        self = objc.super(PDFCompressorController, self).init()
        if self is None:
            return None
        self.queue = CompressionQueue()
        self.batch_paths = []
        self.batch_done = 0
        self.processing = False
        self.drop_zone = None
        self.popover = None
        self.apply_saved_defaults()
        self._build_window()
        self.refresh()
        return self

    @objc.python_method
    def apply_saved_defaults(self):
        """Restore Quality and Save to; Originals always starts on Keep."""
        memory = prefs.window_memory()
        self.quality_index = memory.quality_index
        self.output_folder = memory.output_folder
        self.use_output_folder = memory.use_output_folder
        self.keep_originals = True

    @objc.python_method
    def remember(self):
        prefs.remember_window(
            prefs.WindowMemory(self.quality_index, self.output_folder, self.use_output_folder)
        )

    # -- Derived state ---------------------------------------------------------------

    @property
    def showing_results(self):
        return len(self.queue) > 0

    @objc.python_method
    def bottom_chrome_height(self):
        return self.FOOTER_HEIGHT + self.TILES_HEIGHT

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
        return not isinstance(self.queue[row].state, IN_FLIGHT_STATES)

    @objc.python_method
    def can_select(self, row):
        return self.can_remove(row)

    @objc.python_method
    def selection_active(self):
        return self.table_controller.table.numberOfSelectedRows() > 0

    # -- Window ---------------------------------------------------------------------

    @objc.python_method
    def _build_window(self):
        style = (
            AK.NSWindowStyleMaskTitled
            | AK.NSWindowStyleMaskClosable
            | AK.NSWindowStyleMaskMiniaturizable
            | AK.NSWindowStyleMaskResizable
        )
        self.window = AK.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            AK.NSMakeRect(0, 0, 720, 460), style, AK.NSBackingStoreBuffered, False
        )
        self.window.setTitle_(APP_NAME)
        self.window.setMinSize_(AK.NSMakeSize(660, 400))
        self.window.setReleasedWhenClosed_(False)
        self.window.center()

        self.canvas = DropCanvas.alloc().initWithFrame_controller_(
            AK.NSMakeRect(0, 0, 720, 460), self
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

        self.selection_bar = SelectionBar.alloc().initWithOwner_(self)
        self.selection_bar.setHidden_(True)
        self.canvas.addSubview_(self.selection_bar)

        self._build_bottom()
        self.layout_controls()
        # Only now: restoring the saved frame triggers windowDidResize_, which
        # needs every view above to exist.
        self.window.setDelegate_(self)
        self.window.setFrameAutosaveName_("Pdfs by Kash Main Window")

    @objc.python_method
    def _build_bottom(self):
        self.bottom = ChromeView.alloc().initWithFrame_(AK.NSZeroRect)
        self.canvas.addSubview_(self.bottom)

        self.destination_tile = SettingTile.alloc().initWithKind_caption_symbol_owner_(
            "destination", "Save to", "folder", self
        )
        self.originals_tile = SettingTile.alloc().initWithKind_caption_symbol_owner_(
            "originals", "Originals", "square.on.square", self
        )
        self.quality_tile = SettingTile.alloc().initWithKind_caption_symbol_owner_(
            "quality", "Quality", "circle.lefthalf.filled", self
        )
        for tile in self.tiles:
            self.bottom.addSubview_(tile)

        self.add_button = IconButton.alloc().initWithSymbol_label_target_action_(
            "plus", "Add PDFs", self, "chooseFiles:"
        )
        self.add_button.setToolTip_("Add PDFs")  # icon-only: the one place a label helps
        self.bottom.addSubview_(self.add_button)

        self.status_label = AK.NSTextField.labelWithString_("")
        self.status_label.setFont_(AK.NSFont.systemFontOfSize_(12.5))
        self.status_label.setTextColor_(theme.INK_2)
        self.status_label.setLineBreakMode_(AK.NSLineBreakByTruncatingTail)
        self.bottom.addSubview_(self.status_label)

        # A real (secondary) button with a plain name; disabled, never hidden,
        # so the footer never shifts when the list empties.
        self.clear_button = QuietButton.alloc().initWithTitle_symbol_style_target_action_(
            "Clear List", None, "secondary", self, "clearList:"
        )
        self.bottom.addSubview_(self.clear_button)

        self.compress_button = PrimaryButton.alloc().initWithTitle_target_action_(
            "Compress", self, "compress:"
        )
        self.compress_button.setKeyEquivalent_("\r")
        self.bottom.addSubview_(self.compress_button)

    @property
    def tiles(self):
        return (self.destination_tile, self.originals_tile, self.quality_tile)

    def layout_controls(self):
        bounds = self.canvas.bounds()
        width, height = bounds.size.width, bounds.size.height
        bottom_height = self.bottom_chrome_height()
        footer = self.FOOTER_HEIGHT

        self.bottom.setFrame_(AK.NSMakeRect(0, 0, width, bottom_height))
        self.results_scroll.setFrame_(
            AK.NSMakeRect(0, bottom_height, width, height - bottom_height)
        )

        # Tiles: fixed proportions of the window, never of their text.
        inner = width - 28
        gap = 8.0
        unit = (inner - 2 * gap) / 3.35
        widths = (unit * 1.35, unit, unit)
        x = 14.0
        for tile, tile_width in zip(self.tiles, widths):
            tile.setFrame_(AK.NSMakeRect(x, footer, tile_width, 44))
            x += tile_width + gap

        control_y = (footer - 28) / 2
        self.add_button.setFrame_(AK.NSMakeRect(14, control_y, 30, 28))
        right = width - 14
        self.compress_button.setFrame_(
            AK.NSMakeRect(right - self.COMPRESS_WIDTH, control_y, self.COMPRESS_WIDTH, 28)
        )
        right -= self.COMPRESS_WIDTH + 8
        clear_width = 92.0
        self.clear_button.setFrame_(AK.NSMakeRect(right - clear_width, control_y, clear_width, 28))
        right -= clear_width + 12
        self.status_label.setFrame_(
            AK.NSMakeRect(58, (footer - 20) / 2 - 1, max(90, right - 58), 20)
        )
        self._place_selection_bar()
        self.canvas.setNeedsDisplay_(True)

    @objc.python_method
    def _place_selection_bar(self):
        size = self.selection_bar.frame().size
        width = self.canvas.bounds().size.width
        self.selection_bar.setFrameOrigin_(
            AK.NSMakePoint((width - size.width) / 2, self.bottom_chrome_height() + 12)
        )

    def windowDidResize_(self, notification):
        self.layout_controls()

    # -- Refresh: one place that maps state → controls ---------------------------------

    @objc.python_method
    def refresh(self):
        idle = not self.processing
        self._refresh_tiles(idle)

        has_ready = self.queue.has_ready
        again = not has_ready and self.queue.has_finished
        self.compress_button.setTitle_("Compress Again" if again else "Compress")
        self.compress_button.setEnabled_(idle and (has_ready or again))
        self.clear_button.setEnabled_(idle and len(self.queue) > 0)
        if idle:
            self.bottom.set_progress(None)

        self.results_scroll.setHidden_(not self.showing_results)
        self.table_controller.reload()
        self.selection_changed()
        self.layout_controls()

    @objc.python_method
    def _refresh_status(self):
        if self.processing:
            total = len(self.batch_paths)
            status = f"Compressing {min(self.batch_done + 1, total)} of {total}…"
        else:
            status = self.queue.summary_text()
            ready = len(self.queue.ready_paths)
            # Selection never limits what Compress does; say so while it exists.
            if ready and self.table_controller.selected_rows():
                status += f" · Compress includes all {ready}"
        self.status_label.setStringValue_(status)
        self.status_label.setToolTip_(status)  # the line can truncate when narrow

    @objc.python_method
    def _refresh_tiles(self, idle):
        if self.keep_originals:
            if self.effective_output_dir():
                self.destination_tile.update(
                    Path(self.output_folder).name,
                    tooltip=self.output_folder,
                    symbol="folder.fill",
                )
            else:
                self.destination_tile.update("Next to originals", symbol="folder")
            self.originals_tile.update("Keep", symbol="square.on.square")
        else:
            self.destination_tile.update(
                "In place of originals", mode="off", tooltip="Not used while replacing originals"
            )
            # A deliberate choice, not an error: shown plainly, no warning colour.
            self.originals_tile.update("Replace", symbol="arrow.triangle.2.circlepath")
        self.quality_tile.update(QUALITY_CONTROL_LABELS[self.quality_index])
        if not idle:
            for tile in self.tiles:
                tile.update(tile.value, mode="off", tooltip=None)

    # -- Setting popovers ---------------------------------------------------------

    @objc.python_method
    def open_setting(self, tile):
        if self.processing:
            return
        if self.popover is not None:
            self.popover.dismiss()
        cards = getattr(self, f"_{tile.kind}_cards")()

        def closed():
            tile.open = False
            tile.setNeedsDisplay_(True)
            self.popover = None

        self.popover = OptionPanel.alloc().initWithCards_onClose_(cards, closed)
        tile.open = True
        tile.setNeedsDisplay_(True)
        self.popover.show_above(tile)

    @objc.python_method
    def _pick(self, apply):
        def picked():
            apply()
            self.remember()
            if self.popover is not None:
                self.popover.dismiss()
            self.refresh()

        return picked

    @objc.python_method
    def _originals_cards(self):
        def keep():
            self.keep_originals = True

        def replace():
            self.keep_originals = False

        return [
            OptionCard.alloc().initWithTitle_detail_symbol_selected_warn_action_(
                "Keep originals",
                "Your files stay untouched.",
                "square.on.square",
                self.keep_originals,
                False,
                self._pick(keep),
            ),
            OptionCard.alloc().initWithTitle_detail_symbol_selected_warn_action_(
                "Replace originals",
                "Old versions go to the Trash.",
                "arrow.triangle.2.circlepath",
                not self.keep_originals,
                False,
                self._pick(replace),
            ),
        ]

    @objc.python_method
    def _quality_cards(self):
        cards = []
        for index, description in enumerate(QUALITY_HINTS):

            def choose(index=index):
                self.quality_index = index

            cards.append(
                OptionCard.alloc().initWithTitle_detail_symbol_selected_warn_action_(
                    QUALITY_CONTROL_LABELS[index],
                    description,
                    ("circle", "circle.lefthalf.filled", "circle.fill")[index],
                    index == self.quality_index,
                    False,
                    self._pick(choose),
                )
            )
        return cards

    @objc.python_method
    def _destination_cards(self):
        def alongside():
            self.use_output_folder = False

        def folder():
            self.use_output_folder = True

        cards = [
            OptionCard.alloc().initWithTitle_detail_symbol_selected_warn_action_(
                "Next to each original",
                "Saved as “name compressed.pdf”.",
                "folder",
                not self.effective_output_dir(),
                False,
                self._pick(alongside),
            )
        ]
        if self.output_folder:
            cards.append(
                OptionCard.alloc().initWithTitle_detail_symbol_selected_warn_action_(
                    Path(self.output_folder).name,
                    tilde_path(self.output_folder),
                    "folder.fill",
                    bool(self.effective_output_dir()),
                    False,
                    self._pick(folder),
                )
            )
        cards.append(
            OptionCard.alloc().initWithTitle_detail_symbol_selected_warn_action_(
                "Choose Folder…", None, "folder.badge.plus", False, False, self._choose_folder
            )
        )
        return cards

    @objc.python_method
    def _choose_folder(self):
        if self.popover is not None:
            self.popover.dismiss()
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
            self.remember()
        self.refresh()

    # -- Adding files ------------------------------------------------------------------

    def handle_drop_urls(self, urls):
        self.add_paths([str(url.path()) for url in urls if url.isFileURL()])

    @objc.python_method
    def add_paths(self, paths):
        """Add PDFs (folders are searched) to the list. Never starts compression."""
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
        if os.environ.get("PDFS_BY_KASH_BACKGROUND") == "1":
            self.window.orderBack_(None)  # tests: exist on screen, never in front
        else:
            self.window.makeKeyAndOrderFront_(None)
        self.window.makeFirstResponder_(None)  # no focus ring until the user Tabs
        bring_app_forward()

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

    # -- Selection, removing, revealing ---------------------------------------------------

    @objc.python_method
    def selection_changed(self):
        self._refresh_status()
        rows = self.table_controller.selected_rows()
        if not rows:
            self.selection_bar.setHidden_(True)
        else:
            self.selection_bar.update(
                len(rows),
                can_reveal=True,
                can_remove=any(self.can_remove(r) for r in rows),
            )
            self.selection_bar.setHidden_(False)
            self._place_selection_bar()
        # Checkbox circles show on every row while anything is selected.
        table = self.table_controller.table
        if table.numberOfRows():
            table.reloadDataForRowIndexes_columnIndexes_(
                FN.NSIndexSet.indexSetWithIndexesInRange_(FN.NSMakeRange(0, table.numberOfRows())),
                FN.NSIndexSet.indexSetWithIndex_(0),
            )

    def revealSelection_(self, sender):
        self.reveal_rows(self.table_controller.selected_rows())

    def removeSelection_(self, sender):
        self.remove_rows(self.table_controller.selected_rows())

    def clearSelection_(self, sender):
        self.table_controller.table.deselectAll_(None)

    def cancelOperation_(self, sender):
        """Esc anywhere in the window deselects (the selection bar says so)."""
        self.table_controller.table.deselectAll_(None)

    def showInFinder_(self, sender):
        rows = self.table_controller.selected_rows()
        if not rows:
            row = self.table_controller.table.hovered_row
            rows = [row] if row >= 0 else []
        self.reveal_rows(rows)

    @objc.python_method
    def remove_rows(self, rows):
        if self.queue.remove(r for r in rows if self.can_remove(r)):
            self.table_controller.table.deselectAll_(None)
            self.table_controller.table.hovered_row = -1
            self.refresh()

    def clearList_(self, sender):
        if self.processing:
            return
        self.queue.clear()
        self.table_controller.table.deselectAll_(None)
        self.refresh()

    @objc.python_method
    def _row_file(self, row):
        """The file a row stands for: the compressed copy once it exists."""
        item = self.queue[row]
        if isinstance(item.state, Compressed) and os.path.exists(item.state.output_path):
            return item.state.output_path
        return item.path if os.path.exists(item.path) else None

    @objc.python_method
    def reveal_rows(self, rows):
        urls = [
            FN.NSURL.fileURLWithPath_(path)
            for path in (self._row_file(r) for r in rows if 0 <= r < len(self.queue))
            if path
        ]
        if urls:
            AK.NSWorkspace.sharedWorkspace().activateFileViewerSelectingURLs_(urls)

    @objc.python_method
    def open_rows(self, rows):
        for row in rows:
            if 0 <= row < len(self.queue):
                path = self._row_file(row)
                if path:
                    AK.NSWorkspace.sharedWorkspace().openURL_(FN.NSURL.fileURLWithPath_(path))

    @objc.python_method
    def copy_paths(self, rows):
        paths = [p for p in (self._row_file(r) for r in rows if 0 <= r < len(self.queue)) if p]
        if paths:
            board = AK.NSPasteboard.generalPasteboard()
            board.clearContents()
            board.setString_forType_("\n".join(paths), AK.NSPasteboardTypeString)

    # -- Compressing ---------------------------------------------------------------------

    def compress_(self, sender):
        if self.processing:
            return
        if not self.queue.has_ready:
            self.queue.requeue_finished()
        if not self.queue.has_ready:
            self.refresh()
            return
        if not self.keep_originals and not self._confirm_replace(len(self.queue.ready_paths)):
            return
        if self.popover is not None:
            self.popover.dismiss()
        self.batch_paths = self.queue.queue_ready()
        self.batch_done = 0
        self.processing = True
        self.bottom.set_progress(0.0)
        self.refresh()

        _, setting, _ = QUALITY_PROFILES[self.quality_index]
        threading.Thread(
            target=self._compress_worker,
            args=(list(self.batch_paths), setting, self.keep_originals, self.effective_output_dir()),
            daemon=True,
        ).start()

    @objc.python_method
    def _confirm_replace(self, count):
        if prefs.skip_replace_confirmation():
            return True
        alert = AK.NSAlert.alloc().init()
        noun = "this PDF" if count == 1 else f"these {count} PDFs"
        alert.setMessageText_(f"Replace {noun} with smaller versions?")
        alert.setInformativeText_("The originals go to the Trash, so you can get them back.")
        alert.addButtonWithTitle_("Replace")
        alert.addButtonWithTitle_("Cancel")
        alert.setShowsSuppressionButton_(True)
        alert.suppressionButton().setTitle_("Don’t ask again")
        response = alert.runModal()
        if alert.suppressionButton().state() == AK.NSControlStateValueOn:
            prefs.set_skip_replace_confirmation(True)
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
        self.bottom.set_progress(self.batch_done / total if total else 1.0)
        if self.drop_zone is not None:
            self.drop_zone.batch_progress(self.batch_done, total)
        self.refresh()

    @objc.python_method
    def _finish_compression(self):
        self.processing = False
        for path in self.batch_paths:
            index = self.queue.index_of(path)
            if index is not None and isinstance(self.queue[index].state, IN_FLIGHT_STATES):
                self.queue.set_state(path, Failed("Compression was interrupted"))
        batch = set(self.batch_paths)
        finished = [i for i in self.queue.items if i.path in batch and isinstance(i.state, Compressed)]
        metrics = [
            {"original_size": i.original_size, "saved_size": i.original_size - i.state.new_size}
            for i in finished
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
        self.settings_controller = None
        apply_theme(prefs.theme())
        apply_icon(prefs.app_icon())
        self._build_main_menu()
        self.controller = PDFCompressorController.alloc().init()
        if FN.NSUserDefaults.standardUserDefaults().boolForKey_(
            DROP_ZONE_DEFAULTS_KEY
        ):
            self._set_drop_zone_enabled(True)
        self.controller.show_main_window()
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
        settings_item = application_menu.addItemWithTitle_action_keyEquivalent_(
            "Settings…", "showSettings:", ","
        )
        settings_item.setTarget_(self)

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
        reveal_item = file_menu.addItemWithTitle_action_keyEquivalent_(
            "Show in Finder", "showInFinder:", "r"
        )
        reveal_item.setTarget_(self.controller)
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

    def showSettings_(self, sender):
        if self.settings_controller is None:
            self.settings_controller = SettingsWindowController.alloc().init()
        self.settings_controller.show()

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
    # Tooltips only carry secondary detail (full paths, icon-only buttons, why
    # something is disabled), so they wait a beat instead of popping instantly.
    FN.NSUserDefaults.standardUserDefaults().registerDefaults_({"NSInitialToolTipDelay": theme.TOOLTIP_DELAY_MS})
    application = AK.NSApplication.sharedApplication()
    application.setActivationPolicy_(AK.NSApplicationActivationPolicyRegular)
    delegate = AppDelegate.alloc().init()
    application.setDelegate_(delegate)
    AppHelper.runEventLoop()


if __name__ == "__main__":
    main()
