"""Integration test for ExecutorNode.

Spins the Executor in a background thread, sends an ExecutePlan goal
with one topic_publisher_tool call, and checks that a subscriber on
/turtle1/cmd_vel receives the message.
"""
from __future__ import annotations

import json
import threading
import time
import uuid

import pytest

rclpy = pytest.importorskip('rclpy')

from geometry_msgs.msg import Twist  # noqa: E402
from rclpy.action import ActionClient  # noqa: E402
from rclpy.executors import MultiThreadedExecutor  # noqa: E402

from hermes_msgs.action import ExecutePlan  # noqa: E402
from hermes_msgs.msg import ToolCall  # noqa: E402

from hermes_agent.executor_node import ExecutorNode  # noqa: E402
from hermes_agent.safety_filter import SafetyFilter, SafetyRules  # noqa: E402
from hermes_tools.registry import ToolRegistry  # noqa: E402


@pytest.fixture(scope='module')
def running_executor():
    rclpy.init()
    registry = ToolRegistry.from_config(enabled=['topic_publisher_tool'])
    rules = SafetyRules.from_dict({
        'topic_whitelist': [r'^/turtle1/cmd_vel$'],
        'cmd_vel_limits': {
            'linear_x_abs_max': 0.5, 'angular_z_abs_max': 1.0,
        },
        'duration_sec_max': 10.0,
    })
    exec_node = ExecutorNode(registry, SafetyFilter(rules))

    client_node = rclpy.create_node('test_exec_client')

    executor = MultiThreadedExecutor()
    executor.add_node(exec_node)
    executor.add_node(client_node)
    thread = threading.Thread(target=executor.spin, daemon=True)
    thread.start()

    yield exec_node, client_node

    executor.shutdown()
    exec_node.destroy_node()
    client_node.destroy_node()
    rclpy.shutdown()


def _send_plan(client_node, calls):
    client = ActionClient(
        client_node, ExecutePlan, '/hermes/execute_plan')
    assert client.wait_for_server(timeout_sec=5.0), 'server not up'
    goal = ExecutePlan.Goal()
    goal.calls = calls
    goal.plan_id = 'test'
    goal.max_duration_sec = 5.0
    send_future = client.send_goal_async(goal)
    while not send_future.done():
        time.sleep(0.02)
    goal_handle = send_future.result()
    assert goal_handle.accepted, 'goal rejected'
    result_future = goal_handle.get_result_async()
    while not result_future.done():
        time.sleep(0.02)
    return result_future.result().result


def test_executor_publishes_cmd_vel(running_executor):
    exec_node, client_node = running_executor
    received = []
    client_node.create_subscription(
        Twist, '/turtle1/cmd_vel',
        lambda msg: received.append(msg), 10)

    call = ToolCall()
    call.tool_name = 'topic_publisher_tool'
    call.call_id = uuid.uuid4().hex
    call.args_json = json.dumps({
        'topic': '/turtle1/cmd_vel',
        'msg_type': 'geometry_msgs/Twist',
        'payload': {
            'linear': {'x': 0.3, 'y': 0.0, 'z': 0.0},
            'angular': {'x': 0.0, 'y': 0.0, 'z': 0.0},
        },
    })

    result = _send_plan(client_node, [call])

    time.sleep(0.3)
    assert len(result.results) == 1
    assert result.results[0].ok, result.results[0].error
    assert received, 'subscriber never saw the message'
    assert abs(received[-1].linear.x - 0.3) < 1e-6


def test_safety_clipping_preserves_execution(running_executor):
    _, client_node = running_executor
    received = []
    client_node.create_subscription(
        Twist, '/turtle1/cmd_vel',
        lambda msg: received.append(msg), 10)

    call = ToolCall()
    call.tool_name = 'topic_publisher_tool'
    call.call_id = uuid.uuid4().hex
    call.args_json = json.dumps({
        'topic': '/turtle1/cmd_vel',
        'msg_type': 'geometry_msgs/Twist',
        'payload': {
            'linear': {'x': 5.0, 'y': 0.0, 'z': 0.0},  # over limit
            'angular': {'x': 0.0, 'y': 0.0, 'z': 0.0},
        },
    })

    result = _send_plan(client_node, [call])
    time.sleep(0.3)

    assert result.results[0].ok
    # Safety note should be surfaced.
    assert 'clipped' in result.results[0].error
    assert abs(received[-1].linear.x - 0.5) < 1e-6


def test_safety_blocked_topic_reports_error(running_executor):
    _, client_node = running_executor
    call = ToolCall()
    call.tool_name = 'topic_publisher_tool'
    call.call_id = uuid.uuid4().hex
    call.args_json = json.dumps({
        'topic': '/forbidden/topic',
        'msg_type': 'geometry_msgs/Twist',
        'payload': {},
    })

    result = _send_plan(client_node, [call])

    assert result.status == ExecutePlan.Result.STATUS_SAFETY_BLOCKED
    assert result.results[0].ok is False
    assert result.results[0].error.startswith('SAFETY:')
