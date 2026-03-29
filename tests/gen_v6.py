#!/usr/bin/env python3
"""Generate the v6 render script cleanly."""
import os
OUT = os.path.expanduser("~/claw-architect/openclaw-blender-mcp/tests/portfolio_render_v6.py")

parts = []

# ═══ HEADER + UTILS ═══
parts.append(r'''#!/usr/bin/env python3
"""Portfolio Scene Renderer v6 — Professional Forensic Quality
v6 fixes: per-vehicle colors, custom DriverPOV 1.05m/50mm, buildings+trees+curbs,
road markings, stop signs, street lights, Cam_Orbit fix, 128spl, reduced glass
"""
import socket, json, time, os, subprocess, sys

HOST = "127.0.0.1"
PORT = 9876
LOG = os.path.expanduser("~/claw-architect/openclaw-blender-mcp/renders/v6_render_log.txt")
RENDER_DIR = os.path.expanduser("~/claw-architect/openclaw-blender-mcp/renders/v6/")
BLEND_DIR = os.path.expanduser("~/claw-architect/openclaw-blender-mcp/renders/")
os.makedirs(RENDER_DIR, exist_ok=True)
with open(LOG, "w") as f: f.write("")

def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f: f.write(line + "\n")
''')

with open(OUT, 'w') as f:
    for p in parts:
        f.write(p)
print(f"Phase 1: header written to {OUT}")
