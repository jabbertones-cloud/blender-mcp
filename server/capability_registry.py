"""Canonical, MCP-independent capability registry for Blender dispatch."""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Dict, Iterable, List, Tuple

try:
    from server.capability_router import CAPABILITIES, rank_capabilities
except ModuleNotFoundError:
    from capability_router import CAPABILITIES, rank_capabilities


class CapabilityNotFound(KeyError):
    pass


_GENERIC_SCHEMA = {"type": "object", "additionalProperties": True}
_SCHEMA_OVERRIDES = {
    "scene.create_object": {
        "type": "object",
        "properties": {
            "type": {"type": "string"}, "name": {"type": "string"},
            "location": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
            "rotation": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
            "scale": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
            "size": {"type": "number"},
        },
    },
    "scene.modify_object": {
        "type": "object", "required": ["name"],
        "properties": {
            "name": {"type": "string"}, "new_name": {"type": "string"},
            "location": {"type": "array", "items": {"type": "number"}},
            "rotation": {"type": "array", "items": {"type": "number"}},
            "scale": {"type": "array", "items": {"type": "number"}},
            "visible": {"type": "boolean"},
        },
    },
    "scene.set_material": {
        "type": "object", "required": ["object_name"],
        "properties": {
            "object_name": {"type": "string"}, "material_name": {"type": "string"},
            "color": {"type": "array", "items": {"type": "number"}},
            "metallic": {"type": "number"}, "roughness": {"type": "number"},
        },
    },
    "scene.info": {"type": "object", "properties": {}, "additionalProperties": False},
    "scene.render": {"type": "object", "additionalProperties": True},
    "scene.world": {"type": "object", "additionalProperties": True},
    "scene.camera": {"type": "object", "additionalProperties": True},
    "scene.lighting_preset": {"type": "object", "additionalProperties": True},
}


@dataclass(frozen=True)
class Capability:
    key: str
    family: str
    description: str
    bridge_command: str
    mcp_name: str
    input_schema: dict = field(default_factory=lambda: dict(_GENERIC_SCHEMA))
    aliases: Tuple[str, ...] = ()
    tags: Tuple[str, ...] = ()
    mutates_scene: bool = True


_KEY_OVERRIDES = {
    "blender_get_scene_info": "scene.info", "blender_get_object_data": "scene.object_info",
    "blender_create_object": "scene.create_object", "blender_modify_object": "scene.modify_object",
    "blender_apply_modifier": "model.modifier", "blender_boolean_operation": "model.boolean",
    "blender_mesh_edit": "model.mesh_edit", "blender_sculpt": "model.sculpt",
    "blender_geometry_nodes": "model.geometry_nodes", "blender_set_material": "scene.set_material",
    "blender_shader_nodes": "material.shader_nodes", "blender_procedural_material": "material.procedural",
    "blender_uv_unwrap": "uv.unwrap", "blender_uv_operations": "uv.manage",
    "blender_texture_bake": "material.texture_bake", "blender_scene_lighting": "scene.lighting_preset",
    "blender_product_lighting": "product.lighting", "blender_set_world": "scene.world",
    "blender_product_material": "product.material", "blender_product_camera": "product.camera",
    "blender_camera_advanced": "scene.camera", "blender_render": "scene.render",
    "blender_set_render_settings": "scene.render_settings", "blender_product_render_setup": "product.render_setup",
    "blender_render_quality_audit": "scene.render_audit", "blender_semantic_place": "scene.semantic_place",
    "blender_spatial": "scene.spatial_query", "blender_dimensions": "scene.dimensions",
    "blender_floor_plan": "scene.floor_plan", "blender_set_keyframe": "animation.keyframe",
    "blender_advanced_animation": "animation.advanced", "blender_product_animation": "product.animation",
    "blender_armature_operations": "rig.armature", "blender_constraint_operations": "rig.constraint",
    "blender_physics": "physics.rigid_body", "blender_cloth_simulation": "physics.cloth",
    "blender_fluid_simulation": "physics.fluid", "blender_import_file": "io.import",
    "blender_export_file": "io.export", "blender_save_file": "io.save", "blender_cleanup": "scene.cleanup",
    "blender_scene_template": "scene.template", "blender_forensic_scene": "workflow.forensic_scene",
    "blender_polyhaven": "assets.polyhaven", "blender_sketchfab": "assets.sketchfab",
    "blender_hyper3d": "generation.hyper3d", "blender_hunyuan3d": "generation.hunyuan3d",
}

_FAMILY_OVERRIDES = {
    "model": "create", "transform": "mutate", "product-viz": "product",
    "uv": "uv", "io": "io", "workflow": "mutate", "spatial": "spatial",
}


class CapabilityRegistry:
    def __init__(self, capabilities: Iterable[Capability]):
        self._by_key: Dict[str, Capability] = {}
        self._by_alias: Dict[str, Capability] = {}
        for cap in capabilities:
            if cap.key in self._by_key:
                raise ValueError(f"duplicate capability key: {cap.key}")
            self._by_key[cap.key] = cap
            for name in (cap.key, cap.mcp_name, cap.bridge_command, *cap.aliases):
                normalized = str(name).strip().lower()
                existing = self._by_alias.get(normalized)
                if existing and existing.key != cap.key:
                    raise ValueError(f"ambiguous capability alias: {name}")
                self._by_alias[normalized] = cap

    def resolve_tool(self, name: str) -> Capability:
        cap = self._by_alias.get((name or "").strip().lower())
        if not cap:
            raise CapabilityNotFound(
                f"Unknown capability '{name}'. Re-search capabilities; do not guess a tool name."
            )
        return cap

    def route_intent(self, intent: str) -> Capability:
        ranked = rank_capabilities(intent, limit=1)
        return self.resolve_tool(ranked[0]["tool"]) if ranked else self._by_key["scene.info"]

    def search_capabilities(self, query: str, limit: int = 8) -> List[dict]:
        ranked = rank_capabilities(query, limit=limit)
        output = []
        for row in ranked:
            cap = self.resolve_tool(row["tool"])
            output.append({
                "key": cap.key, "family": cap.family, "description": cap.description,
                "score": row.get("score"), "reason": row.get("reasons", []),
            })
        if not output:
            cap = self._by_key["scene.info"]
            output.append({"key": cap.key, "family": cap.family, "description": cap.description, "score": 0.0, "reason": ["safe inspect-first fallback"]})
        return output

    def get_capability_schema(self, key: str) -> dict:
        return asdict(self.resolve_tool(key))

    def execute(self, key: str, params: dict, send_command):
        cap = self.resolve_tool(key)
        return send_command(cap.bridge_command, params or {})

    def keys(self) -> Tuple[str, ...]:
        return tuple(self._by_key)


def _build_registry() -> CapabilityRegistry:
    caps = []
    for source in CAPABILITIES:
        key = _KEY_OVERRIDES.get(source.tool, source.tool.removeprefix("blender_").replace("_", ".", 1))
        family = _FAMILY_OVERRIDES.get(source.family, source.family)
        caps.append(Capability(
            key=key, family=family, description=source.purpose,
            bridge_command=source.command, mcp_name=source.tool,
            input_schema=_SCHEMA_OVERRIDES.get(key, dict(_GENERIC_SCHEMA)),
            aliases=tuple(source.positive), tags=(source.family,), mutates_scene=source.mutates_scene,
        ))
    return CapabilityRegistry(caps)


registry = _build_registry()
