#!/usr/bin/env python3
"""
OpenClaw Blender MCP - QA Test Runner
======================================
Comprehensive test suite that validates every MCP tool against a live Blender instance.
Requires: Blender running with the OpenClaw Bridge addon active on port 9876.

Usage:
    python3 qa_runner.py              # Run all tests
    python3 qa_runner.py --quick      # Quick smoke test (core tools only)
    python3 qa_runner.py --verbose    # Verbose output with full responses
"""

import json
import socket
import sys
import time
import traceback

HOST = "127.0.0.1"
PORT = 9876
TIMEOUT = 30.0
VERBOSE = "--verbose" in sys.argv or "-v" in sys.argv
QUICK = "--quick" in sys.argv

# ─── Test Infrastructure ─────────────────────────────────────────────────────

_id = 0
_passed = 0
_failed = 0
_skipped = 0
_errors = []


def send(command, params=None):
    global _id
    _id += 1
    payload = {"id": str(_id), "command": command, "params": params or {}}
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(TIMEOUT)
    sock.connect((HOST, PORT))
    sock.sendall(json.dumps(payload).encode("utf-8"))
    chunks = []
    while True:
        chunk = sock.recv(1048576)
        if not chunk:
            break
        chunks.append(chunk)
        try:
            data = json.loads(b"".join(chunks).decode("utf-8"))
            sock.close()
            return data
        except json.JSONDecodeError:
            continue
    sock.close()
    return json.loads(b"".join(chunks).decode("utf-8"))


def test(name, command, params=None, check=None, expect_error=False):
    global _passed, _failed, _skipped
    try:
        result = send(command, params)
        if VERBOSE:
            print(f"  Response: {json.dumps(result, indent=2)[:500]}")

        has_error = "error" in result and result.get("error")
        if has_error and "result" in result:
            has_error = "error" in result["result"] and result["result"]["error"]

        actual_result = result.get("result", result)

        if expect_error:
            if has_error or (isinstance(actual_result, dict) and "error" in actual_result):
                _passed += 1
                print(f"  \033[32m✓ {name}\033[0m (expected error)")
                return True
            else:
                _failed += 1
                _errors.append(f"{name}: Expected error but got success")
                print(f"  \033[31m✗ {name}\033[0m (expected error, got success)")
                return False

        if has_error and not expect_error:
            err_msg = result.get("error") or (actual_result.get("error") if isinstance(actual_result, dict) else "")
            _failed += 1
            _errors.append(f"{name}: {err_msg}")
            print(f"  \033[31m✗ {name}\033[0m → {err_msg}")
            return False

        if check and callable(check):
            if not check(actual_result):
                _failed += 1
                _errors.append(f"{name}: Check failed")
                print(f"  \033[31m✗ {name}\033[0m (check failed)")
                return False

        _passed += 1
        print(f"  \033[32m✓ {name}\033[0m")
        return True

    except ConnectionRefusedError:
        _failed += 1
        _errors.append(f"{name}: Connection refused - Blender bridge not running")
        print(f"  \033[31m✗ {name}\033[0m (connection refused)")
        return False
    except Exception as e:
        _failed += 1
        _errors.append(f"{name}: {str(e)}")
        print(f"  \033[31m✗ {name}\033[0m ({str(e)})")
        return False


def section(title):
    print(f"\n\033[1;36m{'─' * 60}\033[0m")
    print(f"\033[1;36m  {title}\033[0m")
    print(f"\033[1;36m{'─' * 60}\033[0m")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST SUITES
# ═══════════════════════════════════════════════════════════════════════════════

def test_connectivity():
    section("CONNECTIVITY")
    test("Ping Blender", "ping",
         check=lambda r: r.get("status") == "ok" and "blender_version" in r)


def test_scene_reset():
    """Reset to a clean scene for testing."""
    section("SCENE RESET")
    # Delete all non-default objects
    result = send("get_scene_info")
    scene = result.get("result", result)
    if isinstance(scene, dict) and "objects" in scene:
        names = [o["name"] for o in scene["objects"]]
        if names:
            send("delete_object", {"names": names})
    test("Scene cleared", "get_scene_info",
         check=lambda r: isinstance(r, dict) and r.get("object_count", 99) == 0)


