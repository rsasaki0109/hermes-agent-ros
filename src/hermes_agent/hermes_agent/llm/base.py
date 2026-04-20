"""LLMClient abstract contract.

The Planner talks to the LLM through this interface only. Concrete
implementations (Anthropic, OpenAI, Mock) go in sibling modules.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal, Optional


Role = Literal['user', 'assistant', 'tool', 'system']


@dataclass
class Turn:
    role: Role
    content: str = ''
    tool_call_id: Optional[str] = None      # set when role == 'tool'
    tool_name: Optional[str] = None         # set when role == 'tool'


@dataclass
class ToolCallRequest:
    """What the LLM asked us to call. Mirrors hermes_msgs/ToolCall."""
    call_id: str
    tool_name: str
    args: dict = field(default_factory=dict)


@dataclass
class LLMResponse:
    """One turn of LLM output. Either a reply, tool calls, or both."""
    message: Optional[str] = None
    tool_calls: list[ToolCallRequest] = field(default_factory=list)

    @property
    def wants_tools(self) -> bool:
        return bool(self.tool_calls)


class LLMClient(ABC):
    """Abstract. Subclasses talk to a specific provider."""

    @abstractmethod
    def chat(
        self,
        messages: list[Turn],
        tools: list[dict],
        system: str = '',
    ) -> LLMResponse:
        """Single blocking turn.

        `tools` is the LLM-facing spec list from ToolRegistry.specs().
        Implementations must return ToolCallRequests whose `tool_name`
        exactly matches an entry in `tools`.
        """
