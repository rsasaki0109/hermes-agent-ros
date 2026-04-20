"""ToolInterface / ROS2ToolAdapter / ToolContext.

Canonical contract between the Executor and any tool. See
`docs/interfaces.md` for the prose spec.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


class ToolValidationError(ValueError):
    """Raised by ToolInterface.validate when args violate input_schema."""


@dataclass
class ToolContext:
    """Runtime context passed to ToolInterface.run.

    Tools receive rclpy handles through this object rather than holding
    their own — the Executor owns the lifecycle.
    """

    ros_node: Any = None           # rclpy.node.Node, typed as Any to keep
                                   # hermes_tools importable without rclpy
                                   # during unit tests.
    tf_buffer: Any = None
    deadline: Optional[float] = None  # monotonic seconds
    logger: Any = None
    extras: dict = field(default_factory=dict)


class ToolInterface(ABC):
    """Abstract base for every tool exposed to the LLM.

    Subclasses set class attributes `name`, `description`,
    `input_schema`, `output_schema`. `validate` normalizes args;
    `run` executes and returns a dict matching `output_schema`.
    """

    name: str = ''
    description: str = ''
    input_schema: dict = {}
    output_schema: dict = {}

    def validate(self, args: dict) -> dict:
        """Validate args against input_schema. Default: shallow type check.

        Concrete tools may override for domain-specific checks
        (bounds, regex, units). The returned dict is the canonical
        form passed to `run`.
        """
        if not isinstance(args, dict):
            raise ToolValidationError(
                f'args must be a dict, got {type(args).__name__}')
        return _check_against_schema(args, self.input_schema, path='args')

    @abstractmethod
    async def run(self, args: dict, ctx: ToolContext) -> dict:
        """Execute the tool. Must respect `ctx.deadline` if set."""

    def spec(self) -> dict:
        """LLM-facing spec — what the model sees in its tool catalog."""
        return {
            'name': self.name,
            'description': self.description,
            'input_schema': self.input_schema,
            'output_schema': self.output_schema,
        }


class ROS2ToolAdapter(ToolInterface):
    """Mixin-style base for tools that use rclpy.

    Provides helpers for message type resolution and dict<->msg
    conversion. Kept thin on purpose — each concrete tool owns its
    own publishers / clients inside `run`.
    """

    def _resolve_msg_type(self, type_str: str) -> type:
        """'geometry_msgs/Twist' or 'geometry_msgs/msg/Twist' -> class."""
        parts = type_str.split('/')
        if len(parts) == 2:
            pkg, name = parts
            sub = 'msg'
        elif len(parts) == 3:
            pkg, sub, name = parts
        else:
            raise ToolValidationError(
                f'invalid msg type string: {type_str!r}')
        import importlib
        module = importlib.import_module(f'{pkg}.{sub}')
        return getattr(module, name)

    def _dict_to_msg(self, data: dict, msg_type: type) -> Any:
        msg = msg_type()
        _assign_fields(msg, data)
        return msg

    def _msg_to_dict(self, msg: Any) -> dict:
        from rosidl_runtime_py import message_to_ordereddict
        return dict(message_to_ordereddict(msg))

    def _make_qos(self, profile: str = 'default') -> Any:
        from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
        if profile == 'sensor':
            return QoSProfile(
                reliability=ReliabilityPolicy.BEST_EFFORT,
                history=HistoryPolicy.KEEP_LAST, depth=10)
        if profile == 'reliable':
            return QoSProfile(
                reliability=ReliabilityPolicy.RELIABLE,
                history=HistoryPolicy.KEEP_LAST, depth=10)
        return QoSProfile(depth=10)


# ---- internals -------------------------------------------------------


_JSON_TYPE_MAP = {
    'string': str,
    'integer': int,
    'number': (int, float),
    'boolean': bool,
    'object': dict,
    'array': list,
}


def _check_against_schema(value, schema: dict, path: str):
    """Shallow JSON-schema-lite check. Enough for v1 tool inputs.

    Supports: type, properties, required, items, minimum, maximum.
    Does not support: oneOf, allOf, patternProperties, format.
    """
    if not schema:
        return value
    expected = schema.get('type')
    if expected:
        py_type = _JSON_TYPE_MAP.get(expected)
        if py_type and not isinstance(value, py_type):
            raise ToolValidationError(
                f'{path}: expected {expected}, got '
                f'{type(value).__name__}')
    if expected == 'object':
        props = schema.get('properties', {})
        required_keys = schema.get('required', [])
        for key in list(value.keys()):
            if value[key] is None and key not in required_keys:
                del value[key]
        for required in required_keys:
            if required not in value:
                raise ToolValidationError(
                    f'{path}: missing required key {required!r}')
        for key, sub in props.items():
            if key in value:
                value[key] = _check_against_schema(
                    value[key], sub, f'{path}.{key}')
    if expected == 'array':
        item_schema = schema.get('items')
        if item_schema:
            for i, item in enumerate(value):
                value[i] = _check_against_schema(
                    item, item_schema, f'{path}[{i}]')
    if expected in ('integer', 'number'):
        if 'minimum' in schema and value < schema['minimum']:
            raise ToolValidationError(
                f'{path}: {value} < minimum {schema["minimum"]}')
        if 'maximum' in schema and value > schema['maximum']:
            raise ToolValidationError(
                f'{path}: {value} > maximum {schema["maximum"]}')
    return value


def _assign_fields(msg, data: dict) -> None:
    """Recursively copy dict entries into a ROS message."""
    for key, value in data.items():
        if not hasattr(msg, key):
            raise ToolValidationError(
                f'unknown field {key!r} on {type(msg).__name__}')
        current = getattr(msg, key)
        if isinstance(value, dict) and hasattr(current, '__slots__'):
            _assign_fields(current, value)
        else:
            if isinstance(value, int) and not isinstance(value, bool):
                slot = getattr(msg, key)
                if isinstance(slot, float):
                    value = float(value)
            setattr(msg, key, value)
