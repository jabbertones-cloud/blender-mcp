"""
extended_tools.py — Phase 5 MCP tool expansion for OpenClaw Blender MCP.

Adds 7 new tools that fill the gap vs. Blender MCP Pro / sandraschi / mlolson:
  blender_camera_advanced   — look_at, frame_objects, rich properties, turntable_setup
  blender_uv_unwrap         — 7 unwrap methods + preserve
  blender_texture_bake      — diffuse / normal / roughness / AO / metallic / emit / shadow / glossy
  blender_lod               — auto-Decimate chain generator
  blender_vr_optimize       — validate / optimize / export for VR platforms
  blender_gaussian_splat    — import / render KIRI/Polycam .ply/.splat
  blender_grease_pencil     — 2D hybrid workflow
  blender_snapshot          — save/diff/list scene snapshots (for action-hallucination detection)

Exports `register_extended_tools(mcp, send_command, format_result)` matching
the `register_product_tools()` convention used by the main MCP server.
"""
from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ═══════════════════════════════════════════════════════════════════════════════
# INPUT MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class CameraAdvancedInput(BaseModel):
    model_config = ConfigDict(extra="allow")
    action: str = Field(..., description="look_at | frame_objects | set_properties | set_active | get_info | turntable_setup")
    camera: Optional[str] = Field(default=None, description="Camera name")
    name: Optional[str] = Field(default=None, description="Alias for camera")
    target: Optional[str] = Field(default=None, description="Object name to look at / track")
    objects: Optional[List[str]] = Field(default=None, description="Objects to frame")
    lens: Optional[float] = Field(default=None, ge=1, description="Focal length in mm")
    sensor_fit: Optional[str] = Field(default=None, description="AUTO | HORIZONTAL | VERTICAL")
    dof_enabled: Optional[bool] = Field(default=None, description="Enable depth of field")
    dof_focus_distance: Optional[float] = Field(default=None, ge=0)
    dof_fstop: Optional[float] = Field(default=None, gt=0)
    clip_start: Optional[float] = Field(default=None, gt=0)
    clip_end: Optional[float] = Field(default=None, gt=0)
    shift_x: Optional[float] = Field(default=None)
    shift_y: Optional[float] = Field(default=None)
    frames: Optional[int] = Field(default=None, description="Turntable frames")
    radius: Optional[float] = Field(default=None)
    height: Optional[float] = Field(default=None)


class UVUnwrapInput(BaseModel):
    model_config = ConfigDict(extra="allow")
    object_name: str = Field(..., description="Mesh object to unwrap")
    method: str = Field(
        default="smart_project",
        description="smart_project | angle_based | conformal | lightmap_pack | cube_project | cylinder_project | sphere_project | unwrap_preserve",
    )
    angle_limit: Optional[float] = Field(default=66.0, description="Smart project angle threshold")
    island_margin: Optional[float] = Field(default=0.02, description="Island margin 0..1")
    quality: Optional[int] = Field(default=12, description="Lightmap pack quality")
    margin: Optional[float] = Field(default=0.003)
    cube_size: Optional[float] = Field(default=2.0)
    correct_aspect: Optional[bool] = Field(default=True)


class TextureBakeInput(BaseModel):
    model_config = ConfigDict(extra="allow")
    object_name: str = Field(..., description="Object to bake")
    bake_type: str = Field(
        default="diffuse",
        description="diffuse | normal | roughness | ao | metallic | emit | shadow | glossy | combined",
    )
    width: Optional[int] = Field(default=2048, ge=64)
    height: Optional[int] = Field(default=2048, ge=64)
    margin: Optional[int] = Field(default=16, ge=0)
    save_to: Optional[str] = Field(default=None, description="Absolute path to save baked image")
    use_cage: Optional[bool] = Field(default=False)
    cage_extrusion: Optional[float] = Field(default=0.0)


