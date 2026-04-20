"""topic_subscriber_tool — snapshot a topic for up to duration_sec.

Opens a temporary subscription on the Executor's node, collects up to
`max_samples` messages within the window, then returns them as plain
dicts so the LLM can reason about the data.
"""
from __future__ import annotations

import threading
import time

from rosidl_runtime_py import message_to_ordereddict

from .base import ROS2ToolAdapter, ToolContext, ToolValidationError


class TopicSubscriberTool(ROS2ToolAdapter):
    name = 'topic_subscriber_tool'
    description = (
        'Briefly subscribe to a ROS2 topic and return the messages '
        'received during the window as plain dicts.'
    )
    input_schema = {
        'type': 'object',
        'properties': {
            'topic': {'type': 'string'},
            'msg_type': {'type': 'string'},
            'duration_sec': {
                'type': 'number',
                'minimum': 0.1,
                'maximum': 5.0,
            },
            'max_samples': {
                'type': 'integer',
                'minimum': 1,
                'maximum': 100,
            },
            'qos': {'type': 'string'},
        },
        'required': ['topic', 'msg_type', 'duration_sec'],
    }
    output_schema = {
        'type': 'object',
        'properties': {
            'samples': {'type': 'array'},
            'count': {'type': 'integer'},
            'dropped': {'type': 'integer'},
        },
    }

    async def run(self, args: dict, ctx: ToolContext) -> dict:
        if ctx.ros_node is None:
            raise ToolValidationError('ctx.ros_node is required')

        node = ctx.ros_node
        topic = args['topic']
        msg_type_str = args['msg_type']
        duration_sec = float(args['duration_sec'])
        max_samples = int(args.get('max_samples', 20))
        qos_profile = args.get('qos', 'default')

        msg_type = self._resolve_msg_type(msg_type_str)
        qos = self._make_qos(qos_profile)

        samples: list[dict] = []
        dropped = 0
        lock = threading.Lock()

        def _cb(msg) -> None:
            nonlocal dropped
            with lock:
                if len(samples) >= max_samples:
                    dropped += 1
                    return
                samples.append({
                    'stamp': time.time(),
                    'data': dict(message_to_ordereddict(msg)),
                })

        sub = node.create_subscription(msg_type, topic, _cb, qos)
        try:
            end = time.monotonic() + duration_sec
            if ctx.deadline is not None:
                end = min(end, ctx.deadline)
            while time.monotonic() < end:
                with lock:
                    if len(samples) >= max_samples:
                        break
                time.sleep(0.02)
        finally:
            node.destroy_subscription(sub)

        with lock:
            return {
                'samples': list(samples),
                'count': len(samples),
                'dropped': dropped,
            }
