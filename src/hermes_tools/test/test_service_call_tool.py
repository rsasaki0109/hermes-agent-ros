from __future__ import annotations

import asyncio
import threading

import pytest

rclpy = pytest.importorskip('rclpy')

from std_srvs.srv import Trigger  # noqa: E402

from hermes_tools.base import ToolContext  # noqa: E402
from hermes_tools.service_call_tool import ServiceCallTool  # noqa: E402


@pytest.fixture(scope='module')
def ros_context():
    rclpy.init()
    server_node = rclpy.create_node('test_srv_server')
    client_node = rclpy.create_node('test_srv_client')

    def _trigger_cb(request, response):
        response.success = True
        response.message = 'ok'
        return response

    server_node.create_service(Trigger, '/test/trigger', _trigger_cb)

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


def test_call_trigger(ros_context):
    client_node = ros_context
    tool = ServiceCallTool()
    ctx = ToolContext(ros_node=client_node,
                      logger=client_node.get_logger())
    result = asyncio.run(tool.run(
        tool.validate({
            'service': '/test/trigger',
            'srv_type': 'std_srvs/Trigger',
            'request': {},
            'timeout_sec': 3.0,
        }), ctx))
    assert result['status'] == 'ok'
    assert result['response']['success'] is True
    assert result['response']['message'] == 'ok'


def test_unavailable_service_returns_unavailable(ros_context):
    client_node = ros_context
    tool = ServiceCallTool()
    ctx = ToolContext(ros_node=client_node,
                      logger=client_node.get_logger())
    result = asyncio.run(tool.run(
        tool.validate({
            'service': '/nope',
            'srv_type': 'std_srvs/Trigger',
            'request': {},
            'timeout_sec': 0.2,
        }), ctx))
    assert result['status'] == 'unavailable'
    assert result['error']


def test_rejects_invalid_srv_type():
    tool = ServiceCallTool()
    with pytest.raises(Exception):
        asyncio.run(tool.run(
            tool.validate({
                'service': '/x',
                'srv_type': 'notavalidtype',
                'request': {},
            }),
            ToolContext(ros_node=object())))
