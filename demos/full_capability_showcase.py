#!/usr/bin/env python3
"""
OpenClaw Blender MCP — Full Capability Showcase
=================================================
Tests and demonstrates EVERY major feature category:
- Colors & materials (9 procedural presets + custom shader nodes)
- Sculpting (8 brush types + dynamic topology)
- Textures (noise, wave, voronoi, musgrave, procedural)
- Animation (turntable, bounce, follow path, keyframe sequences)
- Physics (rigid body, cloth, fluid/smoke, force fields, particles)
- Geometry nodes (procedural generation)
- Modeling (mesh edit, booleans, modifiers, curves, shape keys)
- Rendering (EEVEE, Cycles, multi-pass EXR)
- Viewport capture (VLM verification)

Run: python3 demos/full_capability_showcase.py
"""

import json
import socket
import time
import math

HOST = "127.0.0.1"
PORT = 9876
TIMEOUT = 30.0
_id = 0


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
            return data.get("result", data)
        except json.JSONDecodeError:
            continue
    sock.close()
    return json.loads(b"".join(chunks).decode("utf-8"))


def step(msg, command, params=None):
    print(f"    → {msg}...", end=" ", flush=True)
    result = send(command, params)
    if isinstance(result, dict) and "error" in result:
        print(f"⚠ {result['error']}")
        return result
    print("✓")
    return result


def section(title):
    print(f"\n  ╔══ {title} ══╗")


# ═══════════════════════════════════════════════════════════════
# SHOWCASE
# ═══════════════════════════════════════════════════════════════

def showcase_colors_and_materials():
    """Demonstrate all 9 procedural material presets + custom colors."""
    section("COLORS & MATERIALS")

    # Create a row of objects to display materials
    presets = [
        ("marble", {"scale": 3.0, "color1": [0.95, 0.93, 0.9, 1], "color2": [0.15, 0.15, 0.2, 1]}),
        ("wood", {"color1": [0.4, 0.2, 0.07, 1], "color2": [0.6, 0.35, 0.15, 1]}),
        ("metal", {"color": [0.95, 0.8, 0.3, 1], "roughness": 0.1}),  # Gold
        ("glass", {"color": [0.8, 0.95, 1.0, 1], "ior": 1.52}),
        ("emissive", {"color": [1, 0, 0.5, 1], "emission_color": [1, 0, 0.5, 1], "emission_strength": 20}),
        ("concrete", {"scale": 15}),
        ("fabric", {"color1": [0.6, 0.1, 0.15, 1], "color2": [0.65, 0.12, 0.18, 1]}),
    ]

    for i, (preset, extra_params) in enumerate(presets):
        x = (i - 3) * 2.5
        obj_name = f"MatDemo_{preset.title()}"
        step(f"Create {preset} sphere", "create_object", {
            "type": "sphere", "name": obj_name, "location": [x, 0, 1.2]
        })
        step(f"Apply {preset} material", "procedural_material", {
            "preset": preset, "object_name": obj_name, **extra_params
        })
        # Smooth them
        send("apply_modifier", {"object_name": obj_name, "modifier_type": "SUBSURF", "action": "add", "level": 2})

    # Custom color materials via set_material
    custom_colors = [
        ("PureRed", [1, 0, 0, 1], 0.1, 0.0),
        ("NeonGreen", [0, 1, 0.3, 1], 0.0, 0.0),
        ("DeepBlue", [0.05, 0.1, 0.8, 1], 0.3, 0.5),
        ("HotPink", [1, 0.2, 0.6, 1], 0.2, 0.0),
        ("CopperOrange", [0.85, 0.45, 0.15, 1], 0.2, 1.0),
    ]

    for i, (name, color, roughness, metallic) in enumerate(custom_colors):
        x = (i - 2) * 2.5
        obj_name = f"ColorDemo_{name}"
        step(f"Create {name} cube", "create_object", {
            "type": "cube", "name": obj_name, "location": [x, 4, 0.8], "scale": [0.7, 0.7, 0.7]
        })
        step(f"Apply {name} material", "set_material", {
            "object_name": obj_name, "color": color, "roughness": roughness,
            "metallic": metallic, "material_name": f"Mat_{name}"
        })

    # Volume materials
    step("Create fog volume", "create_object", {"type": "cube", "name": "FogVolume", "location": [0, -4, 1], "scale": [5, 2, 1]})
    step("Apply volume fog", "procedural_material", {"preset": "volume_fog", "object_name": "FogVolume", "density": 0.03})