def test_object_creation():
    section("OBJECT CREATION")
    types = ["cube", "sphere", "cylinder", "cone", "torus", "plane", "monkey", "ico_sphere"]
    if QUICK:
        types = ["cube", "sphere", "cylinder"]

    for t in types:
        test(f"Create {t}", "create_object",
             {"type": t, "name": f"test_{t}", "location": [0, 0, 0]},
             check=lambda r, t=t: isinstance(r, dict) and "name" in r)

    test("Create with transform", "create_object",
         {"type": "cube", "name": "transformed_cube", "location": [5, 3, 1], "rotation": [45, 0, 90], "scale": [2, 1, 0.5]},
         check=lambda r: r.get("name") == "transformed_cube")

    test("Create camera", "create_object",
         {"type": "camera", "name": "test_camera", "location": [7, -7, 5]},
         check=lambda r: "name" in r)

    test("Create point light", "create_object",
         {"type": "light_point", "name": "test_light", "location": [3, 3, 5]},
         check=lambda r: "name" in r)

    test("Create sun light", "create_object",
         {"type": "light_sun", "name": "test_sun"},
         check=lambda r: "name" in r)


def test_object_modification():
    section("OBJECT MODIFICATION")
    test("Modify location", "modify_object",
         {"name": "test_cube", "location": [10, 0, 0]},
         check=lambda r: isinstance(r, dict) and abs(r.get("location", [0])[0] - 10) < 0.01)

    test("Modify rotation", "modify_object",
         {"name": "test_cube", "rotation": [45, 90, 0]},
         check=lambda r: isinstance(r, dict) and "rotation_euler" in r)

    test("Modify scale", "modify_object",
         {"name": "test_cube", "scale": [2, 2, 2]},
         check=lambda r: isinstance(r, dict) and abs(r.get("scale", [0])[0] - 2) < 0.01)

    test("Rename object", "modify_object",
         {"name": "test_cube", "new_name": "renamed_cube"},
         check=lambda r: r.get("name") == "renamed_cube")

    test("Rename back", "modify_object",
         {"name": "renamed_cube", "new_name": "test_cube"})

    test("Hide object", "modify_object",
         {"name": "test_cube", "visible": False},
         check=lambda r: r.get("visible") == False)

    test("Show object", "modify_object",
         {"name": "test_cube", "visible": True})

    test("Modify nonexistent", "modify_object",
         {"name": "DOES_NOT_EXIST", "location": [0, 0, 0]},
         expect_error=True)


def test_object_selection():
    section("OBJECT SELECTION")
    test("Deselect all", "select_objects", {"action": "none"},
         check=lambda r: len(r.get("selected", ["x"])) == 0)

    test("Select by name", "select_objects",
         {"action": "select", "names": ["test_cube", "test_sphere"]},
         check=lambda r: len(r.get("selected", [])) >= 2)

    test("Select all", "select_objects", {"action": "all"},
         check=lambda r: len(r.get("selected", [])) > 0)

    test("Deselect all again", "select_objects", {"action": "none"})


def test_object_duplication():
    section("OBJECT DUPLICATION")
    test("Duplicate cube", "duplicate_object",
         {"name": "test_cube", "new_name": "cube_copy", "offset": [3, 0, 0]},
         check=lambda r: r.get("name") == "cube_copy")

    test("Duplicate nonexistent", "duplicate_object",
         {"name": "NOPE"},
         expect_error=True)


