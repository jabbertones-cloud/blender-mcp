"""Deterministic lexical capability router used by the canonical registry.

This module deliberately stays independent of MCP and Blender so the routing
floor can be tested in ordinary CI. It is the lexical candidate generator; the
canonical execution boundary lives in capability_registry.py.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Tuple


@dataclass(frozen=True)
class Capability:
    tool: str
    command: str
    family: str
    purpose: str
    positive: Tuple[str, ...]
    negative: Tuple[str, ...] = ()
    requires_object: bool = False
    mutates_scene: bool = True
    priority: int = 0


CAPABILITIES: Tuple[Capability, ...] = (
    Capability("blender_get_scene_info", "get_scene_info", "inspect", "understand the whole scene before editing", ("scene info", "inspect scene", "what is in", "what s in the scene", "analyze scene", "understand scene"), mutates_scene=False, priority=20),
    Capability("blender_get_object_data", "get_object_data", "inspect", "inspect one named object in detail", ("inspect object", "object data", "modifiers on", "materials on", "details for"), requires_object=True, mutates_scene=False, priority=18),
    Capability("blender_create_object", "create_object", "model", "create a primitive, light, camera, or empty", ("create cube", "create a cube", "create sphere", "create a sphere", "create cylinder", "create cone", "create torus", "add cube", "add a cube", "add sphere", "add a sphere", "primitive", "new camera", "new light"), priority=14),
    Capability("blender_modify_object", "modify_object", "transform", "directly change an object's transform, visibility, or name", ("move", "rotate", "scale", "rename", "hide", "show", "position"), requires_object=True, priority=9),
    Capability("blender_apply_modifier", "apply_modifier", "model", "add/apply/remove a standard Blender modifier", ("bevel", "subdivision", "subsurf", "mirror modifier", "array modifier", "solidify", "decimate", "remesh", "shrinkwrap", "wireframe modifier", "modifier"), requires_object=True, priority=22),
    Capability("blender_boolean_operation", "boolean_operation", "model", "cut, union, or intersect two objects", ("boolean", "cut hole", "difference", "union", "intersect", "subtract"), requires_object=True, priority=24),
    Capability("blender_mesh_edit", "mesh_edit", "model", "edit mesh components/topology", ("extrude", "inset", "loop cut", "merge vertices", "delete faces", "edit vertices", "edit faces", "topology"), requires_object=True, priority=18),
    Capability("blender_sculpt", "sculpt", "model", "perform sculpting operations", ("sculpt", "smooth brush", "inflate brush", "grab brush"), requires_object=True, priority=24),
    Capability("blender_geometry_nodes", "geometry_nodes", "procedural", "build or edit procedural geometry-node systems", ("geometry nodes", "procedural geometry", "scatter", "instance on points"), requires_object=True, priority=25),
    Capability("blender_set_material", "set_material", "material", "apply a straightforward Principled material", ("material", "base color", "metallic", "roughness", "make it red", "make it blue", "glass material", "chrome"), requires_object=True, negative=("nodes", "procedural material", "product material"), priority=8),
    Capability("blender_shader_nodes", "shader_nodes", "material", "build or edit a custom shader-node graph", ("shader nodes", "node graph", "mix shader", "principled node", "texture nodes"), requires_object=True, priority=24),
    Capability("blender_procedural_material", "procedural_material", "material", "create procedural materials such as wood/noise/marble", ("procedural material", "wood material", "marble", "noise texture", "procedural texture"), requires_object=True, priority=25),
    Capability("blender_uv_unwrap", "uv_unwrap", "uv", "unwrap UVs using explicit unwrap methods", ("unwrap", "uv unwrap", "smart uv", "cube projection", "cylinder projection", "lightmap pack"), requires_object=True, priority=28),
    Capability("blender_uv_operations", "uv_operations", "uv", "inspect or manipulate existing UV maps", ("uv map", "uv layer", "pack islands", "uv operations"), requires_object=True, negative=("unwrap",), priority=15),
    Capability("blender_texture_bake", "texture_bake", "material", "bake materials, lighting, normals, or AO to textures", ("bake texture", "bake the texture", "bake normal", "bake the normal", "bake the normal texture", "bake ambient occlusion", "texture bake"), requires_object=True, priority=28),
    Capability("blender_scene_lighting", "scene_lighting", "lighting", "set up general scene lighting", ("light the scene", "lighting setup", "three point lighting", "three point lights", "studio lighting", "rim light"), priority=13),
    Capability("blender_product_lighting", "product_lighting", "product-viz", "create product-photography lighting rigs", ("product lighting", "product photo", "product photography", "softbox", "hero product", "commercial product"), negative=("camera", "camera angle", "lens"), priority=30),
    Capability("blender_set_world", "set_world", "world", "change world/background/environment lighting", ("world background", "hdri", "environment", "background color", "world lighting"), priority=18),
    Capability("blender_product_material", "product_material", "product-viz", "create product-visualization materials", ("product material", "packaging material", "label material", "cosmetic bottle material"), requires_object=True, priority=28),
    Capability("blender_product_camera", "product_camera", "product-viz", "compose product shots with product-specific camera controls", ("product camera", "hero product camera", "hero product camera angle", "hero shot camera", "packshot camera", "product angle", "camera angle", "product closeup"), priority=34),
    Capability("blender_camera_advanced", "camera_advanced", "camera", "perform advanced camera composition, lens, motion, and DOF operations", ("move the camera", "position camera", "depth of field", "dof", "camera lens", "camera tracking", "frame object", "camera composition"), priority=20),
    Capability("blender_render", "render", "render", "render the current scene or animation", ("render", "render a png", "final image", "render image", "render animation"), negative=("settings", "setup", "quality audit"), priority=12),
    Capability("blender_set_render_settings", "set_render_settings", "render", "configure render engine, samples, resolution, and output", ("render settings", "resolution", "cycles samples", "eevee", "render engine", "output path"), priority=24),
    Capability("blender_product_render_setup", "product_render_setup", "product-viz", "configure product-focused render settings", ("product render", "product render setup", "amazon image", "ecommerce render"), priority=30),
    Capability("blender_render_quality_audit", "render_quality_audit", "render", "audit render configuration and visual quality", ("quality audit", "render quality", "check render", "audit render"), mutates_scene=False, priority=25),
    Capability("blender_semantic_place", "semantic_place", "spatial", "place an object using semantic relations to another object", ("on top of", "next to", "beside", "under", "inside", "in front of", "behind", "place on", "place beside"), requires_object=True, priority=32),
    Capability("blender_spatial", "spatial", "spatial", "query collision, bounds, raycasts, or safe movement ranges", ("collision", "overlap", "bounding box", "scene bounds", "raycast", "clearance", "movement range", "spatial query"), mutates_scene=False, priority=27),
    Capability("blender_dimensions", "dimensions", "spatial", "look up or apply real-world dimensions", ("dimensions", "real world size", "real-world size", "standard size", "how big"), priority=18),
    Capability("blender_floor_plan", "floor_plan", "spatial", "build a floor plan/room layout", ("floor plan", "room layout", "walls", "architectural plan"), priority=30),
    Capability("blender_set_keyframe", "set_keyframe", "animation", "set simple keyframes", ("keyframe", "animate from", "animate to", "at frame"), requires_object=True, priority=13),
    Capability("blender_advanced_animation", "advanced_animation", "animation", "create complex animation behaviors", ("follow path", "animation loop", "motion path", "complex animation"), priority=20),
    Capability("blender_product_animation", "product_animation", "product-viz", "create product turntables/reveals/exploded animations", ("turntable", "product animation", "explode animation", "product reveal", "360 spin"), priority=30),
    Capability("blender_armature_operations", "armature_operations", "rigging", "create/edit armatures and bones", ("armature", "bones", "rig", "skeleton"), priority=22),
    Capability("blender_constraint_operations", "constraint_operations", "rigging", "add/remove Blender constraints", ("constraint", "track to", "copy location", "copy rotation", "ik constraint"), priority=17),
    Capability("blender_physics", "physics", "physics", "configure rigid-body and common physics", ("rigid body", "physics", "collision physics"), priority=17),
    Capability("blender_cloth_simulation", "cloth_simulation", "physics", "configure cloth simulation", ("cloth", "fabric simulation", "cloth simulation"), priority=28),
    Capability("blender_fluid_simulation", "fluid_simulation", "physics", "configure liquid/smoke simulation", ("fluid", "liquid", "smoke simulation", "fire simulation"), priority=28),
    Capability("blender_import_file", "import_file", "io", "import an external 3D/scene file", ("import", "open fbx", "open gltf", "open obj", "bring in"), priority=18),
    Capability("blender_export_file", "export_file", "io", "export scene/object data", ("export", "save as fbx", "save as gltf", "export obj"), priority=18),
    Capability("blender_save_file", "save_file", "io", "save the Blender .blend file", ("save blend", "save file", "save scene"), priority=20),
    Capability("blender_cleanup", "cleanup", "workflow", "clean mesh/scene data and remove common artifacts", ("cleanup", "clean up", "remove doubles", "merge by distance", "purge"), priority=15),
    Capability("blender_scene_template", "scene_template", "workflow", "start from a reusable scene template", ("template", "scene preset", "starter scene"), priority=13),
    Capability("blender_forensic_scene", "forensic_scene", "forensic", "build structured forensic/accident reconstruction scenes", ("forensic", "accident reconstruction", "crash reconstruction", "courtroom", "collision reconstruction"), priority=40),
    Capability("blender_polyhaven", "polyhaven", "assets", "find/import Poly Haven assets or HDRIs", ("poly haven", "polyhaven", "free hdri", "free texture"), priority=28),
    Capability("blender_sketchfab", "sketchfab", "assets", "find/import Sketchfab assets", ("sketchfab", "download model", "find 3d model"), priority=25),
    Capability("blender_hyper3d", "hyper3d", "generation", "generate/import a 3D asset using Hyper3D", ("hyper3d", "generate 3d", "text to 3d"), priority=28),
    Capability("blender_hunyuan3d", "hunyuan3d", "generation", "generate/import a 3D asset using Hunyuan3D", ("hunyuan", "hunyuan3d", "image to 3d"), priority=28),
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _normalize(text: str) -> str:
    return " ".join(_TOKEN_RE.findall((text or "").lower()))


def _score(cap: Capability, normalized: str) -> Tuple[float, List[str]]:
    score = float(cap.priority) / 10.0
    reasons: List[str] = []
    for phrase in cap.positive:
        p = _normalize(phrase)
        if p and p in normalized:
            score += 7.0 + min(len(p.split()), 4) * 2.0
            reasons.append(f"matches '{phrase}'")
    for phrase in cap.negative:
        p = _normalize(phrase)
        if p and p in normalized:
            score -= 16.0
            reasons.append(f"excluded by '{phrase}'")
    if cap.family in normalized:
        score += 2.0
    return score, reasons


def rank_capabilities(task: str, limit: int = 5, minimum_score: float = 7.0) -> List[Dict[str, Any]]:
    normalized = _normalize(task)
    ranked = []
    for cap in CAPABILITIES:
        score, reasons = _score(cap, normalized)
        if score >= minimum_score and any(r.startswith("matches") for r in reasons):
            ranked.append((score, cap, reasons))
    ranked.sort(key=lambda item: (-item[0], -item[1].priority, item[1].tool))
    output = []
    for score, cap, reasons in ranked[: max(1, limit)]:
        row = asdict(cap)
        row.update({"score": round(score, 2), "reasons": reasons})
        output.append(row)
    return output


def recommend(task: str, limit: int = 5) -> Dict[str, Any]:
    candidates = rank_capabilities(task, limit=limit)
    if not candidates:
        return {"task": task, "decision": "inspect_then_plan", "primary": {"tool": "blender_get_scene_info", "command": "get_scene_info", "family": "inspect", "purpose": "understand the scene before choosing a mutation tool"}, "alternatives": [], "confidence": 0.25, "reason": "No capability had a strong lexical match; do not guess a mutation tool."}
    primary = candidates[0]
    second = candidates[1] if len(candidates) > 1 else None
    margin = primary["score"] - (second["score"] if second else 0.0)
    decision = "use_primary" if not second or margin >= 3.0 else "ambiguous"
    return {"task": task, "decision": decision, "primary": primary, "alternatives": candidates[1:], "confidence": round(min(0.98, 0.55 + max(0.0, margin) / 30.0 + min(primary["score"], 35.0) / 100.0), 2), "reason": "Specific capability match with a clear margin." if decision == "use_primary" else "Several capabilities overlap; inspect context before mutating."}


def plan_goal(goal: str, max_steps: int = 6, profile: str = "default") -> List[Dict[str, Any]]:
    recs = rank_capabilities(goal, limit=max_steps)
    steps: List[Dict[str, Any]] = []
    if profile != "power-user":
        steps.append({"description": "Inspect the current scene and establish object names/state", "tool_hint": "blender_get_scene_info", "command_hint": "get_scene_info", "kind": "inspect"})
    seen = set()
    for rec in recs:
        tool = rec["tool"]
        if tool in seen or tool in {"blender_get_scene_info", "blender_get_object_data"}:
            continue
        seen.add(tool)
        steps.append({"description": rec["purpose"], "tool_hint": tool, "command_hint": rec["command"], "kind": "mutate" if rec["mutates_scene"] else "inspect", "routing_score": rec["score"]})
        if len(steps) >= max_steps - 1:
            break
    if profile != "power-user" and len(steps) < max_steps:
        steps.append({"description": "Verify the result against the requested outcome and spatial/visual constraints", "tool_hint": "blender_verify", "command_hint": None, "kind": "verify"})
    return steps[:max_steps]


def register_capability_router_tools(mcp_instance, send_command=None, format_result=None) -> List[str]:
    @mcp_instance.tool()
    async def blender_recommend_tools(task: str, limit: int = 5) -> Dict[str, Any]:
        """Choose Blender tools for a task before mutating the scene."""
        return recommend(task, limit=limit)

    @mcp_instance.tool()
    async def blender_route_plan(goal: str, max_steps: int = 6, profile: str = "default") -> Dict[str, Any]:
        """Build a routing-aware Blender plan with concrete tool hints."""
        return {"goal": goal, "profile": profile, "steps": plan_goal(goal, max_steps=max_steps, profile=profile)}

    return ["blender_recommend_tools", "blender_route_plan"]
