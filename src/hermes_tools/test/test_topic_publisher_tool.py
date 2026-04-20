"""Integration-level test for topic_publisher_tool.

Requires rclpy — runs inside a short-lived SingleThreadedExecutor.
Skipped if rclpy cannot be imported.
"""
from __future__ import annotations

import asyncio
import threading

import pytest

rclpy = pytest.importorskip('rclpy')

from geometry_msgs.msg import Twist  # noqa: E402

from hermes_tools.base import ToolContext  # noqa: E402
from hermes_tools.topic_publisher_tool import TopicPublisherTool  # noqa: E402


@pytest.fixture
def ros_context():
    rclpy.init()
    node = rclpy.create_node('test_publisher_tool')
    executor = rclpy.executors.SingleThreadedExecutor()
    executor.add_node(node)
    thread = threading.Thread(target=executor.spin, daemon=True)
    thread.start()
    yield node
    executor.shutdown()
    node.destroy_node()
    rclpy.shutdown()


def test_publish_once(ros_context):
    node = ros_context
    received: list[Twist] = []
    node.create_subscription(
        Twist, '/test/cmd_vel',
        lambda msg: received.append(msg), 10)

    tool = TopicPublisherTool()
    ctx = ToolContext(ros_node=node, logger=node.get_logger())
    args = tool.validate({
        'topic': '/test/cmd_vel',
        'msg_type': 'geometry_msgs/Twist',
        'payload': {'linear': {'x': 0.3, 'y': 0.0, 'z': 0.0},
                    'angular': {'x': 0.0, 'y': 0.0, 'z': 0.0}},
    })
    result = asyncio.run(tool.run(args, ctx))

    # Let the subscription callback drain.
    deadline = 1.0
    step = 0.05
    waited = 0.0
    while not received and waited < deadline:
        import time as _t
        _t.sleep(step)
        waited += step

    assert result['status'] == 'ok'
    assert result['published'] == 1
    assert received, 'subscriber never received the message'
    assert abs(received[0].linear.x - 0.3) < 1e-6


def test_publish_rated(ros_context):
    node = ros_context
    received = []
    node.create_subscription(
        Twist, '/test/cmd_vel_rated',
        lambda msg: received.append(msg), 10)

    tool = TopicPublisherTool()
    ctx = ToolContext(ros_node=node, logger=node.get_logger())
    args = tool.validate({
        'topic': '/test/cmd_vel_rated',
        'msg_type': 'geometry_msgs/Twist',
        'payload': {'linear': {'x': 0.2, 'y': 0.0, 'z': 0.0},
                    'angular': {'x': 0.0, 'y': 0.0, 'z': 0.0}},
        'rate_hz': 10.0,
        'duration_sec': 0.5,
    })
    result = asyncio.run(tool.run(args, ctx))

    import time as _t
    _t.sleep(0.3)
    assert result['status'] == 'ok'
    # 10Hz x 0.5s ≈ 5 publishes; allow jitter.
    assert result['published'] >= 3
    assert len(received) >= 3


def test_rejects_unknown_msg_type():
    tool = TopicPublisherTool()
    with pytest.raises(Exception):
        asyncio.run(tool.run(
            tool.validate({
                'topic': '/x',
                'msg_type': 'nonexistent_pkg/DoesNotExist',
                'payload': {},
            }),
            ToolContext(ros_node=object()),  # will never get to publish
        ))