class LODInput(BaseModel):
    model_config = ConfigDict(extra="allow")
    object_name: str = Field(..., description="Source mesh to generate LOD chain from")
    levels: Optional[int] = Field(default=4, ge=2, le=8)
    ratio_step: Optional[float] = Field(default=0.5, gt=0, le=1)
    naming_scheme: Optional[str] = Field(default="{name}_LOD{n}")
    use_decimate: Optional[bool] = Field(default=True, description="True=Decimate collapse, False=poly_reduce")


class VROptimizeInput(BaseModel):
    model_config = ConfigDict(extra="allow")
    action: str = Field(..., description="validate | optimize | export")
    object_name: Optional[str] = Field(default=None)
    platform: Optional[str] = Field(default="meta_quest_3", description="meta_quest_3 | vision_pro | steamvr | webxr")
    target_polycount: Optional[int] = Field(default=None)
    preserve_uvs: Optional[bool] = Field(default=True)
    output_path: Optional[str] = Field(default=None)


class GaussianSplatInput(BaseModel):
    model_config = ConfigDict(extra="allow")
    action: str = Field(..., description="import_ply | import_splat | render_with_splats | list")
    filepath: Optional[str] = Field(default=None)
    output: Optional[str] = Field(default=None)


class GreasePencilInput(BaseModel):
    model_config = ConfigDict(extra="allow")
    action: str = Field(..., description="create_layer | draw_primitive | set_material | convert_to_mesh | clear")
    object_name: Optional[str] = Field(default=None, description="Grease Pencil object name")
    layer_name: Optional[str] = Field(default=None)
    primitive: Optional[str] = Field(default=None, description="circle | square | line")
    location: Optional[List[float]] = Field(default=None)
    size: Optional[float] = Field(default=1.0)
    color: Optional[List[float]] = Field(default=None, description="[r,g,b,a]")
    opacity: Optional[float] = Field(default=1.0)


class SnapshotInput(BaseModel):
    model_config = ConfigDict(extra="allow")
    action: str = Field(..., description="save | diff | list | clear | get")
    snapshot_id: Optional[str] = Field(default=None)
    a_id: Optional[str] = Field(default=None, description="For diff: snapshot A")
    b_id: Optional[str] = Field(default=None, description="For diff: snapshot B (default: latest)")
    include_thumbnail: Optional[bool] = Field(default=False)
    older_than_seconds: Optional[int] = Field(default=None)


class DriftStatusInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    session_id: Optional[str] = Field(default=None, description="Session ID; 'current' uses default session")
    reset: Optional[bool] = Field(default=False, description="Reset the monitor for this session")


# ═══════════════════════════════════════════════════════════════════════════════
# REGISTER
# ═══════════════════════════════════════════════════════════════════════════════

