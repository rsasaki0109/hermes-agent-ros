"""Value objects shared by ShortTermMemory and ToolLog."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ToolLogEntry:
    call_id: str
    tool_name: str
    args: dict = field(default_factory=dict)
    ok: bool = False
    result: dict = field(default_factory=dict)
    error: str = ''
    stamp: float = 0.0


@dataclass
class ConversationTurn:
    """One exchange inside a session.

    `role` is one of 'user' | 'assistant' | 'tool'. For 'tool' turns,
    `tool_call_id` links back to the ToolLogEntry.
    """
    role: str
    content: str = ''
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None
    stamp: float = 0.0
