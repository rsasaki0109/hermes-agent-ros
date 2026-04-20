"""ROS message type <-> JSON schema helpers.

Used to convert `geometry_msgs/Twist`-style identifiers into JSON
schemas that an LLM can reason about when filling in tool arguments.
"""
from __future__ import annotations

import importlib
from typing import Any


_PRIMITIVE_TO_JSON = {
    'bool': {'type': 'boolean'},
    'boolean': {'type': 'boolean'},
    'byte': {'type': 'integer'},
    'octet': {'type': 'integer'},
    'char': {'type': 'integer'},
    'float': {'type': 'number'},
    'float32': {'type': 'number'},
    'double': {'type': 'number'},
    'float64': {'type': 'number'},
    'long double': {'type': 'number'},
    'int8': {'type': 'integer'},
    'uint8': {'type': 'integer'},
    'int16': {'type': 'integer'},
    'uint16': {'type': 'integer'},
    'short': {'type': 'integer'},
    'unsigned short': {'type': 'integer'},
    'int32': {'type': 'integer'},
    'uint32': {'type': 'integer'},
    'long': {'type': 'integer'},
    'unsigned long': {'type': 'integer'},
    'int64': {'type': 'integer'},
    'uint64': {'type': 'integer'},
    'long long': {'type': 'integer'},
    'unsigned long long': {'type': 'integer'},
    'string': {'type': 'string'},
    'wstring': {'type': 'string'},
}


def resolve_msg_class(type_str: str) -> type:
    """'geometry_msgs/Twist' or 'geometry_msgs/msg/Twist' -> class."""
    parts = type_str.split('/')
    if len(parts) == 2:
        pkg, name = parts
        sub = 'msg'
    elif len(parts) == 3:
        pkg, sub, name = parts
    else:
        raise ValueError(f'invalid msg type string: {type_str!r}')
    module = importlib.import_module(f'{pkg}.{sub}')
    return getattr(module, name)


def msg_to_json_schema(msg_type) -> dict:
    """Build a JSON schema describing the fields of a ROS message class.

    Accepts either a class or a type string. Uses
    `get_fields_and_field_types()` which rosidl generates on every
    message class.
    """
    if isinstance(msg_type, str):
        msg_type = resolve_msg_class(msg_type)
    fields = msg_type.get_fields_and_field_types()
    properties = {}
    for fname, ftype in fields.items():
        properties[fname] = _field_schema(ftype)
    return {
        'type': 'object',
        'properties': properties,
        'additionalProperties': False,
    }


def _field_schema(ftype: str) -> dict:
    """Convert a rosidl field type string into a JSON schema fragment."""
    base, is_array, bound = _split_array(ftype)
    inner = _primitive_or_nested(base)
    if not is_array:
        return inner
    schema: dict[str, Any] = {'type': 'array', 'items': inner}
    if bound is not None:
        schema['maxItems'] = bound
    return schema


def _split_array(ftype: str):
    """Return (base_type, is_array, max_items_or_None)."""
    if ftype.endswith(']'):
        base, bracket = ftype[:-1].split('[', 1)
        bound = int(bracket) if bracket else None
        return base, True, bound
    if ftype.startswith('sequence<') and ftype.endswith('>'):
        inner = ftype[len('sequence<'):-1]
        if ',' in inner:
            base, bound_str = [s.strip() for s in inner.split(',', 1)]
            return base, True, int(bound_str)
        return inner, True, None
    return ftype, False, None


def _primitive_or_nested(base: str) -> dict:
    if base in _PRIMITIVE_TO_JSON:
        return dict(_PRIMITIVE_TO_JSON[base])
    if '/' in base:
        return msg_to_json_schema(base)
    raise ValueError(f'unknown field base type: {base!r}')
