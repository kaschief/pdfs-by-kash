# Pdfs by Kash — working agreement

A native macOS PDF compressor (PyObjC + Ghostscript), forked from FS PDF Compressor. This file
is the contract for anyone — human or agent — changing it.

## Non-negotiables

- **Home branch is `pdfs-home`.** Commit there; push to `origin` only. `upstream`
  (gitlares/fs-pdf-compressor) is fetch-only. Branch worktrees live in `.worktrees/` (ignored),
  never as sibling folders.
- **Never steal the user's focus.** Any automated UI run sets `PDFS_BY_KASH_BACKGROUND=1`
  (windows render off-screen; the app never activates). Don't `open` the built app unless asked.
- **The gate is green before you call something done:**

  ```bash
  .build-venv/bin/python -m unittest discover -s tests
  .build-venv/bin/python -m py_compile native_app.py build_macos.py fs_pdf_compressor/*.py
  DIST_DIR=release-test MACOS_GHOSTSCRIPT_SOURCE_APP="/Applications/FS PDF Compressor.app" \
    .build-venv/bin/python build_macos.py && codesign --verify --deep --strict "release-test/Pdfs by Kash.app"
  ```

- **Report honestly.** Say what was and wasn't verified, and how.

## Design

- **Show before building.** New screens or visible layout changes get a mockup for approval
  (see `docs/design/`). Build to the approved mockup; don't substitute stock controls or the
  system accent without saying so.
- **Every colour, border, radius and focus treatment comes from `fs_pdf_compressor/macos_theme.py`.**
  Never `controlAccentColor`, never `system*Color` in views.
- House rules (shared with Geminio and Budget): nothing moves under the pointer (disable, don't
  hide); focus rings only for keyboard use; hover only on what you can click; tooltips only for
  detail you can't see (paths, icon-only buttons, why something is unavailable); labels, not prose.
- Replace is a deliberate choice: show it plainly, never as an error.

## Safety

- An original is replaced **only after** the compressed file is validated **and** the original is
  in the Trash (`core._replace_and_trash_original`). Don't weaken this.
- Every launch starts on **Keep originals**. Only Quality and Save to are remembered.

## Documentation — keep it living

A user-visible change is not finished until:

1. `docs/pdfs-by-kash-changes.md` has an entry under its theme (what, problem, limits) — or the
   entry it makes untrue is edited/removed.
2. `README.md` "What Pdfs by Kash adds" has a line, if it's headline-worthy.
3. Screenshots are regenerated if a screen changed: `.build-venv/bin/python scripts/render_docs_screenshots.py`.

## Map

| Path | What |
|---|---|
| `native_app.py` | App delegate, menus, main window controller |
| `fs_pdf_compressor/core.py` | Ghostscript, output paths, safe replace (shared with Windows/Linux) |
| `fs_pdf_compressor/compression_queue.py` | List model: Ready → Queued → Compressing → Completed / Unchanged / Failed |
| `fs_pdf_compressor/macos_views.py` | Tiles, option card panel, table, selection bar |
| `fs_pdf_compressor/macos_controls.py` | Primary/Quiet buttons, chip control, keyboard-only focus |
| `fs_pdf_compressor/macos_theme.py` | Design tokens |
| `fs_pdf_compressor/macos_settings.py` | Settings: app icon + theme |
| `fs_pdf_compressor/app_icons.py`, `macos_dock_tile/` | Icon switching and the Dock tile plug-in |
| `fs_pdf_compressor/preferences.py` | Saved preferences |
| `assets/app-icons/`, `assets/AppIcon.icns` | The eight icons; Squish bundle icon |
| `docs/design/`, `docs/icon-studies/` | Approved mockups and icon studies |
