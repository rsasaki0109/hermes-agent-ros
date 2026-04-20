"""ShortTermMemory — per-session ring buffer of conversation turns."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque, Iterable

from .types import ConversationTurn


class ShortTermMemory:
    def __init__(self, max_turns: int = 20) -> None:
        self._max = max_turns
        self._by_session: dict[str, Deque[ConversationTurn]] = defaultdict(
            lambda: deque(maxlen=self._max))

    def append(self, session_id: str, turn: ConversationTurn) -> None:
        if not turn.stamp:
            turn.stamp = time.time()
        self._by_session[session_id].append(turn)

    def window(self, session_id: str,
               n: int | None = None) -> list[ConversationTurn]:
        buf = self._by_session.get(session_id, deque())
        if n is None or n >= len(buf):
            return list(buf)
        return list(buf)[-n:]

    def clear(self, session_id: str | None = None) -> None:
        if session_id is None:
            self._by_session.clear()
        else:
            self._by_session.pop(session_id, None)

    def sessions(self) -> Iterable[str]:
        return list(self._by_session.keys())
