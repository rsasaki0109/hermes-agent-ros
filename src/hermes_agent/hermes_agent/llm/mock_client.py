"""Deterministic mock LLM client.

Maps a small set of Japanese prompts to `topic_publisher_tool` calls
on `/turtle1/cmd_vel`. Used by the E2E test and for local dev without
API credentials.
"""
from __future__ import annotations

import uuid

from .base import LLMClient, LLMResponse, ToolCallRequest, Turn


_TWIST_ZERO = {
    'linear': {'x': 0.0, 'y': 0.0, 'z': 0.0},
    'angular': {'x': 0.0, 'y': 0.0, 'z': 0.0},
}


def _publish_cmd_vel(linear_x: float, angular_z: float,
                     duration_sec: float = 2.0) -> ToolCallRequest:
    payload = {
        'linear': {'x': linear_x, 'y': 0.0, 'z': 0.0},
        'angular': {'x': 0.0, 'y': 0.0, 'z': angular_z},
    }
    return ToolCallRequest(
        call_id=uuid.uuid4().hex,
        tool_name='topic_publisher_tool',
        args={
            'topic': '/turtle1/cmd_vel',
            'msg_type': 'geometry_msgs/Twist',
            'payload': payload,
            'rate_hz': 10.0,
            'duration_sec': duration_sec,
        },
    )


class MockClient(LLMClient):
    """Rule-based mock. Deterministic: same prompt -> same ToolCall."""

    def chat(self, messages, tools, system=''):
        prompt = _latest_user_prompt(messages)
        if prompt is None:
            return LLMResponse(message='')

        # Order matters: check "止まって" before substring overlap.
        if '止ま' in prompt or 'stop' in prompt.lower():
            call = ToolCallRequest(
                call_id=uuid.uuid4().hex,
                tool_name='topic_publisher_tool',
                args={
                    'topic': '/turtle1/cmd_vel',
                    'msg_type': 'geometry_msgs/Twist',
                    'payload': _TWIST_ZERO,
                },
            )
            return LLMResponse(message='停止します', tool_calls=[call])

        if '前' in prompt or 'forward' in prompt.lower():
            return LLMResponse(
                message='前進します',
                tool_calls=[_publish_cmd_vel(linear_x=1.0, angular_z=0.0)],
            )

        if '右' in prompt or 'right' in prompt.lower():
            return LLMResponse(
                message='右に回ります',
                tool_calls=[_publish_cmd_vel(linear_x=0.0, angular_z=-1.0)],
            )

        if '左' in prompt or 'left' in prompt.lower():
            return LLMResponse(
                message='左に回ります',
                tool_calls=[_publish_cmd_vel(linear_x=0.0, angular_z=1.0)],
            )

        return LLMResponse(message='要求を理解できませんでした')


def _latest_user_prompt(messages: list[Turn]) -> str | None:
    for turn in reversed(messages):
        if turn.role == 'user':
            return turn.content
    return None
