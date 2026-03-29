#!/usr/bin/env python3
"""
OpenClaw Blender MCP - Advanced Features QA Runner
====================================================
Tests advanced features NOT covered by the core qa_runner.py:
  - Geometry Nodes
  - Curve/NURBS operations
  - Shape Keys (morph targets)
  - Weight Painting
  - Mesh Edit mode operations
  - Sculpting
  - Image operations
  - Grease Pencil

Requires: Blender running with OpenClaw Bridge on port 9876.

Usage:
    python3 qa_advanced.py              # Run all advanced tests
    python3 qa_advanced.py --verbose    # Verbose output
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

# ─── Test Infrastructure ─────────────────────────────────────────────────────

_id = 0
_passed = 0
_failed = 0
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
    global _passed, _failed
    try:
        result = send(command, params)
        if VERBOSE:
            print(f"  Response: {json.dumps(result, indent=2)[:600]}")

        has_error = "error" in result and result.get("error")
        actual_result = result.get("result", result)
        if isinstance(actual_result, dict) and "error" in actual_result:
            has_error = True

        if expect_error:
            if has_error:
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
# ADVANCED TEST SUITES
# ═══════════════════════════════════════════════════════════════════════════════

def test_setup():
    """Reset scene for clean advanced tests."""
    section("SETUP")
    send("scene_operations", {"action": "new_file"})
    test("Scene reset", "ping",
         check=lambda r: r.get("status") == "ok")


def test_geometry_nodes():
    """Test geometry nodes modifier operations."""
    section("GEOMETRY NODES")

    # Create object for geo nodes
    send("create_object", {"type": "cube", "name": "GeoNodesCube", "location": [0, 0, 0]})

    test("Add geometry nodes modifier", "geometry_nodes",
         {"object_name": "GeoNodesCube", "action": "add", "name": "MyGeoNodes"},
         check=lambda r: r.get("modifier") == "MyGeoNodes")

    test("Get geometry nodes info", "geometry_nodes",
         {"object_name": "GeoNodesCube", "action": "info", "modifier_name": "MyGeoNodes"},
         check=lambda r: "nodes" in r and "links" in r)

    test("Add node to geo tree", "geometry_nodes",
         {"object_name": "GeoNodesCube", "action": "add_node",
          "modifier_name": "MyGeoNodes", "node_type": "GeometryNodeMeshGrid", "name": "Grid"},
         check=lambda r: r.get("added") == "Grid")

    test("Geo nodes on nonexistent", "geometry_nodes",
         {"object_name": "GHOST", "action": "add"},
         expect_error=True)


def test_curve_operations():
    """Test curve/NURBS creation and manipulation."""
    section("CURVE / NURBS OPERATIONS")

    test("Create bezier curve", "curve_operations",
         {"action": "create", "curve_type": "BEZIER", "name": "TestBezier", "location": [0, 0, 0]},
         check=lambda r: r.get("created") == "TestBezier" and r.get("type") == "BEZIER")

    test("Create NURBS curve", "curve_operations",
         {"action": "create", "curve_type": "NURBS", "name": "TestNurbs", "location": [3, 0, 0]},
         check=lambda r: r.get("type") == "NURBS")

    test("Create bezier circle", "curve_operations",
         {"action": "create", "curve_type": "CIRCLE", "name": "TestCircle", "location": [6, 0, 0]},
         check=lambda r: r.get("type") == "CIRCLE")

    test("Create NURBS circle", "curve_operations",
         {"action": "create", "curve_type": "NURBS_CIRCLE", "name": "TestNurbsCircle"},
         check=lambda r: r.get("type") == "NURBS_CIRCLE")

    test("Create NURBS path", "curve_operations",
         {"action": "create", "curve_type": "PATH", "name": "TestPath"},
         check=lambda r: r.get("type") == "PATH")

    test("Create curve with bevel", "curve_operations",
         {"action": "create", "curve_type": "BEZIER", "name": "BeveledCurve",
          "bevel_depth": 0.2, "resolution": 12},
         check=lambda r: r.get("created") == "BeveledCurve")

    test("Convert curve to mesh", "curve_operations",
         {"action": "to_mesh", "object_name": "BeveledCurve"},
         check=lambda r: r.get("to") == "MESH")

    test("Invalid curve type", "curve_operations",
         {"action": "create", "curve_type": "INVALID"},
         expect_error=True)


def test_shape_keys():
    """Test shape keys / morph targets."""
    section("SHAPE KEYS (MORPH TARGETS)")

    send("create_object", {"type": "cube", "name": "ShapeKeyCube"})

    test("List shape keys (empty)", "shape_keys",
         {"object_name": "ShapeKeyCube", "action": "list"},
         check=lambda r: len(r.get("shape_keys", [])) == 0)

    test("Add basis shape key", "shape_keys",
         {"object_name": "ShapeKeyCube", "action": "add_basis"},
         check=lambda r: r.get("added") == "Basis")

    test("Add shape key", "shape_keys",
         {"object_name": "ShapeKeyCube", "action": "add", "name": "Smile"},
         check=lambda r: r.get("added") == "Smile")

    test("Add second shape key", "shape_keys",
         {"object_name": "ShapeKeyCube", "action": "add", "name": "Frown"},
         check=lambda r: r.get("added") == "Frown")

    test("Set shape key value", "shape_keys",
         {"object_name": "ShapeKeyCube", "action": "set_value", "key_name": "Smile", "value": 0.75},
         check=lambda r: abs(r.get("value", 0) - 0.75) < 0.01)

    test("List shape keys (populated)", "shape_keys",
         {"object_name": "ShapeKeyCube", "action": "list"},
         check=lambda r: len(r.get("shape_keys", [])) >= 3)

    test("Keyframe shape key", "shape_keys",
         {"object_name": "ShapeKeyCube", "action": "keyframe",
          "key_name": "Smile", "frame": 1, "value": 0.0},
         check=lambda r: r.get("frame") == 1)

    test("Keyframe shape key frame 30", "shape_keys",
         {"object_name": "ShapeKeyCube", "action": "keyframe",
          "key_name": "Smile", "frame": 30, "value": 1.0},
         check=lambda r: r.get("frame") == 30)

    test("Shape key nonexistent", "shape_keys",
         {"object_name": "ShapeKeyCube", "action": "set_value",
          "key_name": "NOPE", "value": 0.5},
         expect_error=True)


def test_weight_paint():
    """Test weight painting operations."""
    section("WEIGHT PAINTING")

    send("create_object", {"type": "cube", "name": "WeightCube"})

    test("Add vertex group", "weight_paint",
         {"object_name": "WeightCube", "action": "add_group", "group_name": "BoneWeight"},
         check=lambda r: r.get("created") == "BoneWeight")

    test("Assign weights", "weight_paint",
         {"object_name": "WeightCube", "action": "assign",
          "group_name": "BoneWeight", "weight": 0.8},
         check=lambda r: r.get("assigned") == "BoneWeight" and abs(r.get("weight", 0) - 0.8) < 0.01)

    test("Enter weight paint mode", "weight_paint",
         {"object_name": "WeightCube", "action": "enter"},
         check=lambda r: r.get("mode") == "WEIGHT_PAINT")

    test("Exit weight paint mode", "weight_paint",
         {"object_name": "WeightCube", "action": "exit"},
         check=lambda r: r.get("mode") == "OBJECT")

    test("Weight paint nonexistent group", "weight_paint",
         {"object_name": "WeightCube", "action": "assign",
          "group_name": "NOPE", "weight": 1.0},
         expect_error=True)


def test_mesh_edit():
    """Test edit mode mesh operations."""
    section("MESH EDIT OPERATIONS")

    send("create_object", {"type": "cube", "name": "EditCube", "location": [0, 0, 0]})

    test("Extrude", "mesh_edit",
         {"object_name": "EditCube", "action": "extrude", "value": 2.0},
         check=lambda r: r.get("extruded") == True)

    test("Inset faces", "mesh_edit",
         {"object_name": "EditCube", "action": "inset", "thickness": 0.2, "depth": 0.0},
         check=lambda r: r.get("inset") == True)

    test("Subdivide", "mesh_edit",
         {"object_name": "EditCube", "action": "subdivide", "cuts": 2},
         check=lambda r: r.get("subdivided") == True)

    test("Smooth vertices", "mesh_edit",
         {"object_name": "EditCube", "action": "smooth_vertices", "repeat": 3},
         check=lambda r: r.get("smoothed") == True)

    test("Flip normals", "mesh_edit",
         {"object_name": "EditCube", "action": "flip_normals"},
         check=lambda r: r.get("flipped") == True)

    test("Recalculate normals", "mesh_edit",
         {"object_name": "EditCube", "action": "recalculate_normals"},
         check=lambda r: r.get("recalculated") == True)

    test("Triangulate", "mesh_edit",
         {"object_name": "EditCube", "action": "triangulate"},
         check=lambda r: r.get("triangulated") == True)

    test("Tris to quads", "mesh_edit",
         {"object_name": "EditCube", "action": "tris_to_quads"},
         check=lambda r: r.get("converted_to_quads") == True)

    test("Poke faces", "mesh_edit",
         {"object_name": "EditCube", "action": "poke_faces"},
         check=lambda r: r.get("poked") == True)

    # Create fresh cube for bevel (needs clean geometry)
    send("create_object", {"type": "cube", "name": "BevelCube"})
    test("Bevel edges", "mesh_edit",
         {"object_name": "BevelCube", "action": "bevel", "width": 0.15, "segments": 2},
         check=lambda r: r.get("beveled") == True)

    test("Unknown mesh action", "mesh_edit",
         {"object_name": "EditCube", "action": "INVALID_ACTION"},
         expect_error=True)


def test_sculpt():
    """Test sculpting operations."""
    section("SCULPTING")

    send("create_object", {"type": "ico_sphere", "name": "SculptSphere", "location": [0, 0, 0]})
    # Add subdivision for more geometry
    send("apply_modifier", {"object_name": "SculptSphere", "modifier_type": "SUBSURF",
                            "properties": {"levels": 3}})
    send("apply_modifier", {"object_name": "SculptSphere", "action": "apply", "modifier_name": "Subsurf"})

    test("Enter sculpt mode", "sculpt",
         {"object_name": "SculptSphere", "action": "enter"},
         check=lambda r: r.get("mode") == "SCULPT")

    test("Set sculpt brush", "sculpt",
         {"object_name": "SculptSphere", "action": "set_brush",
          "brush": "SculptDraw", "radius": 50, "strength": 0.8},
         check=lambda r: r.get("brush") is not None)

    test("Exit sculpt mode", "sculpt",
         {"object_name": "SculptSphere", "action": "exit"},
         check=lambda r: r.get("mode") == "OBJECT")

    test("Voxel remesh", "sculpt",
         {"object_name": "SculptSphere", "action": "remesh", "voxel_size": 0.1},
         check=lambda r: r.get("remeshed") == "SculptSphere")

    test("Sculpt nonexistent object", "sculpt",
         {"object_name": "GHOST", "action": "enter"},
         expect_error=True)


def test_image_operations():
    """Test image/texture operations."""
    section("IMAGE OPERATIONS")

    test("List images", "image_operations",
         {"action": "list"},
         check=lambda r: isinstance(r.get("images"), list))

    test("Create image", "image_operations",
         {"action": "create", "name": "TestTex", "width": 512, "height": 512},
         check=lambda r: r.get("created") == "TestTex" and r.get("size") == [512, 512])

    test("List images (after create)", "image_operations",
         {"action": "list"},
         check=lambda r: any(img["name"] == "TestTex" for img in r.get("images", [])))

    test("Load nonexistent image", "image_operations",
         {"action": "load", "filepath": "/tmp/nonexistent_image.png"},
         expect_error=True)


def test_grease_pencil():
    """Test grease pencil basic operations."""
    section("GREASE PENCIL")

    test("Create grease pencil object", "grease_pencil",
         {"action": "create", "name": "TestGP"},
         check=lambda r: isinstance(r, dict) and ("created" in r or "name" in r or "error" not in r))


def test_combined_workflow():
    """Test a realistic production workflow combining multiple features."""
    section("COMBINED WORKFLOW: Character Setup")

    # 1. Create base mesh
    send("create_object", {"type": "cube", "name": "CharBase", "location": [0, 0, 0]})

    # 2. Add subdivision
    test("Add subdivision modifier", "apply_modifier",
         {"object_name": "CharBase", "modifier_type": "SUBSURF",
          "modifier_name": "SubD", "properties": {"levels": 2}})

    # 3. Add material
    test("Apply skin material", "set_material",
         {"object_name": "CharBase", "material_name": "SkinMat",
          "color": [0.85, 0.65, 0.5], "roughness": 0.4},
         check=lambda r: r.get("material") == "SkinMat")

    # 4. Add shape keys for facial expressions
    test("Add basis key", "shape_keys",
         {"object_name": "CharBase", "action": "add_basis"})

    test("Add smile morph", "shape_keys",
         {"object_name": "CharBase", "action": "add", "name": "Smile"})

    # 5. Create armature for rigging
    test("Create armature", "armature_operations",
         {"action": "create", "name": "CharRig"},
         check=lambda r: r.get("created") == "CharRig")

    test("Add spine bone", "armature_operations",
         {"action": "add_bone", "armature_name": "CharRig",
          "bone_name": "Spine", "head": [0, 0, 0], "tail": [0, 0, 1]})

    # 6. Parent mesh to armature
    test("Parent to armature", "parent_objects",
         {"parent": "CharRig", "children": ["CharBase"]},
         check=lambda r: len(r.get("children", [])) == 1)

    # 7. Add vertex group for weight painting
    test("Add weight group", "weight_paint",
         {"object_name": "CharBase", "action": "add_group", "group_name": "Spine"},
         check=lambda r: r.get("created") == "Spine")

    # 8. Assign weights
    test("Assign bone weights", "weight_paint",
         {"object_name": "CharBase", "action": "assign",
          "group_name": "Spine", "weight": 1.0},
         check=lambda r: r.get("assigned") == "Spine")

    # 9. Animate with keyframes
    test("Set pose keyframe", "set_keyframe",
         {"object_name": "CharBase", "frame": 1, "property": "location", "value": [0, 0, 0]})

    test("Set end keyframe", "set_keyframe",
         {"object_name": "CharBase", "frame": 60, "property": "location", "value": [0, 0, 2]})

    # 10. Keyframe shape key
    test("Animate shape key", "shape_keys",
         {"object_name": "CharBase", "action": "keyframe",
          "key_name": "Smile", "frame": 30, "value": 1.0},
         check=lambda r: r.get("frame") == 30)

    # 11. Setup render
    test("Set render preset", "render_presets",
         {"preset": "preview"},
         check=lambda r: r.get("preset") == "preview")

    # 12. Capture viewport
    test("Capture result", "viewport_capture",
         {"width": 800, "height": 600},
         check=lambda r: "filepath" in r)

    print(f"  \033[33m→ Full character setup workflow complete\033[0m")


def test_procedural_workflow():
    """Test a procedural generation workflow using geometry nodes + batch ops."""
    section("COMBINED WORKFLOW: Procedural City Block")

    # Reset
    send("scene_operations", {"action": "new_file"})

    # 1. Batch create buildings
    test("Batch create buildings", "batch_operations",
         {"action": "create", "objects": [
             {"type": "cube", "name": "Building1", "location": [0, 0, 2], "scale": [1, 1, 4]},
             {"type": "cube", "name": "Building2", "location": [3, 0, 3], "scale": [1, 1, 6]},
             {"type": "cube", "name": "Building3", "location": [6, 0, 1.5], "scale": [1, 1, 3]},
             {"type": "cube", "name": "Building4", "location": [0, 4, 2.5], "scale": [1, 1, 5]},
             {"type": "cube", "name": "Building5", "location": [3, 4, 1], "scale": [1, 1, 2]},
         ]},
         check=lambda r: r.get("count") == 5)

    # 2. Add concrete material to all
    for i in range(1, 6):
        send("set_material", {"object_name": f"Building{i}", "material_name": "Concrete",
                              "color": [0.5, 0.5, 0.5], "roughness": 0.8})

    test("Apply concrete material", "set_material",
         {"object_name": "Building1", "material_name": "Concrete",
          "color": [0.5, 0.5, 0.5], "roughness": 0.8},
         check=lambda r: r.get("material") == "Concrete")

    # 3. Add ground plane
    send("create_object", {"type": "plane", "name": "Ground", "size": 20})
    test("Ground material", "procedural_material",
         {"preset": "concrete", "object_name": "Ground"},
         check=lambda r: "material" in r or "preset" in r)

    # 4. Add randomized variation
    test("Randomize buildings", "batch_operations",
         {"action": "randomize",
          "objects": ["Building1", "Building2", "Building3", "Building4", "Building5"],
          "seed": 42, "rotation_range": [0, 0, 0.1], "scale_range": [0.1, 0.1, 0.3]},
         check=lambda r: r.get("seed") == 42)

    # 5. Scene template for lighting
    test("Add cinematic lighting", "scene_template",
         {"template": "cinematic"})

    # 6. Scene analysis
    test("Analyze city scene", "scene_analyze", {},
         check=lambda r: "objects" in r and "statistics" in r)

    print(f"  \033[33m→ Procedural city block workflow complete\033[0m")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    start = time.time()

    print("\n\033[1;35m═══════════════════════════════════════════════════════════\033[0m")
    print("\033[1;35m  OpenClaw Blender MCP — Advanced Features QA Runner\033[0m")
    print(f"\033[1;35m  Verbose: {VERBOSE}\033[0m")
    print("\033[1;35m═══════════════════════════════════════════════════════════\033[0m")

    # Check connectivity
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((HOST, PORT))
        sock.close()
    except ConnectionRefusedError:
        print(f"\n\033[31mERROR: Cannot connect to Blender on {HOST}:{PORT}")
        print("Make sure Blender is running with the OpenClaw Bridge addon active.\033[0m")
        sys.exit(1)

    # Run advanced test suites
    test_setup()
    test_geometry_nodes()
    test_curve_operations()
    test_shape_keys()
    test_weight_paint()
    test_mesh_edit()
    test_sculpt()
    test_image_operations()
    test_grease_pencil()
    test_combined_workflow()
    test_procedural_workflow()

    elapsed = time.time() - start
    total = _passed + _failed

    print(f"\n\033[1;35m═══════════════════════════════════════════════════════════\033[0m")
    print(f"\033[1;35m  RESULTS: {_passed}/{total} passed ({_passed/total*100:.0f}%) in {elapsed:.1f}s\033[0m")
    if _errors:
        print(f"\033[31m  FAILURES ({_failed}):\033[0m")
        for e in _errors:
            print(f"    • {e}")
    else:
        print(f"\033[32m  ALL ADVANCED TESTS PASSED!\033[0m")
    print(f"\033[1;35m═══════════════════════════════════════════════════════════\033[0m\n")

    sys.exit(0 if _failed == 0 else 1)


if __name__ == "__main__":
    main()