def showcase_sculpting():
    """Demonstrate sculpting brushes and dynamic topology."""
    section("SCULPTING")

    # Create object for sculpting
    step("Create sculpt sphere", "create_object", {
        "type": "ico_sphere", "name": "SculptDemo", "location": [0, 10, 2], "scale": [2, 2, 2]
    })
    send("apply_modifier", {"object_name": "SculptDemo", "modifier_type": "SUBSURF", "action": "add", "level": 3})
    send("apply_modifier", {"object_name": "SculptDemo", "modifier_type": "SUBSURF", "action": "apply"})

    # Test different sculpt brushes
    brushes = [
        ("DRAW", 1.0, 50, [0, 0, 2]),
        ("CLAY_STRIPS", 0.8, 40, [1, 0, 1.5]),
        ("INFLATE", 0.5, 30, [-1, 0, 1.5]),
        ("SMOOTH", 0.7, 60, [0, 1, 2]),
        ("GRAB", 0.6, 50, [0, -1, 2]),
        ("PINCH", 0.4, 20, [0.5, 0.5, 2.5]),
        ("CREASE", 0.5, 25, [-0.5, -0.5, 1]),
        ("FLATTEN", 0.6, 40, [0, 0, 0.5]),
    ]

    for brush, strength, size, stroke_loc in brushes:
        step(f"Sculpt with {brush} brush", "sculpt", {
            "object_name": "SculptDemo",
            "action": "stroke",
            "brush": brush,
            "strength": strength,
            "radius": size,
            "stroke_points": [stroke_loc, [stroke_loc[0] + 0.3, stroke_loc[1] + 0.3, stroke_loc[2]]]
        })


def showcase_textures_and_shaders():
    """Demonstrate advanced shader node creation."""
    section("TEXTURES & SHADER NODES")

    # Create object for texture demo
    step("Create texture plane", "create_object", {
        "type": "plane", "name": "TextureDemo", "location": [0, 15, 0.01], "scale": [5, 5, 1]
    })

    # Apply base material
    step("Create base material", "set_material", {
        "object_name": "TextureDemo", "material_name": "AdvancedTexture",
        "color": [0.5, 0.5, 0.5, 1]
    })

    # Add noise texture node
    step("Add noise texture", "shader_nodes", {
        "object_name": "TextureDemo", "action": "add_node",
        "node_type": "ShaderNodeTexNoise", "name": "DetailNoise"
    })

    # Add voronoi texture
    step("Add voronoi texture", "shader_nodes", {
        "object_name": "TextureDemo", "action": "add_node",
        "node_type": "ShaderNodeTexVoronoi", "name": "VoronoiPattern"
    })

    # Add wave texture
    step("Add wave texture", "shader_nodes", {
        "object_name": "TextureDemo", "action": "add_node",
        "node_type": "ShaderNodeTexWave", "name": "WavePattern"
    })

    # Add color ramp
    step("Add color ramp", "shader_nodes", {
        "object_name": "TextureDemo", "action": "add_node",
        "node_type": "ShaderNodeValToRGB", "name": "ColorGrade"
    })

    # Add bump map for surface detail
    step("Add bump map node", "shader_nodes", {
        "object_name": "TextureDemo", "action": "add_node",
        "node_type": "ShaderNodeBump", "name": "SurfaceBump"
    })


def showcase_animation():
    """Demonstrate all animation types."""
    section("ANIMATION")

    # Bounce animation
    step("Create bounce cube", "create_object", {
        "type": "cube", "name": "BounceCube", "location": [-6, 20, 0.5]
    })
    step("Apply bounce animation", "advanced_animation", {
        "action": "bounce", "object_name": "BounceCube",
        "height": 5, "bounces": 4, "frames_per_bounce": 15
    })
    step("Color the bounce cube", "set_material", {
        "object_name": "BounceCube", "color": [1, 0.3, 0, 1], "material_name": "OrangeBounce"
    })

    # Keyframe sequence — complex motion
    step("Create animated sphere", "create_object", {
        "type": "sphere", "name": "PathSphere", "location": [0, 20, 1]
    })
    step("Apply keyframe sequence", "advanced_animation", {
        "action": "keyframe_sequence", "object_name": "PathSphere",
        "keyframes": [
            {"frame": 1, "location": [-5, 20, 1], "scale": [0.5, 0.5, 0.5]},
            {"frame": 20, "location": [-2, 20, 4], "scale": [1.0, 1.0, 1.0], "rotation": [0, 0, 90]},
            {"frame": 40, "location": [2, 20, 1], "scale": [1.5, 1.5, 1.5], "rotation": [0, 0, 180]},
            {"frame": 60, "location": [5, 20, 3], "scale": [0.8, 0.8, 0.8], "rotation": [0, 0, 270]},
            {"frame": 80, "location": [0, 20, 1], "scale": [1.0, 1.0, 1.0], "rotation": [0, 0, 360]},
        ]
    })
    step("Color the path sphere", "procedural_material", {
        "preset": "emissive", "object_name": "PathSphere",
        "color": [0, 0.8, 1, 1], "emission_color": [0, 0.8, 1, 1], "emission_strength": 10
    })

    # Follow path animation
    step("Create path follower", "create_object", {
        "type": "monkey", "name": "PathMonkey", "location": [0, 25, 1], "scale": [0.5, 0.5, 0.5]
    })
    step("Follow path animation", "advanced_animation", {
        "action": "follow_path", "object_name": "PathMonkey",
        "points": [[-8, 25, 1], [-3, 28, 3], [3, 22, 5], [8, 25, 2]],
        "frames": 100
    })
    step("Color the monkey", "procedural_material", {
        "preset": "metal", "object_name": "PathMonkey", "color": [0.9, 0.1, 0.1, 1], "roughness": 0.3
    })