def test_materials():
    section("MATERIALS")
    test("Set red material", "set_material",
         {"object_name": "test_cube", "material_name": "RedMat", "color": [1, 0, 0], "metallic": 0.0, "roughness": 0.5},
         check=lambda r: r.get("material") == "RedMat")

    test("Set metallic material", "set_material",
         {"object_name": "test_sphere", "material_name": "MetalMat", "color": [0.8, 0.8, 0.9], "metallic": 1.0, "roughness": 0.1})

    test("Set emissive material", "set_material",
         {"object_name": "test_cylinder", "material_name": "GlowMat", "color": [0.1, 0.1, 0.1], "emission_color": [0, 1, 0.5], "emission_strength": 5.0})

    test("Material on nonexistent", "set_material",
         {"object_name": "GHOST", "color": [1, 0, 0]},
         expect_error=True)


def test_modifiers():
    section("MODIFIERS")
    test("Add subdivision", "apply_modifier",
         {"object_name": "test_cube", "modifier_type": "SUBSURF", "modifier_name": "Subdivision", "properties": {"levels": 2}},
         check=lambda r: r.get("modifier") == "Subdivision")

    test("Add mirror", "apply_modifier",
         {"object_name": "test_cube", "modifier_type": "MIRROR", "modifier_name": "Mirror"})

    test("Remove mirror", "apply_modifier",
         {"object_name": "test_cube", "action": "remove", "modifier_name": "Mirror"},
         check=lambda r: r.get("removed") == "Mirror")

    test("Apply subdivision", "apply_modifier",
         {"object_name": "test_cube", "action": "apply", "modifier_name": "Subdivision"})


def test_boolean_operations():
    section("BOOLEAN OPERATIONS")
    # Create two overlapping objects
    send("create_object", {"type": "cube", "name": "bool_a", "location": [0, 0, 0], "size": 2})
    send("create_object", {"type": "sphere", "name": "bool_b", "location": [1, 0, 0], "size": 2})

    test("Boolean difference", "boolean_operation",
         {"object_name": "bool_a", "target_name": "bool_b", "operation": "DIFFERENCE"},
         check=lambda r: r.get("operation") == "DIFFERENCE")


def test_keyframes():
    section("KEYFRAMES / ANIMATION")
    test("Set keyframe frame 1", "set_keyframe",
         {"object_name": "test_sphere", "frame": 1, "property": "location", "value": [0, 0, 0]},
         check=lambda r: r.get("frame") == 1)

    test("Set keyframe frame 50", "set_keyframe",
         {"object_name": "test_sphere", "frame": 50, "property": "location", "value": [10, 0, 5]})

    test("Set rotation keyframe", "set_keyframe",
         {"object_name": "test_sphere", "frame": 1, "property": "rotation_euler", "value": [0, 0, 0]})

    test("Clear keyframes", "clear_keyframes",
         {"object_name": "test_sphere"},
         check=lambda r: "cleared" in r)


def test_scene_operations():
    section("SCENE OPERATIONS")
    test("Set frame", "scene_operations",
         {"action": "set_frame", "frame": 24},
         check=lambda r: r.get("frame") == 24)

    test("List scenes", "scene_operations",
         {"action": "list_scenes"},
         check=lambda r: len(r.get("scenes", [])) >= 1)


def test_collections():
    section("COLLECTIONS")
    test("List collections", "manage_collection",
         {"action": "list"},
         check=lambda r: "collections" in r)

    test("Create collection", "manage_collection",
         {"action": "create", "name": "TestCollection"},
         check=lambda r: r.get("created") == "TestCollection")

    test("Move object to collection", "manage_collection",
         {"action": "move_objects", "objects": ["test_sphere"], "target": "TestCollection"},
         check=lambda r: "test_sphere" in r.get("moved", []))


def test_world():
    section("WORLD / ENVIRONMENT")
    test("Set world color", "set_world",
         {"color": [0.05, 0.05, 0.1], "strength": 1.0},
         check=lambda r: r.get("configured") == True)


def test_uv_operations():
    section("UV OPERATIONS")
    test("Smart UV project", "uv_operations",
         {"object_name": "test_cube", "action": "smart_project"},
         check=lambda r: "uv_layers" in r)

    if not QUICK:
        # Create a fresh sphere for UV test
        send("create_object", {"type": "sphere", "name": "uv_sphere"})
        test("Sphere UV unwrap", "uv_operations",
             {"object_name": "uv_sphere", "action": "unwrap"})


