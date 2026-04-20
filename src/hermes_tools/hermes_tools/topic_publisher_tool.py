"""topic_publisher_tool — publish a ROS2 message one or more times.

Covered by Demo-1 for /turtle1/cmd_vel. The tool is intentionally
stateless: the Executor owns the rclpy.Node and its executor, and this
tool creates / destroys the publisher inside `run`.
"""
from __future__ import annotations

import time

from .base import ROS2ToolAdapter, ToolContext, ToolValidationError


class TopicPublisherTool(ROS2ToolAdapter):
    name = 'topic_publisher_tool'
    description = (
        'Publish a message to a ROS2 topic. Supports one-shot publish or '
        'rate-limited publishing for up to duration_sec seconds.'
    )
    input_schema = {
        'type': 'object',
        'properties': {
            'topic': {'type': 'string'},
            'msg_type': {
                'type': 'string',
                'description': 'e.g. geometry_msgs/Twist',
            },
            'payload': {'type': 'object'},
            'rate_hz': {
                'type': 'number',
                'minimum': 0.1,
                'maximum': 50.0,
                'description':
                    'If set with duration_sec, publish repeatedly at '
                    'this rate. If absent, publish once.',
            },
            'duration_sec': {
                'type': 'number',
                'minimum': 0.0,
                'maximum': 10.0,
            },
            'qos': {'type': 'string'},  # 'default'|'sensor'|'reliable'
        },
        'required': ['topic', 'msg_type', 'payload'],
    }
    output_schema = {
        'type': 'object',
        'properties': {
            'published': {'type': 'integer'},
            'status': {'type': 'string'},
            'error': {'type': 'string'},
        },
    }

    async def run(self, args: dict, ctx: ToolContext) -> dict:
        if ctx.ros_node is None:
            raise ToolValidationError('ctx.ros_node is required')

        node = ctx.ros_node
        topic: str = args['topic']
        msg_type_str: str = args['msg_type']
        payload: dict = args['payload']
        rate_hz: float | None = args.get('rate_hz')
        duration_sec: float = float(args.get('duration_sec', 0.0))
        qos_profile: str = args.get('qos', 'default')

        msg_type = self._resolve_msg_type(msg_type_str)
        qos = self._make_qos(qos_profile)

        publisher = node.create_publisher(msg_type, topic, qos)
        try:
            # Give the discovery a brief moment before first publish.
            time.sleep(0.05)

            msg = self._dict_to_msg(payload, msg_type)

            if rate_hz and duration_sec > 0.0:
                published = self._publish_rated(
                    publisher, msg, rate_hz, duration_sec, ctx.deadline)
            else:
                publisher.publish(msg)
                published = 1

            return {
                'published': published,
                'status': 'ok',
                'error': '',
            }
        finally:
            node.destroy_publisher(publisher)

    @staticmethod
    def _publish_rated(publisher, msg, rate_hz: float,
                       duration_sec: float,
                       deadline: float | None) -> int:
        period = 1.0 / rate_hz
        end = time.monotonic() + duration_sec
        if deadline is not None:
            end = min(end, deadline)
        published = 0
        while time.monotonic() < end:
            publisher.publish(msg)
            published += 1
            time.sleep(period)
        return published
