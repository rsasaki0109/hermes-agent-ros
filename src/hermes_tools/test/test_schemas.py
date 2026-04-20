import pytest

from hermes_tools.schemas import msg_to_json_schema, resolve_msg_class


def test_resolve_two_part():
    cls = resolve_msg_class('geometry_msgs/Twist')
    assert cls.__name__ == 'Twist'


def test_resolve_three_part():
    cls = resolve_msg_class('geometry_msgs/msg/Twist')
    assert cls.__name__ == 'Twist'


def test_resolve_invalid():
    with pytest.raises(ValueError):
        resolve_msg_class('notavalidtype')


def test_twist_schema_has_linear_and_angular():
    schema = msg_to_json_schema('geometry_msgs/Twist')
    assert schema['type'] == 'object'
    props = schema['properties']
    assert 'linear' in props and 'angular' in props
    assert props['linear']['type'] == 'object'
    assert props['linear']['properties']['x']['type'] == 'number'


def test_string_array_field():
    schema = msg_to_json_schema('std_msgs/Header')
    assert 'frame_id' in schema['properties']
    assert schema['properties']['frame_id']['type'] == 'string'


def test_custom_hermes_toolcall_array():
    schema = msg_to_json_schema('hermes_msgs/ToolCall')
    assert schema['properties']['tool_name']['type'] == 'string'
    assert schema['properties']['args_json']['type'] == 'string'
