"""action_client_tool — send a goal to a ROS2 action server and wait."""
from __future__ import annotations

import importlib
import time

from rclpy.action import ActionClient
from rosidl_runtime_py import message_to_ordereddict

from .base import ROS2ToolAdapter, ToolContext, ToolValidationError


_STATUS_MAP = {
    4: 'succeeded',
    5: 'canceled',
    6: 'aborted',
}


class ActionClientTool(ROS2ToolAdapter):
    name = 'action_client_tool'
    description = (
        'Send a goal to a ROS2 action server, wait for the result, and '
        'return it. Optionally records feedback messages.'
    )
    input_schema = {
        'type': 'object',
        'properties': {
            'action': {'type': 'string'},
            'action_type': {
                'type': 'string',
                'description':
                    'e.g. example_interfaces/Fibonacci',
            },
            'goal': {'type': 'object'},
            'feedback': {'type': 'boolean'},
            'timeout_sec': {
                'type': 'number',
                'minimum': 0.1,
                'maximum': 30.0,
            },
        },
        'required': ['action', 'action_type'],
    }
    output_schema = {
        'type': 'object',
        'properties': {
            'result': {'type': 'object'},
            'status': {'type': 'string'},
            'feedback_log': {'type': 'array'},
            'error': {'type': 'string'},
        },
    }

    async def run(self, args: dict, ctx: ToolContext) -> dict:
        if ctx.ros_node is None:
            raise ToolValidationError('ctx.ros_node is required')

        node = ctx.ros_node
        action_name = args['action']
        action_type_str = args['action_type']
        goal_data = args.get('goal') or {}
        want_feedback = bool(args.get('feedback', False))
        timeout_sec = float(args.get('timeout_sec', 10.0))

        action_type = self._resolve_action_type(action_type_str)
        client = ActionClient(node, action_type, action_name)
        feedback_log: list[dict] = []

        def _on_feedback(msg) -> None:
            feedback_log.append(dict(message_to_ordereddict(msg)))

        try:
            if not client.wait_for_server(timeout_sec=timeout_sec):
                return {
                    'result': {}, 'status': 'unavailable',
                    'feedback_log': [],
                    'error': f'action server {action_name!r} not available',
                }

            goal_msg = self._dict_to_msg(goal_data, action_type.Goal)

            send_future = client.send_goal_async(
                goal_msg,
                feedback_callback=_on_feedback if want_feedback else None)
            end = time.monotonic() + timeout_sec
            while not send_future.done() and time.monotonic() < end:
                time.sleep(0.02)
            if not send_future.done():
                return _timeout('goal submission timed out', feedback_log)

            goal_handle = send_future.result()
            if not goal_handle.accepted:
                return {
                    'result': {}, 'status': 'rejected',
                    'feedback_log': feedback_log,
                    'error': 'goal rejected by server',
                }

            result_future = goal_handle.get_result_async()
            while not result_future.done() and time.monotonic() < end:
                time.sleep(0.02)
            if not result_future.done():
                return _timeout('result wait timed out', feedback_log)

            wrapped = result_future.result()
            status = _STATUS_MAP.get(wrapped.status, f'status_{wrapped.status}')
            return {
                'result': dict(message_to_ordereddict(wrapped.result)),
                'status': status,
                'feedback_log': feedback_log,
                'error': '',
            }
        finally:
            client.destroy()

    @staticmethod
    def _resolve_action_type(type_str: str) -> type:
        """'example_interfaces/Fibonacci' -> class."""
        parts = type_str.split('/')
        if len(parts) == 2:
            pkg, name = parts
            sub = 'action'
        elif len(parts) == 3:
            pkg, sub, name = parts
        else:
            raise ToolValidationError(
                f'invalid action type string: {type_str!r}')
        module = importlib.import_module(f'{pkg}.{sub}')
        return getattr(module, name)


def _timeout(msg: str, feedback_log: list) -> dict:
    return {
        'result': {}, 'status': 'timeout',
        'feedback_log': feedback_log, 'error': msg,
    }