def register_extended_tools(mcp, send_command, format_result, drift_registry=None):
    """Register the Phase 5 + drift tools. Returns registered names."""

    @mcp.tool(
        name="blender_camera_advanced",
        annotations={"title": "Camera (Advanced)", "readOnlyHint": False,
                     "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    async def blender_camera_advanced(params: CameraAdvancedInput) -> str:
        """Advanced camera control: look_at, frame_objects, DOF/lens/clipping, turntable_setup."""
        return format_result(send_command("camera_advanced", params.model_dump(exclude_none=True)),
                             command="camera_advanced")

    @mcp.tool(
        name="blender_uv_unwrap",
        annotations={"title": "UV Unwrap", "readOnlyHint": False,
                     "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    )
    async def blender_uv_unwrap(params: UVUnwrapInput) -> str:
        """UV unwrap with 8 methods: smart_project, angle_based, conformal, lightmap_pack,
        cube_project, cylinder_project, sphere_project, unwrap_preserve."""
        return format_result(send_command("uv_unwrap", params.model_dump(exclude_none=True)))

    @mcp.tool(
        name="blender_texture_bake",
        annotations={"title": "Texture Bake", "readOnlyHint": False,
                     "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    )
    async def blender_texture_bake(params: TextureBakeInput) -> str:
        """Bake texture passes: diffuse, normal, roughness, ao, metallic, emit, shadow, glossy, combined."""
        return format_result(send_command("texture_bake", params.model_dump(exclude_none=True)))

    @mcp.tool(
        name="blender_lod",
        annotations={"title": "LOD Generator", "readOnlyHint": False,
                     "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    )
    async def blender_lod(params: LODInput) -> str:
        """Generate an auto-Decimate LOD chain (LOD0..LODn) from a source mesh."""
        return format_result(send_command("generate_lod", params.model_dump(exclude_none=True)))

    @mcp.tool(
        name="blender_vr_optimize",
        annotations={"title": "VR Optimize", "readOnlyHint": False,
                     "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    )
    async def blender_vr_optimize(params: VROptimizeInput) -> str:
        """Validate / optimize / export a mesh for a VR platform.

        Platforms: meta_quest_3 (50k tris), vision_pro (100k), steamvr (500k), webxr (30k).
        """
        return format_result(send_command("vr_" + params.action, params.model_dump(exclude_none=True)))

    @mcp.tool(
        name="blender_gaussian_splat",
        annotations={"title": "Gaussian Splat", "readOnlyHint": False,
                     "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    )
    async def blender_gaussian_splat(params: GaussianSplatInput) -> str:
        """Import or render Gaussian splat scenes (KIRI / Polycam .ply / .splat).
        Requires a splat addon (e.g. KIRI Innovations Blender addon)."""
        return format_result(send_command("gaussian_splat_" + params.action, params.model_dump(exclude_none=True)))

    @mcp.tool(
        name="blender_grease_pencil",
        annotations={"title": "Grease Pencil 2D", "readOnlyHint": False,
                     "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    )
    async def blender_grease_pencil(params: GreasePencilInput) -> str:
        """2D hybrid grease pencil workflow: layers, primitives, colors, convert_to_mesh."""
        return format_result(send_command("grease_pencil_action", params.model_dump(exclude_none=True)))

    @mcp.tool(
        name="blender_snapshot",
        annotations={"title": "Scene Snapshot/Diff", "readOnlyHint": False,
                     "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    async def blender_snapshot(params: SnapshotInput) -> str:
        """Save/diff/list lightweight scene snapshots. Diff reports objects_added/removed/modified,
        vertex_delta, modifier_stack_changes — the primary signal for action-hallucination detection."""
        return format_result(send_command("scene_snapshot_" + params.action, params.model_dump(exclude_none=True)))

    @mcp.tool(
        name="blender_drift_status",
        annotations={"title": "Behavioral Drift", "readOnlyHint": True,
                     "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    async def blender_drift_status(params: Optional[DriftStatusInput] = None) -> str:
        """Return EMA-based behavioral drift score for the current session.

        drift_score >= 0.5 → alert (agent has deviated sharply from baseline style).
        drift_score >= 0.3 → warn (minor drift). See server/drift_guard.py.

        Bug #8 fix (2026-04-24): params is now Optional — clients can call with no args.
        """
        if params is None:
            params = DriftStatusInput()
        try:
            from server.drift_guard import default_registry
        except ImportError:
            from drift_guard import default_registry  # type: ignore

        registry = drift_registry or default_registry()
        session_id = params.session_id or "current"
        monitor = registry.get_or_create(session_id)
        if params.reset:
            monitor.reset()
            return format_result({"reset": True, "session_id": session_id})
        return format_result(monitor.stats())

    return [
        "blender_camera_advanced",
        "blender_uv_unwrap",
        "blender_texture_bake",
        "blender_lod",
        "blender_vr_optimize",
        "blender_gaussian_splat",
        "blender_grease_pencil",
        "blender_snapshot",
        "blender_drift_status",
    ]
