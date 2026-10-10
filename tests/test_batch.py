# SPDX-License-Identifier: AGPL-3.0-or-later

import unittest
from pathlib import Path

from fs_pdf_compressor.batch import BatchSummary, completion_text
from fs_pdf_compressor.core import display_folder


class BatchSummaryTests(unittest.TestCase):
    def test_empty_batch_has_no_summary(self):
        self.assertIsNone(BatchSummary.from_metrics([None, None]))
        self.assertEqual(
            completion_text([None, None]),
            "Done — no files were reduced",
        )

    def test_summary_matches_the_existing_product_copy(self):
        metrics = [
            {"original_size": 1_000_000, "saved_size": 500_000},
            {"original_size": 2_000_000, "saved_size": 500_000},
        ]

        summary = BatchSummary.from_metrics(metrics)

        self.assertIsNotNone(summary)
        self.assertEqual(summary.completed_files, 2)
        self.assertAlmostEqual(summary.average_reduction, 37.5)
        self.assertEqual(summary.saved_size, 1_000_000)
        self.assertEqual(
            summary.status_text,
            "Done — 37.5% average · 1.0 MB saved",
        )
        self.assertEqual(summary.compact_text, "38% smaller")

    def test_single_file_reports_folder_and_new_size(self):
        output = str(Path.home() / "Downloads" / "report compressed.pdf")
        metrics = [
            None,
            {
                "original_size": 5_000_000,
                "saved_size": 3_000_000,
                "new_size": 2_000_000,
                "output_path": output,
            },
        ]

        self.assertEqual(
            completion_text(metrics),
            "Saved to ~/Downloads · 2.0 MB",
        )
        self.assertEqual(
            completion_text(metrics, reveal_hint="click a file to show it in Finder"),
            "Saved to ~/Downloads · 2.0 MB — click a file to show it in Finder",
        )

    def test_multi_file_batch_keeps_summary_and_appends_hint(self):
        metrics = [
            {"original_size": 1_000_000, "saved_size": 500_000},
            {"original_size": 2_000_000, "saved_size": 500_000},
        ]

        self.assertEqual(
            completion_text(metrics, reveal_hint="hint"),
            "Done — 37.5% average · 1.0 MB saved — hint",
        )


class DisplayFolderTests(unittest.TestCase):
    def test_paths_under_home_use_tilde(self):
        path = str(Path.home() / "Documents" / "Taxes" / "a.pdf")
        self.assertEqual(display_folder(path), "~/Documents/Taxes")

    def test_paths_outside_home_are_absolute(self):
        self.assertEqual(display_folder("/Volumes/USB/a.pdf"), "/Volumes/USB")


if __name__ == "__main__":
    unittest.main()
