"""ToolLog — append-only history of every ToolCall/ToolResult pair."""
from __future__ import annotations

import time
from collections import deque
from typing import Deque

from .types import ToolLogEntry


class ToolLog:
    def __init__(self, max_entries: int = 200) -> None:
        self._entries: Deque[ToolLogEntry] = deque(maxlen=max_entries)

    def append(self, entry: ToolLogEntry) -> None:
        if not entry.stamp:
            entry.stamp = time.time()
        self._entries.append(entry)

    def recent(self, n: int = 10) -> list[ToolLogEntry]:
        if n >= len(self._entries):
            return list(self._entries)
        return list(self._entries)[-n:]

    def last(self) -> ToolLogEntry | None:
        return self._entries[-1] if self._entries else None

    def __len__(self) -> int:
        return len(self._entries)
