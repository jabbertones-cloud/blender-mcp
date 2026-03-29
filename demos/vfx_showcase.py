#!/usr/bin/env python3
"""
OpenClaw Blender MCP — VFX Showcase Demo
==========================================
Creates an impressive cinematic scene entirely via MCP commands.
Demonstrates: procedural materials, batch ops, scene templates,
advanced animation, force fields, lighting, and rendering.

Run: python3 demos/vfx_showcase.py
"""

import json
import socket
import sys
import time

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
    print(f"  → {msg}...", end=" ", flush=True)
    result = send(command, params)
    if isinstance(result, dict) and "error" in result:
        print(f"⚠ {result['error']}")
    else:
        print("✓")
    return result


def main():
    print("\n═══════════════════════════════════════════════════")
    print("  OpenClaw Blender MCP — VFX Showcase Demo")
    print("═══════════════════════════════════════════════════\n")

    # 1. Setup cinematic scene
    print("[1/8] Setting up cinematic scene template...")
    step("Load cinematic template", "scene_template", {"template": "cinematic"})

    # 2. Create ground with marble material
    print("\n[2/8] Creating environment...")
    step("Create ground plane", "create_object", {"type": "plane", "name": "MarbleFloor", "location": [0, 0, 0], "scale": [15, 15, 1]})
    step("Apply marble material", "procedural_material", {"preset": "marble", "object_name": "MarbleFloor", "scale": 2.0})

    # 3. Create hero objects with procedural materials
    print("\n[3/8] Creating hero objects with materials...")
    step("Create metal sphere", "create_object", {"type": "sphere", "name": "MetalSphere", "location": [0, 0, 1.5], "scale": [1.5, 1.5, 1.5]})
    step("Apply metal material", "procedural_material", {"preset": "metal", "object_name": "MetalSphere", "roughness": 0.15, "color": [0.9, 0.85, 0.7, 1]})
    step("Subdivide sphere", "apply_modifier", {"object_name": "MetalSphere", "modifier_type": "SUBSURF", "action": "add", "level": 3})

    step("Create glass cube", "create_object", {"type": "cube", "name": "GlassCube", "location": [-3, 0, 1], "scale": [1, 1, 1]})
    step("Apply glass material", "procedural_material", {"preset": "glass", "object_name": "GlassCube", "ior": 1.5})

    step("Create concrete pillar", "create_object", {"type": "cylinder", "name": "Pillar", "location": [3, 0, 2], "scale": [0.5, 0.5, 2]})
    step("Apply concrete material", "procedural_material", {"preset": "concrete", "object_name": "Pillar"})

    # 4. Batch create decorative objects
    print("\n[4/8] Batch creating decorative elements...")
    step("Batch create small spheres", "batch_operations", {
        "action": "create",
        "objects": [
            {"type": "sphere", "location": [-5, -3, 0.3], "scale": [0.3, 0.3, 0.3], "name": "Decor1"},
            {"type": "sphere", "location": [-4, -4, 0.3], "scale": [0.25, 0.25, 0.25], "name": "Decor2"},
            {"type": "sphere", "location": [-3, -3.5, 0.3], "scale": [0.35, 0.35, 0.35], "name": "Decor3"},
            {"type": "cube", "location": [4, -3, 0.3], "scale": [0.3, 0.3, 0.3], "name": "Decor4"},
            {"type": "cube", "location": [5, -4, 0.3], "scale": [0.25, 0.25, 0.25], "name": "Decor5"},
            {"type": "cone", "location": [4.5, -2, 0.4], "scale": [0.2, 0.2, 0.4], "name": "Decor6"},
        ]
    })
    step("Apply emissive to decorations", "procedural_material", {
        "preset": "emissive", "object_name": "Decor1",
        "color": [0, 0.5, 1, 1], "emission_color": [0, 0.5, 1, 1], "emission_strength": 15
    })

    # 5. Add physics drama
    print("\n[5/8] Adding physics & force fields...")
    step("Add wind field", "force_field", {"type": "WIND", "strength": 5, "location": [-5, 0, 2]})
    step("Add turbulence", "force_field", {"type": "TURBULENCE", "strength": 2, "location": [0, 0, 3], "size": 3})

    # 6. Turntable camera animation
    print("\n[6/8] Setting up turntable camera animation...")
    step("Create turntable", "advanced_animation", {
        "action": "turntable", "target": "MetalSphere",
        "frames": 120, "radius": 10, "height": 5
    })

    # 7. Add 3D text
    print("\n[7/8] Adding title text...")
    step("Create title", "text_object", {
        "action": "create", "text": "OpenClaw VFX",
        "location": [0, 5, 3], "size": 1.5, "extrude": 0.15
    })

    # 8. Configure render
    print("\n[8/8] Configuring production render settings...")
    step("Set VFX production preset", "render_presets", {"preset": "high_quality", "samples": 128})

    # Analyze final scene
    print("\n─── Scene Analysis ───")
    analysis = send("scene_analyze", {})
    stats = analysis.get("statistics", {})
    print(f"  Objects:  {stats.get('total_objects', '?')}")
    print(f"  Vertices: {stats.get('total_vertices', '?')}")
    print(f"  Faces:    {stats.get('total_faces', '?')}")
    print(f"  Lights:   {stats.get('total_lights', '?')}")
    print(f"  Cameras:  {stats.get('total_cameras', '?')}")
    print(f"  Materials: {stats.get('materials_count', '?')}")

    print("\n═══════════════════════════════════════════════════")
    print("  ✓ VFX Showcase scene created successfully!")
    print("  Press Space in Blender to play the turntable animation")
    print("  Press F12 to render a frame")
    print("═══════════════════════════════════════════════════\n")


if __name__ == "__main__":
    main()
