from __future__ import annotations

import asyncio
import threading
import time

import pytest

rclpy = pytest.importorskip('rclpy')

from example_interfaces.action import Fibonacci  # noqa: E402
from rclpy.action import ActionServer  # noqa: E402

from hermes_tools.base import ToolContext  # noqa: E402
from hermes_tools.action_client_tool import ActionClientTool  # noqa: E402


@pytest.fixture(scope='module')
def ros_context():
    rclpy.init()
    server_node = rclpy.create_node('test_action_server')
    client_node = rclpy.create_node('test_action_client')

    def _execute(goal_handle):
        order = goal_handle.request.order
        seq = [0, 1]
        for i in range(1, order):
            seq.append(seq[i] + seq[i - 1])
            fb = Fibonacci.Feedback()
            fb.sequence = seq
            goal_handle.publish_feedback(fb)
            time.sleep(0.02)
        goal_handle.succeed()
        result = Fibonacci.Result()
        result.sequence = seq
        return result

    ActionServer(server_node, Fibonacci, '/test/fib', _execute)

    executor = rclpy.executors.MultiThreadedExecutor()
    executor.add_node(server_node)
    executor.add_node(client_node)
    thread = threading.Thread(target=executor.spin, daemon=True)
    thread.start()

    yield client_node

    executor.shutdown()
    server_node.destroy_node()
    client_node.destroy_node()
    rclpy.shutdown()


def test_action_succeeds_with_feedback(ros_context):
    client_node = ros_context
    tool = ActionClientTool()
    ctx = ToolContext(ros_node=client_node,
                      logger=client_node.get_logger())
    result = asyncio.run(tool.run(
        tool.validate({
            'action': '/test/fib',
            'action_type': 'example_interfaces/Fibonacci',
            'goal': {'order': 5},
            'feedback': True,
            'timeout_sec': 5.0,
        }), ctx))
    assert result['status'] == 'succeeded'
    assert list(result['result']['sequence']) == [0, 1, 1, 2, 3, 5]
    assert len(result['feedback_log']) >= 1


def test_unavailable_action_returns_unavailable(ros_context):
    client_node = ros_context
    tool = ActionClientTool()
    ctx = ToolContext(ros_node=client_node,
                      logger=client_node.get_logger())
    result = asyncio.run(tool.run(
        tool.validate({
            'action': '/nowhere',
            'action_type': 'example_interfaces/Fibonacci',
            'goal': {'order': 1},
            'timeout_sec': 0.2,
        }), ctx))
    assert result['status'] == 'unavailable'


def test_rejects_invalid_action_type():
    tool = ActionClientTool()
    with pytest.raises(Exception):
        asyncio.run(tool.run(
            tool.validate({
                'action': '/x',
                'action_type': 'notavalid',
                'goal': {},
            }),
            ToolContext(ros_node=object())))
