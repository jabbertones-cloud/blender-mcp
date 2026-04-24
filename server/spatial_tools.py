"""
spatial_tools.py — Spatial reasoning MCP tools for OpenClaw Blender MCP.

Adds the highest-leverage capability gap identified in the notebook research:
spatial awareness. Without these the LLM cannot know "does this chair fit here?"
and produces overlapping, floating, or clipping scenes.

Tools registered:
  blender_spatial          — raycast, bbox, collision, placement, movement range
  blender_semantic_place   — "place the lamp on the nightstand" -> coords
  blender_dimensions       — real-world size DB + mesh estimation + auto-scale
  blender_floor_plan       — ASCII floor plan from evaluated bboxes

Source: mlolson/blender-orchestrator Spatial Intelligence Suite (notebook 1,
source 6efae520). Dimensions DB pattern + natural-language placement.

Exports `register_spatial_tools(mcp, send_command, format_result)` matching the
`register_product_tools()` signature used by the main MCP server.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field

_DIM_DB: Optional[dict] = None


def _load_dimensions_db() -> dict:
    """Load dimensions-db.json from config/ on first use."""
    global _DIM_DB
    if _DIM_DB is not None:
        return _DIM_DB
    # Resolve relative to this file: server/spatial_tools.py -> ../config/
    here = Path(__file__).resolve().parent
    candidates = [
        here.parent / "config" / "dimensions-db.json",
        Path.cwd() / "config" / "dimensions-db.json",
    ]
    for c in candidates:
        if c.exists():
            _DIM_DB = json.loads(c.read_text())
            return _DIM_DB
    _DIM_DB = {"aliases": {}, "objects": {}}
    return _DIM_DB


def _resolve_alias(key: str, db: dict) -> str:
    """Try direct key, then alias table."""
    if key in db.get("objects", {}):
        return key
    k = db.get("aliases", {}).get(key)
    return k if k else key


# ═══════════════════════════════════════════════════════════════════════════════
# INPUT MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class SpatialInput(BaseModel):
    model_config = ConfigDict(extra="allow")
    action: str = Field(
        ...,
        description=(
            "Action: 'raycast', 'bounding_box_world', 'check_collision', "
            "'find_placement_position', 'get_safe_movement_range', 'scene_bounds'"
        ),
    )
    origin: Optional[List[float]] = Field(default=None, description="[x,y,z] ray origin (for raycast)")
    direction: Optional[List[float]] = Field(default=None, description="[x,y,z] ray direction (for raycast)")
    max_distance: Optional[float] = Field(default=1000.0, description="Max raycast distance")
    name: Optional[str] = Field(default=None, description="Object name (for bounding_box_world)")
    a: Optional[str] = Field(default=None, description="First object (for collision)")
    b: Optional[str] = Field(default=None, description="Second object (for collision)")
    tolerance: Optional[float] = Field(default=0.001, description="Collision tolerance")
    object: Optional[str] = Field(default=None, description="Object to place / move")
    on_top_of: Optional[str] = Field(default=None, description="Target object for placement")
    offset_z: Optional[float] = Field(default=0.0, description="Z offset added to placement")
    axes: Optional[List[str]] = Field(default=None, description="Axes for movement range: ['x','y','z']")


class SemanticPlaceInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    instruction: str = Field(..., description="English placement command, e.g. 'place the lamp on the nightstand'")
    object_name: Optional[str] = Field(default=None, description="Override the object to place (skip parsing)")
    target_name: Optional[str] = Field(default=None, description="Override the target object (skip parsing)")
    dry_run: Optional[bool] = Field(default=False, description="Return parsed intent + coords without moving")


class DimensionsInput(BaseModel):
    model_config = ConfigDict(extra="allow")
    action: str = Field(..., description="Action: 'get', 'list', 'estimate_from_mesh', 'scale_to_realistic'")
    object_type: Optional[str] = Field(default=None, description="Dimension DB key, e.g. 'chair_dining'")
    object_name: Optional[str] = Field(default=None, description="Blender object name (for estimate/scale)")
    category: Optional[str] = Field(default=None, description="Filter by category on 'list'")


class FloorPlanInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    axis: Optional[str] = Field(default="z", description="Viewing axis: 'z' (top-down), 'x', or 'y'")
    width: Optional[int] = Field(default=80, ge=40, le=200, description="ASCII width in characters")
    height: Optional[int] = Field(default=30, ge=10, le=80, description="ASCII height in characters")


# ═══════════════════════════════════════════════════════════════════════════════
# NATURAL-LANGUAGE PLACEMENT PARSER
# ═══════════════════════════════════════════════════════════════════════════════

_PLACEMENT_RELATIONS = [
    (re.compile(r"\b(on top of|on|atop|above)\b", re.I), "on_top_of"),
    (re.compile(r"\b(inside|into|in)\b", re.I), "inside"),
    (re.compile(r"\b(next to|beside|adjacent to)\b", re.I), "next_to"),
    (re.compile(r"\b(left of)\b", re.I), "left_of"),
    (re.compile(r"\b(right of)\b", re.I), "right_of"),
    (re.compile(r"\b(in front of)\b", re.I), "in_front_of"),
    (re.compile(r"\b(behind)\b", re.I), "behind"),
    (re.compile(r"\b(below|under|underneath|beneath)\b", re.I), "below"),
]


def parse_placement_instruction(text: str) -> dict:
    """Parse "place the lamp on the nightstand" -> {object: 'lamp', relation: 'on_top_of', target: 'nightstand'}."""
    t = text.strip()
    # Strip leading "place the X", "put the X", "move the X"
    m = re.match(r"(?:place|put|move|position)\s+(?:the\s+)?(\S+)\s+(.+)", t, re.I)
    obj = None
    rest = t
    if m:
        obj = m.group(1).strip().rstrip(",")
        rest = m.group(2)

    relation = None
    target = None
    for pattern, rel in _PLACEMENT_RELATIONS:
        m2 = pattern.search(rest)
        if m2:
            relation = rel
            # Text after the relation is the target
            after = rest[m2.end():].strip()
            # Strip "the " prefix and trailing period
            after = re.sub(r"^the\s+", "", after, flags=re.I).rstrip(".,;!")
            target = after.split()[0] if after else None
            break

    return {"object": obj, "relation": relation, "target": target, "raw": text}


def _format_ascii_floor_plan(objects: list, width: int, height: int, axis: str) -> str:
    """Render a list of world-space bboxes as an ASCII grid.

    objects: [{"name": ..., "bbox": {"min": [x,y,z], "max": [x,y,z]}}]
    axis: 'z' => top-down (X horizontal, Y vertical).
    """
    if not objects:
        return "(scene is empty)\n"

    # Pick the 2 relevant axes
    if axis == "z":
        h_idx, v_idx = 0, 1  # x, y
    elif axis == "x":
        h_idx, v_idx = 1, 2  # y, z
    else:  # y
        h_idx, v_idx = 0, 2  # x, z

    # Determine scene bounds
    all_mins = [o["bbox"]["min"] for o in objects if o.get("bbox")]
    all_maxs = [o["bbox"]["max"] for o in objects if o.get("bbox")]
    if not all_mins:
        return "(no bboxes available)\n"
    hmin = min(m[h_idx] for m in all_mins)
    hmax = max(m[h_idx] for m in all_maxs)
    vmin = min(m[v_idx] for m in all_mins)
    vmax = max(m[v_idx] for m in all_maxs)
    hspan = max(hmax - hmin, 0.001)
    vspan = max(vmax - vmin, 0.001)

    grid = [[" "] * width for _ in range(height)]
    legend = {}
    for i, obj in enumerate(objects):
        label = chr(ord("A") + (i % 26)) if i < 26 else "#"
        legend[label] = obj["name"]
        bb = obj.get("bbox")
        if not bb:
            continue
        x0 = int((bb["min"][h_idx] - hmin) / hspan * (width - 1))
        x1 = int((bb["max"][h_idx] - hmin) / hspan * (width - 1))
        y0 = int((bb["min"][v_idx] - vmin) / vspan * (height - 1))
        y1 = int((bb["max"][v_idx] - vmin) / vspan * (height - 1))
        y0, y1 = height - 1 - y1, height - 1 - y0  # flip Y (ASCII row 0 is top)
        for r in range(max(0, y0), min(height, y1 + 1)):
            for c in range(max(0, x0), min(width, x1 + 1)):
                grid[r][c] = label

    title = f"Floor plan (axis={axis}, span {hspan:.2f}m × {vspan:.2f}m)"
    ruler = "+" + "-" * width + "+"
    body = "\n".join("|" + "".join(row) + "|" for row in grid)
    legend_str = "\n".join(f"  {k} = {v}" for k, v in legend.items())
    return f"{title}\n{ruler}\n{body}\n{ruler}\n{legend_str}\n"


# ═══════════════════════════════════════════════════════════════════════════════
# REGISTER TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

def register_spatial_tools(mcp, send_command, format_result):
    """Register blender_spatial / blender_semantic_place / blender_dimensions /
    blender_floor_plan with the FastMCP server. Returns the list of registered tool names."""

    @mcp.tool(
        name="blender_spatial",
        annotations={"title": "Spatial Reasoning", "readOnlyHint": True,
                     "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    async def blender_spatial(params: SpatialInput) -> str:
        """Spatial reasoning via the addon's depsgraph-backed helpers.

        Actions:
          - raycast: fire a ray from origin along direction, return first hit
          - bounding_box_world: world-space evaluated bbox of an object
          - check_collision: do two objects' bboxes intersect?
          - find_placement_position: suggest (x,y,z) to center `object` on top of `on_top_of`
          - get_safe_movement_range: how far can `object` move in each axis without colliding
          - scene_bounds: overall scene bbox
        """
        return format_result(send_command("spatial_" + params.action, params.model_dump(exclude_none=True)),
                             command="spatial")

    @mcp.tool(
        name="blender_semantic_place",
        annotations={"title": "Semantic Placement", "readOnlyHint": False,
                     "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    )
    async def blender_semantic_place(params: SemanticPlaceInput) -> str:
        """Parse an English placement command and move the object.

        Example: 'place the lamp on the nightstand' →
          1. parse: {object: 'lamp', relation: 'on_top_of', target: 'nightstand'}
          2. call spatial_find_placement with (object, on_top_of=target)
          3. if not dry_run, call modify_object with the new location
        """
        parsed = parse_placement_instruction(params.instruction)
        obj = params.object_name or parsed["object"]
        target = params.target_name or parsed["target"]
        relation = parsed["relation"]

        if not obj or not target or not relation:
            return format_result({"error": f"Could not parse placement. Parsed: {parsed}"})

        if relation != "on_top_of":
            # For now, defer other relations to the addon with a `relation` param
            return format_result(send_command("semantic_place", {
                "object": obj, "target": target, "relation": relation, "dry_run": params.dry_run
            }))

        # on_top_of path
        placement = send_command("spatial_find_placement", {"object": obj, "on_top_of": target})
        if "error" in placement:
            return format_result(placement)

        new_loc = placement.get("location") or placement.get("suggested_location")
        result = {"parsed": parsed, "placement": placement}
        if params.dry_run:
            result["dry_run"] = True
            return format_result(result)

        move = send_command("modify_object", {"name": obj, "location": new_loc})
        result["move_result"] = move
        return format_result(result)

    @mcp.tool(
        name="blender_dimensions",
        annotations={"title": "Dimensions Database", "readOnlyHint": False,
                     "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    )
    async def blender_dimensions(params: DimensionsInput) -> str:
        """Real-world dimensions DB for grounding LLM scene generation.

        Actions:
          - get: lookup by object_type (kitchen_counter, chair_dining, ...)
          - list: all known object_types (optionally filtered by category)
          - estimate_from_mesh: return the evaluated bbox dimensions of `object_name`
          - scale_to_realistic: scale the mesh so it matches `object_type`'s dimensions
        """
        db = _load_dimensions_db()
        action = params.action

        if action == "list":
            items = db.get("objects", {})
            if params.category:
                items = {k: v for k, v in items.items() if v.get("category") == params.category}
            return format_result({"count": len(items), "objects": items})

        if action == "get":
            if not params.object_type:
                return format_result({"error": "object_type required"})
            key = _resolve_alias(params.object_type, db)
            entry = db.get("objects", {}).get(key)
            if not entry:
                return format_result({"error": f"'{params.object_type}' not in dimensions DB", "hint": "try blender_dimensions(action='list')"})
            return format_result({"object_type": key, "requested": params.object_type, **entry})

        if action == "estimate_from_mesh":
            if not params.object_name:
                return format_result({"error": "object_name required"})
            return format_result(send_command("dimensions_estimate", {"name": params.object_name}))

        if action == "scale_to_realistic":
            if not (params.object_name and params.object_type):
                return format_result({"error": "object_name and object_type required"})
            key = _resolve_alias(params.object_type, db)
            target = db.get("objects", {}).get(key)
            if not target:
                return format_result({"error": f"'{params.object_type}' not in dimensions DB"})
            # Ask addon to compute and apply the scale factor in one step
            return format_result(send_command("dimensions_scale", {
                "name": params.object_name, "target_dimensions": target,
            }))

        return format_result({"error": f"Unknown action '{action}'"})

    @mcp.tool(
        name="blender_floor_plan",
        annotations={"title": "ASCII Floor Plan", "readOnlyHint": True,
                     "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    async def blender_floor_plan(params: FloorPlanInput) -> str:
        """Render the scene as an ASCII floor plan — cheap spatial context for the LLM.

        Reads evaluated world-space bboxes for every visible mesh, projects onto
        the chosen axis, and returns a labeled ASCII grid with a legend.
        """
        data = send_command("floor_plan_data", {"axis": params.axis or "z"})
        if "error" in data:
            return format_result(data)
        objects = data.get("objects", [])
        plan = _format_ascii_floor_plan(objects, params.width or 80, params.height or 30, params.axis or "z")
        return format_result({"floor_plan": plan, "object_count": len(objects), "axis": params.axis or "z"})

    return [
        "blender_spatial",
        "blender_semantic_place",
        "blender_dimensions",
        "blender_floor_plan",
    ]