def test_transforms():
    section("TRANSFORM OPERATIONS")
    test("Origin to geometry", "transform_object",
         {"action": "origin_to_geometry", "name": "test_cube"})

    test("Apply transforms", "transform_object",
         {"action": "apply_transforms", "name": "test_cube"})

    test("Snap cursor to origin", "transform_object",
         {"action": "snap_cursor", "target": "world_origin"},
         check=lambda r: r.get("cursor") == [0, 0, 0])


def test_parenting():
    section("PARENTING")
    send("create_object", {"type": "empty", "name": "parent_empty"})
    test("Parent objects", "parent_objects",
         {"parent": "parent_empty", "children": ["test_cube", "test_sphere"]},
         check=lambda r: len(r.get("children", [])) == 2)


def test_render_settings():
    section("RENDER SETTINGS")
    test("Set render engine", "set_render_settings",
         {"engine": "cycles", "resolution_x": 1920, "resolution_y": 1080, "samples": 32},
         check=lambda r: "CYCLES" in r.get("engine", ""))

    test("Set output format", "set_render_settings",
         {"file_format": "PNG", "film_transparent": True})


def test_render_quality_audit():
    section("RENDER QUALITY AUDIT")
    test("Render QA baseline", "render_quality_audit",
         {"profile": "cinema"},
         check=lambda r: isinstance(r, dict) and "summary" in r and "checks" in r and "snapshot" in r)

    test("Render QA strict", "render_quality_audit",
         {"profile": "cinema", "strict": True, "min_samples": 64},
         check=lambda r: isinstance(r.get("summary", {}), dict) and "score" in r.get("summary", {}))


def test_text_objects():
    section("TEXT OBJECTS")
    test("Create 3D text", "text_object",
         {"action": "create", "text": "OpenClaw", "name": "title_text", "size": 2, "extrude": 0.2, "bevel_depth": 0.05},
         check=lambda r: r.get("text") == "OpenClaw")

    test("Edit text content", "text_object",
         {"action": "edit", "name": "title_text", "text": "OpenClaw MCP"})


def test_physics():
    section("PHYSICS")
    send("create_object", {"type": "cube", "name": "phys_cube", "location": [0, 0, 5]})
    test("Add rigid body", "physics",
         {"object_name": "phys_cube", "physics_type": "rigid_body", "rb_type": "ACTIVE"},
         check=lambda r: r.get("applied") == True)

    send("create_object", {"type": "plane", "name": "phys_floor", "size": 20})
    test("Add collision", "physics",
         {"object_name": "phys_floor", "physics_type": "collision"})


def test_particles():
    if QUICK:
        return
    section("PARTICLE SYSTEMS")
    send("create_object", {"type": "sphere", "name": "particle_emitter"})
    test("Add particle system", "particle_system",
         {"object_name": "particle_emitter", "action": "add", "count": 500, "lifetime": 50},
         check=lambda r: "added" in r)


def test_armature():
    if QUICK:
        return
    section("ARMATURE / RIGGING")
    test("Create armature", "armature_operations",
         {"action": "create", "name": "TestArmature"},
         check=lambda r: r.get("created") == "TestArmature")

    test("Add bone", "armature_operations",
         {"action": "add_bone", "armature_name": "TestArmature", "bone_name": "Spine",
          "head": [0, 0, 0], "tail": [0, 0, 1]})

    test("Add child bone", "armature_operations",
         {"action": "add_bone", "armature_name": "TestArmature", "bone_name": "Head",
          "head": [0, 0, 1], "tail": [0, 0, 1.5], "parent_bone": "Spine", "connected": True})

    test("List bones", "armature_operations",
         {"action": "list_bones", "armature_name": "TestArmature"},
         check=lambda r: len(r.get("bones", [])) >= 2)


