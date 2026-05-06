#!/usr/bin/env python3
"""
OpenClaw Blender MCP Server
============================
FastMCP server that bridges Claude/AI to a running Blender instance
via the OpenClaw Blender Bridge addon (TCP socket on 127.0.0.1:9876).

Install: pip install mcp pydantic
Run:     python blender_mcp_server.py
"""

import json
import socket
import traceback
import sys
import os
import uuid
from collections import OrderedDict
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict, field_validator
from mcp.server.fastmcp import FastMCP

# CADAM-style parametric workflow (v3.1) — system prompt + safe parameter parsing
try:
    from server.codegen_prompt import (
        BPY_GENERATION_SYSTEM_PROMPT,
        PARAMETERS_BLOCK_TEMPLATE,
        extract_parameters as _extract_parameters,
        validate_parameters_block as _validate_parameters_block,
        replace_parameters as _replace_parameters,
    )
except ModuleNotFoundError:
    from codegen_prompt import (  # type: ignore
        BPY_GENERATION_SYSTEM_PROMPT,
        PARAMETERS_BLOCK_TEMPLATE,
        extract_parameters as _extract_parameters,
        validate_parameters_block as _validate_parameters_block,
        replace_parameters as _replace_parameters,
    )

# Server-side AST safety check (defense in depth — addon also checks)
try:
    from server.safety import check as _safety_check, CodeSafetyError as _CodeSafetyError
except ModuleNotFoundError:
    try:
        from safety import check as _safety_check, CodeSafetyError as _CodeSafetyError  # type: ignore
    except ModuleNotFoundError:
        _safety_check = None  # type: ignore
        _CodeSafetyError = Exception  # type: ignore
try:
    from server.runtime_config import (
        DEFAULT_BLENDER_PORT,
        resolve_blender_host,
        resolve_blender_port,
    )
except ModuleNotFoundError:
    from runtime_config import (  # type: ignore
        DEFAULT_BLENDER_PORT,
        resolve_blender_host,
        resolve_blender_port,
    )

# CADAM-style image extraction (two-pass reference image workflow)
try:
    from server.image_extraction import (
        IMAGE_EXTRACTION_PROMPT,
        IMAGE_EXTRACTION_SCHEMA,
        validate_extraction,
        build_seed_params,
    )
except ModuleNotFoundError:
    from image_extraction import (  # type: ignore
        IMAGE_EXTRACTION_PROMPT,
        IMAGE_EXTRACTION_SCHEMA,
        validate_extraction,
        build_seed_params,
    )

# Product animation tools extension
try:
    from product_animation_tools import register_product_tools
    _HAS_PRODUCT_TOOLS = True
except ImportError:
    try:
        import importlib.util
        _pat_path = os.path.join(os.path.dirname(__file__), "product_animation_tools.py")
        if os.path.exists(_pat_path):
            spec = importlib.util.spec_from_file_location("product_animation_tools", _pat_path)
            _pat_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(_pat_mod)
            register_product_tools = _pat_mod.register_product_tools
            _HAS_PRODUCT_TOOLS = True
        else:
            _HAS_PRODUCT_TOOLS = False
    except Exception:
        _HAS_PRODUCT_TOOLS = False

# ─── Configuration ───────────────────────────────────────────────────────────
BLENDER_HOST = resolve_blender_host()
BLENDER_PORT = resolve_blender_port()  # Supports BLENDER_PORT and OPENCLAW_PORT
SOCKET_TIMEOUT = float(os.getenv("OPENCLAW_TIMEOUT", "30.0"))
COMPACT_MODE = os.getenv("OPENCLAW_COMPACT", "").lower() in ("1", "true", "yes")
MAX_RESPONSE_CHARS = 4000
BLENDER_REGISTRY_PATH = os.getenv("BLENDER_REGISTRY_PATH", "config/blender-instances.json")
BLENDER_HEARTBEAT_TIMEOUT = int(os.getenv("BLENDER_HEARTBEAT_TIMEOUT", "300"))  # 5 minutes

# ─── Multi-Instance Registry ─────────────────────────────────────────────────
# Tracks all known Blender instances for concurrent agent work.
# Each instance runs on a different port and works on a different .blend file.
_instance_registry: Dict[str, Dict[str, Any]] = {}


def discover_instances(port_range: tuple = (9876, 9886)) -> Dict[str, Dict[str, Any]]:
    """Probe a range of ports to discover running Blender Bridge instances.
    Returns dict of instance_id -> {port, blender_version, file, objects, scene}."""
    found = {}
    for port in range(port_range[0], port_range[1]):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.0)
            sock.connect((BLENDER_HOST, port))
            ping = json.dumps({"id": "discover", "command": "ping", "params": {}})
            sock.sendall(ping.encode("utf-8"))
            raw = b""
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                raw += chunk
                try:
                    resp = json.loads(raw.decode("utf-8"))
                    break
                except json.JSONDecodeError:
                    continue
            sock.close()
            result = resp.get("result", resp)
            instance_id = result.get("instance_id", f"blender-{port}")
            found[instance_id] = {
                "port": port,
                "host": BLENDER_HOST,
                "blender_version": result.get("blender_version", "unknown"),
                "file": result.get("file", "unknown"),
                "objects": result.get("objects", 0),
                "scene": result.get("scene", "unknown"),
            }
        except (ConnectionRefusedError, socket.timeout, OSError):
            continue
        except Exception:
            continue
    _instance_registry.update(found)
    return found


def send_command_to(port: int, command: str, params: dict = None, host: str = None) -> dict:
    """Send a command to a specific Blender instance by port number."""
    target_host = host or BLENDER_HOST
    global _request_counter
    _request_counter += 1

    payload = {
        "id": str(_request_counter),
        "command": command,
        "params": params or {},
    }

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(SOCKET_TIMEOUT)
        sock.connect((target_host, port))
        sock.sendall(json.dumps(payload).encode("utf-8"))

        chunks = []
        while True:
            chunk = sock.recv(1048576)
            if not chunk:
                break
            chunks.append(chunk)
            try:
                return json.loads(b"".join(chunks).decode("utf-8"))
            except json.JSONDecodeError:
                continue

        return json.loads(b"".join(chunks).decode("utf-8"))
    except ConnectionRefusedError:
        return {
            "error": (
                f"Blender not running on {target_host}:{port}. "
                f"Start Blender with BLENDER_PORT={port} and OPENCLAW_PORT={port}"
            )
        }
    except socket.timeout:
        return {"error": f"Blender on port {port} timed out after {SOCKET_TIMEOUT}s"}
    except Exception as e:
        return {"error": f"Connection to {target_host}:{port} failed: {str(e)}"}
    finally:
        try:
            sock.close()
        except:
            pass

# ─── Initialize MCP Server ──────────────────────────────────────────────────
mcp = FastMCP("blender_mcp")

# ─── Socket Communication ───────────────────────────────────────────────────
_request_counter = 0


def send_command(command: str, params: dict = None) -> dict:
    """Send a command to the Blender Bridge addon and return the response."""
    global _request_counter
    _request_counter += 1

    payload = {
        "id": str(_request_counter),
        "command": command,
        "params": params or {},
    }

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(SOCKET_TIMEOUT)
        sock.connect((BLENDER_HOST, BLENDER_PORT))
        sock.sendall(json.dumps(payload).encode("utf-8"))

        # Receive response
        chunks = []
        while True:
            chunk = sock.recv(1048576)  # 1MB buffer
            if not chunk:
                break
            chunks.append(chunk)
            # Try to parse
            try:
                data = json.loads(b"".join(chunks).decode("utf-8"))
                sock.close()
                if "error" in data and data["error"]:
                    return {"error": data["error"], "traceback": data.get("traceback", "")}
                return data.get("result", data)
            except json.JSONDecodeError:
                continue

        sock.close()
        raw = b"".join(chunks).decode("utf-8")
        return json.loads(raw) if raw else {"error": "Empty response from Blender"}

    except ConnectionRefusedError:
        return {
            "error": "Cannot connect to Blender. Make sure Blender is running with the OpenClaw Bridge addon enabled "
            f"(default port {DEFAULT_BLENDER_PORT}). Install the addon: Blender > Edit > Preferences > Add-ons > "
            "Install > select openclaw_blender_bridge.py"
        }
    except socket.timeout:
        return {"error": "Blender command timed out (30s). The operation may still be running in Blender."}
    except Exception as e:
        return {"error": f"Socket error: {str(e)}", "traceback": traceback.format_exc()}


