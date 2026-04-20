"""service_call_tool — call any ROS2 service by name and type string."""
from __future__ import annotations

import importlib
import time

from rosidl_runtime_py import message_to_ordereddict

from .base import ROS2ToolAdapter, ToolContext, ToolValidationError


class ServiceCallTool(ROS2ToolAdapter):
    name = 'service_call_tool'
    description = (
        'Call a ROS2 service and return the response as a dict. '
        'Respects SafetyFilter.service_allowlist when enforced.'
    )
    input_schema = {
        'type': 'object',
        'properties': {
            'service': {'type': 'string'},
            'srv_type': {
                'type': 'string',
                'description': 'e.g. std_srvs/Trigger',
            },
            'request': {'type': 'object'},
            'timeout_sec': {
                'type': 'number',
                'minimum': 0.1,
                'maximum': 5.0,
            },
        },
        'required': ['service', 'srv_type'],
    }
    output_schema = {
        'type': 'object',
        'properties': {
            'response': {'type': 'object'},
            'status': {'type': 'string'},
            'error': {'type': 'string'},
        },
    }

    async def run(self, args: dict, ctx: ToolContext) -> dict:
        if ctx.ros_node is None:
            raise ToolValidationError('ctx.ros_node is required')

        node = ctx.ros_node
        service = args['service']
        srv_type_str = args['srv_type']
        request_data = args.get('request') or {}
        timeout_sec = float(args.get('timeout_sec', 3.0))

        srv_type = self._resolve_srv_type(srv_type_str)

        client = node.create_client(srv_type, service)
        try:
            if not client.wait_for_service(timeout_sec=timeout_sec):
                return {
                    'response': {},
                    'status': 'unavailable',
                    'error': f'service {service!r} not available',
                }

            request = self._dict_to_msg(request_data, srv_type.Request)
            future = client.call_async(request)

            end = time.monotonic() + timeout_sec
            while not future.done() and time.monotonic() < end:
                time.sleep(0.01)

            if not future.done():
                return {
                    'response': {}, 'status': 'timeout',
                    'error': f'no response within {timeout_sec}s',
                }

            response = future.result()
            return {
                'response': dict(message_to_ordereddict(response)),
                'status': 'ok',
                'error': '',
            }
        finally:
            node.destroy_client(client)

    @staticmethod
    def _resolve_srv_type(type_str: str) -> type:
        """'std_srvs/Trigger' or 'std_srvs/srv/Trigger' -> class."""
        parts = type_str.split('/')
        if len(parts) == 2:
            pkg, name = parts
            sub = 'srv'
        elif len(parts) == 3:
            pkg, sub, name = parts
        else:
            raise ToolValidationError(
                f'invalid srv type string: {type_str!r}')
        module = importlib.import_module(f'{pkg}.{sub}')
        return getattr(module, name)
