# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Kaschief

"""Saved preferences (NSUserDefaults keys, defaults and typed access).

These are the *starting* values for each launch. The main window copies them
when it opens; changes made there last for the session only, so a one-off
"Replace originals" can never silently become the next launch's behaviour.
Only the Settings window writes them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import Foundation as FN

from fs_pdf_compressor.core import QUALITY_PROFILES

APP_ICON_KEY = "AppIcon"
THEME_KEY = "Appearance"
QUALITY_KEY = "QualityIndex"
ORIGINALS_KEY = "OriginalsMode"
OUTPUT_FOLDER_KEY = "OutputFolder"
USE_OUTPUT_FOLDER_KEY = "UseOutputFolder"
REVEAL_WHEN_DONE_KEY = "RevealWhenDone"
SKIP_REPLACE_CONFIRMATION_KEY = "SkipReplaceConfirmation"

Theme = Literal["system", "light", "dark"]
THEMES: tuple[Theme, ...] = ("system", "light", "dark")

FACTORY_DEFAULTS = {
    APP_ICON_KEY: "squish",
    THEME_KEY: "system",
    QUALITY_KEY: 1,
    ORIGINALS_KEY: "keep",
    OUTPUT_FOLDER_KEY: "",
    USE_OUTPUT_FOLDER_KEY: False,
    REVEAL_WHEN_DONE_KEY: False,
}


@dataclass(frozen=True)
class CompressionDefaults:
    quality_index: int
    keep_originals: bool
    output_folder: str | None
    use_output_folder: bool
    reveal_when_done: bool


def _defaults():
    defaults = FN.NSUserDefaults.standardUserDefaults()
    defaults.registerDefaults_(FACTORY_DEFAULTS)
    return defaults


def compression_defaults() -> CompressionDefaults:
    defaults = _defaults()
    quality = defaults.integerForKey_(QUALITY_KEY)
    folder = str(defaults.stringForKey_(OUTPUT_FOLDER_KEY) or "") or None
    return CompressionDefaults(
        quality_index=max(0, min(len(QUALITY_PROFILES) - 1, quality)),
        keep_originals=defaults.stringForKey_(ORIGINALS_KEY) != "replace",
        output_folder=folder,
        use_output_folder=bool(folder) and defaults.boolForKey_(USE_OUTPUT_FOLDER_KEY),
        reveal_when_done=defaults.boolForKey_(REVEAL_WHEN_DONE_KEY),
    )


def save_compression_defaults(value: CompressionDefaults) -> None:
    defaults = _defaults()
    defaults.setInteger_forKey_(value.quality_index, QUALITY_KEY)
    defaults.setObject_forKey_("keep" if value.keep_originals else "replace", ORIGINALS_KEY)
    defaults.setObject_forKey_(value.output_folder or "", OUTPUT_FOLDER_KEY)
    defaults.setBool_forKey_(value.use_output_folder, USE_OUTPUT_FOLDER_KEY)
    defaults.setBool_forKey_(value.reveal_when_done, REVEAL_WHEN_DONE_KEY)


def theme() -> Theme:
    value = str(_defaults().stringForKey_(THEME_KEY) or "system")
    return value if value in THEMES else "system"  # type: ignore[return-value]


def set_theme(value: Theme) -> None:
    _defaults().setObject_forKey_(value, THEME_KEY)


def app_icon() -> str:
    return str(_defaults().stringForKey_(APP_ICON_KEY) or FACTORY_DEFAULTS[APP_ICON_KEY])


def set_app_icon(slug: str) -> None:
    _defaults().setObject_forKey_(slug, APP_ICON_KEY)


def skip_replace_confirmation() -> bool:
    return _defaults().boolForKey_(SKIP_REPLACE_CONFIRMATION_KEY)


def set_skip_replace_confirmation(value: bool) -> None:
    _defaults().setBool_forKey_(value, SKIP_REPLACE_CONFIRMATION_KEY)
