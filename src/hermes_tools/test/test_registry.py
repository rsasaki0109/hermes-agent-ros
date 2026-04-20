import pytest

from hermes_tools.base import ToolInterface
from hermes_tools.registry import ToolRegistry


class _DummyA(ToolInterface):
    name = 'dummy_a'
    description = 'a'
    input_schema = {'type': 'object'}
    output_schema = {'type': 'object'}

    async def run(self, args, ctx):
        return {}


class _DummyB(ToolInterface):
    name = 'dummy_b'
    description = 'b'
    input_schema = {'type': 'object'}
    output_schema = {'type': 'object'}

    async def run(self, args, ctx):
        return {}


def test_register_and_get():
    r = ToolRegistry()
    r.register(_DummyA())
    assert r.has('dummy_a')
    assert r.get('dummy_a').description == 'a'


def test_get_missing_raises():
    r = ToolRegistry()
    with pytest.raises(KeyError):
        r.get('missing')


def test_specs_sorted():
    r = ToolRegistry()
    r.register(_DummyB())
    r.register(_DummyA())
    names = [s['name'] for s in r.specs()]
    assert names == ['dummy_a', 'dummy_b']


def test_from_yaml(tmp_path):
    cfg = tmp_path / 'tools.yaml'
    cfg.write_text(
        'enabled:\n'
        '  - dummy_a\n'
        'modules:\n'
        '  - test.test_registry\n'
    )
    r = ToolRegistry.from_yaml(cfg, extra_modules=['test.test_registry'])
    assert r.names() == ['dummy_a']


def test_from_yaml_rejects_unknown(tmp_path):
    cfg = tmp_path / 'tools.yaml'
    cfg.write_text('enabled:\n  - nonexistent\n')
    with pytest.raises(KeyError):
        ToolRegistry.from_yaml(cfg)
