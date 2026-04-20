"""AgentNode — Planner + user-facing ROS2 endpoint.

- Hosts `/hermes/ask` (srv) for single-shot user queries.
- Calls the configured LLMClient to turn a prompt into ToolCalls.
- Dispatches those ToolCalls through an ExecutePlan action client.
- Publishes /hermes/agent_status on state changes.

Memory management (long history, tool logs) lives in the `memory/`
module and is wired in by T-15.
"""
from __future__ import annotations

import json
import time
from typing import Optional

import rclpy
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from hermes_msgs.action import ExecutePlan
from hermes_msgs.msg import AgentStatus, ToolCall
from hermes_msgs.srv import AskAgent

from .llm.base import LLMClient, Turn
from .llm.mock_client import MockClient


class AgentNode(Node):
    def __init__(self, llm: LLMClient,
                 tool_specs: Optional[list[dict]] = None) -> None:
        super().__init__('hermes_agent')
        self._llm = llm
        self._tool_specs = tool_specs or []
        self._cb = ReentrantCallbackGroup()

        self._ask_srv = self.create_service(
            AskAgent, '/hermes/ask',
            self._handle_ask, callback_group=self._cb)
        self._status_pub = self.create_publisher(
            AgentStatus, '/hermes/agent_status', 10)
        self._execute_client = ActionClient(
            self, ExecutePlan, '/hermes/execute_plan',
            callback_group=self._cb)

        self._publish_status(AgentStatus.IDLE)
        self.get_logger().info('AgentNode ready')

    def _handle_ask(self, request: AskAgent.Request,
                    response: AskAgent.Response) -> AskAgent.Response:
        prompt = request.prompt or ''
        self._publish_status(AgentStatus.PLANNING, prompt=prompt)

        # For v1: single-turn. History lives inside the srv request.
        messages = [Turn(role='user', content=prompt)]
        llm_resp = self._llm.chat(
            messages=messages,
            tools=self._tool_specs,
            system='',
        )

        response.reply = llm_resp.message or ''
        response.executed_calls = []

        if not llm_resp.wants_tools:
            self._publish_status(AgentStatus.IDLE)
            response.ok = True
            return response

        calls_msgs = _to_toolcall_msgs(llm_resp.tool_calls)

        self._publish_status(
            AgentStatus.EXECUTING,
            prompt=prompt,
            current_call_id=calls_msgs[0].call_id if calls_msgs else '')
        result = self._execute_plan(calls_msgs,
                                    timeout_sec=15.0)
        self._publish_status(AgentStatus.IDLE)

        if result is None:
            response.reply += '\n(executor unavailable)'
            response.ok = False
            return response

        response.executed_calls = calls_msgs
        response.ok = (
            result.status == ExecutePlan.Result.STATUS_OK
            and all(r.ok for r in result.results))

        notes = [r.error for r in result.results if r.error]
        if notes:
            response.reply += '\n' + '\n'.join(notes)

        return response

    def _execute_plan(self, calls: list[ToolCall],
                      timeout_sec: float):
        if not self._execute_client.wait_for_server(timeout_sec=5.0):
            self.get_logger().error(
                '/hermes/execute_plan action server not available')
            return None

        goal = ExecutePlan.Goal()
        goal.calls = calls
        goal.plan_id = f'plan-{int(time.time() * 1000)}'
        goal.max_duration_sec = float(timeout_sec)

        send_future = self._execute_client.send_goal_async(goal)
        _spin_until_done(send_future, timeout_sec=timeout_sec)
        if not send_future.done():
            return None
        goal_handle = send_future.result()
        if not goal_handle.accepted:
            self.get_logger().error('ExecutePlan goal rejected')
            return None

        result_future = goal_handle.get_result_async()
        _spin_until_done(result_future, timeout_sec=timeout_sec)
        if not result_future.done():
            return None
        return result_future.result().result

    def _publish_status(self, state: int, prompt: str = '',
                        current_call_id: str = '') -> None:
        msg = AgentStatus()
        msg.state = state
        msg.last_user_prompt = prompt
        msg.current_call_id = current_call_id
        msg.stamp = self.get_clock().now().to_msg()
        self._status_pub.publish(msg)


def _to_toolcall_msgs(tool_calls) -> list[ToolCall]:
    out: list[ToolCall] = []
    for tc in tool_calls:
        m = ToolCall()
        m.tool_name = tc.tool_name
        m.call_id = tc.call_id
        m.args_json = json.dumps(tc.args)
        out.append(m)
    return out


def _spin_until_done(future, timeout_sec: float) -> None:
    """Busy-wait on a Future that will be resolved by another thread."""
    end = time.monotonic() + timeout_sec
    while not future.done() and time.monotonic() < end:
        time.sleep(0.02)


# ---- entrypoint ------------------------------------------------------


def main(args=None) -> None:
    rclpy.init(args=args)
    node = AgentNode(llm=MockClient())
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    finally:
        node.destroy_node()
        rclpy.shutdown()
