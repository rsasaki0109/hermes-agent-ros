from __future__ import annotations

import asyncio
import threading
import time

import pytest

rclpy = pytest.importorskip('rclpy')

from std_msgs.msg import String  # noqa: E402

from hermes_tools.base import ToolContext  # noqa: E402
from hermes_tools.topic_subscriber_tool import TopicSubscriberTool  # noqa: E402


@pytest.fixture(scope='module')
def ros_context():
    rclpy.init()
    node = rclpy.create_node('test_subscriber_tool')
    executor = rclpy.executors.SingleThreadedExecutor()
    executor.add_node(node)
    thread = threading.Thread(target=executor.spin, daemon=True)
    thread.start()
    yield node
    executor.shutdown()
    node.destroy_node()
    rclpy.shutdown()


def test_collects_samples_in_window(ros_context):
    node = ros_context
    pub = node.create_publisher(String, '/test/chatter', 10)

    def _pump():
        for i in range(15):
            msg = String()
            msg.data = f'm{i}'
            pub.publish(msg)
            time.sleep(0.05)
    threading.Thread(target=_pump, daemon=True).start()

    tool = TopicSubscriberTool()
    ctx = ToolContext(ros_node=node, logger=node.get_logger())
    args = tool.validate({
        'topic': '/test/chatter',
        'msg_type': 'std_msgs/String',
        'duration_sec': 1.0,
        'max_samples': 100,
    })
    result = asyncio.run(tool.run(args, ctx))

    assert result['count'] >= 5
    assert result['samples'][0]['data'].get('data', '').startswith('m')


def test_max_samples_enforced(ros_context):
    node = ros_context
    pub = node.create_publisher(String, '/test/chatter_burst', 20)

    def _pump():
        for i in range(30):
            msg = String()
            msg.data = f'x{i}'
            pub.publish(msg)
            time.sleep(0.01)
    threading.Thread(target=_pump, daemon=True).start()

    tool = TopicSubscriberTool()
    ctx = ToolContext(ros_node=node, logger=node.get_logger())
    result = asyncio.run(tool.run(
        tool.validate({
            'topic': '/test/chatter_burst',
            'msg_type': 'std_msgs/String',
            'duration_sec': 2.0,
            'max_samples': 5,
        }), ctx))

    assert result['count'] <= 5


def test_rejects_duration_over_limit():
    tool = TopicSubscriberTool()
    with pytest.raises(Exception):
        tool.validate({
            'topic': '/x',
            'msg_type': 'std_msgs/String',
            'duration_sec': 60.0,
        })
