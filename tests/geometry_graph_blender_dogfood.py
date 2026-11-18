"""Run with Blender --background --disable-autoexec <private .blend> --python this_file.

The test consumes a LOCAL spec through BLENDER_GRAPH_DOGFOOD_SPEC. Neither
the artist's scene nor her extracted node graph belongs in the Git repository.
"""
import array
import copy
import hashlib
import json
import os
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender_addon"))
from graph_transaction import build_graph

spec_path = os.environ.get("BLENDER_GRAPH_DOGFOOD_SPEC")
assert spec_path and Path(spec_path).is_file(), "Set BLENDER_GRAPH_DOGFOOD_SPEC to the local approved fixture"
spec = json.loads(Path(spec_path).read_text())
obj = bpy.data.objects["SprayEmitter"]
modifier = obj.modifiers["SprayNodes"]
old_group = modifier.node_group
assert old_group
scene = bpy.context.scene
frames = [int(x) for x in os.environ.get("BLENDER_GRAPH_DOGFOOD_FRAMES", "1,5,10,12,15,24,48").split(",")]

def capture(frame):
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        values = array.array("f", [0.0]) * (3 * len(mesh.vertices))
        mesh.vertices.foreach_get("co", values)
        return len(mesh.vertices), len(mesh.polygons), hashlib.sha256(values.tobytes()).hexdigest()
    finally:
        evaluated.to_mesh_clear()

source = {frame: capture(frame) for frame in frames}
assert any(record[0] > 0 for record in source.values()), "An all-empty test is not sufficient"
expected_curves = int(os.environ.get("BLENDER_GRAPH_DOGFOOD_CURVES", "2"))
result = build_graph({"object_name": obj.name, "modifier_name": modifier.name, "spec": spec})
assert result["nodes"] == 74 and result["links"] == 113, result
assert result["preserved_inputs"] == 18 and result["rebound_curves"] == expected_curves, result
candidate = {frame: capture(frame) for frame in frames}
assert candidate == source, {"source": source, "candidate": candidate}
good_group = modifier.node_group
saved_paths = [(fc, fc.data_path) for layer in obj.animation_data.action.layers
               for strip in layer.strips for bag in strip.channelbags
               if bag.slot_handle == obj.animation_data.action_slot.handle
               for fc in bag.fcurves]
# Adversarial: malformed graph cannot change current structure or animation.
bad = copy.deepcopy(spec)
bad["nodes"][0]["type"] = "GeometryNodeDefinitelyDoesNotExist"
try:
    build_graph({"object_name": obj.name, "modifier_name": modifier.name, "spec": bad})
    raise AssertionError("Invalid node type accepted")
except (ValueError, TypeError, RuntimeError):
    pass
assert modifier.node_group == good_group and saved_paths == [(fc, fc.data_path) for fc, _ in saved_paths]
rejected_spec = copy.deepcopy(spec)
rejected_spec["inputs"][0]["name"] = "RenamedWithoutAgreement"
try:
    build_graph({"object_name": obj.name, "modifier_name": modifier.name, "spec": rejected_spec})
    raise AssertionError("Incompatible modifier sockets accepted")
except (ValueError, TypeError, RuntimeError):
    pass
assert modifier.node_group == good_group
assert {frame: capture(frame) for frame in frames} == source
# Original remains unchanged, and only the new group is used by the modifier.
assert old_group is not good_group
assert bpy.data.node_groups.get(old_group.name) is old_group
print("GRAPH_DOGFOOD_PASS=" + json.dumps({
    "scene": Path(bpy.data.filepath).name,
    "blender": bpy.app.version_string,
    "frames": len(frames),
    "nonempty_frames": sum(v[0] > 0 for v in source.values()),
    "nodes": result["nodes"],
    "links": result["links"],
    "inputs_preserved": result["preserved_inputs"],
    "curves_rebound": result["rebound_curves"],
    "hash_match": True,
    "invalid_node_rejected": True,
    "mismatched_interface_rejected": True,
}, sort_keys=True))
