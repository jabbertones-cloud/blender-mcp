#!/usr/bin/env python3
"""Generate the guided capability schemas from the authoritative Pydantic inputs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server import blender_mcp_server as main
from server import extended_tools, product_animation_tools, spatial_tools

OUTPUT = ROOT / "config" / "capability-schemas.json"

NO_ARGS = {"type": "object", "properties": {}, "additionalProperties": False}


def _model_schema(model: type) -> dict[str, Any]:
    schema = model.model_json_schema()
    schema.pop("title", None)
    return schema


def build_schemas() -> dict[str, dict[str, Any]]:
    schemas: dict[str, dict[str, Any]] = {
        "scene.info": dict(NO_ARGS),
        "scene.object_info": {
            "type": "object",
            "required": ["name"],
            "properties": {"name": {"type": "string", "minLength": 1}},
            "additionalProperties": False,
        },
        "scene.create_object": _model_schema(main.CreateObjectInput),
        "scene.modify_object": _model_schema(main.ModifyObjectInput),
        "model.modifier": _model_schema(main.ModifierInput),
        "model.boolean": _model_schema(main.BooleanInput),
        "model.mesh_edit": _model_schema(main.MeshEditInput),
        "model.sculpt": _model_schema(main.SculptInput),
        "model.geometry_nodes": _model_schema(main.GeometryNodesInput),
        "scene.set_material": _model_schema(main.MaterialInput),
        "material.shader_nodes": _model_schema(main.ShaderNodeInput),
        "material.procedural": _model_schema(main.ProceduralMaterialInput),
        "uv.unwrap": _model_schema(extended_tools.UVUnwrapInput),
        "uv.manage": _model_schema(main.UVInput),
        "material.texture_bake": _model_schema(extended_tools.TextureBakeInput),
        "scene.lighting_preset": _model_schema(main.SceneLightingInput),
        "product.lighting": _model_schema(product_animation_tools.ProductLightingInput),
        "scene.world": _model_schema(main.WorldInput),
        "product.material": _model_schema(product_animation_tools.ProductMaterialInput),
        "product.camera": _model_schema(product_animation_tools.ProductCameraInput),
        "scene.camera": _model_schema(extended_tools.CameraAdvancedInput),
        "scene.render": _model_schema(main.RenderInput),
        "scene.render_settings": _model_schema(main.RenderSettingsInput),
        "product.render_setup": _model_schema(product_animation_tools.ProductRenderInput),
        "scene.render_audit": _model_schema(main.RenderQualityAuditInput),
        "scene.semantic_place": _model_schema(spatial_tools.SemanticPlaceInput),
        "scene.spatial_query": _model_schema(spatial_tools.SpatialInput),
        "scene.dimensions": _model_schema(spatial_tools.DimensionsInput),
        "scene.floor_plan": _model_schema(spatial_tools.FloorPlanInput),
        "animation.keyframe": _model_schema(main.KeyframeInput),
        "animation.advanced": _model_schema(main.AdvancedAnimInput),
        "product.animation": _model_schema(product_animation_tools.ProductAnimationInput),
        "rig.armature": _model_schema(main.ArmatureInput),
        "rig.constraint": _model_schema(main.ConstraintInput),
        "physics.rigid_body": _model_schema(main.PhysicsInput),
        "physics.cloth": _model_schema(main.ClothSimInput),
        "physics.fluid": _model_schema(main.FluidSimInput),
        "io.import": {
            "type": "object",
            "required": ["filepath"],
            "properties": {"filepath": {"type": "string", "minLength": 1}},
            "additionalProperties": False,
        },
        "io.export": _model_schema(main.ExportInput),
        "io.save": _model_schema(main.FileInput),
        "scene.cleanup": _model_schema(main.CleanupInput),
        "scene.template": _model_schema(main.SceneTemplateInput),
        "workflow.forensic_scene": _model_schema(main.ForensicSceneInput),
        "assets.polyhaven": _model_schema(main.PolyHavenInput),
        "assets.sketchfab": _model_schema(main.SketchfabInput),
        "generation.hunyuan3d": _model_schema(main.Hunyuan3DInput),
        "object.duplicate": _model_schema(main.DuplicateObjectInput),
        "object.parent": _model_schema(main.ParentInput),
        "scene.collections": _model_schema(main.CollectionInput),
        "model.curve": _model_schema(main.CurveInput),
        "animation.shape_keys": _model_schema(main.ShapeKeyInput),
        "rig.weight_paint": _model_schema(main.WeightPaintInput),
        "physics.particles": _model_schema(main.ParticleInput),
        "physics.force_field": _model_schema(main.ForceFieldInput),
        "scene.text": _model_schema(main.TextInput),
        "render.compositor": _model_schema(main.CompositorInput),
        "image.manage": _model_schema(main.ImageInput),
        "animation.clear": {
            "type": "object",
            "required": ["object_name"],
            "properties": {"object_name": {"type": "string", "minLength": 1}},
            "additionalProperties": False,
        },
        "scene.manage": _model_schema(main.SceneInput),
        "scene.context": dict(NO_ARGS),
        "scene.inspect": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["summary", "object", "topology", "modifiers", "materials", "hierarchy"], "default": "summary"},
                "object_name": {"type": "string", "minLength": 1},
            },
            "additionalProperties": False,
        },
        "mesh.inspect": {
            "type": "object",
            "required": ["object_name"],
            "properties": {
                "object_name": {"type": "string", "minLength": 1},
                "action": {"type": "string", "enum": ["summary", "vertices", "edges", "faces", "uvs", "normals", "attributes", "shape_keys", "group_weights"], "default": "summary"},
                "selected_only": {"type": "boolean", "default": False},
                "offset": {"type": "integer", "minimum": 0, "default": 0},
                "limit": {"type": "integer", "minimum": 1, "maximum": 5000, "default": 250},
                "uv_layer": {"type": "string"},
                "attribute_name": {"type": "string"},
                "group_name": {"type": "string"},
            },
            "additionalProperties": False,
        },
        "runtime.rna_search": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "offset": {"type": "integer", "minimum": 0, "default": 0},
                "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 50},
            },
            "additionalProperties": False,
        },
        "runtime.rna_describe": {
            "type": "object",
            "required": ["type_name"],
            "properties": {
                "type_name": {"type": "string", "minLength": 1},
                "query": {"type": "string"},
                "offset": {"type": "integer", "minimum": 0, "default": 0},
                "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 100},
            },
            "additionalProperties": False,
        },
        "scene.delete_object": {
            "type": "object",
            "required": ["names"],
            "properties": {
                "names": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"type": "string", "minLength": 1},
                }
            },
            "additionalProperties": False,
        },
        "scene.diagnostics": dict(NO_ARGS),
    }

    # Bridge-contract overlays: source models may document constraints only in prose.
    # Runtime handler semantics are authoritative for guided execution.
    schemas["scene.render"]["properties"]["type"]["enum"] = ["image", "animation"]
    schemas["scene.render"]["properties"]["type"]["default"] = "image"
    return schemas


def serialized() -> str:
    return json.dumps(build_schemas(), indent=2, sort_keys=True) + "\n"


def main_cli() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    expected = serialized()
    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != expected:
            print(f"{OUTPUT} is stale; run {Path(__file__).name}")
            return 1
        print(f"{OUTPUT} is current")
        return 0

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(expected, encoding="utf-8")
    print(f"wrote {OUTPUT} ({len(build_schemas())} schemas)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main_cli())