def estimate_tokens(text: str) -> int:
    """Estimate token count as roughly 1 token per 4 characters."""
    return max(1, len(text) // 4)


def _summarize_scene_info(data: dict) -> dict:
    """Smart summarization for get_scene_info: count objects, list only names/types, full details for active object."""
    if "error" in data:
        return data
    
    summary = {
        "summary": {
            "total_objects": len(data.get("objects", [])),
            "meshes": len([o for o in data.get("objects", []) if o.get("type") == "MESH"]),
            "lights": len([o for o in data.get("objects", []) if o.get("type") == "LIGHT"]),
            "cameras": len([o for o in data.get("objects", []) if o.get("type") == "CAMERA"]),
            "materials": len(data.get("materials", [])),
        },
        "objects": [
            {"name": o.get("name"), "type": o.get("type")}
            for o in data.get("objects", [])
        ],
        "active_object": data.get("active_object"),
        "render_engine": data.get("render_engine"),
        "frame_range": data.get("frame_range"),
    }
    return summary


def format_result(result: dict, command: Optional[str] = None, compact: Optional[bool] = None) -> str:
    """Format a result dict as JSON with optional compaction, truncation, and response envelope.
    
    Args:
        result: The result dict from send_command()
        command: Optional command name (used to apply smart summarization)
        compact: Override COMPACT_MODE setting. If None, uses env var.
    
    Returns:
        Formatted JSON string, possibly compact and truncated with envelope.
    """
    use_compact = compact if compact is not None else COMPACT_MODE
    
    # Handle errors first
    if isinstance(result, dict) and "error" in result:
        error_msg = f"Error: {result['error']}"
        if result.get("traceback"):
            error_msg += f"\n\nTraceback:\n{result['traceback']}"
        return error_msg
    
    # Apply smart summarization for get_scene_info
    if command == "get_scene_info" and isinstance(result, dict):
        result = _summarize_scene_info(result)
    
    # Format JSON
    if use_compact:
        json_str = json.dumps(result, separators=(',', ':'), default=str)
    else:
        json_str = json.dumps(result, indent=2, default=str)
    
    # Truncate if needed
    if len(json_str) > MAX_RESPONSE_CHARS:
        # Count items in top-level array/dict for summary
        item_count = len(result) if isinstance(result, dict) else len(result) if isinstance(result, list) else 1
        truncated = json_str[:MAX_RESPONSE_CHARS - 50]
        json_str = truncated + f"... [truncated, {item_count} total items]"
    
    # Wrap in response envelope
    tokens_est = estimate_tokens(json_str)
    envelope = {
        "status": "ok",
        "tokens_est": tokens_est,
        "data": result,
    }
    
    if use_compact:
        return json.dumps(envelope, separators=(',', ':'), default=str)
    else:
        return json.dumps(envelope, indent=2, default=str)


# ═══════════════════════════════════════════════════════════════════════════════
# INPUT MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class Vector3(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    x: float = Field(default=0.0, description="X coordinate")
    y: float = Field(default=0.0, description="Y coordinate")
    z: float = Field(default=0.0, description="Z coordinate")

    def to_list(self):
        return [self.x, self.y, self.z]


class Color4(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    r: float = Field(default=0.8, ge=0.0, le=1.0, description="Red (0-1)")
    g: float = Field(default=0.8, ge=0.0, le=1.0, description="Green (0-1)")
    b: float = Field(default=0.8, ge=0.0, le=1.0, description="Blue (0-1)")
    a: float = Field(default=1.0, ge=0.0, le=1.0, description="Alpha (0-1)")

    def to_list(self):
        return [self.r, self.g, self.b, self.a]


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL DEFINITIONS (59 MCP tools here; +6 product tools in product_animation_tools.py = 65)
# ═══════════════════════════════════════════════════════════════════════════════

# ─── Health & Scene Info ─────────────────────────────────────────────────────

@mcp.tool(
    name="blender_ping",
    annotations={"title": "Ping Blender", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
async def blender_ping() -> str:
    """Check if Blender is running and the bridge addon is active. Returns Blender version, current file, and object count."""
    return format_result(send_command("ping"))


@mcp.tool(
    name="blender_get_scene_info",
    annotations={"title": "Get Scene Info", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
async def blender_get_scene_info() -> str:
    """Get comprehensive information about the current Blender scene: all objects (with types, locations, materials, vertex counts), render settings, collections, active object, frame range, and world settings. Use this first to understand the current state."""
    return format_result(send_command("get_scene_info"))


@mcp.tool(
    name="blender_get_object_data",
    annotations={"title": "Get Object Details", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
async def blender_get_object_data(name: str = Field(..., description="Exact name of the object in Blender (e.g. 'Cube', 'Suzanne')")) -> str:
    """Get detailed data about a specific object: mesh stats, modifiers, constraints, animation data, materials, children, collections. More detailed than scene info for a single object."""
    return format_result(send_command("get_object_data", {"name": name}))


# ─── Object Creation ────────────────────────────────────────────────────────

class CreateObjectInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    type: str = Field(default="cube", description="Object type: cube, sphere, ico_sphere, cylinder, cone, torus, plane, circle, grid, monkey, empty, camera, light_point, light_sun, light_spot, light_area")
    name: Optional[str] = Field(default=None, description="Custom name for the object")
    location: Optional[List[float]] = Field(default=[0, 0, 0], description="XYZ location [x, y, z]")
    rotation: Optional[List[float]] = Field(default=[0, 0, 0], description="XYZ rotation in degrees [rx, ry, rz]")
    scale: Optional[List[float]] = Field(default=[1, 1, 1], description="XYZ scale [sx, sy, sz]")
    size: Optional[float] = Field(default=2.0, description="Base size of the primitive", gt=0)


@mcp.tool(
    name="blender_create_object",
    annotations={"title": "Create Object", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
)
async def blender_create_object(params: CreateObjectInput) -> str:
    """Create a new mesh primitive, camera, light, or empty in the scene. Supports: cube, sphere, ico_sphere, cylinder, cone, torus, plane, circle, grid, monkey, empty, camera, light_point, light_sun, light_spot, light_area. Returns the created object's name and transform."""
    return format_result(send_command("create_object", params.model_dump(exclude_none=True)))


# ─── Object Modification ────────────────────────────────────────────────────

class ModifyObjectInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(..., description="Name of the object to modify")
    location: Optional[List[float]] = Field(default=None, description="New XYZ location [x, y, z]")
    rotation: Optional[List[float]] = Field(default=None, description="New XYZ rotation in degrees [rx, ry, rz]")
    scale: Optional[List[float]] = Field(default=None, description="New XYZ scale [sx, sy, sz]")
    visible: Optional[bool] = Field(default=None, description="Show/hide object in viewport and render")
    new_name: Optional[str] = Field(default=None, description="Rename the object")


@mcp.tool(
    name="blender_modify_object",
    annotations={"title": "Modify Object", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
async def blender_modify_object(params: ModifyObjectInput) -> str:
    """Modify an existing object's location, rotation, scale, visibility, or name. All parameters except 'name' are optional - only provided values are changed."""
    return format_result(send_command("modify_object", params.model_dump(exclude_none=True)))


# ─── Object Deletion ────────────────────────────────────────────────────────

@mcp.tool(
    name="blender_delete_object",
    annotations={"title": "Delete Objects", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": True, "openWorldHint": False},
)
async def blender_delete_object(names: List[str] = Field(..., description="List of object names to delete")) -> str:
    """Delete one or more objects by name. Returns which objects were deleted and which were not found."""
    return format_result(send_command("delete_object", {"names": names}))


# ─── Object Selection ───────────────────────────────────────────────────────

class SelectObjectsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(default="select", description="Action: 'select', 'deselect', 'toggle', 'all', 'none'")
    names: Optional[List[str]] = Field(default=[], description="Object names (for select/deselect/toggle)")
    set_active: Optional[bool] = Field(default=False, description="Set the first named object as active")


@mcp.tool(
    name="blender_select_objects",
    annotations={"title": "Select Objects", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
async def blender_select_objects(params: SelectObjectsInput) -> str:
    """Select or deselect objects. Actions: 'select' (add to selection), 'deselect', 'toggle', 'all' (select everything), 'none' (deselect all). Returns list of currently selected objects."""
    return format_result(send_command("select_objects", params.model_dump()))


# ─── Object Duplication ─────────────────────────────────────────────────────

class DuplicateObjectInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(..., description="Name of object to duplicate")
    new_name: Optional[str] = Field(default=None, description="Name for the duplicate")
    offset: Optional[List[float]] = Field(default=None, description="XYZ offset from original [x, y, z]")
    linked: Optional[bool] = Field(default=False, description="Create a linked duplicate (shares mesh data)")


@mcp.tool(
    name="blender_duplicate_object",
    annotations={"title": "Duplicate Object", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
)
async def blender_duplicate_object(params: DuplicateObjectInput) -> str:
    """Duplicate an object. Optionally offset the copy, rename it, or create a linked duplicate that shares mesh data."""
    return format_result(send_command("duplicate_object", params.model_dump(exclude_none=True)))


# ─── Transform Operations ───────────────────────────────────────────────────

class TransformInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(..., description="Action: 'join', 'origin_to_geometry', 'origin_to_cursor', 'apply_transforms', 'snap_cursor'")
    name: Optional[str] = Field(default=None, description="Object name (for single-object operations)")
    names: Optional[List[str]] = Field(default=None, description="Object names (for join)")
    target: Optional[str] = Field(default=None, description="Snap cursor target: 'world_origin', 'selected', 'active'")
    apply_location: Optional[bool] = Field(default=True)
    apply_rotation: Optional[bool] = Field(default=True)
    apply_scale: Optional[bool] = Field(default=True)


@mcp.tool(
    name="blender_transform_object",
    annotations={"title": "Transform Operations", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
)
async def blender_transform_object(params: TransformInput) -> str:
    """Advanced transform operations: 'join' (merge objects), 'origin_to_geometry', 'origin_to_cursor', 'apply_transforms' (apply loc/rot/scale), 'snap_cursor' (move 3D cursor)."""
    return format_result(send_command("transform_object", params.model_dump(exclude_none=True)))


# ─── Parent/Child ────────────────────────────────────────────────────────────

class ParentInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    parent: str = Field(..., description="Name of the parent object")
    children: List[str] = Field(..., description="Names of child objects")
    keep_transform: Optional[bool] = Field(default=True, description="Keep children's world transforms")


@mcp.tool(
    name="blender_parent_objects",
    annotations={"title": "Parent Objects", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
async def blender_parent_objects(params: ParentInput) -> str:
    """Set parent-child relationships between objects. Children will inherit the parent's transform."""
    return format_result(send_command("parent_objects", params.model_dump()))


# ─── Modifiers ───────────────────────────────────────────────────────────────

class ModifierInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    object_name: str = Field(..., description="Object to add modifier to")
    action: str = Field(default="add", description="Action: 'add', 'apply', 'remove'")
    modifier_type: Optional[str] = Field(default=None, description="Modifier type: SUBSURF, MIRROR, ARRAY, BEVEL, SOLIDIFY, BOOLEAN, DECIMATE, REMESH, SHRINKWRAP, SMOOTH, SIMPLE_DEFORM, DISPLACE, WIREFRAME, etc.")
    modifier_name: Optional[str] = Field(default=None, description="Name for the modifier")
    properties: Optional[Dict[str, Any]] = Field(default=None, description="Modifier properties to set (e.g. {'levels': 2, 'render_levels': 3} for Subdivision Surface)")


@mcp.tool(
    name="blender_apply_modifier",
    annotations={"title": "Modifiers", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
)
async def blender_apply_modifier(params: ModifierInput) -> str:
    """Add, apply, or remove modifiers on an object. Common modifiers: SUBSURF (subdivision), MIRROR, ARRAY, BEVEL, SOLIDIFY, BOOLEAN, DECIMATE, REMESH, SHRINKWRAP, SMOOTH, WIREFRAME, DISPLACE."""
    return format_result(send_command("apply_modifier", params.model_dump(exclude_none=True)))


# ─── Boolean Operations ─────────────────────────────────────────────────────

class BooleanInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    object_name: str = Field(..., description="Main object")
    target_name: str = Field(..., description="Object to boolean with")
    operation: str = Field(default="DIFFERENCE", description="Operation: DIFFERENCE, UNION, INTERSECT")
    apply: Optional[bool] = Field(default=True, description="Apply the modifier immediately")
    delete_target: Optional[bool] = Field(default=True, description="Delete the target object after applying")


@mcp.tool(
    name="blender_boolean_operation",
    annotations={"title": "Boolean Operation", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": False},
)
async def blender_boolean_operation(params: BooleanInput) -> str:
    """Perform boolean operations (DIFFERENCE, UNION, INTERSECT) between two objects. By default applies the modifier and deletes the target object."""
    return format_result(send_command("boolean_operation", params.model_dump()))


# ─── Materials ───────────────────────────────────────────────────────────────

class MaterialInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    object_name: str = Field(..., description="Object to apply material to")
    material_name: Optional[str] = Field(default=None, description="Material name (creates new if doesn't exist)")
    color: Optional[List[float]] = Field(default=None, description="Base color [R, G, B] or [R, G, B, A] (0-1 range)")
    metallic: Optional[float] = Field(default=0.0, ge=0.0, le=1.0, description="Metallic factor (0=dielectric, 1=metal)")
    roughness: Optional[float] = Field(default=0.5, ge=0.0, le=1.0, description="Roughness factor (0=glossy, 1=rough)")
    emission_color: Optional[List[float]] = Field(default=None, description="Emission color [R, G, B] (0-1)")
    emission_strength: Optional[float] = Field(default=0.0, ge=0.0, description="Emission strength")
    slot: Optional[int] = Field(default=0, ge=0, description="Material slot index")


@mcp.tool(
    name="blender_set_material",
    annotations={"title": "Set Material", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
async def blender_set_material(params: MaterialInput) -> str:
    """Create or assign a Principled BSDF material to an object. Set base color, metallic, roughness, and emission. Creates the material if it doesn't exist."""
    return format_result(send_command("set_material", params.model_dump(exclude_none=True)))


# ─── Shader Nodes ────────────────────────────────────────────────────────────

class ShaderNodeInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    material_name: str = Field(..., description="Material name (created if doesn't exist)")
    action: str = Field(default="info", description="Action: 'info' (list nodes), 'add_node', 'connect', 'set_value'")
    node_type: Optional[str] = Field(default=None, description="Node type for add_node (e.g. 'ShaderNodeTexNoise', 'ShaderNodeMixShader', 'ShaderNodeTexImage')")
    name: Optional[str] = Field(default=None, description="Name for new node")
    location: Optional[List[float]] = Field(default=None, description="Node location [x, y]")
    from_node: Optional[str] = Field(default=None, description="Source node name (for connect)")
    to_node: Optional[str] = Field(default=None, description="Destination node name (for connect)")
    from_output: Optional[int] = Field(default=0, description="Source output socket index")
    to_input: Optional[int] = Field(default=0, description="Destination input socket index")
    node_name: Optional[str] = Field(default=None, description="Node name (for set_value)")
    input_name: Optional[str] = Field(default=None, description="Input name (for set_value)")
    value: Optional[Any] = Field(default=None, description="Value to set")


@mcp.tool(
    name="blender_shader_nodes",
    annotations={"title": "Shader Nodes", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
)
async def blender_shader_nodes(params: ShaderNodeInput) -> str:
    """Manipulate shader/material nodes: 'info' (list all nodes and connections), 'add_node' (add texture, math, mix nodes etc.), 'connect' (link node outputs to inputs), 'set_value' (set input defaults). For advanced procedural materials."""
    return format_result(send_command("shader_nodes", params.model_dump(exclude_none=True)))


# ─── Render Settings ────────────────────────────────────────────────────────

class RenderSettingsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    engine: Optional[str] = Field(default=None, description="Render engine: 'eevee', 'cycles', 'workbench'")
    resolution_x: Optional[int] = Field(default=None, ge=1, le=16384, description="Render width in pixels")
    resolution_y: Optional[int] = Field(default=None, ge=1, le=16384, description="Render height in pixels")
    resolution_percentage: Optional[int] = Field(default=None, ge=1, le=100, description="Resolution scale percentage")
    samples: Optional[int] = Field(default=None, ge=1, description="Render samples (Cycles)")
    film_transparent: Optional[bool] = Field(default=None, description="Transparent background")
    output_path: Optional[str] = Field(default=None, description="Output file path")
    file_format: Optional[str] = Field(default=None, description="Output format: PNG, JPEG, EXR, TIFF, BMP")
    fps: Optional[int] = Field(default=None, ge=1, description="Frames per second")
    frame_start: Optional[int] = Field(default=None, description="Animation start frame")
    frame_end: Optional[int] = Field(default=None, description="Animation end frame")


@mcp.tool(
    name="blender_set_render_settings",
    annotations={"title": "Set Render Settings", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
async def blender_set_render_settings(params: RenderSettingsInput) -> str:
    """Configure render settings: engine (eevee/cycles/workbench), resolution, samples, output path, file format, fps, frame range. Only provided values are changed."""
    return format_result(send_command("set_render_settings", params.model_dump(exclude_none=True)))


# ─── Render ──────────────────────────────────────────────────────────────────

class RenderInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    output_path: Optional[str] = Field(default=None, description="Output file path (e.g. '/tmp/render.png')")
    type: str = Field(default="image", description="Render type: 'image' (single frame) or 'animation' (all frames)")


@mcp.tool(
    name="blender_render",
    annotations={"title": "Render Scene", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
)
async def blender_render(params: RenderInput) -> str:
    """Render the current scene to an image file or animation. Set output_path first via blender_set_render_settings or pass it here. Returns the output path."""
    return format_result(send_command("render", params.model_dump(exclude_none=True)))


# ─── Keyframes / Animation ──────────────────────────────────────────────────

class KeyframeInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    object_name: str = Field(..., description="Object to keyframe")
    frame: Optional[int] = Field(default=None, description="Frame number (uses current if omitted)")
    property: str = Field(default="location", description="Property to keyframe: 'location', 'rotation_euler', 'scale'")
    value: Optional[List[float]] = Field(default=None, description="Property value (e.g. [1, 2, 3] for location). If omitted, keyframes current value.")


@mcp.tool(
    name="blender_set_keyframe",
    annotations={"title": "Set Keyframe", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
async def blender_set_keyframe(params: KeyframeInput) -> str:
    """Insert a keyframe on an object at a specific frame for location, rotation, or scale. Provide a value to also set the property, or omit to keyframe the current value."""
    return format_result(send_command("set_keyframe", params.model_dump(exclude_none=True)))


@mcp.tool(
    name="blender_clear_keyframes",
    annotations={"title": "Clear Keyframes", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": True, "openWorldHint": False},
)
async def blender_clear_keyframes(object_name: str = Field(..., description="Object to clear animation from")) -> str:
    """Remove all keyframes and animation data from an object."""
    return format_result(send_command("clear_keyframes", {"object_name": object_name}))


# ─── Scene Operations ───────────────────────────────────────────────────────

class SceneInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(..., description="Action: 'set_frame', 'new_scene', 'delete_scene', 'list_scenes', 'switch_scene'")
    frame: Optional[int] = Field(default=None, description="Frame number (for set_frame)")
    name: Optional[str] = Field(default=None, description="Scene name")


@mcp.tool(
    name="blender_scene_operations",
    annotations={"title": "Scene Operations", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
async def blender_scene_operations(params: SceneInput) -> str:
    """Manage scenes: 'set_frame' (jump to frame), 'new_scene' (create), 'delete_scene', 'list_scenes', 'switch_scene'."""
    return format_result(send_command("scene_operations", params.model_dump(exclude_none=True)))


# ─── Collections ─────────────────────────────────────────────────────────────

class CollectionInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(default="list", description="Action: 'list', 'create', 'delete', 'move_objects'")
    name: Optional[str] = Field(default=None, description="Collection name")
    parent: Optional[str] = Field(default=None, description="Parent collection (for create)")
    objects: Optional[List[str]] = Field(default=None, description="Object names (for move_objects)")
    target: Optional[str] = Field(default=None, description="Target collection (for move_objects)")


@mcp.tool(
    name="blender_manage_collection",
    annotations={"title": "Manage Collections", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
)
async def blender_manage_collection(params: CollectionInput) -> str:
    """Manage scene collections: 'list' (show hierarchy), 'create' (new collection), 'delete', 'move_objects' (move objects between collections)."""
    return format_result(send_command("manage_collection", params.model_dump(exclude_none=True)))


# ─── World / Environment ────────────────────────────────────────────────────

class WorldInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    color: Optional[List[float]] = Field(default=None, description="Background color [R, G, B] (0-1)")
    strength: Optional[float] = Field(default=None, ge=0.0, description="Background strength")
    hdri_path: Optional[str] = Field(default=None, description="Path to HDRI image for environment lighting")


@mcp.tool(
    name="blender_set_world",
    annotations={"title": "Set World/Environment", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
async def blender_set_world(params: WorldInput) -> str:
    """Configure the world/environment: set background color, strength, or load an HDRI for realistic environment lighting."""
    return format_result(send_command("set_world", params.model_dump(exclude_none=True)))


# ─── UV Mapping ──────────────────────────────────────────────────────────────

class UVInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    object_name: str = Field(..., description="Mesh object name")
    action: str = Field(default="smart_project", description="UV method: 'smart_project', 'unwrap', 'cube_project', 'cylinder_project', 'sphere_project', 'reset'")
    angle_limit: Optional[float] = Field(default=66, description="Angle limit for smart project (degrees)")
    island_margin: Optional[float] = Field(default=0.0, ge=0.0, description="Margin between UV islands")
    method: Optional[str] = Field(default="ANGLE_BASED", description="Unwrap method: 'ANGLE_BASED', 'CONFORMAL'")


@mcp.tool(
    name="blender_uv_operations",
    annotations={"title": "UV Operations", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
)
async def blender_uv_operations(params: UVInput) -> str:
    """UV mapping operations: 'smart_project' (automatic), 'unwrap' (standard), 'cube_project', 'cylinder_project', 'sphere_project', 'reset'. Works on the entire mesh."""
    return format_result(send_command("uv_operations", params.model_dump(exclude_none=True)))


# ─── Import / Export ─────────────────────────────────────────────────────────

@mcp.tool(
    name="blender_import_file",
    annotations={"title": "Import File", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
)
async def blender_import_file(filepath: str = Field(..., description="Path to file. Supported: .fbx, .obj, .glb, .gltf, .stl, .ply, .svg, .abc, .usd, .usdc, .usda")) -> str:
    """Import a 3D file into the scene. Supports FBX, OBJ, glTF/GLB, STL, PLY, SVG, Alembic, USD. Returns the names of newly imported objects."""
    return format_result(send_command("import_file", {"filepath": filepath}))


class ExportInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    filepath: str = Field(..., description="Output file path with extension (.fbx, .obj, .glb, .gltf, .stl, .ply, .abc, .usd)")
    selected_only: Optional[bool] = Field(default=False, description="Export only selected objects")


@mcp.tool(
    name="blender_export_file",
    annotations={"title": "Export File", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
)
async def blender_export_file(params: ExportInput) -> str:
    """Export the scene (or selected objects) to a file. Supports: FBX, OBJ, glTF/GLB, STL, PLY, Alembic, USD."""
    return format_result(send_command("export_file", params.model_dump()))


# ─── Armature / Rigging ─────────────────────────────────────────────────────

class ArmatureInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(default="create", description="Action: 'create' (new armature), 'add_bone', 'list_bones'")
    name: Optional[str] = Field(default=None, description="Armature name (for create)")
    armature_name: Optional[str] = Field(default=None, description="Armature name (for add_bone, list_bones)")
    bone_name: Optional[str] = Field(default=None, description="Bone name (for add_bone)")
    head: Optional[List[float]] = Field(default=None, description="Bone head position [x, y, z]")
    tail: Optional[List[float]] = Field(default=None, description="Bone tail position [x, y, z]")
    parent_bone: Optional[str] = Field(default=None, description="Parent bone name")
    connected: Optional[bool] = Field(default=False, description="Connect to parent bone")
    location: Optional[List[float]] = Field(default=None, description="Location for new armature")


@mcp.tool(
    name="blender_armature_operations",
    annotations={"title": "Armature/Rigging", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
)
async def blender_armature_operations(params: ArmatureInput) -> str:
    """Armature and bone operations for rigging: 'create' (new armature), 'add_bone' (with optional parent), 'list_bones' (show bone hierarchy)."""
    return format_result(send_command("armature_operations", params.model_dump(exclude_none=True)))


# ─── Constraints ─────────────────────────────────────────────────────────────

class ConstraintInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    object_name: str = Field(..., description="Object to add constraint to")
    action: str = Field(default="add", description="Action: 'add', 'remove', 'list'")
    constraint_type: Optional[str] = Field(default=None, description="Constraint type: COPY_LOCATION, COPY_ROTATION, COPY_SCALE, TRACK_TO, DAMPED_TRACK, LIMIT_LOCATION, FOLLOW_PATH, etc.")
    name: Optional[str] = Field(default=None, description="Constraint name")
    constraint_name: Optional[str] = Field(default=None, description="Constraint name (for remove)")
    target: Optional[str] = Field(default=None, description="Target object name")
    properties: Optional[Dict[str, Any]] = Field(default=None, description="Constraint properties")


@mcp.tool(
    name="blender_constraint_operations",
    annotations={"title": "Constraints", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
)
async def blender_constraint_operations(params: ConstraintInput) -> str:
    """Manage object constraints: 'add' (COPY_LOCATION, TRACK_TO, DAMPED_TRACK, etc.), 'remove', 'list'. Constraints drive automated object behavior."""
    return format_result(send_command("constraint_operations", params.model_dump(exclude_none=True)))


# ─── Particle Systems ───────────────────────────────────────────────────────

class ParticleInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    object_name: str = Field(..., description="Object to add particles to")
    action: str = Field(default="add", description="Action: 'add', 'remove'")
    particle_type: Optional[str] = Field(default="EMITTER", description="Type: 'EMITTER' or 'HAIR'")
    count: Optional[int] = Field(default=None, ge=1, description="Number of particles")
    lifetime: Optional[float] = Field(default=None, ge=1, description="Particle lifetime in frames")
    emit_from: Optional[str] = Field(default=None, description="Emission source: 'VERT', 'FACE', 'VOLUME'")
    render_type: Optional[str] = Field(default=None, description="Render type: 'HALO', 'LINE', 'PATH', 'OBJECT', 'COLLECTION'")


@mcp.tool(
    name="blender_particle_system",
    annotations={"title": "Particle System", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
)
async def blender_particle_system(params: ParticleInput) -> str:
    """Add or remove particle systems. Configure emitter/hair type, particle count, lifetime, emission source, and render type."""
    return format_result(send_command("particle_system", params.model_dump(exclude_none=True)))


# ─── Physics ─────────────────────────────────────────────────────────────────

class PhysicsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    object_name: str = Field(..., description="Object to apply physics to")
    physics_type: str = Field(..., description="Physics type: 'rigid_body', 'cloth', 'fluid', 'soft_body', 'collision'")
    rb_type: Optional[str] = Field(default="ACTIVE", description="Rigid body type: 'ACTIVE' or 'PASSIVE'")


@mcp.tool(
    name="blender_physics",
    annotations={"title": "Physics Simulation", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
)
async def blender_physics(params: PhysicsInput) -> str:
    """Add physics simulations: 'rigid_body' (with ACTIVE/PASSIVE type), 'cloth', 'fluid', 'soft_body', 'collision'."""
    return format_result(send_command("physics", params.model_dump(exclude_none=True)))


# ─── Text Objects ────────────────────────────────────────────────────────────

class TextInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(default="create", description="Action: 'create', 'edit'")
    text: Optional[str] = Field(default=None, description="Text content")
    name: Optional[str] = Field(default=None, description="Object name")
    location: Optional[List[float]] = Field(default=None, description="XYZ location")
    size: Optional[float] = Field(default=None, gt=0, description="Text size")
    extrude: Optional[float] = Field(default=None, ge=0, description="Extrusion depth for 3D text")
    bevel_depth: Optional[float] = Field(default=None, ge=0, description="Bevel depth for rounded edges")
    font_path: Optional[str] = Field(default=None, description="Path to .ttf or .otf font file")
    align_x: Optional[str] = Field(default=None, description="Horizontal alignment: 'LEFT', 'CENTER', 'RIGHT', 'JUSTIFY', 'FLUSH'")


@mcp.tool(
    name="blender_text_object",
    annotations={"title": "Text Object", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
)
async def blender_text_object(params: TextInput) -> str:
    """Create or edit 3D text objects. Set text content, size, extrusion depth, bevel for rounded edges, custom fonts, and alignment."""
    return format_result(send_command("text_object", params.model_dump(exclude_none=True)))


# ─── File Operations ─────────────────────────────────────────────────────────

class FileInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(..., description="Action: 'save', 'open', 'new'")
    filepath: Optional[str] = Field(default=None, description="File path for save/open (.blend)")
    use_empty: Optional[bool] = Field(default=False, description="Start with empty scene (for 'new')")


@mcp.tool(
    name="blender_save_file",
    annotations={"title": "File Operations", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
)
async def blender_save_file(params: FileInput) -> str:
    """Save, open, or create new Blender files. 'save' (save current or save-as with filepath), 'open' (open .blend file), 'new' (new empty scene)."""
    return format_result(send_command("save_file", params.model_dump(exclude_none=True)))


# ─── Compositor ──────────────────────────────────────────────────────────────

class CompositorInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(default="info", description="Action: 'info' (list nodes), 'add_node', 'connect'")
    node_type: Optional[str] = Field(default=None, description="Node type for add_node")
    name: Optional[str] = Field(default=None, description="Node name")
    from_node: Optional[str] = Field(default=None, description="Source node name")
    to_node: Optional[str] = Field(default=None, description="Dest node name")
    from_output: Optional[int] = Field(default=0)
    to_input: Optional[int] = Field(default=0)


@mcp.tool(
    name="blender_compositor",
    annotations={"title": "Compositor", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
)
async def blender_compositor(params: CompositorInput) -> str:
    """Compositor node operations for post-processing: 'info' (list current nodes), 'add_node' (add compositor nodes), 'connect' (link nodes together)."""
    return format_result(send_command("compositor", params.model_dump(exclude_none=True)))


# ─── Viewport ────────────────────────────────────────────────────────────────

class ViewportInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(..., description="Action: 'set_shading' (WIREFRAME/SOLID/MATERIAL/RENDERED), 'camera_view' (look through camera), 'frame_selected'")
    shading: Optional[str] = Field(default=None, description="Shading mode: WIREFRAME, SOLID, MATERIAL, RENDERED")


@mcp.tool(
    name="blender_viewport",
    annotations={"title": "Viewport Controls", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
async def blender_viewport(params: ViewportInput) -> str:
    """Control the 3D viewport: change shading mode (wireframe/solid/material/rendered), switch to camera view, frame selected objects."""
    return format_result(send_command("viewport", params.model_dump(exclude_none=True)))


# ─── Cleanup ─────────────────────────────────────────────────────────────────

class CleanupInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(default="purge_orphans", description="Action: 'purge_orphans', 'merge_by_distance', 'shade_smooth', 'shade_flat'")
    object_name: Optional[str] = Field(default=None, description="Object name (for mesh operations)")
    threshold: Optional[float] = Field(default=0.0001, description="Distance threshold for merge")


@mcp.tool(
    name="blender_cleanup",
    annotations={"title": "Cleanup Operations", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
async def blender_cleanup(params: CleanupInput) -> str:
    """Scene cleanup: 'purge_orphans' (remove unused data), 'merge_by_distance' (weld close vertices), 'shade_smooth', 'shade_flat'."""
    return format_result(send_command("cleanup", params.model_dump(exclude_none=True)))


# ─── v3.1 CADAM-style parametric workflow ────────────────────────────────────
# Generate (returns prompt+contract) → Run (validates + caches + executes) →
# Apply Params (re-runs only the PARAMETERS block — see blender_apply_params).
#
# The slider/tweak loop avoids round-tripping the LLM for every parameter change:
# the LLM is called ONCE to produce a script that follows the contract, and
# subsequent tweaks edit only the # --- PARAMETERS --- block.

_SCRIPT_CACHE: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
_SCRIPT_CACHE_MAX = 32


def _cache_script(script: str, parameters: Dict[str, Any]) -> str:
    """Insert (or refresh) a script in the LRU cache. Returns a 12-char script_id."""
    script_id = uuid.uuid4().hex[:12]
    _SCRIPT_CACHE[script_id] = {
        "script": script,
        "parameters": parameters,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    _SCRIPT_CACHE.move_to_end(script_id)
    while len(_SCRIPT_CACHE) > _SCRIPT_CACHE_MAX:
        _SCRIPT_CACHE.popitem(last=False)
    return script_id


def _get_cached(script_id: str) -> Optional[Dict[str, Any]]:
    """Return the cached entry (and mark as recently used) or None."""
    entry = _SCRIPT_CACHE.get(script_id)
    if entry is not None:
        _SCRIPT_CACHE.move_to_end(script_id)
    return entry


# ─── v3.1.1 needs_input — typed clarification payload (Issue #6) ─────────────
# Pattern from PatrykIti/blender-ai-mcp: when a tool can't proceed because of
# missing/unknown input, return a typed `needs_input` payload so the calling
# model can ask the user instead of guessing or regenerating an entire script.

_PARAM_KIND_BY_TYPE = {
    bool:  "boolean",
    int:   "number",
    float: "number",
    str:   "string",
    list:  "array",
    dict:  "object",
    type(None): "any",
}


def _kind_for_value(value: Any) -> str:
    """Map a Python value's type to a needs_input `kind` token."""
    return _PARAM_KIND_BY_TYPE.get(type(value), "any")


def needs_input_payload(
    field: str,
    *,
    kind: str,
    description: str,
    default: Any = None,
    choices: Optional[List[Any]] = None,
    available: Optional[Dict[str, Any]] = None,
    hint: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the standardized needs_input response.

    The shape is intentionally narrow so callers can rely on it across tools:
      {
        "status": "needs_input",
        "needs_input": {
          "field": <str>,
          "kind": "string|number|boolean|array|object|enum|any",
          "description": <human-friendly prompt>,
          "default": <value or null>,
          "choices": [...]            # only when kind == "enum"
          "available": {k: v, ...}    # only when listing existing options (e.g. param keys)
          "hint": <next-step hint>
        }
      }
    """
    payload: Dict[str, Any] = {
        "field": field,
        "kind": kind,
        "description": description,
    }
    if default is not None:
        payload["default"] = default
    if choices is not None:
        payload["choices"] = list(choices)
        if kind not in ("enum",):
            payload["kind"] = "enum"
    if available is not None:
        payload["available"] = dict(available)
    if hint is not None:
        payload["hint"] = hint
    return {"status": "needs_input", "needs_input": payload}


# ─── v3.1.1 run_cadam_script — sync helper for in-process CADAM execution ───
# Used by register_product_tools (Issue #10) to migrate raw `execute_python`
# call sites to the PARAMETERS-block contract without rebuilding their async
# tool plumbing. Mirrors what blender_run_bpy_script does internally:
#   1. Wrap an opaque `code` block in a PARAMETERS-block manifest of inputs
#   2. AST-validate (server-side defense in depth)
#   3. Cache by script_id (LRU, 32 entries — same as run_bpy_script)
#   4. Send to the addon
# Returns a dict (not a JSON envelope) so callers can compose with their own
# format_result wrappers.

_PARAMETERS_HEADER = "# --- PARAMETERS ---"
_PARAMETERS_FOOTER = "# --- /PARAMETERS ---"


_LITERAL_TYPES = (type(None), bool, int, float, str, list, tuple, dict)


def _is_literal_safe(value: Any) -> bool:
    """Recursively check that `value` is composed only of types ast.literal_eval
    can parse: None, bool, int, float, str, list, tuple, dict."""
    if isinstance(value, (type(None), bool, int, float, str)):
        return True
    if isinstance(value, (list, tuple)):
        return all(_is_literal_safe(v) for v in value)
    if isinstance(value, dict):
        return all(isinstance(k, str) and _is_literal_safe(v) for k, v in value.items())
    return False


def _build_parameters_block(parameters: Dict[str, Any]) -> str:
    """Render a Dict[str, literal] as a PARAMETERS block. Uses Python repr()
    so values round-trip through ast.literal_eval (json.dumps would emit
    null/true/false which Python literal_eval rejects)."""
    if not parameters:
        return f"{_PARAMETERS_HEADER}\n{_PARAMETERS_FOOTER}\n"
    lines = [_PARAMETERS_HEADER]
    for k, v in parameters.items():
        if not (isinstance(k, str) and k.isidentifier() and k.upper() == k):
            raise ValueError(
                f"Parameter name {k!r} must be UPPER_SNAKE_CASE identifier."
            )
        if not _is_literal_safe(v):
            raise ValueError(
                f"Parameter {k!r}=({type(v).__name__}) not literal-safe "
                f"(must be None/bool/int/float/str/list/dict; got {v!r})."
            )
        # repr() emits valid Python literals for all _LITERAL_TYPES, including
        # the critical None/True/False that json.dumps would mangle.
        lines.append(f"{k} = {v!r}")
    lines.append(_PARAMETERS_FOOTER)
    return "\n".join(lines) + "\n"


def run_cadam_script(
    code: str,
    parameters: Optional[Dict[str, Any]] = None,
    *,
    cache: bool = True,
    script_kind: Optional[str] = None,
) -> Dict[str, Any]:
    """Synchronously run an opaque bpy script through the CADAM contract.

    Why: the v3.1.0 ship moved the canonical execution path to
    blender_run_bpy_script (PARAMETERS block + AST gate + LRU cache). Older
    helpers in product_animation_tools.py (and anywhere else) historically
    called send_command("execute_python", ...) directly, bypassing all four
    benefits. This helper closes that gap with a one-line replacement.

    Args:
      code: The bpy Python source to run. Will be wrapped in a synthetic
            PARAMETERS block built from `parameters` (the caller's intent
            manifest).
      parameters: Inputs that drove `code` generation. Become the
                  PARAMETERS-block constants. Pass an empty dict for "no
                  tunable parameters" (still cached, still gated).
      cache: If True, store in the LRU cache and return a script_id.
      script_kind: Optional human-readable tag (e.g. "product_material") that
                   becomes part of the cached entry for diagnostic listing.

    Returns:
      {"script_id": str | None, "parameters": dict, "result": ..., "blocked_by_policy": bool?}
      On policy/parse failure, returns {"error": str, "blocked_by_policy": True}.
    """
    parameters = parameters or {}
    try:
        block = _build_parameters_block(parameters)
    except ValueError as e:
        return {"error": f"PARAMETERS block build failed: {e}", "blocked_by_policy": True}

    full_script = block + "\n" + code

    ok, reason = _validate_parameters_block(full_script)
    if not ok:
        return {
            "error": f"Wrapped script failed PARAMETERS validation: {reason}",
            "blocked_by_policy": True,
        }

    if _safety_check is not None:
        try:
            _safety_check(full_script, strict=True)
        except _CodeSafetyError as e:  # type: ignore[misc]
            return {
                "error": f"Script blocked by server safety policy: {getattr(e, 'reason', str(e))}",
                "blocked_by_policy": True,
            }

    script_id: Optional[str] = None
    if cache:
        script_id = _cache_script(full_script, parameters)
        # Tag the entry for diagnostic listing
        if script_kind and script_id and script_id in _SCRIPT_CACHE:
            _SCRIPT_CACHE[script_id]["script_kind"] = script_kind

    raw = send_command("execute_python", {"code": full_script})

    response: Dict[str, Any] = {
        "script_id": script_id,
        "parameters": parameters,
    }
    if isinstance(raw, dict):
        response.update(raw)
    else:
        response["result"] = raw
    return response


def _list_cached() -> List[Dict[str, Any]]:
    """Return a JSON-friendly summary of the cache for diagnostic tooling."""
    return [
        {
            "script_id": sid,
            "parameters": entry["parameters"],
            "created_at": entry["created_at"],
            "script_chars": len(entry["script"]),
        }
        for sid, entry in _SCRIPT_CACHE.items()
    ]


# ─── CADAM-style image extraction (two-pass workflow) ──────────────────────────

class ReferenceImageInput(BaseModel):
    """Input for blender_reference_image_to_scene tool (two-pass reference image extraction)."""
    action: str = Field(
        ...,
        description="Action: 'extraction_prompt' (get Claude instruction), 'submit_extraction' (validate JSON), 'build_seed_params' (map to Blender params)"
    )
    image_data: Optional[str] = Field(
        None,
        description="Base64-encoded image data (for submit_extraction action)"
    )
    extraction_json: Optional[str] = Field(
        None,
        description="JSON string from Claude (for submit_extraction action)"
    )
    cache_id: Optional[str] = Field(
        None,
        description="Cache ID returned by submit_extraction (for build_seed_params action)"
    )

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


_EXTRACTION_CACHE: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
_EXTRACTION_CACHE_MAX = 32


def _cache_extraction(extraction: Dict[str, Any]) -> str:
    """Insert extraction in the LRU cache. Returns a 12-char cache_id."""
    cache_id = uuid.uuid4().hex[:12]
    _EXTRACTION_CACHE[cache_id] = {
        "extraction": extraction,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    _EXTRACTION_CACHE.move_to_end(cache_id)
    while len(_EXTRACTION_CACHE) > _EXTRACTION_CACHE_MAX:
        _EXTRACTION_CACHE.popitem(last=False)
    return cache_id


def _get_extraction_cached(cache_id: str) -> Optional[Dict[str, Any]]:
    """Return the cached extraction (and mark as recently used) or None."""
    entry = _EXTRACTION_CACHE.get(cache_id)
    if entry is not None:
        _EXTRACTION_CACHE.move_to_end(cache_id)
    return entry



# ─── Execute Python (DEPRECATED — kept as alias, prefer generate+run) ─────────

@mcp.tool(
    name="blender_execute_python",
    annotations={"title": "Execute Python (deprecated)", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": False},
)
async def blender_execute_python(code: str = Field(..., description="Python code to execute in Blender. Has access to bpy, mathutils. Set __result__ to return data.")) -> str:
    """DEPRECATED in v3.1. Prefer blender_generate_bpy_script + blender_run_bpy_script
    so numeric literals are pinned to a # --- PARAMETERS --- block (CADAM-style
    slider loop). This tool delegates to blender_run_bpy_script with
    require_parameters_block=False for backward compatibility. Has access to bpy,
    Vector, Euler, Matrix, Color, math. Set __result__ to any JSON-serializable
    value to return data from the script."""
    return await blender_run_bpy_script(  # type: ignore[arg-type]
        script=code, cache=False, require_parameters_block=False
    )


# ─── v3.1 generate_bpy_script — publishes the contract, no execution ─────────

class GenerateBpyScriptInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent: str = Field(..., description="Natural-language description of what the script should produce.")
    reference_params: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional pre-existing parameter values (e.g. from reference_image_to_scene) to seed the PARAMETERS block.",
    )


@mcp.tool(
    name="blender_reference_image_to_scene",
    title="Reference Image to Scene (CADAM two-pass)",
    description="Two-pass reference image extraction: Pass 1 provides Claude with detailed extraction prompt for structured JSON. Pass 2 validates JSON and maps to Blender seed parameters.",
    destructiveHint=False,
)
async def blender_reference_image_to_scene(params: ReferenceImageInput) -> str:
    """
    Two-pass CADAM-style reference image extraction workflow.
    
    Actions:
    - extraction_prompt: Returns detailed instruction prompt for Claude to analyze reference images
    - submit_extraction: Validates extracted JSON, caches it, returns cache_id for use in Pass 2
    - build_seed_params: Retrieves cached extraction and maps fields to Blender generation parameters
    
    Two-pass pattern (image → JSON → parameters) improves reliability vs direct image → parameters.
    """
    
    if params.action == "extraction_prompt":
        # Pass 1: Return the detailed extraction prompt for Claude
        return IMAGE_EXTRACTION_PROMPT
    
    elif params.action == "submit_extraction":
        # Pass 2a: Validate the extracted JSON
        if not params.extraction_json:
            return format_result({"error": "extraction_json required for submit_extraction action"}, False)
        
        # Parse and validate
        try:
            if isinstance(params.extraction_json, str):
                extraction = json.loads(params.extraction_json)
            else:
                extraction = params.extraction_json
        except (json.JSONDecodeError, ValueError) as e:
            return format_result({
                "error": f"Invalid JSON: {str(e)}",
                "extraction_json": params.extraction_json[:100] if isinstance(params.extraction_json, str) else str(params.extraction_json)[:100]
            }, False)
        
        # Validate extraction schema
        is_valid, errors = validate_extraction(extraction)
        if not is_valid:
            return format_result({
                "error": "Extraction validation failed",
                "validation_errors": errors,
                "extraction": extraction
            }, False)
        
        # Cache and return cache_id
        cache_id = _cache_extraction(extraction)
        return format_result({
            "ok": True,
            "cache_id": cache_id,
            "cached_at": datetime.utcnow().isoformat() + "Z",
            "extraction_keys": list(extraction.keys()),
            "cache_size": len(_EXTRACTION_CACHE)
        })
    
    elif params.action == "build_seed_params":
        # Pass 2b: Build seed parameters from cached extraction
        if not params.cache_id:
            return format_result({"error": "cache_id required for build_seed_params action"}, False)
        
        # Retrieve cached extraction
        cached_entry = _get_extraction_cached(params.cache_id)
        if cached_entry is None:
            return format_result({
                "error": f"Extraction not found in cache: {params.cache_id}",
                "available_cache_ids": list(_EXTRACTION_CACHE.keys())
            }, False)
        
        extraction = cached_entry["extraction"]
        
        # Build seed parameters
        seed_params, warnings = build_seed_params(extraction)
        
        return format_result({
            "ok": True,
            "seed_parameters": seed_params,
            "warnings": warnings if warnings else [],
            "cache_id": params.cache_id,
            "created_at": cached_entry["created_at"],
            "parameter_count": len(seed_params),
            "next_step": "Use seed_parameters with blender_generate_bpy_script to create a parametrized Blender script"
        })
    
    else:
        return format_result({
            "error": f"Unknown action: {params.action}",
            "valid_actions": ["extraction_prompt", "submit_extraction", "build_seed_params"]
        }, False)



@mcp.tool(
    name="blender_generate_bpy_script",
    annotations={"title": "Generate bpy Script (contract publisher)", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
async def blender_generate_bpy_script(params: GenerateBpyScriptInput) -> str:
    """Publish the CADAM-style generation contract for the calling LLM.

    This tool DOES NOT call an LLM and DOES NOT produce a script. It returns the
    canonical system prompt + parameter template + (optionally) seed values.
    The calling agent is expected to author a script that follows the contract
    and then submit it via blender_run_bpy_script.

    Returns JSON:
    {
      "system_prompt": "<contract>",
      "parameters_template": "<boilerplate>",
      "intent": "<echoed user intent>",
      "seed_parameters": {...} | None,
      "next_call": "blender_run_bpy_script",
      "system_prompt_version": "<sha12>"
    }
    """
    try:
        from server.codegen_prompt import PROMPT_VERSION
    except Exception:
        try:
            from codegen_prompt import PROMPT_VERSION  # type: ignore
        except Exception:
            PROMPT_VERSION = "unknown"

    payload = {
        "system_prompt": BPY_GENERATION_SYSTEM_PROMPT,
        "parameters_template": PARAMETERS_BLOCK_TEMPLATE,
        "intent": params.intent,
        "seed_parameters": params.reference_params,
        "next_call": "blender_run_bpy_script",
        "system_prompt_version": PROMPT_VERSION,
    }
    return json.dumps(payload, indent=2)


# ─── v3.1 run_bpy_script — validates, caches, executes ───────────────────────

@mcp.tool(
    name="blender_run_bpy_script",
    annotations={"title": "Run bpy Script", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": False},
)
async def blender_run_bpy_script(
    script: str = Field(..., description="Complete bpy Python script. By default must start with a # --- PARAMETERS --- block (CADAM contract)."),
    cache: bool = Field(default=True, description="If True, cache the script keyed by script_id for later blender_apply_params calls."),
    require_parameters_block: bool = Field(default=True, description="If True (default), reject scripts without a valid PARAMETERS block. Set False to run legacy/ad-hoc snippets."),
) -> str:
    """Execute a bpy script inside the connected Blender instance. The script is
    AST-validated server-side BEFORE being sent to the addon (defense in depth
    on top of the addon's existing OPENCLAW_ALLOW_EXEC + AST gates).

    Returns JSON: {"script_id", "parameters", "result", "blocked_by_policy"?}.
    The addon enforces OPENCLAW_ALLOW_EXEC at bridge time; if disabled, that
    error is surfaced unchanged."""
    parameters: Dict[str, Any] = {}

    if require_parameters_block:
        ok, reason = _validate_parameters_block(script)
        if not ok:
            return format_result({
                "error": f"PARAMETERS block missing/invalid: {reason}",
                "blocked_by_policy": True,
                "hint": "Call blender_generate_bpy_script first to get the contract, "
                        "or pass require_parameters_block=False to bypass.",
            })
        try:
            parameters = _extract_parameters(script)
        except ValueError as e:
            return format_result({
                "error": f"PARAMETERS block parse error: {e}",
                "blocked_by_policy": True,
            })

    # Server-side AST gate (the addon also checks; this is defense in depth).
    if _safety_check is not None:
        try:
            _safety_check(script, strict=True)
        except _CodeSafetyError as e:  # type: ignore[misc]
            return format_result({
                "error": f"Script blocked by server safety policy: {getattr(e, 'reason', str(e))}",
                "blocked_by_policy": True,
            })

    script_id: Optional[str] = None
    if cache:
        script_id = _cache_script(script, parameters)

    raw = send_command("execute_python", {"code": script})

    # send_command returns either {"result": ...} or {"error": ...}
    response: Dict[str, Any] = {
        "script_id": script_id,
        "parameters": parameters,
    }
    if isinstance(raw, dict):
        response.update(raw)
    else:
        response["result"] = raw
    return format_result(response)


# ─── v3.1 apply_params — re-run only the PARAMETERS block of a cached script ─

class ApplyParamsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    script_id: str = Field(..., description="script_id returned by a prior blender_run_bpy_script call.")
    new_values: Dict[str, Any] = Field(..., description="Parameter overrides. Keys must be a subset of the cached script's parameter names.")
    rerun: bool = Field(default=True, description="If True, re-execute the script with the new parameters. If False, only return the rewritten script.")


@mcp.tool(
    name="blender_apply_params",
    annotations={"title": "Apply Params (CADAM slider loop)", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": False},
)
async def blender_apply_params(params: ApplyParamsInput) -> str:
    """CADAM-style slider re-run: rewrite the # --- PARAMETERS --- block of a
    previously-cached script with new values and (optionally) re-execute. The
    LLM is NOT called — only the parameter values change. Use this for fast
    tweaks (camera FOV, light energy, material roughness) without spending
    tokens on regeneration."""
    entry = _get_cached(params.script_id)
    if entry is None:
        return format_result({
            "error": f"Unknown script_id {params.script_id!r}. "
                     f"Cache holds {len(_SCRIPT_CACHE)} scripts (max {_SCRIPT_CACHE_MAX}).",
        })

    # ─── needs_input: unknown override key ─────────────────────────────────
    cached_params: Dict[str, Any] = entry.get("parameters", {}) or {}
    unknown = [k for k in params.new_values.keys() if k not in cached_params]
    if unknown:
        bad_key = unknown[0]
        return format_result(needs_input_payload(
            field=bad_key,
            kind="enum",
            description=(
                f"Override key {bad_key!r} is not in this script's PARAMETERS block. "
                f"Pick one of the available keys, or call blender_generate_bpy_script "
                f"to author a new script with that parameter."
            ),
            choices=list(cached_params.keys()),
            available=cached_params,
            hint="Re-call blender_apply_params with new_values keyed by an existing PARAMETERS name.",
        ))

    # ─── needs_input: empty override but the script has tunable params ─────
    if not params.new_values and cached_params:
        # Caller explicitly asked to "apply" with no overrides — usually a mistake.
        # Surface the available keys instead of silently re-running the same script.
        first = next(iter(cached_params.items()))
        return format_result(needs_input_payload(
            field=first[0],
            kind=_kind_for_value(first[1]),
            description=(
                "blender_apply_params was called with no overrides. "
                "Pass new_values to actually change something, or call blender_run_bpy_script "
                "with cache=True to just re-run the cached script."
            ),
            default=first[1],
            available=cached_params,
            hint="Pass new_values={'KEY': value} to override one or more PARAMETERS.",
        ))

    try:
        new_script = _replace_parameters(entry["script"], params.new_values)
        new_params = _extract_parameters(new_script)
    except ValueError as e:
        # Type/parse errors → needs_input (the rewritten block didn't validate)
        return format_result(needs_input_payload(
            field=str(e).split("'")[1] if "'" in str(e) else "(unknown)",
            kind="any",
            description=f"PARAMETERS block rewrite failed: {e}",
            available=cached_params,
            hint="Check that override values are literal Python (str/int/float/bool/list/dict/None).",
        ))

    # Update the cache entry in-place (same script_id, refreshed contents)
    _SCRIPT_CACHE[params.script_id] = {
        "script": new_script,
        "parameters": new_params,
        "created_at": entry["created_at"],
    }
    _SCRIPT_CACHE.move_to_end(params.script_id)

    if not params.rerun:
        return format_result({
            "script_id": params.script_id,
            "parameters": new_params,
            "rerun": False,
        })

    # Server-side safety still applies (parameters can't subvert it but we keep
    # the gate for symmetry with run_bpy_script).
    if _safety_check is not None:
        try:
            _safety_check(new_script, strict=True)
        except _CodeSafetyError as e:  # type: ignore[misc]
            return format_result({
                "error": f"Rewritten script blocked by server safety policy: {getattr(e, 'reason', str(e))}",
                "blocked_by_policy": True,
            })

    raw = send_command("execute_python", {"code": new_script})
    response: Dict[str, Any] = {
        "script_id": params.script_id,
        "parameters": new_params,
        "rerun": True,
    }
    if isinstance(raw, dict):
        response.update(raw)
    else:
        response["result"] = raw
    return format_result(response)


@mcp.tool(
    name="blender_list_cached_scripts",
    annotations={"title": "List Cached Scripts", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
async def blender_list_cached_scripts() -> str:
    """List script_ids currently held in the v3.1 LRU cache (max 32 entries).
    Useful for picking a target for blender_apply_params after a long session."""
    return format_result({
        "cached": _list_cached(),
        "max_size": _SCRIPT_CACHE_MAX,
    })


# ─── v3.1 list_available_assets — discover already-downloaded HDRIs/textures ──
# CADAM bundles BOSL with the WASM build; our equivalent is letting the LLM
# discover what Poly Haven / ambientCG / Sketchfab assets are ALREADY on disk
# so it references existing ids instead of re-downloading or hallucinating.

_KNOWN_PROVIDERS = ("polyhaven", "ambientcg", "sketchfab", "hyper3d", "hunyuan3d", "local")
_ASSET_LISTING_CACHE: Dict[str, Any] = {}

_HDRI_EXTS = {".hdr", ".exr"}
_TEX_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}
_MODEL_EXTS = {".glb", ".gltf", ".fbx", ".obj", ".usd", ".usdz", ".ply", ".stl"}
_BLEND_EXTS = {".blend"}

_RES_SUFFIXES = ("_8k", "_4k", "_2k", "_1k", "_512", "_256")
_PBR_CHANNELS = ("_diff", "_nor_gl", "_nor", "_rough", "_arm", "_disp", "_ao", "_metal", "_metallic", "_normal", "_albedo", "_basecolor")


def _classify_extension(ext: str) -> Optional[str]:
    e = ext.lower()
    if e in _HDRI_EXTS: return "hdri"
    if e in _TEX_EXTS:  return "texture"
    if e in _MODEL_EXTS: return "model"
    if e in _BLEND_EXTS: return "blend"
    return None


def _strip_resolution_and_channel(stem: str) -> str:
    """Group `kiara_1_dawn_2k` and `brown_mud_leaves_01_diff_2k` to a stable id."""
    s = stem
    for suffix in _RES_SUFFIXES:
        if s.lower().endswith(suffix):
            s = s[: -len(suffix)]
            break
    s_lower = s.lower()
    for ch in _PBR_CHANNELS:
        if s_lower.endswith(ch):
            s = s[: -len(ch)]
            break
    return s


def _resolve_asset_cache_roots() -> Dict[str, List[str]]:
    """Return {provider: [paths_that_exist]} based on env vars + standard locations."""
    candidates: Dict[str, List[str]] = {p: [] for p in _KNOWN_PROVIDERS}
    bases: List[str] = []
    for env in ("OPENCLAW_ASSET_CACHE", "BLENDER_MCP_ASSET_CACHE"):
        v = os.environ.get(env)
        if v:
            bases.append(os.path.expanduser(v))
    bases.append(os.path.expanduser("~/.openclaw/assets"))
    bases.append(os.path.expanduser("~/.cache/blender_mcp"))
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bases.append(os.path.join(repo_root, "assets"))
    bases.append(os.path.join(repo_root, "cache"))

    for base in bases:
        if not base or not os.path.isdir(base):
            continue
        for provider in _KNOWN_PROVIDERS:
            sub = os.path.join(base, provider)
            if os.path.isdir(sub) and sub not in candidates[provider]:
                candidates[provider].append(sub)
        # Also treat the base itself as the "local" pool if it contains files directly
        # (useful when OPENCLAW_ASSET_CACHE points straight at a flat folder).
        try:
            entries = os.listdir(base)
        except OSError:
            entries = []
        if any(os.path.isfile(os.path.join(base, e)) for e in entries):
            if base not in candidates["local"]:
                candidates["local"].append(base)
    return candidates


def _scan_provider_cache(
    provider: str,
    roots: List[str],
    asset_types: Optional[List[str]],
    limit: int,
) -> Dict[str, Any]:
    allowed = set(asset_types) if asset_types else {"hdri", "texture", "model", "blend"}
    grouped: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
    truncated = False
    for root in roots:
        for dirpath, _dirs, files in os.walk(root):
            for fname in files:
                stem, ext = os.path.splitext(fname)
                kind = _classify_extension(ext)
                if kind is None or kind not in allowed:
                    continue
                asset_id = _strip_resolution_and_channel(stem)
                full = os.path.join(dirpath, fname)
                try:
                    size = os.path.getsize(full)
                except OSError:
                    size = -1
                # Detect resolution token (1k/2k/4k/8k) for the file
                res = None
                for suffix in _RES_SUFFIXES:
                    if stem.lower().endswith(suffix):
                        res = suffix.lstrip("_")
                        break
                entry = grouped.setdefault(asset_id, {
                    "id": asset_id,
                    "type": kind,
                    "files": [],
                    "resolutions_available": [],
                    "size_bytes": 0,
                    "root": root,
                })
                entry["files"].append({"path": full, "name": fname, "size": size})
                if res and res not in entry["resolutions_available"]:
                    entry["resolutions_available"].append(res)
                if size > 0:
                    entry["size_bytes"] += size
                if len(grouped) >= limit:
                    truncated = True
                    break
            if truncated:
                break
        if truncated:
            break
    return {
        "name": provider,
        "cache_roots": roots,
        "assets": list(grouped.values()),
        "total_assets": len(grouped),
        "truncated": truncated,
    }


class ListAvailableAssetsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    providers: Optional[List[str]] = Field(
        default=None,
        description=f"Filter by provider names. Supported: {', '.join(_KNOWN_PROVIDERS)}. Default: all.",
    )
    asset_types: Optional[List[str]] = Field(
        default=None,
        description="Filter by type: hdri, texture, model, blend. Default: all.",
    )
    limit_per_provider: int = Field(default=50, ge=1, le=500)
    refresh: bool = Field(default=False, description="Re-scan disk instead of using memoized listing.")


@mcp.tool(
    name="blender_list_available_assets",
    annotations={"title": "List Available Assets", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
async def blender_list_available_assets(params: ListAvailableAssetsInput) -> str:
    """List ALREADY-DOWNLOADED Poly Haven / ambientCG / Sketchfab / Hyper3D /
    Hunyuan3D / local assets so the calling LLM references them by id rather
    than re-downloading or hallucinating new asset names.

    Returns JSON with one entry per provider — cache_roots, asset list (with
    resolutions_available), total_assets, truncated flag, plus global_hints.
    Use the returned ids in the PARAMETERS block (e.g. HDRI_ID = 'kiara_1_dawn')
    and pass them to blender_polyhaven action='download_hdri' if not already
    applied to the world."""
    providers = params.providers or list(_KNOWN_PROVIDERS)
    invalid = [p for p in providers if p not in _KNOWN_PROVIDERS]
    if invalid:
        return format_result({
            "error": f"Unknown provider(s): {invalid}. Supported: {list(_KNOWN_PROVIDERS)}",
        })

    cache_key = (
        ",".join(sorted(providers)),
        ",".join(sorted(params.asset_types)) if params.asset_types else "*",
        params.limit_per_provider,
    )
    if not params.refresh and cache_key in _ASSET_LISTING_CACHE:
        return format_result(_ASSET_LISTING_CACHE[cache_key])

    roots_by_provider = _resolve_asset_cache_roots()
    out_providers: List[Dict[str, Any]] = []
    for p in providers:
        roots = roots_by_provider.get(p, [])
        if not roots:
            out_providers.append({
                "name": p, "cache_roots": [], "assets": [],
                "total_assets": 0, "truncated": False,
            })
            continue
        out_providers.append(_scan_provider_cache(
            p, roots, params.asset_types, params.limit_per_provider,
        ))

    hints: List[str] = []
    empty = [p["name"] for p in out_providers if p["total_assets"] == 0]
    if empty:
        hints.append(
            f"No cached assets for: {', '.join(empty)}. "
            f"Use blender_polyhaven(action='search') / blender_sketchfab to download first."
        )
    if any(p["total_assets"] > 0 for p in out_providers):
        hints.append(
            "Reference asset ids as PARAMETERS-block constants "
            "(e.g. HDRI_ID = 'kiara_1_dawn') — never inline as magic strings."
        )

    payload = {
        "providers": out_providers,
        "global_hints": hints,
        "scanned_at": datetime.utcnow().isoformat() + "Z",
    }
    _ASSET_LISTING_CACHE[cache_key] = payload
    return format_result(payload)


# ─── Hyper3D Rodin AI Mesh Generation ────────────────────────────────────

class Hyper3DInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(..., description="Action: 'generate' (submit mesh generation), 'status' (check progress), 'import' (import generated mesh), 'generate_and_import' (combined workflow)")
    prompt: Optional[str] = Field(default=None, description="Text description for mesh generation (required for 'generate' and 'generate_and_import')")
    format: Optional[str] = Field(default="glb", description="Output format: 'glb' (default), 'fbx', 'obj'")
    quality: Optional[str] = Field(default="standard", description="Generation quality: 'draft' (fastest), 'standard' (default), 'high' (best quality)")
    task_id: Optional[str] = Field(default=None, description="Task ID from previous generation (for 'status' and 'import' actions)")
    filepath: Optional[str] = Field(default=None, description="Local file path for mesh import (alternative to task_id for 'import' action)")
    api_key: Optional[str] = Field(default=None, description="Hyper3D API key (falls back to HYPER3D_API_KEY environment variable)")


@mcp.tool(
    name="blender_hyper3d",
    annotations={"title": "Hyper3D Rodin AI Mesh Generation", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
)
async def blender_hyper3d(params: Hyper3DInput) -> str:
    """AI-powered 3D mesh generation using Hyper3D Rodin API. Submit a text prompt to generate photorealistic 3D models, check generation status, and import directly into Blender.

    Actions:
    - 'generate': Submit text prompt for mesh generation. Returns task_id to check status.
    - 'status': Check generation progress by task_id. Shows when ready to download.
    - 'import': Download and import generated mesh into current Blender scene.
    - 'generate_and_import': Combined workflow - generates, polls for completion, and imports (takes 2-5 minutes).

    Requires HYPER3D_API_KEY environment variable or pass api_key in params. Get API key from https://hyperhuman.deemos.com
    """
    return format_result(send_command("hyper3d", params.model_dump(exclude_none=True)), command="hyper3d")


class SketchfabInput(BaseModel):
    model_config = ConfigDict(extra="allow")
    action: str = Field(..., description="Action: 'search', 'model_info', 'download', 'import', 'download_and_import'")
    query: Optional[str] = Field(default=None, description="Search query for assets")
    model_uid: Optional[str] = Field(default=None, description="Sketchfab model UID")
    format: Optional[str] = Field(default="glb", description="Preferred format: glb, gltf, fbx, obj")
    kind: Optional[str] = Field(default="models", description="Search type, usually 'models'")
    downloadable: Optional[str] = Field(default="true", description="Filter downloadable assets (true/false)")
    count: Optional[int] = Field(default=10, ge=1, le=50, description="Search result count")
    api_token: Optional[str] = Field(default=None, description="Sketchfab API token (falls back to SKETCHFAB_API_TOKEN)")
    api_base: Optional[str] = Field(default=None, description="Optional Sketchfab API base URL override")


@mcp.tool(
    name="blender_sketchfab",
    annotations={"title": "Sketchfab Assets", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
)
async def blender_sketchfab(params: SketchfabInput) -> str:
    """Search, download, and import Sketchfab models for scene dressing and cinematic assembly workflows."""
    return format_result(send_command("sketchfab", params.model_dump(exclude_none=True)), command="sketchfab")


class Hunyuan3DInput(BaseModel):
    model_config = ConfigDict(extra="allow")
    action: str = Field(..., description="Action: 'generate', 'status', 'import', 'generate_and_import'")
    prompt: Optional[str] = Field(default=None, description="Text prompt for generation")
    image_url: Optional[str] = Field(default=None, description="Optional image URL for image-to-3D")
    mode: Optional[str] = Field(default="text_to_3d", description="Generation mode: text_to_3d or image_to_3d")
    format: Optional[str] = Field(default="glb", description="Output format: glb, fbx, obj")
    quality: Optional[str] = Field(default="standard", description="Quality tier")
    negative_prompt: Optional[str] = Field(default=None, description="Negative prompt")
    job_id: Optional[str] = Field(default=None, description="Job ID from generate/status")
    filepath: Optional[str] = Field(default=None, description="Local path to import")
    max_polls: Optional[int] = Field(default=90, ge=1, description="Max polling iterations for generate_and_import")
    poll_interval: Optional[float] = Field(default=4.0, ge=0.5, description="Polling interval in seconds")
    api_key: Optional[str] = Field(default=None, description="Hunyuan3D API key (falls back to HUNYUAN3D_API_KEY)")
    api_base: Optional[str] = Field(default=None, description="Optional Hunyuan3D API base URL override")


@mcp.tool(
    name="blender_hunyuan3d",
    annotations={"title": "Hunyuan3D Generation", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
)
async def blender_hunyuan3d(params: Hunyuan3DInput) -> str:
    """Generate 3D assets with Hunyuan3D and import directly into Blender via job-based workflow."""
    return format_result(send_command("hunyuan3d", params.model_dump(exclude_none=True)), command="hunyuan3d")


# ─── Mesh Editing ────────────────────────────────────────────────────────────

class MeshEditInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    object_name: str = Field(..., description="Mesh object name")
    action: str = Field(..., description="Edit action: 'extrude', 'inset', 'bevel', 'loop_cut', 'subdivide', 'bridge_edge_loops', 'fill', 'grid_fill', 'merge', 'dissolve_edges', 'dissolve_faces', 'dissolve_vertices', 'delete', 'separate', 'flip_normals', 'recalculate_normals', 'mark_seam', 'mark_sharp', 'poke_faces', 'triangulate', 'tris_to_quads', 'spin', 'solidify', 'wireframe', 'beautify_fill', 'smooth_vertices'")
    select_mode: Optional[str] = Field(default="all", description="Selection before action: 'all' (default), 'none'")
    value: Optional[float] = Field(default=None, description="Extrude distance")
    thickness: Optional[float] = Field(default=None, description="Inset thickness / wireframe thickness")
    depth: Optional[float] = Field(default=None, description="Inset depth")
    width: Optional[float] = Field(default=None, description="Bevel width")
    segments: Optional[int] = Field(default=None, ge=1, description="Bevel segments")
    cuts: Optional[int] = Field(default=None, ge=1, description="Loop cut / subdivide count")
    smoothness: Optional[float] = Field(default=None, ge=0, description="Subdivide smoothness")
    merge_type: Optional[str] = Field(default=None, description="Merge type: 'CENTER', 'CURSOR', 'COLLAPSE', 'FIRST', 'LAST'")
    delete_type: Optional[str] = Field(default=None, description="Delete type: 'VERT', 'EDGE', 'FACE', 'ONLY_FACE'")
    separate_type: Optional[str] = Field(default=None, description="Separate type: 'SELECTED', 'MATERIAL', 'LOOSE'")
    clear: Optional[bool] = Field(default=False, description="Clear seam/sharp (instead of mark)")
    inside: Optional[bool] = Field(default=False, description="Recalculate normals inside")
    angle: Optional[float] = Field(default=None, description="Spin angle in degrees")
    steps: Optional[int] = Field(default=None, description="Spin steps")
    repeat: Optional[int] = Field(default=None, description="Smooth repeat count")


@mcp.tool(
    name="blender_mesh_edit",
    annotations={"title": "Mesh Edit Operations", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
)
async def blender_mesh_edit(params: MeshEditInput) -> str:
    """Edit mode mesh operations. Actions: extrude, inset, bevel, loop_cut, subdivide, bridge_edge_loops, fill, grid_fill, merge, dissolve_edges/faces/vertices, delete, separate, flip_normals, recalculate_normals, mark_seam, mark_sharp, poke_faces, triangulate, tris_to_quads, spin, solidify, wireframe, smooth_vertices. These are the core modeling tools a Blender user works with daily."""
    return format_result(send_command("mesh_edit", params.model_dump(exclude_none=True)))


# ─── Sculpting ───────────────────────────────────────────────────────────────

class SculptInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    object_name: str = Field(..., description="Mesh object to sculpt")
    action: str = Field(default="enter", description="Action: 'enter' (start sculpting), 'set_brush', 'remesh' (voxel remesh), 'exit'")
    dyntopo: Optional[bool] = Field(default=False, description="Enable dynamic topology (for 'enter')")
    brush: Optional[str] = Field(default=None, description="Brush name: 'SculptDraw', 'Clay Strips', 'Smooth', 'Grab', 'Inflate', 'Crease', 'Pinch', 'Snake Hook', 'Flatten', 'Scrape'")
    radius: Optional[int] = Field(default=None, ge=1, description="Brush radius in pixels")
    strength: Optional[float] = Field(default=None, ge=0, le=1, description="Brush strength 0-1")
    auto_smooth: Optional[float] = Field(default=None, ge=0, le=1, description="Auto smooth factor")
    voxel_size: Optional[float] = Field(default=None, gt=0, description="Voxel size for remesh")


@mcp.tool(
    name="blender_sculpt",
    annotations={"title": "Sculpt Mode", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
)
async def blender_sculpt(params: SculptInput) -> str:
    """Enter sculpt mode, configure brushes, voxel remesh. Actions: 'enter' (with optional dyntopo), 'set_brush' (set brush type, radius, strength), 'remesh' (voxel remesh for clean topology), 'exit'. For organic modeling and detailing."""
    return format_result(send_command("sculpt", params.model_dump(exclude_none=True)))


# ─── Geometry Nodes ──────────────────────────────────────────────────────────

class GeometryNodesInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    object_name: str = Field(..., description="Object to add geometry nodes to")
    action: str = Field(default="add", description="Action: 'add' (new GN modifier), 'info' (list nodes), 'add_node', 'connect'")
    name: Optional[str] = Field(default=None, description="Modifier name")
    modifier_name: Optional[str] = Field(default=None, description="Existing modifier name (for info/add_node/connect)")
    node_type: Optional[str] = Field(default=None, description="Geometry node type (e.g. 'GeometryNodeMeshCube', 'GeometryNodeDistributePointsOnFaces', 'GeometryNodeInstanceOnPoints')")
    location: Optional[List[float]] = Field(default=None, description="Node position [x, y]")
    from_node: Optional[str] = Field(default=None, description="Source node name")
    to_node: Optional[str] = Field(default=None, description="Destination node name")
    from_output: Optional[int] = Field(default=0)
    to_input: Optional[int] = Field(default=0)


@mcp.tool(
    name="blender_geometry_nodes",
    annotations={"title": "Geometry Nodes", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
)
async def blender_geometry_nodes(params: GeometryNodesInput) -> str:
    """Procedural geometry with Geometry Nodes: 'add' (create GN modifier), 'info' (inspect node tree), 'add_node' (add nodes like MeshCube, DistributePointsOnFaces, InstanceOnPoints, SetPosition, etc.), 'connect' (link nodes). For procedural modeling, scattering, and parametric design."""
    return format_result(send_command("geometry_nodes", params.model_dump(exclude_none=True)))


# ─── Weight Painting ─────────────────────────────────────────────────────────

class WeightPaintInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    object_name: str = Field(..., description="Mesh object")
    action: str = Field(default="enter", description="Action: 'enter', 'exit', 'add_group', 'assign', 'auto_weights'")
    group_name: Optional[str] = Field(default=None, description="Vertex group name")
    weight: Optional[float] = Field(default=None, ge=0, le=1, description="Weight value 0-1")


@mcp.tool(
    name="blender_weight_paint",
    annotations={"title": "Weight Painting", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
)
async def blender_weight_paint(params: WeightPaintInput) -> str:
    """Weight painting for rigging: 'enter' (enter mode), 'exit', 'add_group' (vertex group), 'assign' (set weight for all verts), 'auto_weights' (automatic weights from armature parent)."""
    return format_result(send_command("weight_paint", params.model_dump(exclude_none=True)))


# ─── Shape Keys ──────────────────────────────────────────────────────────────

class ShapeKeyInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    object_name: str = Field(..., description="Mesh object")
    action: str = Field(default="list", description="Action: 'list', 'add_basis', 'add', 'set_value', 'keyframe'")
    name: Optional[str] = Field(default=None, description="Shape key name (for add)")
    key_name: Optional[str] = Field(default=None, description="Shape key name (for set_value/keyframe)")
    value: Optional[float] = Field(default=None, ge=0, le=1, description="Shape key value")
    frame: Optional[int] = Field(default=None, description="Frame for keyframing")


@mcp.tool(
    name="blender_shape_keys",
    annotations={"title": "Shape Keys / Morph Targets", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
)
async def blender_shape_keys(params: ShapeKeyInput) -> str:
    """Shape keys (morph targets / blend shapes): 'list' (show all), 'add_basis' (create basis key), 'add' (new shape key), 'set_value' (blend amount 0-1), 'keyframe' (animate shape key). For facial expressions, corrective shapes, and morph animations."""
    return format_result(send_command("shape_keys", params.model_dump(exclude_none=True)))


# ─── Curves ──────────────────────────────────────────────────────────────────

class CurveInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(default="create", description="Action: 'create', 'to_mesh'")
    curve_type: Optional[str] = Field(default="BEZIER", description="Curve type: 'BEZIER', 'NURBS', 'CIRCLE', 'NURBS_CIRCLE', 'PATH'")
    name: Optional[str] = Field(default=None, description="Object name")
    location: Optional[List[float]] = Field(default=None, description="XYZ location")
    bevel_depth: Optional[float] = Field(default=None, ge=0, description="Bevel depth (makes tube)")
    extrude: Optional[float] = Field(default=None, ge=0, description="Extrusion amount")
    resolution: Optional[int] = Field(default=None, ge=1, description="Curve resolution")
    fill_mode: Optional[str] = Field(default=None, description="Fill mode: 'FULL', 'HALF', 'FRONT', 'BACK', 'NONE'")
    object_name: Optional[str] = Field(default=None, description="Object name (for to_mesh)")


@mcp.tool(
    name="blender_curve_operations",
    annotations={"title": "Curve Operations", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
)
async def blender_curve_operations(params: CurveInput) -> str:
    """Curve operations: 'create' (Bezier, NURBS, Circle, Path with optional bevel/extrude for tubes), 'to_mesh' (convert curve to mesh). Curves are great for pipes, cables, paths, and profile-based modeling."""
    return format_result(send_command("curve_operations", params.model_dump(exclude_none=True)))


# ─── Image Operations ────────────────────────────────────────────────────────

class ImageInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    action: str = Field(default="list", description="Action: 'list', 'load', 'create', 'save'")
    filepath: Optional[str] = Field(default=None, description="Image file path")
    name: Optional[str] = Field(default=None, description="Image name")
    width: Optional[int] = Field(default=None, ge=1, description="Image width")
    height: Optional[int] = Field(default=None, ge=1, description="Image height")


@mcp.tool(
    name="blender_image_operations",
    annotations={"title": "Image Operations", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
)
async def blender_image_operations(params: ImageInput) -> str:
    """Image/texture management: 'list' (all loaded images), 'load' (import image file), 'create' (new blank image), 'save' (save image to disk). For texture work, baking, and painting."""
    return format_result(send_command("image_operations", params.model_dump(exclude_none=True)))


# ═══════════════════════════════════════════════════════════════════════════════
# VFX-GRADE TOOLS (v2.0)
# ═══════════════════════════════════════════════════════════════════════════════


class FluidSimInput(BaseModel):
    model_config = ConfigDict(extra="allow")
    action: str = Field("create_domain", description="Action: 'create_domain' (gas/liquid domain), 'add_flow' (emitter), 'add_effector' (obstacle), 'bake'")
    domain_type: Optional[str] = Field(None, description="Domain type: 'GAS' (smoke/fire) or 'LIQUID'")
    name: Optional[str] = None
    object_name: Optional[str] = Field(None, description="Object to use as flow source or effector")
    flow_type: Optional[str] = Field(None, description="Flow type: 'SMOKE', 'FIRE', 'BOTH', 'LIQUID'")
    resolution: Optional[int] = Field(None, description="Domain resolution (32-256)")
    fire: Optional[bool] = Field(None, description="Enable fire in gas domain")
    size: Optional[float] = None
    location: Optional[List[float]] = None


@mcp.tool(
    name="blender_fluid_simulation",
    annotations={"title": "Fluid Simulation", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
)
async def blender_fluid_simulation(params: FluidSimInput) -> str:
    """VFX-grade fluid/smoke/fire simulation. Create domains ('GAS' for smoke/fire, 'LIQUID' for water), add flow emitters, configure effectors, and bake simulations."""
    return format_result(send_command("fluid_simulation", params.model_dump(exclude_none=True)))


class ForceFieldInput(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: str = Field("FORCE", description="Field type: FORCE, WIND, VORTEX, MAGNETIC, TURBULENCE, DRAG, HARMONIC")
    strength: Optional[float] = Field(5.0, description="Field strength")
    location: Optional[List[float]] = None
    name: Optional[str] = None
    noise: Optional[float] = None
    size: Optional[float] = None
    falloff: Optional[str] = None
    falloff_power: Optional[float] = None


@mcp.tool(
    name="blender_force_field",
    annotations={"title": "Force Field", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
)
async def blender_force_field(params: ForceFieldInput) -> str:
    """Create physics force fields: wind, vortex, turbulence, magnetic, drag, etc. Essential for particle and fluid simulations."""
    return format_result(send_command("force_field", params.model_dump(exclude_none=True)))


class ProceduralMaterialInput(BaseModel):
    model_config = ConfigDict(extra="allow")
    preset: str = Field("marble", description="Material preset: marble, wood, metal, glass, emissive, concrete, fabric, volume_fog, volume_fire")
    object_name: Optional[str] = Field(None, description="Object to apply material to")
    name: Optional[str] = None
    scale: Optional[float] = None
    roughness: Optional[float] = None
    color: Optional[List[float]] = None
    color1: Optional[List[float]] = None
    color2: Optional[List[float]] = None
    ior: Optional[float] = None
    density: Optional[float] = None
    emission_strength: Optional[float] = None
    emission_color: Optional[List[float]] = None


@mcp.tool(
    name="blender_procedural_material",
    annotations={"title": "Procedural Material", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
)
async def blender_procedural_material(params: ProceduralMaterialInput) -> str:
    """Create VFX-grade procedural materials from presets: marble, wood, metal, glass, emissive, concrete, fabric, volume_fog, volume_fire. Full shader node trees built automatically."""
    return format_result(send_command("procedural_material", params.model_dump(exclude_none=True)))


class ViewportCaptureInput(BaseModel):
    model_config = ConfigDict(extra="allow")
    width: Optional[int] = Field(800, description="Capture width in pixels")
    height: Optional[int] = Field(600, description="Capture height in pixels")
    filepath: Optional[str] = Field(None, description="Save path (auto-generated if omitted)")
    base64: Optional[bool] = Field(False, description="Return image as base64 string")


@mcp.tool(
    name="blender_viewport_capture",
    annotations={"title": "Viewport Capture", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
)
async def blender_viewport_capture(params: ViewportCaptureInput) -> str:
    """Capture current viewport as PNG image. Use for visual verification of scene state. Supports base64 encoding for VLM analysis."""
    return format_result(send_command("viewport_capture", params.model_dump(exclude_none=True)))


class BatchInput(BaseModel):
    model_config = ConfigDict(extra="allow")
    action: str = Field("create", description="Action: 'create' (batch create objects), 'transform' (batch move/rotate/scale), 'delete' (batch delete), 'randomize' (random variation)")
    objects: Optional[List[Any]] = Field(None, description="For create: list of {type, location, scale, name}. For randomize: list of object names")
    transforms: Optional[List[Any]] = Field(None, description="For transform: list of {object_name, location, rotation, scale}")
    names: Optional[List[str]] = Field(None, description="For delete: list of names")
    seed: Optional[int] = None
    location_range: Optional[List[float]] = None
    rotation_range: Optional[List[float]] = None
    scale_range: Optional[List[float]] = None


@mcp.tool(
    name="blender_batch_operations",
    annotations={"title": "Batch Operations", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
)
async def blender_batch_operations(params: BatchInput) -> str:
    """Batch operations for efficiency: create multiple objects at once, apply transforms to many objects, bulk delete, or randomize transforms with seed control."""
    return format_result(send_command("batch_operations", params.model_dump(exclude_none=True)))


class SceneTemplateInput(BaseModel):
    model_config = ConfigDict(extra="allow")
    template: str = Field("product_viz", description="Template: 'product_viz' (3-point lighting, studio), 'cinematic' (dramatic spot, DOF), 'architecture' (sun, wide camera), 'motion_graphics' (clean bg, even light)")
    bg_color: Optional[List[float]] = None


@mcp.tool(
    name="blender_scene_template",
    annotations={"title": "Scene Template", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True},
)
async def blender_scene_template(params: SceneTemplateInput) -> str:
    """Setup complete VFX scene templates with lighting, camera, and render settings. CLEARS existing scene. Templates: product_viz, cinematic, architecture, motion_graphics."""
    return format_result(send_command("scene_template", params.model_dump(exclude_none=True)))


class AdvancedAnimInput(BaseModel):
    model_config = ConfigDict(extra="allow")
    action: str = Field("turntable", description="Action: 'turntable' (orbit camera), 'follow_path' (animate along curve), 'bounce' (physics-like bounce), 'keyframe_sequence' (multi-keyframe)")
    target: Optional[str] = None
    object_name: Optional[str] = None
    frames: Optional[int] = Field(None, description="Total animation frames")
    radius: Optional[float] = None
    height: Optional[float] = None
    points: Optional[List[List[float]]] = None
    bounces: Optional[int] = None
    keyframes: Optional[List[Any]] = Field(None, description="For keyframe_sequence: list of {frame, location, rotation, scale}")


@mcp.tool(
    name="blender_advanced_animation",
    annotations={"title": "Advanced Animation", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
)
async def blender_advanced_animation(params: AdvancedAnimInput) -> str:
    """Advanced animation: turntable orbits, follow-path curves, physics-style bouncing, and multi-keyframe sequences. Production-ready camera and object animation."""
    return format_result(send_command("advanced_animation", params.model_dump(exclude_none=True)))


class RenderPresetInput(BaseModel):
    model_config = ConfigDict(extra="allow")
    preset: str = Field("high_quality", description="Preset: 'preview' (fast EEVEE), 'high_quality' (Cycles 256 spp), 'vfx_production' (Cycles EXR multi-pass), 'animation' (H264 video)")
    width: Optional[int] = None
    height: Optional[int] = None
    samples: Optional[int] = None
    fps: Optional[int] = None
    motion_blur: Optional[bool] = None
    transparent_bg: Optional[bool] = None


@mcp.tool(
    name="blender_render_presets",
    annotations={"title": "Render Presets", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
)
async def blender_render_presets(params: RenderPresetInput) -> str:
    """Configure render engine with VFX presets: preview (fast), high_quality (Cycles), vfx_production (EXR multi-pass + motion blur), animation (H264 video output)."""
    return format_result(send_command("render_presets", params.model_dump(exclude_none=True)))


class ClothSimInput(BaseModel):
    model_config = ConfigDict(extra="allow")
    object_name: str = Field(..., description="Object to apply cloth simulation to")
    action: str = Field("add", description="Action: 'add' (create cloth sim), 'pin' (assign pin vertex group)")
    fabric: Optional[str] = Field("cotton", description="Fabric preset: cotton, silk, leather, rubber")
    collision_quality: Optional[int] = None
    vertex_group: Optional[str] = None


@mcp.tool(
    name="blender_cloth_simulation",
    annotations={"title": "Cloth Simulation", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
)
async def blender_cloth_simulation(params: ClothSimInput) -> str:
    """Setup cloth simulation with fabric presets: cotton, silk, leather, rubber. Includes collision detection and vertex group pinning."""
    return format_result(send_command("cloth_simulation", params.model_dump(exclude_none=True)))


@mcp.tool(
    name="blender_scene_analyze",
    annotations={"title": "Scene Analysis", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
)
async def blender_scene_analyze() -> str:
    """Deep scene analysis for VLM verification: spatial layout, object relationships, vertex/face counts, materials, lights, cameras, render settings. Returns structured JSON."""
    return format_result(send_command("scene_analyze", {}))


class RenderQualityAuditInput(BaseModel):
    model_config = ConfigDict(extra="allow")
    profile: Optional[str] = Field(default="cinema", description="Audit profile: cinema, preview, animation")
    strict: Optional[bool] = Field(default=False, description="Treat threshold misses as failures instead of warnings")
    min_samples: Optional[int] = Field(default=None, ge=1, description="Override minimum sample count")
    require_exr: Optional[bool] = Field(default=None, description="Require OPEN_EXR output format")
    require_motion_blur: Optional[bool] = Field(default=None, description="Require motion blur enabled")
    require_dof: Optional[bool] = Field(default=None, description="Require active camera depth-of-field")
    require_compositor: Optional[bool] = Field(default=None, description="Require compositor nodes/compositing enabled")


@mcp.tool(
    name="blender_render_quality_audit",
    annotations={"title": "Render Quality Audit", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
async def blender_render_quality_audit(params: RenderQualityAuditInput) -> str:
    """Audit scene render settings for cinema-quality readiness: samples, denoising, color management, output depth/format, motion blur, DOF, and compositor pass coverage."""
    return format_result(send_command("render_quality_audit", params.model_dump(exclude_none=True)))


# ─── v2.1: PolyHaven Asset Integration ─────────────────────────────────────────

class PolyHavenInput(BaseModel):
    action: str = Field(description="Action: search, categories, download_hdri, download_texture, apply_texture")
    asset_type: Optional[str] = Field(default="all", description="Asset type: hdris, textures, models, all")
    asset_id: Optional[str] = Field(default=None, description="PolyHaven asset ID (e.g. 'brown_mud_leaves_01')")
    resolution: Optional[str] = Field(default="1k", description="Download resolution: 1k, 2k, 4k, 8k")
    object_name: Optional[str] = Field(default=None, description="Target object for apply_texture")
    material_name: Optional[str] = Field(default=None, description="Name for the created material")
    texture_files: Optional[dict] = Field(default=None, description="Map of texture files from download_texture (diff, nor_gl, rough, disp)")
    categories: Optional[str] = Field(default=None, description="Category filter for search")
    strength: Optional[float] = Field(default=1.0, description="HDRI strength for download_hdri")


@mcp.tool(
    name="blender_polyhaven",
    annotations={"title": "PolyHaven Assets", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
)
async def blender_polyhaven(input: PolyHavenInput) -> str:
    """Search and download free HDRIs, PBR textures, and 3D models from PolyHaven.
    Workflow: search → download_hdri/download_texture → apply_texture.
    download_hdri auto-applies as world environment. download_texture returns file paths to use with apply_texture."""
    return format_result(send_command("polyhaven", input.model_dump(exclude_none=True)))


# ─── v2.1: Scene Lighting Presets ───────────────────────────────────────────────

class SceneLightingInput(BaseModel):
    preset: str = Field(description="Lighting preset: studio, outdoor, sunset, dramatic, night, three_point")
    strength: Optional[float] = Field(default=1.0, description="World/environment light strength")
    clear_existing: Optional[bool] = Field(default=True, description="Remove existing lights before applying preset")
    sun_energy: Optional[float] = Field(default=None, description="Sun light energy (outdoor/sunset)")
    sun_elevation: Optional[float] = Field(default=None, description="Sun elevation in degrees (outdoor)")
    key_energy: Optional[float] = Field(default=None, description="Key light energy (three_point)")
    fill_energy: Optional[float] = Field(default=None, description="Fill light energy (three_point)")
    rim_energy: Optional[float] = Field(default=None, description="Rim/back light energy (three_point)")


@mcp.tool(
    name="blender_scene_lighting",
    annotations={"title": "Scene Lighting", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
async def blender_scene_lighting(input: SceneLightingInput) -> str:
    """Apply professional lighting presets to the scene. Includes studio (3-light neutral),
    outdoor (sun + Nishita sky), sunset (warm sun + low sky), dramatic (spot + rim),
    night (moonlight + ambient), and three_point (classic 3-point setup). Each preset
    sets up both lights and world environment."""
    return format_result(send_command("scene_lighting", input.model_dump(exclude_none=True)))


# ─── v2.2: Forensic/Litigation Scene Reconstruction ────────────────────────────

class ForensicSceneInput(BaseModel):
    action: str = Field(description="Action: build_road, place_vehicle, place_figure, add_annotation, setup_cameras, set_time_of_day, animate_vehicle, add_impact_marker, ghost_scenario, build_full_scene")
    # build_road params
    road_type: Optional[str] = Field(default=None, description="Road type: straight, intersection")
    lanes: Optional[int] = Field(default=None, description="Number of lanes (default 2)")
    length: Optional[float] = Field(default=None, description="Road length in meters")
    # place_vehicle params
    name: Optional[str] = Field(default=None, description="Object name")
    vehicle_type: Optional[str] = Field(default=None, description="Vehicle: sedan, suv, truck, pickup, van, motorcycle, bicycle, bus, semi")
    location: Optional[list] = Field(default=None, description="[x, y, z] position in meters")
    rotation: Optional[float] = Field(default=None, description="Rotation in degrees (Z axis)")
    color: Optional[list] = Field(default=None, description="[R, G, B, A] color (0-1 range)")
    label: Optional[str] = Field(default=None, description="Text label above object")
    damaged: Optional[bool] = Field(default=None, description="Show damage indicator on vehicle")
    impact_side: Optional[str] = Field(default=None, description="Damage side: front, rear, left, right")
    # annotation params
    annotation_type: Optional[str] = Field(default=None, description="Annotation: label, speed, distance, arrow")
    text: Optional[str] = Field(default=None, description="Annotation text content")
    size: Optional[float] = Field(default=None, description="Text size")
    start: Optional[list] = Field(default=None, description="Arrow start [x,y,z]")
    end: Optional[list] = Field(default=None, description="Arrow end [x,y,z]")
    # camera params
    camera_type: Optional[str] = Field(default=None, description="Camera: bird_eye, driver_pov, witness, orbit, all")
    target: Optional[list] = Field(default=None, description="Camera target point [x,y,z]")
    driver_vehicle: Optional[str] = Field(default=None, description="Vehicle name for driver POV camera")
    # animate params
    vehicle_name: Optional[str] = Field(default=None, description="Vehicle to animate")
    waypoints: Optional[list] = Field(default=None, description="List of {frame, location, rotation, speed_label}")
    # marker params
    marker_type: Optional[str] = Field(default=None, description="Marker: impact_point, skid_mark, debris")
    # ghost params
    source_vehicle: Optional[str] = Field(default=None, description="Source vehicle for ghost copy")
    ghost_alpha: Optional[float] = Field(default=None, description="Ghost transparency (0-1)")
    # time of day
    time: Optional[str] = Field(default=None, description="Time: day, night, dusk, dawn, overcast")
    strength: Optional[float] = Field(default=None, description="Light strength")
    # build_full_scene params
    road: Optional[dict] = Field(default=None, description="Road config for build_full_scene")
    vehicles: Optional[list] = Field(default=None, description="Vehicle list for build_full_scene")
    figures: Optional[list] = Field(default=None, description="Figure list for build_full_scene")
    annotations: Optional[list] = Field(default=None, description="Annotation list for build_full_scene")
    markers: Optional[list] = Field(default=None, description="Marker list for build_full_scene")
    cameras: Optional[str] = Field(default=None, description="Camera setup type for build_full_scene")
    time_of_day: Optional[str] = Field(default=None, description="Time of day for build_full_scene")
    frame_end: Optional[int] = Field(default=None, description="Last animation frame")


@mcp.tool(
    name="blender_forensic_scene",
    annotations={"title": "Forensic Scene Reconstruction", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
)
async def blender_forensic_scene(input: ForensicSceneInput) -> str:
    """Build courtroom-ready forensic/litigation scene reconstructions for legal cases.

    Creates complete accident/incident scenes with: roads & intersections with lane markings,
    vehicles (sedan/SUV/truck/motorcycle/etc) with damage indicators, human figures with labels,
    annotations (speed indicators, distance markers, trajectory arrows), multiple camera angles
    (bird's eye, driver POV, witness perspective, orbit), time-of-day lighting, skid marks,
    debris fields, impact point markers, and semi-transparent "ghost" what-if scenario overlays.

    Use build_full_scene to construct an entire scene from a structured description in one call,
    or use individual actions (build_road, place_vehicle, etc.) for step-by-step construction.

    Typical workflow: build_road → place_vehicle(s) → add_annotation(s) → add_impact_marker(s) →
    setup_cameras → set_time_of_day → animate_vehicle(s) → ghost_scenario (optional)"""
    return format_result(send_command("forensic_scene", input.model_dump(exclude_none=True)))


# ═══════════════════════════════════════════════════════════════════════════════
# PRODUCT ANIMATION TOOLS (auto-registered if product_animation_tools.py exists)
# ═══════════════════════════════════════════════════════════════════════════════

if _HAS_PRODUCT_TOOLS:
    # v3.1.1 (Issue #10): pass run_cadam_script so the 11 raw execute_python
    # call sites in product_animation_tools can opt into the PARAMETERS-block
    # contract. Falls back to the old send_command path if the legacy
    # signature (3-arg) is still in use.
    try:
        _product_tool_names = register_product_tools(
            mcp, send_command, format_result, run_cadam_script,
        )
    except TypeError:
        _product_tool_names = register_product_tools(mcp, send_command, format_result)
    print(f"[OpenClaw] Registered {len(_product_tool_names)} product animation tools: {', '.join(_product_tool_names)}")
else:
    print("[OpenClaw] Product animation tools not found — skipping (place product_animation_tools.py in server/)")


# ═══════════════════════════════════════════════════════════════════════════════
# v3.0.0 — Phase 3 (agent loop), Phase 5 (spatial / extended), Phase 2 (drift)
# Each _try_register call is best-effort so the server still boots if a module
# is missing or fails to import. See docs/CHANGELOG.md.
# ═══════════════════════════════════════════════════════════════════════════════

def _try_register(module_name, registrar_name, *args, **kwargs):
    """Best-effort registration — server still boots if a module is missing."""
    try:
        import importlib
        mod = importlib.import_module(module_name)
        registrar = getattr(mod, registrar_name)
        names = registrar(mcp, send_command, format_result, *args, **kwargs)
        print(f"[OpenClaw] Registered {len(names)} {module_name} tools: {', '.join(names)}")
        return names
    except Exception as e:
        print(f"[OpenClaw] {module_name}.{registrar_name} skipped: {e}")
        return []

# Phase 3 — agent loop (router, plan, act, critique, verify, session_status)
_AGENT_LOOP_TOOLS = (_try_register("server.agent_loop", "register_agent_loop_tools")
                     or _try_register("agent_loop", "register_agent_loop_tools"))

# Phase 5 — spatial reasoning (raycast, bbox, collision, placement, semantic_place, dimensions, floor_plan)
_SPATIAL_TOOLS = (_try_register("server.spatial_tools", "register_spatial_tools")
                  or _try_register("spatial_tools", "register_spatial_tools"))

# Phase 5 — extended tools (camera, UV, bake, LOD, VR, splat, GP, snapshot) + Phase 2 drift
_EXTENDED_TOOLS = (_try_register("server.extended_tools", "register_extended_tools")
                   or _try_register("extended_tools", "register_extended_tools"))

print(f"[OpenClaw] v3.0.0 tool registration complete. "
      f"agent_loop={len(_AGENT_LOOP_TOOLS)}, spatial={len(_SPATIAL_TOOLS)}, extended={len(_EXTENDED_TOOLS)}")


# ═══════════════════════════════════════════════════════════════════════════════
# MULTI-INSTANCE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool(
    name="blender_instances",
    annotations={"title": "Blender Instance Manager", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
async def blender_instances(action: str = "list", port: Optional[int] = None, port_start: int = 9876, port_end: int = 9886) -> str:
    """Manage multiple Blender instances for concurrent agent work.

    Each agent can connect to a different Blender instance (different port, different .blend file)
    so they don't interfere with each other.

    Actions:
      list      — Discover all running Blender Bridge instances (scans port range)
      ping      — Ping a specific instance by port number
      connect   — Set this MCP server's target port (for all subsequent commands)

    Environment: Set OPENCLAW_PORT before launching Blender to assign its port.
    Example: OPENCLAW_PORT=9877 /Applications/Blender.app/Contents/MacOS/Blender

    Port convention:
      9876 = default (agent 1)
      9877 = agent 2
      9878 = agent 3
      ...up to 9885 (10 concurrent instances max)
    """
    global BLENDER_PORT

    if action == "list":
        instances = discover_instances((port_start, port_end))
        if not instances:
            return f"No Blender instances found on ports {port_start}-{port_end-1}. Start Blender with the OpenClaw addon enabled."
        lines = [f"Found {len(instances)} Blender instance(s):\n"]
        for iid, info in instances.items():
            lines.append(f"  {iid} — port {info['port']}, file: {info['file']}, objects: {info['objects']}, scene: {info['scene']}")
        return "\n".join(lines)

    elif action == "ping":
        if port is None:
            return "Error: 'port' parameter required for ping action"
        result = send_command_to(port, "ping")
        if "error" in result:
            return f"Instance on port {port}: {result['error']}"
        r = result.get("result", result)
        return f"Instance '{r.get('instance_id', 'unknown')}' on port {port}: OK — Blender {r.get('blender_version')}, file: {r.get('file')}, {r.get('objects')} objects"

    elif action == "connect":
        if port is None:
            return "Error: 'port' parameter required for connect action"
        # Verify the instance is reachable before switching
        result = send_command_to(port, "ping")
        if "error" in result:
            return f"Cannot connect to port {port}: {result['error']}"
        BLENDER_PORT = port
        r = result.get("result", result)
        return f"Switched to instance '{r.get('instance_id', 'unknown')}' on port {port}. All subsequent commands will target this instance."

    else:
        return f"Unknown action '{action}'. Use: list, ping, connect"


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print(f"[OpenClaw MCP] Targeting Blender on {BLENDER_HOST}:{BLENDER_PORT}")
    mcp.run()
