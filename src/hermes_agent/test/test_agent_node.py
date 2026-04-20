"""Integration test: AgentNode + ExecutorNode + MockClient.

End-to-end: call /hermes/ask with '前に進んで', expect a Twist to land
on /turtle1/cmd_vel.
"""
from __future__ import annotations

import threading
import time

import pytest

rclpy = pytest.importorskip('rclpy')

from geometry_msgs.msg import Twist  # noqa: E402
from rclpy.executors import MultiThreadedExecutor  # noqa: E402

from hermes_msgs.srv import AskAgent  # noqa: E402

from hermes_agent.agent_node import AgentNode  # noqa: E402
from hermes_agent.executor_node import ExecutorNode  # noqa: E402
from hermes_agent.llm.mock_client import MockClient  # noqa: E402
from hermes_agent.safety_filter import SafetyFilter, SafetyRules  # noqa: E402
from hermes_tools.registry import ToolRegistry  # noqa: E402


@pytest.fixture(scope='module')
def stack():
    rclpy.init()
    registry = ToolRegistry.from_config(enabled=['topic_publisher_tool'])
    rules = SafetyRules.from_dict({
        'topic_whitelist': [r'^/turtle1/cmd_vel$'],
        'cmd_vel_limits': {
            'linear_x_abs_max': 0.5, 'angular_z_abs_max': 1.0,
        },
        'duration_sec_max': 10.0,
    })
    executor_node = ExecutorNode(registry, SafetyFilter(rules))
    agent_node = AgentNode(llm=MockClient(), tool_specs=registry.specs())
    client_node = rclpy.create_node('test_ask_client')

    executor = MultiThreadedExecutor()
    executor.add_node(executor_node)
    executor.add_node(agent_node)
    executor.add_node(client_node)
    thread = threading.Thread(target=executor.spin, daemon=True)
    thread.start()

    yield agent_node, executor_node, client_node

    executor.shutdown()
    agent_node.destroy_node()
    executor_node.destroy_node()
    client_node.destroy_node()
    rclpy.shutdown()


def _ask(client_node, prompt: str, timeout_sec: float = 10.0):
    client = client_node.create_client(AskAgent, '/hermes/ask')
    assert client.wait_for_service(timeout_sec=5.0)
    req = AskAgent.Request()
    req.prompt = prompt
    req.session_id = 'test'
    future = client.call_async(req)
    end = time.monotonic() + timeout_sec
    while not future.done() and time.monotonic() < end:
        time.sleep(0.02)
    assert future.done(), 'ask timed out'
    return future.result()


def test_forward_produces_cmd_vel(stack):
    _, _, client_node = stack
    received: list[Twist] = []
    client_node.create_subscription(
        Twist, '/turtle1/cmd_vel',
        lambda msg: received.append(msg), 10)

    resp = _ask(client_node, '前に進んで')
    time.sleep(0.5)

    assert resp.ok, resp.reply
    assert resp.executed_calls, 'no tool calls were executed'
    assert resp.executed_calls[0].tool_name == 'topic_publisher_tool'
    assert received, 'no Twist observed'
    # MockClient emits linear_x=1.0, safety clips to 0.5.
    assert any(abs(m.linear.x - 0.5) < 1e-6 for m in received)


def test_stop_produces_zero_twist(stack):
    _, _, client_node = stack
    received: list[Twist] = []
    client_node.create_subscription(
        Twist, '/turtle1/cmd_vel',
        lambda msg: received.append(msg), 10)

    resp = _ask(client_node, '止まって')
    time.sleep(0.3)

    assert resp.ok, resp.reply
    assert received
    assert received[-1].linear.x == 0.0
    assert received[-1].angular.z == 0.0


def test_unknown_prompt_returns_message_no_tools(stack):
    _, _, client_node = stack
    resp = _ask(client_node, '今日の晩御飯は？')
    assert resp.ok
    assert not resp.executed_calls
    assert resp.reply
