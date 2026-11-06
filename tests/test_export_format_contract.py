"""Reject invalid export modes and keep native extension routing available."""
import pytest
from server.capability_registry import registry, CapabilityArgumentsInvalid


def test_export_action_is_typed_and_auto_is_accepted():
    schema=registry.get_capability_schema('io.export')['input_schema']
    prop=schema['properties']['action']
    assert any('auto' in x.get('enum', []) for x in prop['anyOf'])
    assert registry.validate_arguments('io.export',{'filepath':'/tmp/model.glb','action':'auto'})['action']=='auto'
    with pytest.raises(CapabilityArgumentsInvalid):
        registry.validate_arguments('io.export',{'filepath':'/tmp/model.glb','action':'not_a_format'})
