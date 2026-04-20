"""ExecutorNode — the single trust boundary.

Hosts the `/hermes/execute_plan` action server. For each ToolCall:
  1. Decode args_json.
  2. Run SafetyFilter.check — abort or clip.
  3. Look up the tool in ToolRegistry.
  4. Call ToolInterface.validate, then run(args, ctx).
  5. Emit feedback, accumulate ToolResult.

Tools run in-process and share this node (ctx.ros_node), so all
publishers / clients they create obey this node's executor.
"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Optional

import rclpy
from rclpy.action import ActionServer
from rclpy.action.server import ServerGoalHandle
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from hermes_msgs.action import ExecutePlan
from hermes_msgs.msg import ToolCall, ToolResult

from hermes_tools.base import ToolContext, ToolValidationError
from hermes_tools.registry import ToolRegistry

from .safety_filter import SafetyFilter, SafetyRules


DEFAULT_SAFETY_RULES = {
    'topic_whitelist': [r'^/turtle1/cmd_vel$', r'^/cmd_vel$'],
    'service_allowlist': [],
    'action_allowlist': [],
    'cmd_vel_limits': {
        'linear_x_abs_max': 0.5,
        'angular_z_abs_max': 1.0,
    },
    'duration_sec_max': 10.0,
}


class ExecutorNode(Node):
    def __init__(self, registry: ToolRegistry,
                 safety: SafetyFilter) -> None:
        super().__init__('hermes_executor')
        self._registry = registry
        self._safety = safety
        self._cb_group = ReentrantCallbackGroup()
        self._server = ActionServer(
            self,
            ExecutePlan,
            '/hermes/execute_plan',
            execute_callback=self._execute,
            callback_group=self._cb_group,
        )
        self.get_logger().info(
            f'ExecutorNode ready with tools: {self._registry.names()}')

    async def _execute(self, goal_handle: ServerGoalHandle
                       ) -> ExecutePlan.Result:
        goal = goal_handle.request
        plan_id = goal.plan_id or 'anon'
        self.get_logger().info(
            f'plan {plan_id}: {len(goal.calls)} calls, '
            f'deadline={goal.max_duration_sec}s')

        deadline: Optional[float] = None
        if goal.max_duration_sec and goal.max_duration_sec > 0.0:
            deadline = time.monotonic() + float(goal.max_duration_sec)

        result_msg = ExecutePlan.Result()
        result_msg.status = ExecutePlan.Result.STATUS_OK
        total = len(goal.calls)

        for i, call in enumerate(goal.calls):
            if deadline is not None and time.monotonic() >= deadline:
                result_msg.status = ExecutePlan.Result.STATUS_TIMEOUT
                break

            fb = ExecutePlan.Feedback()
            fb.current_call = call
            fb.progress = (i / total) if total else 1.0
            goal_handle.publish_feedback(fb)

            tool_result = await self._run_one(call, deadline)
            result_msg.results.append(tool_result)

            if (not tool_result.ok
                    and tool_result.error.startswith('SAFETY:')):
                result_msg.status = ExecutePlan.Result.STATUS_SAFETY_BLOCKED
                break

        goal_handle.succeed()
        return result_msg

    async def _run_one(self, call: ToolCall,
                       deadline: Optional[float]) -> ToolResult:
        out = ToolResult()
        out.call_id = call.call_id

        try:
            args = json.loads(call.args_json) if call.args_json else {}
        except json.JSONDecodeError as exc:
            out.ok = False
            out.error = f'BAD_JSON: {exc}'
            return out

        decision = self._safety.check(call.tool_name, args)
        if not decision.ok:
            out.ok = False
            out.error = f'SAFETY: {decision.reason}'
            return out

        if not self._registry.has(call.tool_name):
            out.ok = False
            out.error = f'UNKNOWN_TOOL: {call.tool_name}'
            return out

        tool = self._registry.get(call.tool_name)
        try:
            validated = tool.validate(decision.sanitized_args)
        except ToolValidationError as exc:
            out.ok = False
            out.error = f'VALIDATION: {exc}'
            return out

        ctx = ToolContext(
            ros_node=self,
            deadline=deadline,
            logger=self.get_logger(),
        )
        try:
            result = await tool.run(validated, ctx)
        except Exception as exc:  # noqa: BLE001 — surface to caller
            out.ok = False
            out.error = f'RUNTIME: {type(exc).__name__}: {exc}'
            return out

        out.ok = True
        note = f'; safety_note={decision.reason}' if decision.clipped else ''
        out.result_json = json.dumps(result, default=str)
        out.error = note.lstrip('; ')
        return out


# ---- entrypoint ------------------------------------------------------


def main(args=None) -> None:
    rclpy.init(args=args)
    node = _build_node()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    finally:
        node.destroy_node()
        rclpy.shutdown()


def _build_node() -> ExecutorNode:
    from ament_index_python.packages import get_package_share_directory

    try:
        bringup = Path(get_package_share_directory('hermes_bringup'))
        tools_yaml = bringup / 'config' / 'tools.yaml'
        rules_yaml = bringup / 'config' / 'safety_rules.yaml'
        registry = (
            ToolRegistry.from_yaml(tools_yaml)
            if tools_yaml.exists()
            else _default_registry()
        )
        rules = (
            SafetyRules.from_yaml(rules_yaml)
            if rules_yaml.exists()
            else SafetyRules.from_dict(DEFAULT_SAFETY_RULES)
        )
    except Exception:
        registry = _default_registry()
        rules = SafetyRules.from_dict(DEFAULT_SAFETY_RULES)

    return ExecutorNode(registry, SafetyFilter(rules))


def _default_registry() -> ToolRegistry:
    return ToolRegistry.from_config(enabled=['topic_publisher_tool'])