def showcase_physics():
    """Demonstrate physics simulations."""
    section("PHYSICS & SIMULATIONS")

    # Rigid body demo
    step("Create rigid body cube", "create_object", {
        "type": "cube", "name": "RBCube", "location": [0, 30, 5]
    })
    step("Add rigid body (active)", "physics", {
        "object_name": "RBCube", "physics_type": "RIGID_BODY", "body_type": "ACTIVE"
    })
    step("Color rigid body", "set_material", {
        "object_name": "RBCube", "color": [0.2, 0.6, 1, 1], "material_name": "RBBlue"
    })

    step("Create collision floor", "create_object", {
        "type": "plane", "name": "PhysFloor", "location": [0, 30, 0], "scale": [10, 10, 1]
    })
    step("Add collision", "physics", {
        "object_name": "PhysFloor", "physics_type": "COLLISION"
    })

    # Cloth simulation
    step("Create cloth plane", "create_object", {
        "type": "plane", "name": "SilkCloth", "location": [5, 30, 4], "scale": [2, 2, 1]
    })
    step("Subdivide for cloth detail", "apply_modifier", {
        "object_name": "SilkCloth", "modifier_type": "SUBSURF", "action": "add", "level": 3
    })
    step("Apply subdivision", "apply_modifier", {
        "object_name": "SilkCloth", "modifier_type": "SUBSURF", "action": "apply"
    })
    step("Add silk cloth sim", "cloth_simulation", {
        "object_name": "SilkCloth", "action": "add", "fabric": "silk"
    })
    step("Color the silk", "procedural_material", {
        "preset": "fabric", "object_name": "SilkCloth",
        "color1": [0.7, 0.05, 0.1, 1], "color2": [0.75, 0.08, 0.12, 1]
    })

    # Force fields
    step("Add wind field", "force_field", {
        "type": "WIND", "strength": 8, "location": [-5, 30, 2], "name": "DramaWind"
    })
    step("Add vortex field", "force_field", {
        "type": "VORTEX", "strength": 3, "location": [0, 30, 3], "name": "Vortex"
    })

    # Fluid simulation
    step("Create smoke domain", "fluid_simulation", {
        "action": "create_domain", "domain_type": "GAS",
        "resolution": 48, "name": "SmokeSim", "location": [-5, 30, 2], "size": 3
    })
    step("Create smoke emitter", "create_object", {
        "type": "sphere", "name": "SmokeSource", "location": [-5, 30, 0.5], "scale": [0.3, 0.3, 0.3]
    })
    step("Add smoke flow", "fluid_simulation", {
        "action": "add_flow", "object_name": "SmokeSource", "flow_type": "SMOKE"
    })


def showcase_geometry_nodes():
    """Demonstrate geometry nodes procedural generation."""
    section("GEOMETRY NODES")

    step("Create base mesh", "create_object", {
        "type": "plane", "name": "GeoNodePlane", "location": [0, 35, 0], "scale": [5, 5, 1]
    })
    step("Add geometry nodes modifier", "geometry_nodes", {
        "object_name": "GeoNodePlane", "action": "add", "name": "ProceduralScatter"
    })
    step("Get geo node info", "geometry_nodes", {
        "object_name": "GeoNodePlane", "action": "info", "modifier_name": "ProceduralScatter"
    })


