# SPDX-License-Identifier: AGPL-3.0-or-later

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fs_pdf_compressor.compression_queue import (
    CompressionQueue,
    Compressed,
    Compressing,
    Failed,
    Pending,
    Unchanged,
    state_from_result,
)
from fs_pdf_compressor.core import compress_pdf, compressed_copy_path, planned_output_path


def sizes(mapping):
    return lambda path: mapping[path]


class QueueTests(unittest.TestCase):
    def test_adding_only_queues_files_as_pending(self):
        queue = CompressionQueue()
        added = queue.add(["/a.pdf", "/b.pdf"], size_of=sizes({"/a.pdf": 10, "/b.pdf": 20}))

        self.assertEqual(added, 2)
        self.assertTrue(all(isinstance(i.state, Pending) for i in queue.items))
        self.assertEqual([i.original_size for i in queue.items], [10, 20])
        self.assertEqual(queue.pending_paths, ["/a.pdf", "/b.pdf"])

    def test_duplicates_are_ignored_but_finished_files_are_requeued(self):
        queue = CompressionQueue()
        size_of = sizes({"/a.pdf": 10})
        queue.add(["/a.pdf"], size_of=size_of)
        self.assertEqual(queue.add(["/a.pdf"], size_of=size_of), 0)

        queue.set_state("/a.pdf", Compressed("/a compressed.pdf", 4))
        self.assertEqual(queue.add(["/a.pdf"], size_of=size_of), 1)
        self.assertIsInstance(queue[0].state, Pending)
        self.assertEqual(len(queue), 1)

    def test_rows_being_compressed_cannot_be_removed(self):
        queue = CompressionQueue()
        queue.add(["/a.pdf", "/b.pdf"], size_of=lambda _: 1)
        queue.set_state("/a.pdf", Compressing())

        self.assertEqual(queue.remove([0, 1]), 1)
        self.assertEqual([i.path for i in queue.items], ["/a.pdf"])

    def test_clear_keeps_in_flight_rows(self):
        queue = CompressionQueue()
        queue.add(["/a.pdf", "/b.pdf"], size_of=lambda _: 1)
        queue.set_state("/b.pdf", Compressing())
        queue.clear()
        self.assertEqual([i.path for i in queue.items], ["/b.pdf"])

    def test_reduction_only_exists_for_compressed_rows(self):
        queue = CompressionQueue()
        queue.add(["/a.pdf"], size_of=lambda _: 200)
        self.assertIsNone(queue[0].reduction)
        queue.set_state("/a.pdf", Compressed("/out.pdf", 50))
        self.assertAlmostEqual(queue[0].reduction, 75.0)

    def test_summary_before_and_after_compression(self):
        queue = CompressionQueue()
        self.assertEqual(queue.summary_text(), "Add PDFs to get started")
        queue.add(
            ["/a.pdf", "/b.pdf", "/c.pdf"],
            size_of=sizes({"/a.pdf": 4_000_000, "/b.pdf": 1_000_000, "/c.pdf": 500_000}),
        )
        self.assertEqual(queue.summary_text(), "3 PDFs ready · 5.5 MB")

        queue.set_state("/a.pdf", Compressed("/a2.pdf", 1_000_000))
        queue.set_state("/b.pdf", Failed("Could not open PDF"))
        queue.set_state("/c.pdf", Unchanged("left unchanged"))
        self.assertEqual(
            queue.summary_text(),
            "1 compressed · 3.0 MB saved (75%) · 1 unchanged · 1 failed",
        )

    def test_requeue_finished_resets_rows_that_still_exist(self):
        with tempfile.TemporaryDirectory() as directory:
            existing = str(Path(directory) / "here.pdf")
            Path(existing).write_bytes(b"x" * 7)
            queue = CompressionQueue()
            queue.add([existing, "/gone.pdf"], size_of=lambda p: 7 if p == existing else 1)
            queue.set_state(existing, Compressed(existing, 3))
            queue.set_state("/gone.pdf", Failed("x"))

            self.assertEqual(queue.requeue_finished(), 1)
            self.assertIsInstance(queue[0].state, Pending)
            self.assertIsInstance(queue[1].state, Failed)


class StateFromResultTests(unittest.TestCase):
    def test_success(self):
        state = state_from_result(
            "a compressed.pdf   ↓ 50.0%",
            {"original_size": 10, "saved_size": 5, "new_size": 5, "output_path": "/x.pdf"},
        )
        self.assertEqual(state, Compressed("/x.pdf", 5))

    def test_no_reduction_is_unchanged_not_failed(self):
        self.assertIsInstance(state_from_result("a.pdf — no size reduction", None), Unchanged)

    def test_failure_reason_is_kept(self):
        self.assertEqual(
            state_from_result("a.pdf — could not open PDF", None), Failed("Could not open PDF")
        )


class OutputLocationTests(unittest.TestCase):
    def test_alongside_uses_compressed_suffix(self):
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "Report.pdf"
            self.assertEqual(
                compressed_copy_path(str(original)),
                str(Path(directory) / "Report compressed.pdf"),
            )

    def test_separate_folder_keeps_name_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as out:
            original = Path(source) / "Report.pdf"
            self.assertEqual(
                compressed_copy_path(str(original), out), str(Path(out) / "Report.pdf")
            )
            (Path(out) / "Report.pdf").write_bytes(b"existing")
            self.assertEqual(
                compressed_copy_path(str(original), out), str(Path(out) / "Report 2.pdf")
            )

    def test_choosing_the_source_folder_still_adds_suffix(self):
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "Report.pdf"
            self.assertEqual(
                compressed_copy_path(str(original), directory),
                str(Path(directory) / "Report compressed.pdf"),
            )

    def test_planned_output_for_replace_is_the_original(self):
        self.assertEqual(planned_output_path("/a/b.pdf", False, "/elsewhere"), "/a/b.pdf")

    def test_compress_pdf_writes_into_output_folder(self):
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as out:
            original = Path(source) / "Report.pdf"
            original.write_bytes(b"%PDF-1.7\n" + b"x" * 64 + b"\n%%EOF")
            destination = Path(out) / "nested"

            def write_smaller(command, **_kwargs):
                output = next(a for a in command if a.startswith("-sOutputFile="))
                Path(output.split("=", 1)[1]).write_bytes(b"%PDF-1.7\n%%EOF")
                return mock.Mock(returncode=0)

            with (
                mock.patch(
                    "fs_pdf_compressor.core.get_ghostscript_config", return_value=("gs", {})
                ),
                mock.patch("fs_pdf_compressor.core.subprocess.run", side_effect=write_smaller),
            ):
                _, metrics = compress_pdf(str(original), "/ebook", True, str(destination))

            self.assertEqual(metrics["output_path"], str(destination / "Report.pdf"))
            self.assertTrue((destination / "Report.pdf").exists())
            self.assertTrue(original.exists(), "original must be kept")


if __name__ == "__main__":
    unittest.main()
