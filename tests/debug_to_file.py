#!/usr/bin/env python3
import socket, json

def cmd(c, t=30):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(t)
    try:
        s.connect(('127.0.0.1', 9876))
        s.sendall((json.dumps(c) + '\n').encode())
        d = b''
        while True:
            ch = s.recv(16384)
            if not ch: break
            d += ch
            try:
                json.loads(d.decode())
                break
            except: continue
        return json.loads(d.decode()).get('result', {})
    except Exception as e:
        return {'error': str(e)}
    finally:
        s.close()

r = cmd({'command': 'execute_python', 'params': {'code': """
import bpy
out = []
for mat in list(bpy.data.materials)[:30]:
    if not mat.use_nodes:
        out.append(f"MAT {mat.name}: no nodes")
        continue
    nodes = [(n.name, n.type) for n in mat.node_tree.nodes]
    out.append(f"MAT {mat.name}: {nodes}")
    for n in mat.node_tree.nodes:
        if n.type == 'BSDF_PRINCIPLED':
            bc = list(n.inputs['Base Color'].default_value)
            out.append(f"  BSDF BC={bc[:3]}")
            # Check if Base Color input has a link
            for link in mat.node_tree.links:
                if link.to_node == n and link.to_socket.name == 'Base Color':
                    out.append(f"  BC LINKED FROM: {link.from_node.name} ({link.from_node.type})")
        if n.type == 'TEX_IMAGE':
            if n.image:
                out.append(f"  IMG: {n.image.name} size={list(n.image.size)} packed={n.image.packed_file is not None}")
            else:
                out.append(f"  IMG: MISSING")

out.append("---OBJECTS---")
for obj in bpy.data.objects:
    if obj.type == 'MESH':
        root = obj
        while root.parent:
            root = root.parent
        mats = [s.material.name if s.material else 'NONE' for s in obj.material_slots]
        out.append(f"OBJ {obj.name} root={root.name} mats={mats}")

with open('/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders/debug_mats.txt', 'w') as f:
    f.write('\\n'.join(out))
"""}})
print("DONE:", r)