def test_constraints():
    if QUICK:
        return
    section("CONSTRAINTS")
    send("create_object", {"type": "empty", "name": "constraint_target", "location": [5, 0, 0]})
    test("Add track-to constraint", "constraint_operations",
         {"object_name": "test_camera", "action": "add", "constraint_type": "TRACK_TO",
          "target": "constraint_target", "name": "LookAt"},
         check=lambda r: r.get("added") == "LookAt")

    test("List constraints", "constraint_operations",
         {"object_name": "test_camera", "action": "list"},
         check=lambda r: len(r.get("constraints", [])) >= 1)


def test_shader_nodes():
    if QUICK:
        return
    section("SHADER NODES")
    test("Get material nodes", "shader_nodes",
         {"material_name": "RedMat", "action": "info"},
         check=lambda r: len(r.get("nodes", [])) >= 1)

    test("Add noise texture node", "shader_nodes",
         {"material_name": "RedMat", "action": "add_node",
          "node_type": "ShaderNodeTexNoise", "name": "NoiseTexture"})


def test_compositor():
    if QUICK:
        return
    section("COMPOSITOR")
    test("Get compositor info", "compositor",
         {"action": "info"},
         check=lambda r: "nodes" in r)


def test_viewport():
    section("VIEWPORT")
    test("Set wireframe shading", "viewport",
         {"action": "set_shading", "shading": "WIREFRAME"})

    test("Set solid shading", "viewport",
         {"action": "set_shading", "shading": "SOLID"})

    test("Camera view", "viewport",
         {"action": "camera_view"})


def test_cleanup():
    section("CLEANUP")
    test("Purge orphans", "cleanup",
         {"action": "purge_orphans"})

    test("Shade smooth", "cleanup",
         {"action": "shade_smooth", "object_name": "test_cube"})


def test_python_execution():
    section("PYTHON EXECUTION")
    test("Simple expression", "execute_python",
         {"code": "__result__ = 2 + 2"},
         check=lambda r: r.get("result") == 4)

    test("bpy scene access", "execute_python",
         {"code": "__result__ = bpy.context.scene.name"},
         check=lambda r: isinstance(r.get("result"), str))

    test("Create object via code", "execute_python",
         {"code": "bpy.ops.mesh.primitive_cube_add(size=1, location=(20, 0, 0))\n__result__ = bpy.context.active_object.name"})

    test("Error handling", "execute_python",
         {"code": "raise ValueError('test error')"},
         expect_error=True)


def test_object_data():
    section("OBJECT DATA QUERIES")
    test("Get cube data", "get_object_data",
         {"name": "test_cube"},
         check=lambda r: r.get("type") == "MESH" and "mesh" in r)

    test("Get camera data", "get_object_data",
         {"name": "test_camera"},
         check=lambda r: r.get("type") == "CAMERA")


def test_scene_info():
    section("SCENE INFO")
    test("Full scene info", "get_scene_info",
         check=lambda r: r.get("object_count", 0) > 0 and "objects" in r)


def test_deletion():
    section("OBJECT DELETION")
    test("Delete single", "delete_object",
         {"names": ["cube_copy"]},
         check=lambda r: "cube_copy" in r.get("deleted", []))

    test("Delete nonexistent", "delete_object",
         {"names": ["GHOST_OBJECT"]},
         check=lambda r: "GHOST_OBJECT" in r.get("not_found", []))


