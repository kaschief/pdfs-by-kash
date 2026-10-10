# What Pdfs by Kash changes

> **This is a running list.** It is kept up to date as the fork changes, not written once:
>
> - When an improvement lands, add an entry under the theme it belongs to: what changed, the
>   problem it solves, and its limits.
> - One entry per change someone would notice — a user, or a developer taking the project over —
>   not one per commit. Fold follow-up fixes into the entry they refine.
> - When something stops being true, edit or remove its entry in the same change. The list
>   describes the app as it is, not its history.
> - Leave out trivial churn: refactors, copy tweaks, a moved pixel.
> - When a screen changes, regenerate the screenshots (`scripts/render_docs_screenshots.py`).
>
> The [README](../README.md#what-pdfs-by-kash-adds) carries a one-line digest of this list;
> update it when an entry big enough to belong there is added or removed.

Pdfs by Kash began as a fork of [FS PDF Compressor](https://github.com/gitlares/fs-pdf-compressor)
by Daniel Lares, taken at upstream's **1.0.16**. The Ghostscript engine and upstream's file-safety
checks are kept; this page is the record of what the fork changed on top of the **macOS app**, and
why. The Windows and Linux apps are upstream's, apart from the shared Trash rule under
[Safe replacing](#safe-replacing).

Upstream is followed, not abandoned: taking an upstream release means merging `upstream/main`
into `pdfs-home` and rebuilding. Upstream's auto-update is off (see
[Identity & distribution](#identity--distribution)).

**Contents**

- [Workflow](#workflow)
- [Settings in view](#settings-in-view)
- [Safe replacing](#safe-replacing)
- [Selecting and finding files](#selecting-and-finding-files)
- [Settings window & app icons](#settings-window--app-icons)
- [Look & feel](#look--feel)
- [Identity & distribution](#identity--distribution)
- [Development](#development)

---

## Workflow

**Adding never compresses.** The window, **+**, the Dock icon, the Drop Zone and Finder's
**Add to Pdfs by Kash** only add files to the list; folders are searched. **Compress** (or Return)
starts a batch. *Problem:* upstream compressed the moment files arrived, with no chance to check
where they would go or what would happen to the originals. *Limits:* files added during a batch
wait for the next one.

**Original, Compressed and Reduction columns,** a total saved, and a per-file line saying where
the file will go or went. *Problem:* upstream showed only a percentage and never said where the
compressed copy was saved.

**File states that mean something.** A newly added file carries no badge — being in the list
says “ready”. After **Compress**: Queued → Compressing (a progress line under the name) →
Completed, Not smaller (nothing written), or Failed with the reason in plain words.
*Problem:* an early build labelled every new file “Pending” although nothing was pending.

**Compress Again** re-runs finished files with the current settings, once a batch is over.
**Clear List** empties the list; files on disk are never touched.

**Progress is a line, not a bar.** During a batch the bottom bar's top hairline fills with the
accent colour. It takes no space, so nothing moves and the status text is never cut off.

## Settings in view

**Three setting tiles — Save to · Originals · Quality** — above the footer, each showing its value
in words and opening a small card of choices with one line of explanation. Chosen from four
mockup directions ([design/settings-bar](design/settings-bar/index.html)). The tiles have fixed
widths, so changing a value never reflows the row; a tile that doesn't apply greys out in place.

**Save to** next to each original (`name compressed.pdf`) or a chosen folder, where the original
name is kept and `name 2.pdf` is used if taken. Choosing the original's own folder still adds
“compressed”.

**Keep or Replace originals,** Keep by default. **Every launch starts on Keep,** so a one-off
Replace never carries over. Quality and Save to are remembered between launches.

## Safe replacing

**An original is replaced only once it is in the Trash.** The compressed file is created and
validated first; then the original goes to the Trash; only then does the new file take its place,
with a recovery copy until that succeeds. If the original can't reach the Trash, it is left
untouched and its row says “couldn't move the original to the Trash, so it was left as is”.
*Problem:* upstream treated the Trash as best-effort and replaced anyway, so on volumes without a
Trash (some network and external drives) the original was lost. *Limits:* this is in the shared
engine, so the Windows and Linux apps follow the same rule.

**A calm confirmation** before the first Replace: “Replace these 4 PDFs with smaller versions? The
originals go to the Trash, so you can get them back.” with **Don't ask again**. Replace is shown
plainly elsewhere — rows say “Will replace the original” in the normal grey, the tile reads
“Replace” — because it is a deliberate choice, not an error.

## Selecting and finding files

**Additive selection.** Hovering a row shows a circle; clicking circles builds a selection one file
at a time, no ⌘ needed (⌘ and ⇧ still work). A floating bar offers **Show in Finder**, **Remove
from List** and **✕** to deselect; Esc deselects from anywhere in the window. *Problem:* “Remove”
read like deleting files and “Done” didn't look like a button.

**Selection never limits Compress.** Compress always covers every ready file; while files are
selected the footer says “Compress includes all N”, so nothing is skipped by accident.

**Show in Finder without clutter.** A Finder icon (and remove ✕) appears only on the hovered row,
instead of a magnifier on every row. Also on double-click, ⌘R, the right-click menu (with Open and
Copy Path) and the selection bar. It reveals the compressed copy once it exists, otherwise the
original.

**Fixed columns.** Resizable columns were evaluated and left out: the size columns hold short
values that always fit, and the file name grows with the window.

## Settings window & app icons

**Settings (⌘,) holds only the app icon and the theme.** Everything about compressing lives on the
main screen. *Problem:* an earlier Settings duplicated the main screen's controls with paragraphs
of explanation.

**Eight app icons** — Monoline, Squish, Sheet, Accordion, Diamond, Didone, Strata, Origami — with
**Squish** as the default and the bundle icon. Selection is the soft accent ring; icons don't react
to hover. The [icon studies](icon-studies/index.html) keep every size and the mock Dock.

**How the icon applies.** The running app's Dock tile, app switcher and About panel update at once
(`NSApp.applicationIconImage`). A bundled `NSDockTilePlugIn` (`macos_dock_tile/`) shows the choice
on the kept-in-Dock tile while the app is closed. *Limits:* Finder, Launchpad and Spotlight always
show Squish — the only API that changes them writes into the signed bundle and breaks its
signature.

**Theme: System, Light or Dark.** Icon and theme both survive a full restart (verified).

## Look & feel

**One design system** (`fs_pdf_compressor/macos_theme.py`): indigo accent (`#5B4EE8` light,
`#8F87FF` dark), lavender-tinted neutrals, one hairline, 8–12 pt radii, a keyboard-only focus ring,
hover fade and tooltip delay. Nothing reads the system accent colour, so the app looks the same on
every Mac — like Geminio and Budget. *Problem:* the first build mixed the system accent (pink),
stock controls and the system's see-through popover, and drifted from the approved mockups
([design/settings-v2](design/settings-v2/index.html)).

**An opaque option card** replaces NSPopover, whose material showed the desktop through it and
made the selected option unreadable over a dark desktop.

**Consistent button states.** Selection-bar buttons, row icons, **+**, Clear List and Compress share
hover, pressed, disabled and keyboard-focus treatments. Things that don't apply grey out instead
of disappearing.

**Focus rings only for keyboard use** — never on a click, never when a window opens.

**Quiet tooltips:** they wait one second and only carry full paths, icon-only button names and why
something is unavailable.

## Identity & distribution

**Renamed to Pdfs by Kash** — app and window, bundle id `com.kaschief.pdfsbykash`, Finder Quick
Action (“Add to Pdfs by Kash”), URL scheme `pdfsbykash://`, DMG and zip names.

**Upstream's Sparkle update feed is off.** *Problem:* left on, it would replace this app with an
upstream FS PDF Compressor build. The build skips Sparkle entirely unless `SPARKLE_FEED_URL` is set.

**Attribution kept.** About credits Daniel Lares and links the original project and the AGPL; source
files carry “Modifications Copyright (C) 2026 Kaschief”. The original README is at
[UPSTREAM-README.md](UPSTREAM-README.md).

## Development

**Never steals focus.** UI checks and the screenshot script set `PDFS_BY_KASH_BACKGROUND=1`: the
app renders off-screen, never activates and never shows a window.

**Screenshots are generated, not grabbed:** `scripts/render_docs_screenshots.py` builds demo PDFs,
drives the real windows off-screen at 2× and writes `docs/screenshots/`.

**Tested model.** `compression_queue.py` (one state per file) and the output-location rules are
covered by unit tests alongside upstream's suite.
