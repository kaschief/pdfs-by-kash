# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Daniel Lares
# Modifications Copyright (C) 2026 Kaschief

"""Platform-neutral model of a compression queue.

Each queued PDF is in exactly one state. States are separate frozen
dataclasses (a discriminated union keyed by type) so a row can never be, say,
"compressed" without an output path or "failed" without a reason.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Iterable, Mapping, Union

from fs_pdf_compressor.core import format_file_size


@dataclass(frozen=True)
class Ready:
    """Added to the list; nothing has been started. Shown with no status at all."""


@dataclass(frozen=True)
class Queued:
    """Compress was pressed; waiting for its turn in the running batch."""


@dataclass(frozen=True)
class Compressing:
    pass


@dataclass(frozen=True)
class Compressed:
    output_path: str
    new_size: int


@dataclass(frozen=True)
class Unchanged:
    """Ghostscript ran but could not make the file smaller; nothing was written."""

    reason: str


@dataclass(frozen=True)
class Failed:
    reason: str


ItemState = Union[Ready, Queued, Compressing, Compressed, Unchanged, Failed]
IN_FLIGHT_STATES = (Queued, Compressing)
FINISHED_STATES = (Compressed, Unchanged, Failed)


@dataclass(frozen=True)
class QueueItem:
    path: str
    original_size: int
    state: ItemState = field(default_factory=Ready)

    @property
    def name(self) -> str:
        return os.path.basename(self.path)

    @property
    def reduction(self) -> float | None:
        if isinstance(self.state, Compressed) and self.original_size:
            return 100 - self.state.new_size / self.original_size * 100
        return None


def state_from_result(status: str, metrics: Mapping[str, int | str] | None) -> ItemState:
    """Translate compress_pdf's (status, metrics) pair into an ItemState."""
    if metrics is not None and "output_path" in metrics:
        return Compressed(str(metrics["output_path"]), int(metrics["new_size"]))
    _, _, reason = status.partition(" — ")
    reason = reason or "compression failed"
    if reason == "no size reduction":
        return Unchanged("Already as small as it can get — left unchanged")
    return Failed(reason[0].upper() + reason[1:])


class CompressionQueue:
    """Ordered, de-duplicated list of PDFs and their compression state."""

    def __init__(self) -> None:
        self._items: list[QueueItem] = []

    # -- Reading -------------------------------------------------------------

    @property
    def items(self) -> tuple[QueueItem, ...]:
        return tuple(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __getitem__(self, index: int) -> QueueItem:
        return self._items[index]

    def index_of(self, path: str) -> int | None:
        key = _key(path)
        for index, item in enumerate(self._items):
            if _key(item.path) == key:
                return index
        return None

    def paths_in(self, *states: type) -> list[str]:
        return [item.path for item in self._items if isinstance(item.state, states)]

    @property
    def ready_paths(self) -> list[str]:
        return self.paths_in(Ready)

    @property
    def has_ready(self) -> bool:
        return any(isinstance(item.state, Ready) for item in self._items)

    @property
    def has_finished(self) -> bool:
        return any(isinstance(item.state, FINISHED_STATES) for item in self._items)

    @property
    def is_running(self) -> bool:
        return any(isinstance(item.state, IN_FLIGHT_STATES) for item in self._items)

    # -- Mutating ------------------------------------------------------------

    def add(self, paths: Iterable[str], size_of=os.path.getsize) -> int:
        """Add PDFs as Ready. Re-adding a finished file makes it Ready again.

        Returns how many rows were added or re-queued.
        """
        changed = 0
        for path in paths:
            index = self.index_of(path)
            if index is not None:
                existing = self._items[index]
                if isinstance(existing.state, FINISHED_STATES):
                    self._items[index] = replace(
                        existing, original_size=_safe_size(path, size_of), state=Ready()
                    )
                    changed += 1
                continue
            self._items.append(QueueItem(path, _safe_size(path, size_of)))
            changed += 1
        return changed

    def remove(self, indexes: Iterable[int]) -> int:
        """Remove rows that are not part of a running batch."""
        doomed = {
            index
            for index in indexes
            if 0 <= index < len(self._items)
            and not isinstance(self._items[index].state, IN_FLIGHT_STATES)
        }
        self._items = [item for i, item in enumerate(self._items) if i not in doomed]
        return len(doomed)

    def clear(self) -> None:
        """Remove every row except ones in a running batch."""
        self._items = [i for i in self._items if isinstance(i.state, IN_FLIGHT_STATES)]

    def requeue_finished(self, size_of=os.path.getsize) -> int:
        """Return finished rows to Ready so they can be compressed again."""
        count = 0
        for index, item in enumerate(self._items):
            if isinstance(item.state, FINISHED_STATES) and os.path.exists(item.path):
                self._items[index] = replace(
                    item, original_size=_safe_size(item.path, size_of), state=Ready()
                )
                count += 1
        return count

    def queue_ready(self) -> list[str]:
        """Mark every Ready row Queued (Compress was pressed); returns their paths."""
        paths = []
        for index, item in enumerate(self._items):
            if isinstance(item.state, Ready):
                self._items[index] = replace(item, state=Queued())
                paths.append(item.path)
        return paths

    def set_state(self, path: str, state: ItemState) -> int | None:
        index = self.index_of(path)
        if index is not None:
            self._items[index] = replace(self._items[index], state=state)
        return index

    # -- Presentation ----------------------------------------------------------

    def summary_text(self) -> str:
        """Idle summary for the footer (the running batch has its own text)."""
        if not self._items:
            return "Add PDFs to get started"
        done = [i for i in self._items if isinstance(i.state, Compressed)]
        failed = sum(isinstance(i.state, Failed) for i in self._items)
        unchanged = sum(isinstance(i.state, Unchanged) for i in self._items)
        ready = [i for i in self._items if isinstance(i.state, Ready)]

        parts: list[str] = []
        if done:
            before = sum(i.original_size for i in done)
            after = sum(i.state.new_size for i in done)
            saved = before - after
            percent = saved / before * 100 if before else 0
            parts.append(
                f"{len(done)} compressed · {format_file_size(saved)} saved ({percent:.0f}%)"
            )
        if unchanged:
            parts.append(f"{unchanged} unchanged")
        if failed:
            parts.append(f"{failed} failed")
        if ready and parts:
            parts.append(f"{len(ready)} ready")
        elif ready:
            size = sum(i.original_size for i in ready)
            noun = "PDF" if len(ready) == 1 else "PDFs"
            parts.append(f"{len(ready)} {noun} ready · {format_file_size(size)}")
        return " · ".join(parts)


def _key(path: str) -> str:
    return str(Path(path).resolve())


def _safe_size(path: str, size_of) -> int:
    try:
        return int(size_of(path))
    except OSError:
        return 0
