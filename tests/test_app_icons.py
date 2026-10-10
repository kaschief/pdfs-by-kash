# SPDX-License-Identifier: AGPL-3.0-or-later

import unittest
from pathlib import Path

from fs_pdf_compressor.app_icons import APP_ICONS, DEFAULT_ICON, icon_path, resolve

ROOT = Path(__file__).resolve().parents[1]


class AppIconTests(unittest.TestCase):
    def test_all_eight_approved_icons_are_offered_in_study_order(self):
        self.assertEqual(
            [icon.slug for icon in APP_ICONS],
            ["monoline", "squish", "sheet", "accordion", "diamond", "didone", "strata", "origami"],
        )

    def test_squish_is_the_default(self):
        self.assertEqual(DEFAULT_ICON, "squish")
        self.assertEqual(resolve(None).slug, "squish")
        self.assertEqual(resolve("not-an-icon").slug, "squish")

    def test_every_icon_ships_a_png_and_its_svg_source(self):
        for icon in APP_ICONS:
            self.assertTrue(icon_path(icon.slug).is_file(), icon.slug)
            self.assertTrue((ROOT / "assets" / "app-icons" / f"{icon.slug}.svg").is_file(), icon.slug)

    def test_bundle_icon_is_built_from_squish(self):
        self.assertTrue((ROOT / "assets" / "AppIcon.icns").is_file())


if __name__ == "__main__":
    unittest.main()
