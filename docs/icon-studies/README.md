# Pdfs by Kash: app icon studies

The eight app icons for **Pdfs by Kash**. All eight were approved and ship in the app: Settings → App Icon offers every one, with **Squish** as the default. The shipped copies live in `assets/app-icons/` (SVG source + 512 px PNG) and `assets/AppIcon.icns` (Squish, the bundle icon). This folder keeps the original study: renders at every size, the comparison page and the generator.

Open `index.html` in a browser: every concept large, at 128/64/32/16 px on dark and light, and in a mock macOS Dock on a light and a dark wallpaper.

## Conventions (same as Geminio and Budget)

- 1024 canvas, 824 px rounded-square body at (100, 100), radius 188, soft drop shadow (dy 16, blur 16, 38 %), fine grain, a hairline light rim on top.
- The by Kash signature is one illustrated lowercase initial (Geminio's `g`, Budget's `b`). Five concepts carry a `p`; three try a picture instead.
- Unlike the siblings, the art is pure SVG geometry (no system fonts), so the SVGs render identically anywhere.

## Concepts

| # | Name | Direction | Idea |
|---|---|---|---|
| 01 | Monoline | family | Hairline p in a warm gradient; faint rings around the bowl are the bigger file it used to be. Sibling of Geminio's Monoline. |
| 02 | Squish | playful | A fat glossy p squashed flat under a press plate. |
| 03 | Sheet | macOS-native | Preview-white page, its old outline dashed behind it, system "shrink" arrows in system blue. |
| 04 | Accordion | abstract | A page of text folded into bellows; the folds tighten until the page is a few pleats. |
| 05 | Diamond | elegant | Pressure makes diamonds: a small, bright cut stone on midnight. |
| 06 | Didone | editorial | Didot-style p in ink on warm paper; the ruled lines behind set tighter toward the bottom; red full stop as maker's mark. |
| 07 | Strata | modern | Colour bands pressed thinner toward the bottom under a heavy white p. Compression without an arrow. |
| 08 | Origami | minimal | A p folded from one strip of paper; the navy back shows at the folded foot. |

Strongest: **Strata** (clear idea, best at 16 px). Best family fit: **Monoline** (thin at 16 px; would need a heavier small-size variant). Most native: **Sheet**.

## Layout

- `concepts/NN-name.svg`: sources (written by the generator; edit the generator, not the SVGs)
- `png/NN-name-{1024,256,128,64,32,16}.png`: renders; `png/sheet.png` contact sheet
- `reference/`: Geminio and Budget icons, for the family comparison
- `scripts/generate.py`, `scripts/render.sh`, `scripts/sheet.py`

## Regenerate

```bash
brew install librsvg            # rsvg-convert
python3 icon-studies/scripts/generate.py            # all, or e.g. `generate.py strata sheet`
icon-studies/scripts/render.sh                      # PNGs + contact sheet (needs Pillow)
```

## If one is picked (not started)

Build `assets/PDFCompresor.icns` from the 1024 render with `iconutil` (16–1024 incl. @2x), plus `.png`/`.ico`; consider a simplified 16/32 px variant for thin designs.
