"""Canonical, MCP-independent capability registry for Blender dispatch."""
from __future__ import annotations

from collections import Counter
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
    "scene.create_object": {"type": "object", "properties": {"type": {"type": "string"}, "name": {"type": "string"}, "location": {"type": "array", "items": {"type": "number"}}, "rotation": {"type": "array", "items": {"type": "number"}}, "scale": {"type": "array", "items": {"type": "number"}}, "size": {"type": "number"}}},
    "scene.modify_object": {"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}, "new_name": {"type": "string"}, "location": {"type": "array", "items": {"type": "number"}}, "rotation": {"type": "array", "items": {"type": "number"}}, "scale": {"type": "array", "items": {"type": "number"}}, "visible": {"type": "boolean"}}},
    "scene.delete_object": {"type": "object", "required": ["names"], "properties": {"names": {"type": "array", "items": {"type": "string"}}}, "additionalProperties": False},
    "scene.set_material": {"type": "object", "required": ["object_name"], "properties": {"object_name": {"type": "string"}, "material_name": {"type": "string"}, "color": {"type": "array", "items": {"type": "number"}}, "metallic": {"type": "number"}, "roughness": {"type": "number"}}},
    "scene.info": {"type": "object", "properties": {}, "additionalProperties": False},
    "scene.render": {"type": "object", "properties": {"type": {"type": "string", "enum": ["image", "animation"], "default": "image"}, "output_path": {"type": "string"}}, "additionalProperties": False},
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
    "blender_mesh_edit": "model.mesh_edit", "blender_sculpt": "model.sculpt", "blender_geometry_nodes": "model.geometry_nodes",
    "blender_set_material": "scene.set_material", "blender_shader_nodes": "material.shader_nodes", "blender_procedural_material": "material.procedural",
    "blender_uv_unwrap": "uv.unwrap", "blender_uv_operations": "uv.manage", "blender_texture_bake": "material.texture_bake",
    "blender_scene_lighting": "scene.lighting_preset", "blender_product_lighting": "product.lighting", "blender_set_world": "scene.world",
    "blender_product_material": "product.material", "blender_product_camera": "product.camera", "blender_camera_advanced": "scene.camera",
    "blender_render": "scene.render", "blender_set_render_settings": "scene.render_settings", "blender_product_render_setup": "product.render_setup",
    "blender_render_quality_audit": "scene.render_audit", "blender_semantic_place": "scene.semantic_place", "blender_spatial": "scene.spatial_query",
    "blender_dimensions": "scene.dimensions", "blender_floor_plan": "scene.floor_plan", "blender_set_keyframe": "animation.keyframe",
    "blender_advanced_animation": "animation.advanced", "blender_product_animation": "product.animation", "blender_armature_operations": "rig.armature",
    "blender_constraint_operations": "rig.constraint", "blender_physics": "physics.rigid_body", "blender_cloth_simulation": "physics.cloth",
    "blender_fluid_simulation": "physics.fluid", "blender_import_file": "io.import", "blender_export_file": "io.export", "blender_save_file": "io.save",
    "blender_cleanup": "scene.cleanup", "blender_scene_template": "scene.template", "blender_forensic_scene": "workflow.forensic_scene",
    "blender_polyhaven": "assets.polyhaven", "blender_sketchfab": "assets.sketchfab", "blender_hyper3d": "generation.hyper3d", "blender_hunyuan3d": "generation.hunyuan3d",
}

# MCP-side wrappers must advertise the real addon boundary they ultimately use.
# Dynamic adapters are executed in capability_executor.py; bridge_command records
# a real registered handler used by that adapter rather than a fictional socket name.
_BRIDGE_COMMAND_OVERRIDES = {
    "product.material": "execute_python",
    "product.lighting": "execute_python",
    "product.camera": "execute_python",
    "product.render_setup": "execute_python",
    "product.animation": "execute_python",
    "scene.spatial_query": "spatial_scene_bounds",
    "scene.dimensions": "dimensions_estimate",
    "scene.floor_plan": "floor_plan_data",
}

# The fat MCP still owns integrations that do not have an addon command or a
# canonical adapter yet. Do not advertise them through guided execution.
_GUIDED_EXCLUDED_MCP = {"blender_hyper3d"}

_FAMILY_OVERRIDES = {"model": "create", "transform": "mutate", "product-viz": "product", "uv": "uv", "io": "io", "workflow": "mutate", "spatial": "spatial"}
_SPECIFIC_FAMILIES = {
    "scene.create_object": "create", "scene.modify_object": "mutate", "scene.delete_object": "mutate",
    "scene.lighting_preset": "lighting", "product.lighting": "lighting", "scene.world": "world",
    "scene.set_material": "material", "material.shader_nodes": "material", "material.procedural": "material", "material.texture_bake": "material",
    "scene.info": "inspect", "scene.object_info": "inspect", "scene.render": "render", "scene.render_settings": "render", "scene.render_audit": "render",
    "scene.camera": "camera", "product.camera": "camera",
}


