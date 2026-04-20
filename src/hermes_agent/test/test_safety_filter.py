import pytest

from hermes_agent.safety_filter import SafetyFilter, SafetyRules


@pytest.fixture
def flt():
    rules = SafetyRules.from_dict({
        'topic_whitelist': [r'^/turtle1/cmd_vel$', r'^/cmd_vel$'],
        'service_allowlist': ['/spawn'],
        'action_allowlist': ['/navigate_to_pose'],
        'cmd_vel_limits': {
            'linear_x_abs_max': 0.5,
            'angular_z_abs_max': 1.0,
        },
        'duration_sec_max': 10.0,
    })
    return SafetyFilter(rules)


def test_allows_in_whitelist(flt):
    d = flt.check('topic_publisher_tool', {
        'topic': '/turtle1/cmd_vel',
        'msg_type': 'geometry_msgs/Twist',
        'payload': {'linear': {'x': 0.1}, 'angular': {'z': 0.0}},
    })
    assert d.ok and not d.clipped


def test_blocks_topic_outside_whitelist(flt):
    d = flt.check('topic_publisher_tool', {
        'topic': '/some/other/topic',
        'msg_type': 'geometry_msgs/Twist',
        'payload': {},
    })
    assert not d.ok
    assert 'whitelist' in d.reason


def test_clips_linear_x(flt):
    d = flt.check('topic_publisher_tool', {
        'topic': '/turtle1/cmd_vel',
        'msg_type': 'geometry_msgs/Twist',
        'payload': {'linear': {'x': 1.5}, 'angular': {'z': 0.0}},
    })
    assert d.ok
    assert d.clipped
    assert d.sanitized_args['payload']['linear']['x'] == 0.5


def test_clips_negative_angular_z(flt):
    d = flt.check('topic_publisher_tool', {
        'topic': '/turtle1/cmd_vel',
        'msg_type': 'geometry_msgs/Twist',
        'payload': {'linear': {'x': 0.0}, 'angular': {'z': -2.5}},
    })
    assert d.ok
    assert d.clipped
    assert d.sanitized_args['payload']['angular']['z'] == -1.0


def test_clips_duration(flt):
    d = flt.check('topic_publisher_tool', {
        'topic': '/turtle1/cmd_vel',
        'msg_type': 'geometry_msgs/Twist',
        'payload': {'linear': {'x': 0.0}, 'angular': {'z': 0.0}},
        'duration_sec': 60.0,
    })
    assert d.ok
    assert d.sanitized_args['duration_sec'] == 10.0


def test_service_blocked(flt):
    d = flt.check('service_call_tool', {
        'service': '/forbidden', 'srv_type': 'x', 'request': {},
    })
    assert not d.ok


def test_service_allowed(flt):
    d = flt.check('service_call_tool', {
        'service': '/spawn', 'srv_type': 'x', 'request': {},
    })
    assert d.ok


def test_action_blocked(flt):
    d = flt.check('action_client_tool', {
        'action': '/drop_robot', 'action_type': 'x', 'goal': {},
    })
    assert not d.ok


def test_from_yaml(tmp_path):
    p = tmp_path / 'rules.yaml'
    p.write_text(
        'topic_whitelist:\n'
        '  - "^/cmd_vel$"\n'
        'cmd_vel_limits:\n'
        '  linear_x_abs_max: 0.2\n'
    )
    rules = SafetyRules.from_yaml(p)
    f = SafetyFilter(rules)
    d = f.check('topic_publisher_tool', {
        'topic': '/cmd_vel',
        'msg_type': 'geometry_msgs/Twist',
        'payload': {'linear': {'x': 1.0}, 'angular': {'z': 0.0}},
    })
    assert d.sanitized_args['payload']['linear']['x'] == 0.2
