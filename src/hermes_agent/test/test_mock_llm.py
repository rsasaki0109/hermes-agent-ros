from hermes_agent.llm.base import Turn
from hermes_agent.llm.mock_client import MockClient


def _ask(prompt: str):
    client = MockClient()
    return client.chat([Turn(role='user', content=prompt)], tools=[])


def test_forward_prompt_emits_positive_linear_x():
    resp = _ask('前に進んで')
    assert resp.wants_tools
    call = resp.tool_calls[0]
    assert call.tool_name == 'topic_publisher_tool'
    assert call.args['topic'] == '/turtle1/cmd_vel'
    assert call.args['payload']['linear']['x'] > 0


def test_stop_prompt_emits_zero_twist():
    resp = _ask('止まって')
    assert resp.wants_tools
    call = resp.tool_calls[0]
    payload = call.args['payload']
    assert payload['linear']['x'] == 0.0
    assert payload['angular']['z'] == 0.0


def test_turn_right_emits_negative_angular_z():
    resp = _ask('右に回って')
    assert resp.wants_tools
    call = resp.tool_calls[0]
    assert call.args['payload']['angular']['z'] < 0


def test_unknown_prompt_returns_message_only():
    resp = _ask('夕飯は何がいい？')
    assert not resp.wants_tools
    assert resp.message


def test_deterministic_across_calls():
    a = _ask('前に進んで').tool_calls[0].args
    b = _ask('前に進んで').tool_calls[0].args
    # call_id varies but args match
    assert a == b