def test_file_operations():
    section("FILE OPERATIONS")
    test("Save file", "save_file",
         {"action": "save", "filepath": "/tmp/openclaw_test.blend"},
         check=lambda r: "saved" in r)

    test("New file", "save_file",
         {"action": "new", "use_empty": True})


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def test_vfx_features():
    """Test VFX-grade v2.0 handlers."""
    if QUICK:
        return

    # Reset scene first
    send("scene_operations", {"action": "new_file"})

    section("VFX: PROCEDURAL MATERIALS")
    test("Marble material", "procedural_material",
         {"preset": "marble", "scale": 5.0},
         check=lambda r: "material" in r)
    test("Metal material", "procedural_material",
         {"preset": "metal", "roughness": 0.3},
         check=lambda r: r.get("preset") == "metal")
    test("Glass material", "procedural_material",
         {"preset": "glass", "ior": 1.5},
         check=lambda r: r.get("preset") == "glass")
    test("Wood material", "procedural_material",
         {"preset": "wood"},
         check=lambda r: r.get("preset") == "wood")
    test("Volume fog", "procedural_material",
         {"preset": "volume_fog", "density": 0.1},
         check=lambda r: r.get("preset") == "volume_fog")

    section("VFX: BATCH OPERATIONS")
    test("Batch create objects", "batch_operations",
         {"action": "create", "objects": [
             {"type": "cube", "location": [0, 0, 0], "name": "BatchCube1"},
             {"type": "sphere", "location": [3, 0, 0], "name": "BatchSphere1"},
             {"type": "cylinder", "location": [6, 0, 0], "name": "BatchCyl1"},
         ]},
         check=lambda r: r.get("count") == 3)
    test("Batch transform", "batch_operations",
         {"action": "transform", "transforms": [
             {"object_name": "BatchCube1", "location": [1, 1, 1]},
             {"object_name": "BatchSphere1", "scale": [2, 2, 2]},
         ]},
         check=lambda r: len(r.get("results", [])) == 2)
    test("Batch randomize", "batch_operations",
         {"action": "randomize", "objects": ["BatchCube1", "BatchSphere1"],
          "seed": 42, "location_range": [1, 1, 0], "rotation_range": [0.5, 0.5, 0.5]},
         check=lambda r: r.get("seed") == 42)
    test("Batch delete", "batch_operations",
         {"action": "delete", "names": ["BatchCube1", "BatchSphere1", "BatchCyl1"]},
         check=lambda r: len(r.get("deleted", [])) == 3)

    section("VFX: SCENE TEMPLATES")
    test("Product viz template", "scene_template",
         {"template": "product_viz"},
         check=lambda r: "ProductCam" in r.get("objects", []))
    test("Motion graphics template", "scene_template",
         {"template": "motion_graphics"},
         check=lambda r: "MoGraphCam" in r.get("objects", []))

    section("VFX: ADVANCED ANIMATION")
    # Create object for animation tests
    send("create_object", {"type": "cube", "name": "AnimCube", "location": [0, 0, 0]})
    test("Bounce animation", "advanced_animation",
         {"action": "bounce", "object_name": "AnimCube", "height": 5, "bounces": 3},
         check=lambda r: r.get("bounces") == 3)
    test("Keyframe sequence", "advanced_animation",
         {"action": "keyframe_sequence", "object_name": "AnimCube",
          "keyframes": [
              {"frame": 1, "location": [0, 0, 0], "rotation": [0, 0, 0]},
              {"frame": 30, "location": [5, 0, 3], "rotation": [0, 0, 45]},
              {"frame": 60, "location": [10, 0, 0], "rotation": [0, 0, 90]},
          ]},
         check=lambda r: r.get("keyframes_set") == 3)
    test("Turntable camera", "advanced_animation",
         {"action": "turntable", "target": "AnimCube", "frames": 60, "radius": 8},
         check=lambda r: r.get("camera") == "TurntableCam")

    section("VFX: RENDER PRESETS")
    test("Preview preset", "render_presets",
         {"preset": "preview"},
         check=lambda r: r.get("preset") == "preview")
    test("High quality preset", "render_presets",
         {"preset": "high_quality", "samples": 128},
         check=lambda r: r.get("engine") == "CYCLES")
    test("VFX production preset", "render_presets",
         {"preset": "vfx_production", "samples": 64},
         check=lambda r: "EXR" in str(r.get("format", "")) or r.get("engine") == "CYCLES")

    section("VFX: FORCE FIELDS")
    test("Wind force field", "force_field",
         {"type": "WIND", "strength": 10, "location": [0, 0, 5]},
         check=lambda r: r.get("type") == "WIND")
    test("Turbulence field", "force_field",
         {"type": "TURBULENCE", "strength": 3, "size": 2},
         check=lambda r: r.get("type") == "TURBULENCE")

    section("VFX: CLOTH SIMULATION")
    send("create_object", {"type": "plane", "name": "ClothPlane", "location": [0, 0, 3]})
    test("Add silk cloth", "cloth_simulation",
         {"object_name": "ClothPlane", "action": "add", "fabric": "silk"},
         check=lambda r: r.get("fabric") == "silk")

    section("VFX: FLUID SIMULATION")
    test("Create gas domain", "fluid_simulation",
         {"action": "create_domain", "domain_type": "GAS", "resolution": 32, "name": "SmokeDomain"},
         check=lambda r: r.get("type") == "GAS")
    send("create_object", {"type": "sphere", "name": "SmokeEmitter", "location": [0, 0, -1]})
    test("Add smoke flow", "fluid_simulation",
         {"action": "add_flow", "object_name": "SmokeEmitter", "flow_type": "SMOKE"},
         check=lambda r: r.get("type") == "SMOKE")

    section("VFX: SCENE ANALYSIS")
    test("Analyze scene", "scene_analyze", {},
         check=lambda r: "objects" in r and "statistics" in r)

    section("VFX: VIEWPORT CAPTURE")
    test("Capture viewport", "viewport_capture",
         {"width": 400, "height": 300},
         check=lambda r: "filepath" in r)

    section("VFX: EXTERNAL ASSET/GEN TOOL AVAILABILITY")
    test("Sketchfab tool reachable", "sketchfab",
         {"action": "search", "query": "cinematic car", "count": 2},
         expect_error=True)
    test("Hunyuan3D tool reachable", "hunyuan3d",
         {"action": "status", "job_id": "demo"},
         expect_error=True)


