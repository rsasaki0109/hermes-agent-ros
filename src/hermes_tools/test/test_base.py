import asyncio

import pytest

from hermes_tools.base import (
    ToolContext, ToolInterface, ToolValidationError,
)


class _EchoTool(ToolInterface):
    name = 'echo'
    description = 'echo input'
    input_schema = {
        'type': 'object',
        'properties': {
            'text': {'type': 'string'},
            'count': {'type': 'integer', 'minimum': 1, 'maximum': 10},
        },
        'required': ['text'],
    }
    output_schema = {
        'type': 'object',
        'properties': {
            'echoed': {'type': 'string'},
        },
    }

    async def run(self, args, ctx):
        return {'echoed': args['text'] * args.get('count', 1)}


def test_spec_exposes_name_and_schemas():
    t = _EchoTool()
    s = t.spec()
    assert s['name'] == 'echo'
    assert s['input_schema']['required'] == ['text']


def test_validate_accepts_good_args():
    t = _EchoTool()
    out = t.validate({'text': 'hi', 'count': 3})
    assert out == {'text': 'hi', 'count': 3}


def test_validate_rejects_missing_required():
    t = _EchoTool()
    with pytest.raises(ToolValidationError):
        t.validate({'count': 2})


def test_validate_rejects_wrong_type():
    t = _EchoTool()
    with pytest.raises(ToolValidationError):
        t.validate({'text': 123})


def test_validate_drops_null_optional_properties():
    t = _EchoTool()
    out = t.validate({'text': 'hi', 'count': None})
    assert out == {'text': 'hi'}


def test_validate_rejects_out_of_bounds():
    t = _EchoTool()
    with pytest.raises(ToolValidationError):
        t.validate({'text': 'hi', 'count': 99})


def test_run_returns_output():
    t = _EchoTool()
    ctx = ToolContext()
    result = asyncio.run(t.run({'text': 'ab', 'count': 2}, ctx))
    assert result == {'echoed': 'abab'}
