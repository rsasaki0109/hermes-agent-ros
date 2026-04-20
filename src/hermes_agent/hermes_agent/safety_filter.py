"""SafetyFilter — single trust boundary for every ToolCall.

Runs inside the ExecutorNode, just before a ToolCall reaches its
ToolInterface.run. Rules come from safety_rules.yaml:

  topic_whitelist: [ "<regex>", ... ]   # topic arg must match one
  service_allowlist: [ ... ]
  action_allowlist: [ ... ]
  cmd_vel_limits:
    linear_x_abs_max: <float>
    angular_z_abs_max: <float>
  duration_sec_max: <float>

A blocked call becomes (ok=False, sanitized=original, reason=...).
A clipped call becomes (ok=True, sanitized=<new args>, reason=<note>).
"""
from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class SafetyDecision:
    ok: bool
    sanitized_args: dict
    reason: str = ''
    clipped: bool = False


@dataclass
class SafetyRules:
    topic_whitelist: list[re.Pattern] = field(default_factory=list)
    service_allowlist: list[str] = field(default_factory=list)
    action_allowlist: list[str] = field(default_factory=list)
    cmd_vel_linear_x_abs_max: float | None = None
    cmd_vel_angular_z_abs_max: float | None = None
    duration_sec_max: float | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'SafetyRules':
        limits = data.get('cmd_vel_limits') or {}
        return cls(
            topic_whitelist=[re.compile(p)
                             for p in data.get('topic_whitelist', [])],
            service_allowlist=list(data.get('service_allowlist', [])),
            action_allowlist=list(data.get('action_allowlist', [])),
            cmd_vel_linear_x_abs_max=limits.get('linear_x_abs_max'),
            cmd_vel_angular_z_abs_max=limits.get('angular_z_abs_max'),
            duration_sec_max=data.get('duration_sec_max'),
        )

    @classmethod
    def from_yaml(cls, path: str | Path) -> 'SafetyRules':
        return cls.from_dict(yaml.safe_load(Path(path).read_text()) or {})


class SafetyFilter:
    def __init__(self, rules: SafetyRules) -> None:
        self._rules = rules

    def check(self, tool_name: str, args: dict) -> SafetyDecision:
        sanitized = copy.deepcopy(args)
        notes: list[str] = []

        # 1. duration upper bound (applies to any tool with duration_sec).
        if self._rules.duration_sec_max is not None:
            d = sanitized.get('duration_sec')
            if isinstance(d, (int, float)) and d > self._rules.duration_sec_max:
                sanitized['duration_sec'] = self._rules.duration_sec_max
                notes.append(
                    f'duration_sec clipped to {self._rules.duration_sec_max}')

        # 2. tool-specific checks.
        if tool_name == 'topic_publisher_tool':
            decision = self._check_publisher(sanitized, notes)
            if not decision.ok:
                return decision

        if tool_name == 'service_call_tool':
            service = sanitized.get('service', '')
            if (self._rules.service_allowlist
                    and service not in self._rules.service_allowlist):
                return SafetyDecision(
                    ok=False, sanitized_args=sanitized,
                    reason=f'service {service!r} not in allowlist')

        if tool_name == 'action_client_tool':
            action = sanitized.get('action', '')
            if (self._rules.action_allowlist
                    and action not in self._rules.action_allowlist):
                return SafetyDecision(
                    ok=False, sanitized_args=sanitized,
                    reason=f'action {action!r} not in allowlist')

        return SafetyDecision(
            ok=True, sanitized_args=sanitized,
            reason='; '.join(notes), clipped=bool(notes))

    def _check_publisher(self, args: dict,
                         notes: list[str]) -> SafetyDecision:
        topic = args.get('topic', '')

        if self._rules.topic_whitelist:
            if not any(p.search(topic) for p in self._rules.topic_whitelist):
                return SafetyDecision(
                    ok=False, sanitized_args=args,
                    reason=f'topic {topic!r} not in whitelist')

        msg_type = args.get('msg_type', '')
        payload = args.get('payload') or {}
        if msg_type.endswith('/Twist') or msg_type.endswith('/msg/Twist'):
            self._clip_twist(payload, notes)
            args['payload'] = payload
        return SafetyDecision(ok=True, sanitized_args=args)

    def _clip_twist(self, payload: dict, notes: list[str]) -> None:
        lim_lin = self._rules.cmd_vel_linear_x_abs_max
        lim_ang = self._rules.cmd_vel_angular_z_abs_max
        linear = payload.setdefault('linear', {})
        angular = payload.setdefault('angular', {})
        if lim_lin is not None:
            lx = float(linear.get('x', 0.0))
            if abs(lx) > lim_lin:
                linear['x'] = lim_lin if lx > 0 else -lim_lin
                notes.append(
                    f'linear.x clipped {lx:.3f} -> {linear["x"]:.3f}')
        if lim_ang is not None:
            az = float(angular.get('z', 0.0))
            if abs(az) > lim_ang:
                angular['z'] = lim_ang if az > 0 else -lim_ang
                notes.append(
                    f'angular.z clipped {az:.3f} -> {angular["z"]:.3f}')


def safety_check_toolcall_json(filter_: SafetyFilter, tool_name: str,
                               args_json: str) -> SafetyDecision:
    """Helper for the ExecutorNode: decode ToolCall.args_json then check."""
    args = json.loads(args_json) if args_json else {}
    return filter_.check(tool_name, args)
