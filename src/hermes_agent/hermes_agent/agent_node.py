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
import os
import time
from pathlib import Path
from typing import Optional

import rclpy
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from hermes_msgs.action import ExecutePlan
from hermes_msgs.msg import AgentStatus, ToolCall
from hermes_msgs.srv import AskAgent
from hermes_tools.registry import ToolRegistry

from .llm.base import LLMClient, Turn
from .llm.mock_client import MockClient
from .llm.ollama_client import OllamaClient
from .memory.short_term import ShortTermMemory
from .memory.tool_log import ToolLog
from .memory.types import ConversationTurn, ToolLogEntry


class AgentNode(Node):
    def __init__(
        self,
        llm: Optional[LLMClient] = None,
        tool_specs: Optional[list[dict]] = None,
        memory: Optional[ShortTermMemory] = None,
        tool_log: Optional[ToolLog] = None,
        system_prompt: Optional[str] = None,
    ) -> None:
        super().__init__('hermes_agent')
        self.declare_parameter('llm_provider', 'mock')
        self.declare_parameter('ollama_host', 'http://localhost:11434')
        self.declare_parameter('ollama_model', '')
        self.declare_parameter('ollama_temperature', 0.2)
        self.declare_parameter('ollama_timeout_sec', 120.0)

        if tool_specs is None:
            self._tool_specs, auto_system = _load_registry_specs_and_system()
        else:
            self._tool_specs = tool_specs
            auto_system = ''

        if system_prompt is not None:
            self._system_prompt = system_prompt
        else:
            self._system_prompt = auto_system

        self._llm = llm if llm is not None else _make_llm(self)
        self._memory = memory or ShortTermMemory()
        self._tool_log = tool_log or ToolLog()
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
        session_id = request.session_id or 'default'
        self._publish_status(AgentStatus.PLANNING, prompt=prompt)

        self._memory.append(
            session_id,
            ConversationTurn(role='user', content=prompt))

        history = self._memory.window(session_id)
        messages = [
            Turn(role=t.role, content=t.content,
                 tool_call_id=t.tool_call_id,
                 tool_name=t.tool_name)
            for t in history
        ]
        llm_resp = self._llm.chat(
            messages=messages,
            tools=self._tool_specs,
            system=self._system_prompt,
        )

        response.reply = llm_resp.message or ''
        response.executed_calls = []

        if not llm_resp.wants_tools:
            self._memory.append(
                session_id,
                ConversationTurn(role='assistant',
                                 content=response.reply))
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

        self._record_tool_turns(session_id, llm_resp.tool_calls,
                                result.results)
        self._memory.append(
            session_id,
            ConversationTurn(role='assistant', content=response.reply))

        return response

    def _record_tool_turns(self, session_id, tool_calls, results):
        by_id = {r.call_id: r for r in results}
        for call in tool_calls:
            r = by_id.get(call.call_id)
            if r is None:
                continue
            entry = ToolLogEntry(
                call_id=call.call_id,
                tool_name=call.tool_name,
                args=dict(call.args),
                ok=bool(r.ok),
                error=r.error or '',
            )
            self._tool_log.append(entry)
            self._memory.append(
                session_id,
                ConversationTurn(
                    role='tool', content=r.result_json or r.error or '',
                    tool_call_id=call.call_id, tool_name=call.tool_name))

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
    node = AgentNode()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    finally:
        node.destroy_node()
        rclpy.shutdown()


def _load_registry_specs_and_system() -> tuple[list[dict], str]:
    """Match ExecutorNode: same tools.yaml + optional system_prompt.md."""
    try:
        from ament_index_python.packages import get_package_share_directory

        bringup = Path(get_package_share_directory('hermes_bringup'))
        tools_yaml = bringup / 'config' / 'tools.yaml'
        if tools_yaml.exists():
            registry = ToolRegistry.from_yaml(tools_yaml)
        else:
            registry = ToolRegistry.from_config(enabled=['topic_publisher_tool'])
        prompt_path = bringup / 'config' / 'system_prompt.md'
        system = (
            prompt_path.read_text(encoding='utf-8')
            if prompt_path.exists()
            else ''
        )
        return registry.specs(), system
    except Exception:
        reg = ToolRegistry.from_config(enabled=['topic_publisher_tool'])
        return reg.specs(), ''


def _make_llm(node: Node) -> LLMClient:
    provider = node.get_parameter('llm_provider').value
    if provider == 'mock':
        return MockClient()
    if provider == 'ollama':
        host = node.get_parameter('ollama_host').value
        model_param = node.get_parameter('ollama_model').value
        model = model_param or os.environ.get(
            'HERMES_OLLAMA_MODEL', 'qwen2.5:7b-instruct')
        temperature = float(node.get_parameter('ollama_temperature').value)
        timeout = float(node.get_parameter('ollama_timeout_sec').value)
        return OllamaClient(
            host=host,
            model=model,
            temperature=temperature,
            timeout_sec=timeout,
        )
    raise ValueError(f'unknown llm provider: {provider!r}')
