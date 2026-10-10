# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Daniel Lares
# Modifications Copyright (C) 2026 Kaschief

"""Small, platform-neutral helpers for presenting compression batches."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from fs_pdf_compressor.core import display_folder, format_file_size


# original_size / saved_size / new_size are byte counts; output_path is a str.
CompressionMetric = Mapping[str, int | str]


@dataclass(frozen=True)
class BatchSummary:
    """Aggregate the successful results from one compression batch."""

    completed_files: int
    average_reduction: float
    saved_size: int

    @classmethod
    def from_metrics(
        cls, metrics: Iterable[CompressionMetric | None]
    ) -> BatchSummary | None:
        completed = [metric for metric in metrics if metric is not None]
        if not completed:
            return None
        average = sum(
            metric["saved_size"] / metric["original_size"] * 100 for metric in completed
        ) / len(completed)
        return cls(
            completed_files=len(completed),
            average_reduction=average,
            saved_size=sum(metric["saved_size"] for metric in completed),
        )

    @property
    def status_text(self) -> str:
        return (
            f"Done — {self.average_reduction:.1f}% average · "
            f"{format_file_size(self.saved_size)} saved"
        )

    @property
    def compact_text(self) -> str:
        return f"{self.average_reduction:.0f}% smaller"


def completion_text(
    metrics: Iterable[CompressionMetric | None], reveal_hint: str | None = None
) -> str:
    """Summarise a batch; a single file names its folder and new size.

    ``reveal_hint`` lets a platform UI that supports click-to-reveal append
    an instruction (e.g. "click a file to show it in Finder").
    """
    completed = [metric for metric in metrics if metric is not None]
    summary = BatchSummary.from_metrics(completed)
    if summary is None:
        return "Done — no files were reduced"
    if len(completed) == 1 and "output_path" in completed[0]:
        only = completed[0]
        text = (
            f"Saved to {display_folder(only['output_path'])} · "
            f"{format_file_size(only['new_size'])}"
        )
    else:
        text = summary.status_text
    return f"{text} — {reveal_hint}" if reveal_hint else text
