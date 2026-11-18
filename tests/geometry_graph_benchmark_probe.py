"""Blender-native same-file baseline/candidate evaluation."""
import array
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path
import bpy

repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo / "blender_addon"))
source_file = os.environ["BLENDER_GRAPH_DOGFOOD_SPEC"]
spec = json.loads(Path(source_file).read_text())
target = bpy.data.objects["SprayEmitter"]
frames = (1, 5, 10, 12, 15, 24, 48)

def metrics(frame):
    bpy.context.scene.frame_set(frame)
    bpy.context.view_layer.update()
    evaluated = target.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        coords = array.array("f", [0.0]) * (3 * len(mesh.vertices))
        mesh.vertices.foreach_get("co", coords)
        return (len(mesh.vertices), len(mesh.polygons),
                hashlib.sha256(coords.tobytes()).hexdigest())
    finally:
        evaluated.to_mesh_clear()

source = {frame: metrics(frame) for frame in frames}
assert sum(row[0] > 0 for row in source.values()) >= 3
module_path = os.environ["BLENDER_GRAPH_BRIDGE_MODULE"]
specification = importlib.util.spec_from_file_location("isolated_graph_bridge", module_path)
module = importlib.util.module_from_spec(specification)
specification.loader.exec_module(module)
response = module.handle_geometry_nodes({
    "action": "build_graph", "object_name": "SprayEmitter",
    "modifier_name": "SprayNodes", "spec": spec
})
success = isinstance(response, dict) and response.get("nodes") == 74
count = sum(metrics(f) == source[f] for f in frames) if success else 0
if os.environ["BLENDER_GRAPH_MODE"] == "candidate":
    assert success and count == len(frames), response
if os.environ["BLENDER_GRAPH_MODE"] == "baseline":
    assert not success, response
print("GRAPH_BENCHMARK_PROBE=" + json.dumps({
    "mode": os.environ["BLENDER_GRAPH_MODE"], "frames_matched": count,
    "frames_total": len(frames), "action_supported": success,
    "error": response.get("error") if isinstance(response, dict) else None
}, sort_keys=True))
