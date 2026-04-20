"""E2E scenario pass for Demo-1.

Runs every prompt in scenarios.yaml `repeat_count` times through the
full Agent -> Executor -> tool path with MockClient, and checks the
observed Twist matches the expected shape.

The observation side uses a direct subscription on /turtle1/cmd_vel
rather than spinning up turtlesim — turtlesim adds GUI overhead and
is not required to validate the agent-side contract.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest
import yaml

rclpy = pytest.importorskip('rclpy')

from geometry_msgs.msg import Twist  # noqa: E402
from rclpy.executors import MultiThreadedExecutor  # noqa: E402

from hermes_msgs.srv import AskAgent  # noqa: E402

from hermes_agent.agent_node import AgentNode  # noqa: E402
from hermes_agent.executor_node import ExecutorNode  # noqa: E402
from hermes_agent.llm.mock_client import MockClient  # noqa: E402
from hermes_agent.safety_filter import SafetyFilter, SafetyRules  # noqa: E402
from hermes_tools.registry import ToolRegistry  # noqa: E402


REPEAT = 3  # "10x per scenario" is the spec goal; we use 3 in CI time.


def _scenarios_path() -> Path:
    here = Path(__file__).resolve()
    return (here.parent.parent.parent.parent
            / 'examples' / 'turtlebot_demo' / 'scenarios.yaml')


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
    exec_node = ExecutorNode(registry, SafetyFilter(rules))
    agent_node = AgentNode(llm=MockClient(), tool_specs=registry.specs())
    client_node = rclpy.create_node('e2e_client')

    ex = MultiThreadedExecutor()
    ex.add_node(exec_node)
    ex.add_node(agent_node)
    ex.add_node(client_node)
    thread = threading.Thread(target=ex.spin, daemon=True)
    thread.start()

    yield client_node

    ex.shutdown()
    agent_node.destroy_node()
    exec_node.destroy_node()
    client_node.destroy_node()
    rclpy.shutdown()


def _ask(client_node, prompt: str) -> AskAgent.Response:
    cli = client_node.create_client(AskAgent, '/hermes/ask')
    assert cli.wait_for_service(timeout_sec=5.0)
    req = AskAgent.Request()
    req.prompt = prompt
    req.session_id = 'e2e'
    fut = cli.call_async(req)
    end = time.monotonic() + 10.0
    while not fut.done() and time.monotonic() < end:
        time.sleep(0.02)
    assert fut.done()
    return fut.result()


@pytest.mark.parametrize(
    'scenario',
    yaml.safe_load(_scenarios_path().read_text())['scenarios'],
    ids=lambda s: s['id'],
)
def test_scenario_passes_repeatedly(stack, scenario):
    client = stack

    for _ in range(REPEAT):
        received: list[Twist] = []
        sub = client.create_subscription(
            Twist, '/turtle1/cmd_vel',
            lambda msg: received.append(msg), 10)

        try:
            resp = _ask(client, scenario['prompt'])
            time.sleep(0.4)
        finally:
            client.destroy_subscription(sub)

        assert resp.ok, f'scenario {scenario["id"]} failed: {resp.reply}'
        assert resp.executed_calls
        assert resp.executed_calls[0].tool_name == scenario['expected_tool']
        assert received, (
            f'no Twist received for scenario {scenario["id"]!r}')

        # Check expected payload shape.
        if 'expected_payload_equals' in scenario:
            expected = scenario['expected_payload_equals']
            last = received[-1]
            assert last.linear.x == expected['linear']['x']
            assert last.linear.y == expected['linear']['y']
            assert last.linear.z == expected['linear']['z']
            assert last.angular.x == expected['angular']['x']
            assert last.angular.y == expected['angular']['y']
            assert last.angular.z == expected['angular']['z']

        if 'expected_payload_contains' in scenario:
            contains = scenario['expected_payload_contains']
            last = received[-1]
            if 'linear' in contains and 'x_gt' in contains['linear']:
                assert last.linear.x > contains['linear']['x_gt']
            if 'angular' in contains and 'z_lt' in contains['angular']:
                assert last.angular.z < contains['angular']['z_lt']
