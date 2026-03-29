#!/usr/bin/env python3
"""Probe Blender's EEVEE settings via bridge to find correct shadow/AO attribute names."""
import socket, json

def send(command, params=None):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(30)
    s.connect(("127.0.0.1", 9876))
    s.sendall(json.dumps({"id": "1", "command": command, "params": params or {}}).encode())
    raw = b""
    while True:
        chunk = s.recv(65536)
        if not chunk:
            break
        raw += chunk
        try:
            resp = json.loads(raw.decode())
            s.close()
            return resp
        except:
            continue
    s.close()
    return json.loads(raw.decode())

code = r"""
import bpy

scene = bpy.context.scene
eevee = scene.eevee
out = []

# EEVEE shadow/AO/bloom attributes
out.append("=== EEVEE SETTINGS ===")
for a in sorted(dir(eevee)):
    if a.startswith('_'):
        continue
    low = a.lower()
    if any(k in low for k in ('shadow', 'ao', 'gtao', 'bloom', 'ambient', 'occlusion', 'ray')):
        try:
            val = getattr(eevee, a)
            out.append(f"  eevee.{a} = {val}")
        except Exception as e:
            out.append(f"  eevee.{a} = ERROR: {e}")

# Sun light shadow attributes
out.append("\n=== SUN LIGHT ===")
for obj in bpy.data.objects:
    if obj.type == 'LIGHT' and obj.data.type == 'SUN':
        out.append(f"  Light: {obj.name}")
        for a in sorted(dir(obj.data)):
            if a.startswith('_'):
                continue
            if 'shadow' in a.lower() or 'contact' in a.lower():
                try:
                    val = getattr(obj.data, a)
                    out.append(f"  sun.{a} = {val}")
                except Exception as e:
                    out.append(f"  sun.{a} = ERROR: {e}")
        break

# Current render engine
out.append(f"\n=== RENDER ENGINE: {scene.render.engine} ===")

result = "\n".join(out)
with open("/tmp/eevee_probe.txt", "w") as f:
    f.write(result)
"""

resp = send("execute_python", {"code": code})
print("Bridge response:", resp.get("result", resp))