def main():
    start = time.time()

    print("\n\033[1;35m═══════════════════════════════════════════════════════════\033[0m")
    print("\033[1;35m  OpenClaw Blender MCP — QA Test Runner\033[0m")
    print(f"\033[1;35m  Mode: {'QUICK' if QUICK else 'FULL'} | Verbose: {VERBOSE}\033[0m")
    print("\033[1;35m═══════════════════════════════════════════════════════════\033[0m")

    # Check connectivity first
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((HOST, PORT))
        sock.close()
    except ConnectionRefusedError:
        print(f"\n\033[31mERROR: Cannot connect to Blender on {HOST}:{PORT}")
        print("Make sure Blender is running with the OpenClaw Bridge addon active.\033[0m")
        sys.exit(1)

    # Run test suites in order
    test_connectivity()
    test_scene_reset()
    test_object_creation()
    test_object_modification()
    test_object_selection()
    test_object_duplication()
    test_materials()
    test_modifiers()
    test_boolean_operations()
    test_keyframes()
    test_scene_operations()
    test_collections()
    test_world()
    test_uv_operations()
    test_transforms()
    test_parenting()
    test_render_settings()
    test_render_quality_audit()
    test_text_objects()
    test_physics()
    test_particles()
    test_armature()
    test_constraints()
    test_shader_nodes()
    test_compositor()
    test_viewport()
    test_cleanup()
    test_python_execution()
    test_object_data()
    test_scene_info()
    test_deletion()
    test_file_operations()
    test_vfx_features()

    elapsed = time.time() - start
    total = _passed + _failed

    print(f"\n\033[1;35m═══════════════════════════════════════════════════════════\033[0m")
    print(f"\033[1;35m  RESULTS: {_passed}/{total} passed ({_passed/total*100:.0f}%) in {elapsed:.1f}s\033[0m")
    if _errors:
        print(f"\033[31m  FAILURES ({_failed}):\033[0m")
        for e in _errors:
            print(f"    • {e}")
    else:
        print(f"\033[32m  ALL TESTS PASSED!\033[0m")
    print(f"\033[1;35m═══════════════════════════════════════════════════════════\033[0m\n")

    sys.exit(0 if _failed == 0 else 1)


if __name__ == "__main__":
    main()