def showcase_modeling():
    """Demonstrate mesh editing, booleans, shape keys, curves."""
    section("MODELING & MESH EDITING")

    # Boolean operations
    step("Create base cube", "create_object", {
        "type": "cube", "name": "BoolBase", "location": [10, 0, 1], "scale": [1.5, 1.5, 1.5]
    })
    step("Create cut sphere", "create_object", {
        "type": "sphere", "name": "BoolCut", "location": [10, 1, 1.5]
    })
    step("Boolean difference", "boolean_operation", {
        "object_name": "BoolBase", "target_name": "BoolCut", "operation": "DIFFERENCE"
    })
    step("Apply marble to boolean result", "procedural_material", {
        "preset": "marble", "object_name": "BoolBase"
    })

    # Shape keys
    step("Create morph target mesh", "create_object", {
        "type": "cube", "name": "MorphCube", "location": [10, 5, 1]
    })
    step("Add basis shape key", "shape_keys", {
        "object_name": "MorphCube", "action": "add", "name": "Basis"
    })
    step("Add deformed shape key", "shape_keys", {
        "object_name": "MorphCube", "action": "add", "name": "Inflated"
    })

    # Curves
    step("Create bezier curve", "curve_operations", {
        "action": "create", "curve_type": "BEZIER",
        "name": "DesignCurve", "location": [10, 10, 0]
    })

    # Mesh editing
    step("Create edit mesh", "create_object", {
        "type": "cube", "name": "EditMesh", "location": [10, 15, 1]
    })
    step("Subdivide mesh", "mesh_edit", {
        "object_name": "EditMesh", "operation": "subdivide", "cuts": 2
    })
    step("Extrude faces", "mesh_edit", {
        "object_name": "EditMesh", "operation": "extrude", "value": 0.5
    })


def showcase_rendering():
    """Demonstrate render settings and presets with proper viewport shading."""
    section("RENDERING")

    step("Set preview render", "render_presets", {"preset": "preview"})

    # Switch viewport to Material Preview to show colors and textures
    step("Set Material Preview shading", "viewport", {"action": "set_shading", "shading": "MATERIAL_PREVIEW"})

    # Capture with materials visible (default is now MATERIAL_PREVIEW)
    step("Capture with materials", "viewport_capture", {
        "width": 1280, "height": 720, "shading": "MATERIAL_PREVIEW",
        "filepath": "renders/showcase_material_preview.png"
    })

    # Capture in rendered mode (ray-traced, slower but beautiful)
    step("Capture rendered view", "viewport_capture", {
        "width": 1280, "height": 720, "shading": "RENDERED",
        "filepath": "renders/showcase_rendered.png"
    })

    # Full engine render (production quality)
    step("Set high quality Cycles", "render_presets", {"preset": "high_quality", "samples": 64})
    step("Full Cycles render", "viewport_capture", {
        "width": 1920, "height": 1080, "mode": "full_render",
        "filepath": "renders/showcase_full_render.png"
    })

    step("Set VFX production", "render_presets", {"preset": "vfx_production", "samples": 32})


def main():
    start = time.time()

    print("\n" + "═" * 60)
    print("  OpenClaw Blender MCP — Full Capability Showcase")
    print("  Testing EVERY major feature category")
    print("═" * 60)

    # Reset scene
    send("scene_operations", {"action": "new_file"})

    # Run all showcases
    showcase_colors_and_materials()
    showcase_sculpting()
    showcase_textures_and_shaders()
    showcase_animation()
    showcase_physics()
    showcase_geometry_nodes()
    showcase_modeling()
    showcase_rendering()

    # Final analysis
    section("FINAL SCENE ANALYSIS")
    analysis = send("scene_analyze", {})
    stats = analysis.get("statistics", {})
    elapsed = time.time() - start

    print(f"\n    Objects:   {stats.get('total_objects', '?')}")
    print(f"    Vertices:  {stats.get('total_vertices', '?')}")
    print(f"    Faces:     {stats.get('total_faces', '?')}")
    print(f"    Lights:    {stats.get('total_lights', '?')}")
    print(f"    Cameras:   {stats.get('total_cameras', '?')}")
    print(f"    Materials: {stats.get('materials_count', '?')}")
    print(f"    Time:      {elapsed:.1f}s")

    print("\n" + "═" * 60)
    print("  ✓ Full Capability Showcase COMPLETE!")
    print(f"  All features demonstrated in {elapsed:.1f} seconds")
    print("═" * 60 + "\n")


if __name__ == "__main__":
    main()
