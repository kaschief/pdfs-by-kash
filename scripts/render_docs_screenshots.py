# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Kaschief
"""Regenerate the README screenshots in docs/screenshots.

    .build-venv/bin/python scripts/render_docs_screenshots.py

Renders the real windows off-screen at 2x: no window appears, focus is never
taken (PDFS_BY_KASH_BACKGROUND=1), and a watchdog ends the run after 4 minutes.
Demo PDFs are generated in a temporary folder and deleted afterwards. Your own
preferences are not touched: the script runs under Python's own defaults
domain (not com.kaschief.pdfsbykash) and removes the keys it sets.
"""
import faulthandler, os, random, shutil, sys, tempfile
from pathlib import Path

faulthandler.dump_traceback_later(240, exit=True)  # hard stop: never linger
os.environ["PDFS_BY_KASH_BACKGROUND"] = "1"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import AppKit as AK, Foundation as FN, Quartz as Q
from PyObjCTools import AppHelper
import native_app

OUT = str(ROOT / "docs" / "screenshots")
WORK = tempfile.mkdtemp(prefix="pdfs-by-kash-demo-")


def make_demo_pdfs(folder):
    cs = Q.CGColorSpaceCreateDeviceRGB()

    def make(name, pages, width, seed):
        random.seed(seed)
        path = os.path.join(folder, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        pdf = Q.CGPDFContextCreateWithURL(FN.NSURL.fileURLWithPath_(path), Q.CGRectMake(0, 0, 612, 792), None)
        for _ in range(pages):
            data = bytearray(os.urandom(width * width * 4))
            ctx = Q.CGBitmapContextCreate(data, width, width, 8, width * 4, cs, Q.kCGImageAlphaNoneSkipLast)
            Q.CGContextSetRGBFillColor(ctx, random.random(), random.random(), random.random(), 0.8)
            Q.CGContextFillRect(ctx, Q.CGRectMake(0, 0, width, width))
            Q.CGContextBeginPage(pdf, None)
            Q.CGContextDrawImage(pdf, Q.CGRectMake(0, 0, 612, 792), Q.CGBitmapContextCreateImage(ctx))
            Q.CGContextEndPage(pdf)
        Q.CGPDFContextClose(pdf)

    make("Apartment Lease (signed).pdf", 5, 1400, 1)
    make("Annual Report 2025.pdf", 3, 1300, 2)
    make("Taxes 2025/Receipts Q3.pdf", 2, 1000, 3)
    make("Portfolio — Kash.pdf", 4, 1500, 4)
    pdf = Q.CGPDFContextCreateWithURL(
        FN.NSURL.fileURLWithPath_(os.path.join(folder, "Invoice 0142.pdf")), Q.CGRectMake(0, 0, 612, 792), None
    )
    Q.CGContextBeginPage(pdf, None)
    Q.CGContextFillRect(pdf, Q.CGRectMake(72, 700, 200, 2))
    Q.CGContextEndPage(pdf)
    Q.CGPDFContextClose(pdf)


make_demo_pdfs(WORK)
defaults = FN.NSUserDefaults.standardUserDefaults()
for k in ("AppIcon", "Appearance", "QualityIndex", "OutputFolder", "UseOutputFolder", "SkipReplaceConfirmation"):
    defaults.removeObjectForKey_(k)

app = AK.NSApplication.sharedApplication(); app.setActivationPolicy_(AK.NSApplicationActivationPolicyProhibited)
d = native_app.AppDelegate.alloc().init(); app.setDelegate_(d)

def render(view, name, dark=False):
    win = view.window()
    win.setAppearance_(AK.NSAppearance.appearanceNamed_(AK.NSAppearanceNameDarkAqua if dark else AK.NSAppearanceNameAqua))
    frame_view = win.contentView().superview() if view is win.contentView() else view
    frame_view.layoutSubtreeIfNeeded(); frame_view.setNeedsDisplay_(True); frame_view.displayIfNeeded()
    size = frame_view.bounds().size  # render at 2x (Retina) though the window is off-screen
    rep = AK.NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, int(size.width * 2), int(size.height * 2), 8, 4, True, False, AK.NSDeviceRGBColorSpace, 0, 0)
    rep.setSize_(size)
    frame_view.cacheDisplayInRect_toBitmapImageRep_(frame_view.bounds(), rep)
    rep.representationUsingType_properties_(AK.NSBitmapImageFileTypePNG, None).writeToFile_atomically_(os.path.join(OUT, name + ".png"), True)
    print("wrote", name, flush=True)

def main_view(): return d.controller.window.contentView()

def s_empty():
    c = d.controller
    c.window.setContentSize_(AK.NSMakeSize(760, 480)); c.layout_controls()
    render(main_view(), "empty")
    c.add_paths([os.path.join(WORK, n) for n in ("Apartment Lease (signed).pdf", "Annual Report 2025.pdf", "Portfolio — Kash.pdf", "Invoice 0142.pdf", "Taxes 2025")])
    AppHelper.callLater(1.5, s_ready)

def s_ready():
    c = d.controller; t = c.table_controller
    render(main_view(), "ready")
    t.setHoveredRow_(1)
    t.toggleRow_(0); t.toggleRow_(2)
    c.selection_bar.reveal_button.hovered = True
    render(main_view(), "selection")
    c.selection_bar.reveal_button.hovered = False
    c.clearSelection_(None); t.setHoveredRow_(-1)
    c.open_setting(c.originals_tile)
    AppHelper.callLater(0.4, s_panel)

def s_panel():
    c = d.controller
    if c.popover is not None:
        render(c.popover.contentView(), "option-panel")
        c.popover.dismiss()
    c._originals_cards()[1].action()
    render(main_view(), "replace")
    c._originals_cards()[0].action()
    c.compress_(None)
    AppHelper.callLater(0.2, s_mid)

def s_mid():
    c = d.controller
    if c.processing and c.batch_done >= 1:
        render(main_view(), "compressing"); AppHelper.callLater(0.3, s_wait); return
    if not c.processing:
        s_wait(); return
    AppHelper.callLater(0.1, s_mid)

def s_wait():
    if d.controller.processing: AppHelper.callLater(0.3, s_wait); return
    c = d.controller; t = c.table_controller
    t.setHoveredRow_(0)
    AppHelper.callLater(0.3, s_results)

def s_results():
    render(main_view(), "results"); render(main_view(), "results-dark", True)
    d.showSettings_(None)
    s = d.settings_controller
    render(s.window.contentView(), "settings")
    s.chooseIcon_("strata"); s.theme_control.select(2)
    render(s.window.contentView(), "settings-dark", True)
    s.chooseIcon_("squish")
    for k in ("AppIcon", "Appearance", "QualityIndex", "OutputFolder", "UseOutputFolder", "SkipReplaceConfirmation"):
        defaults.removeObjectForKey_(k)
    shutil.rmtree(WORK, ignore_errors=True)
    AK.NSApp.terminate_(None)

AppHelper.callLater(1.0, s_empty); AppHelper.runEventLoop()