class CapabilityRegistry:
    def __init__(self, capabilities: Iterable[Capability]):
        caps = list(capabilities)
        self._by_key: Dict[str, Capability] = {}
        self._by_alias: Dict[str, Capability] = {}
        bridge_counts = Counter(cap.bridge_command for cap in caps)
        for cap in caps:
            if cap.key in self._by_key:
                raise ValueError(f"duplicate capability key: {cap.key}")
            self._by_key[cap.key] = cap
            names = [cap.key, cap.mcp_name, *cap.aliases]
            if bridge_counts[cap.bridge_command] == 1:
                names.append(cap.bridge_command)
            for name in names:
                normalized = str(name).strip().lower()
                existing = self._by_alias.get(normalized)
                if existing and existing.key != cap.key:
                    raise ValueError(f"ambiguous capability alias: {name}")
                self._by_alias[normalized] = cap

    def resolve_tool(self, name: str) -> Capability:
        cap = self._by_alias.get((name or "").strip().lower())
        if not cap:
            raise CapabilityNotFound(f"Unknown capability '{name}'. Re-search capabilities; do not guess a tool name.")
        return cap

    def route_intent(self, intent: str) -> Capability:
        text = " ".join((intent or "").lower().replace("'s", " is").split())
        if any(x in text for x in ("what is in the scene", "what's in the scene", "inspect scene", "scene info")):
            return self._by_key["scene.info"]
        if any(x in text for x in ("add a cube", "add cube", "create a cube", "create cube", "add a sphere", "create a sphere", "add a cylinder", "create a cylinder")):
            return self._by_key["scene.create_object"]
        if any(x in text for x in ("three point light", "three-point light", "three point lighting", "studio lighting")):
            return self._by_key["scene.lighting_preset"]
        if any(x in text for x in ("delete ", "remove the", "remove default cube")):
            return self._by_key["scene.delete_object"]
        if any(x in text for x in ("hdri", "world background", "environment background")):
            return self._by_key["scene.world"]
        if "camera" in text and any(x in text for x in ("move", "position", "lens", "dof", "depth of field", "frame")):
            return self._by_key["scene.camera"]
        if any(x in text for x in ("chrome", "metal material", "make it metallic")):
            return self._by_key["scene.set_material"]
        for row in rank_capabilities(intent, limit=8):
            try:
                return self.resolve_tool(row["tool"])
            except CapabilityNotFound:
                continue
        return self._by_key["scene.info"]

    def search_capabilities(self, query: str, limit: int = 8) -> List[dict]:
        primary = self.route_intent(query)
        rows = [{"key": primary.key, "family": primary.family, "description": primary.description, "score": 100.0, "reason": ["deterministic family-first route"]}]
        seen = {primary.key}
        for row in rank_capabilities(query, limit=max(limit * 2, 8)):
            try:
                cap = self.resolve_tool(row["tool"])
            except CapabilityNotFound:
                continue
            if cap.key in seen:
                continue
            seen.add(cap.key)
            rows.append({"key": cap.key, "family": cap.family, "description": cap.description, "score": row.get("score"), "reason": row.get("reasons", [])})
            if len(rows) >= limit:
                break
        return rows

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
        if source.tool in _GUIDED_EXCLUDED_MCP:
            continue
        key = _KEY_OVERRIDES.get(source.tool, source.tool.removeprefix("blender_").replace("_", ".", 1))
        family = _SPECIFIC_FAMILIES.get(key, _FAMILY_OVERRIDES.get(source.family, source.family))
        bridge_command = _BRIDGE_COMMAND_OVERRIDES.get(key, source.command)
        aliases = (source.command, *source.positive) if source.command != bridge_command else tuple(source.positive)
        caps.append(Capability(key=key, family=family, description=source.purpose, bridge_command=bridge_command, mcp_name=source.tool, input_schema=_SCHEMA_OVERRIDES.get(key, dict(_GENERIC_SCHEMA)), aliases=aliases, tags=(source.family,), mutates_scene=source.mutates_scene))
    caps.append(Capability(key="scene.delete_object", family="mutate", description="delete one or more named scene objects", bridge_command="delete_object", mcp_name="blender_delete_object", input_schema=_SCHEMA_OVERRIDES["scene.delete_object"], aliases=("delete object", "remove object", "delete default cube"), tags=("objects",), mutates_scene=True))
    return CapabilityRegistry(caps)


registry = _build_registry()
