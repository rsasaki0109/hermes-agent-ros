"""Unit tests for OllamaClient (HTTP mocked). Optional live probe."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from hermes_agent.llm.base import Turn
from hermes_agent.llm.ollama_client import OllamaClient


def test_ollama_chat_builds_tools_and_parses_tool_calls():
    canned = {
        'message': {
            'role': 'assistant',
            'content': '前進します',
            'tool_calls': [{
                'function': {
                    'name': 'topic_publisher_tool',
                    'arguments': {
                        'topic': '/turtle1/cmd_vel',
                        'msg_type': 'geometry_msgs/Twist',
                        'payload': {
                            'linear': {'x': 0.3, 'y': 0.0, 'z': 0.0},
                            'angular': {'x': 0.0, 'y': 0.0, 'z': 0.0},
                        },
                    },
                },
            }],
        },
    }
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(canned).encode('utf-8')
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = lambda *a: None

    with patch('hermes_agent.llm.ollama_client.urlopen', return_value=mock_resp) as uo:
        client = OllamaClient()
        specs = [{
            'name': 'topic_publisher_tool',
            'description': 'pub',
            'input_schema': {'type': 'object', 'properties': {}},
        }]
        r = client.chat(
            [Turn(role='user', content='前に進んで')],
            specs,
            system='You are a turtle.',
        )

    assert r.message == '前進します'
    assert r.wants_tools
    assert r.tool_calls[0].tool_name == 'topic_publisher_tool'
    assert r.tool_calls[0].args['topic'] == '/turtle1/cmd_vel'

    req = uo.call_args[0][0]
    body = json.loads(req.data.decode('utf-8'))
    assert body['model'] == 'qwen2.5:7b-instruct'
    assert body['messages'][0] == {
        'role': 'system', 'content': 'You are a turtle.'}
    assert body['messages'][-1]['role'] == 'user'
    assert len(body['tools']) == 1
    assert body['tools'][0]['function']['name'] == 'topic_publisher_tool'


def test_ollama_parses_string_arguments():
    args_str = json.dumps({'topic': '/t', 'msg_type': 'geometry_msgs/Twist', 'payload': {}})
    canned = {
        'message': {
            'role': 'assistant',
            'content': '',
            'tool_calls': [{
                'function': {
                    'name': 'topic_publisher_tool',
                    'arguments': args_str,
                },
            }],
        },
    }
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(canned).encode('utf-8')
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = lambda *a: None

    with patch('hermes_agent.llm.ollama_client.urlopen', return_value=mock_resp):
        r = OllamaClient().chat([Turn(role='user', content='x')], [], system='')
    assert r.tool_calls[0].args['topic'] == '/t'


def test_tool_turn_includes_tool_call_id_and_name():
    canned = {'message': {'role': 'assistant', 'content': 'ok'}}
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(canned).encode('utf-8')
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = lambda *a: None

    with patch('hermes_agent.llm.ollama_client.urlopen', return_value=mock_resp) as uo:
        OllamaClient().chat(
            [
                Turn(role='user', content='hi'),
                Turn(role='tool', content='{"published":1}',
                     tool_call_id='abc', tool_name='topic_publisher_tool'),
            ],
            [],
            system='',
        )
    body = json.loads(uo.call_args[0][0].data.decode('utf-8'))
    tool_msgs = [m for m in body['messages'] if m.get('role') == 'tool']
    assert tool_msgs[0]['tool_call_id'] == 'abc'
    assert tool_msgs[0]['name'] == 'topic_publisher_tool'

