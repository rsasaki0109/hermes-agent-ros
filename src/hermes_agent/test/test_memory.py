from hermes_agent.memory.short_term import ShortTermMemory
from hermes_agent.memory.tool_log import ToolLog
from hermes_agent.memory.types import ConversationTurn, ToolLogEntry


def test_short_term_window():
    m = ShortTermMemory(max_turns=3)
    for i in range(5):
        m.append('s1', ConversationTurn(role='user', content=f't{i}'))
    window = m.window('s1')
    assert [t.content for t in window] == ['t2', 't3', 't4']


def test_short_term_sessions_isolated():
    m = ShortTermMemory()
    m.append('a', ConversationTurn(role='user', content='hi-a'))
    m.append('b', ConversationTurn(role='user', content='hi-b'))
    assert m.window('a')[0].content == 'hi-a'
    assert m.window('b')[0].content == 'hi-b'


def test_short_term_auto_stamps():
    m = ShortTermMemory()
    m.append('s', ConversationTurn(role='user', content='x'))
    assert m.window('s')[0].stamp > 0


def test_short_term_clear_session():
    m = ShortTermMemory()
    m.append('s1', ConversationTurn(role='user', content='x'))
    m.clear('s1')
    assert m.window('s1') == []


def test_tool_log_ring_buffer():
    log = ToolLog(max_entries=3)
    for i in range(5):
        log.append(ToolLogEntry(call_id=str(i), tool_name='t'))
    assert len(log) == 3
    assert [e.call_id for e in log.recent(10)] == ['2', '3', '4']
    assert log.last().call_id == '4'
