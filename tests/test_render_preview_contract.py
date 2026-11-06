"""Fast reference scoring uses a typed, reversible Blender render preview."""
import pytest
from jsonschema import Draft202012Validator
from server.capability_registry import registry, CapabilityArgumentsInvalid
from server.capability_executor import WORKFLOW_SCHEMAS


def test_render_preview_is_typed_and_does_not_accept_invalid_values():
    schema = registry.get_capability_schema('scene.render')['input_schema']
    assert schema['properties']['preview']['type'] == 'boolean'
    assert registry.validate_arguments('scene.render', {'type':'image', 'preview': True})['preview'] is True
    with pytest.raises(CapabilityArgumentsInvalid):
        registry.validate_arguments('scene.render', {'type':'image', 'preview':'maybe'})


def test_reference_score_contract_rejects_ambiguous_preview():
    schema = WORKFLOW_SCHEMAS['workflow.reference_score']
    assert not list(Draft202012Validator(schema).iter_errors({'preview': False}))
    assert list(Draft202012Validator(schema).iter_errors({'preview': 'fast'}))
