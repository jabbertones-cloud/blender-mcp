from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from server.capability_executor import execute_canonical
from server.capability_registry import CapabilityArgumentsInvalid, registry

ROOT = Path(__file__).resolve().parents[1]
GENERIC = {"type": "object", "additionalProperties": True}


def test_every_guided_capability_has_a_real_schema():
    generic = [
        key for key in registry.keys()
        if registry.resolve_tool(key).input_schema == GENERIC
    ]
    assert generic == []
    assert len(registry.keys()) >= 48
    assert len(registry.keys()) == len(set(registry.keys()))


def test_high_leverage_schemas_preserve_authoritative_contracts():
    modifier = registry.resolve_tool("model.modifier").input_schema
    assert modifier["required"] == ["object_name"]
    assert {"action", "modifier_type", "modifier_name", "properties"} <= set(modifier["properties"])

    mesh = registry.resolve_tool("model.mesh_edit").input_schema
    assert set(mesh["required"]) == {"object_name", "action"}
    assert {"select_mode", "cuts", "segments", "merge_type", "delete_type"} <= set(mesh["properties"])

    product = registry.resolve_tool("product.material").input_schema
    assert set(product["required"]) == {"object_name", "preset"}
    preset = product["properties"]["preset"]
    assert "$ref" in preset

    camera = registry.resolve_tool("scene.camera").input_schema
    assert camera["required"] == ["action"]
    assert {"lens", "dof_enabled", "dof_fstop", "target", "objects"} <= set(camera["properties"])


def test_invalid_arguments_fail_before_any_blender_socket_call():
    calls = []

    def send(command, params):
        calls.append((command, params))
        return {"ok": True}

    with pytest.raises(CapabilityArgumentsInvalid, match="object_name"):
        execute_canonical("model.modifier", {"action": "add", "modifier_type": "BEVEL"}, send)

    assert calls == []


def test_schema_rejects_out_of_range_product_camera_before_socket():
    calls = []

    def send(command, params):
        calls.append((command, params))
        return {"ok": True}

    with pytest.raises(CapabilityArgumentsInvalid, match="focal_length"):
        execute_canonical(
            "product.camera",
            {"style": "turntable", "target_object": "Bottle", "focal_length": 1000},
            send,
        )

    assert calls == []


def test_generated_schema_contract_is_not_stale():
    proc = subprocess.run(
        [sys.executable, "scripts/generate_capability_schemas.py", "--check"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
