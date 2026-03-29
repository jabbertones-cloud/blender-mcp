#!/usr/bin/env python3
"""Debug: inspect actual material node trees to understand the magenta issue."""
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

# Detailed material debug
r = cmd({'command': 'execute_python', 'params': {'code': """
import bpy
# List all materials with their nodes
for mat in list(bpy.data.materials)[:20]:
    if not mat.use_nodes:
        print(f"MAT {mat.name}: no nodes")
        continue
    nodes = [(n.name, n.type, n.label) for n in mat.node_tree.nodes]
    links_info = [(l.from_node.name, l.from_socket.name, l.to_node.name, l.to_socket.name) for l in mat.node_tree.links]
    print(f"MAT {mat.name}:")
    print(f"  Nodes: {nodes}")
    print(f"  Links: {links_info}")
    # Check BSDF base color
    for n in mat.node_tree.nodes:
        if n.type == 'BSDF_PRINCIPLED':
            bc = list(n.inputs['Base Color'].default_value)
            met = n.inputs['Metallic'].default_value
            print(f"  BSDF BaseColor={bc[:3]} Metallic={met}")
    # Check image textures
    for n in mat.node_tree.nodes:
        if n.type == 'TEX_IMAGE':
            img = n.image
            if img:
                print(f"  IMG: {img.name} size={img.size[:]} packed={img.packed_file is not None}")
            else:
                print(f"  IMG: None (missing)")
"""}})
print("DEBUG:", str(r))
