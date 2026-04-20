"""ToolRegistry — loads tool classes from YAML config.

The YAML lists which tools are enabled and optional per-tool allow-lists
(e.g. topic name regexes). The registry itself does not enforce the
allow-list — that is the SafetyFilter's job. It only controls which
tools are exposed to the LLM.
"""
from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import yaml

from .base import ToolInterface


class ToolRegistry:
    """Map tool_name -> ToolInterface instance."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolInterface] = {}

    def register(self, tool: ToolInterface) -> None:
        if not tool.name:
            raise ValueError(
                f'tool {type(tool).__name__} has empty name attribute')
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolInterface:
        if name not in self._tools:
            raise KeyError(f'unknown tool: {name!r}')
        return self._tools[name]

    def has(self, name: str) -> bool:
        return name in self._tools

    def names(self) -> list[str]:
        return sorted(self._tools)

    def specs(self) -> list[dict]:
        """LLM-facing spec list for every enabled tool."""
        return [self._tools[n].spec() for n in self.names()]

    @classmethod
    def from_yaml(cls, path: str | Path,
                  extra_modules: list[str] | None = None) -> 'ToolRegistry':
        """Load enabled tools from a YAML config.

        Schema:
          enabled:
            - <tool_name>       # matches ToolInterface.name
          modules: []           # optional extra import paths to scan
        """
        data = yaml.safe_load(Path(path).read_text()) or {}
        enabled = list(data.get('enabled', []))
        modules = list(data.get('modules', []))
        if extra_modules:
            modules.extend(extra_modules)
        return cls.from_config(enabled=enabled, modules=modules)

    @classmethod
    def from_config(cls, enabled: list[str],
                    modules: list[str] | None = None) -> 'ToolRegistry':
        reg = cls()
        available = _discover_tools(modules or _default_modules())
        for name in enabled:
            if name not in available:
                raise KeyError(
                    f'tool {name!r} not found in modules; '
                    f'available: {sorted(available)}')
            reg.register(available[name]())
        return reg


def _default_modules() -> list[str]:
    return [
        'hermes_tools.topic_publisher_tool',
        'hermes_tools.topic_subscriber_tool',
        'hermes_tools.service_call_tool',
        'hermes_tools.action_client_tool',
    ]


def _discover_tools(modules: list[str]) -> dict[str, type[ToolInterface]]:
    """Import listed modules and return {tool.name: class}."""
    found: dict[str, type[ToolInterface]] = {}
    for modname in modules:
        try:
            mod = importlib.import_module(modname)
        except ImportError:
            continue
        for attr in dir(mod):
            obj: Any = getattr(mod, attr)
            if (isinstance(obj, type)
                    and issubclass(obj, ToolInterface)
                    and obj is not ToolInterface
                    and getattr(obj, 'name', '')):
                found[obj.name] = obj
    return found
