#!/usr/bin/env python3
import socket, json, time

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(10)
s.connect(("127.0.0.1", 9876))

code = """
import bpy
out_path = "/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders/cam_check.txt"
lines = []
cams = [o for o in bpy.data.objects if o.type == "CAMERA"]
lines.append(f"Cameras found: {len(cams)}")
for c in cams:
    lines.append(f"  {c.name} at {[round(v,1) for v in c.location]}, lens={c.data.lens}")
lines.append(f"Total objects: {len(bpy.data.objects)}")
lines.append(f"Active camera: {bpy.context.scene.camera.name if bpy.context.scene.camera else 'None'}")
with open(out_path, "w") as f:
    f.write("\\n".join(lines))
"""

payload = json.dumps({"id": "1", "command": "execute_python", "params": {"code": code}})
s.sendall(payload.encode())
raw = b""
while True:
    chunk = s.recv(65536)
    if not chunk:
        break
    raw += chunk
    try:
        json.loads(raw.decode())
        break
    except:
        continue
s.close()

time.sleep(0.5)
with open("/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders/cam_check.txt") as f:
    print(f.read())
