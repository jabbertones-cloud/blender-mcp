"""
Portfolio Scene 3: Highway Rear-End Chain Reaction
Case: Thompson v. ABC Trucking — 2026-CV-11290
Vehicle 1 (Red sedan) stopped in traffic
Vehicle 2 (Silver SUV) stopped behind V1
Vehicle 3 (Blue semi-truck) rear-ends V2 at 55 mph, pushing V2 into V1
Chain reaction — 3 vehicles, speed/distance analysis

Demonstrates: multi-vehicle, speed indicators, braking distance, highway template
"""
import bpy
import math
import os
import sys

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

addon_dir = os.path.expanduser("~/Library/Application Support/Blender/5.1/scripts/addons")
if addon_dir not in sys.path:
    sys.path.insert(0, addon_dir)
from openclaw_blender_bridge import handle_forensic_scene

# ── Build highway straight ──
handle_forensic_scene({
    "action": "add_scene_template",
    "template": "highway_straight"
})

# ── V1: Red sedan (stopped, front of chain) ──
handle_forensic_scene({
    "action": "place_vehicle",
    "name": "V1_Sedan_Thompson",
    "vehicle_type": "sedan",
    "location": [5, -1.8, 0],
    "rotation": 90,
    "color": [0.65, 0.07, 0.05, 1],
    "damaged": True,
    "impact_side": "rear",
    "severity": "moderate"
})

# ── V2: Silver SUV (middle, pushed into V1) ──
handle_forensic_scene({
    "action": "place_vehicle",
    "name": "V2_SUV_Williams",
    "vehicle_type": "suv",
    "location": [-2, -1.5, 0],
    "rotation": 85,
    "color": [0.6, 0.6, 0.58, 1],
    "damaged": True,
    "impact_side": "rear",
    "severity": "severe"
})

# ── V3: Blue truck (rear-ending vehicle) ──
handle_forensic_scene({
    "action": "place_vehicle",
    "name": "V3_Truck_ABC",
    "vehicle_type": "truck",
    "location": [-12, -2.2, 0],
    "rotation": 88,
    "color": [0.05, 0.1, 0.5, 1],
    "damaged": True,
    "impact_side": "front",
    "severity": "severe"
})

# ── Skid marks (V3 — long skid, late braking at highway speed) ──
handle_forensic_scene({
    "action": "add_impact_marker",
    "marker_type": "skid_mark",
    "start": [-55, -2.2, 0.005],
    "end": [-14, -2.2, 0.005],
    "name": "V3_SkidMark_Long",
    "skid_width": 0.28
})

# ── Impact points ──
# Impact 1: V3 rear-ends V2
handle_forensic_scene({
    "action": "add_impact_marker",
    "marker_type": "impact_point",
    "location": [-7, -1.8, 0],
    "name": "POI_Impact_V3_V2"
})

# Impact 2: V2 pushed into V1
handle_forensic_scene({
    "action": "add_impact_marker",
    "marker_type": "impact_point",
    "location": [1, -1.7, 0],
    "name": "POI_Impact_V2_V1"
})

# ── Debris fields ──
handle_forensic_scene({
    "action": "add_impact_marker",
    "marker_type": "debris",
    "location": [-6, -2, 0],
    "count": 20,
    "radius": 3,
    "debris_type": "mixed"
})
handle_forensic_scene({
    "action": "add_impact_marker",
    "marker_type": "debris",
    "location": [2, -1.5, 0],
    "count": 15,
    "radius": 2.5,
    "debris_type": "mixed"
})

# ── Fluid spill ──
handle_forensic_scene({
    "action": "add_impact_marker",
    "marker_type": "fluid_spill",
    "location": [-9, -2.5, 0],
    "spill_type": "oil",
    "radius": 2.0
})

# ── Speed labels with trajectory arrows ──
# V3 trajectory (heading east at 55 mph)
bpy.ops.mesh.primitive_cylinder_add(radius=0.08, depth=40, location=(-35, -2.2, 0.2))
arr3 = bpy.context.active_object
arr3.name = "V3_Trajectory"
arr3.rotation_euler = (math.radians(90), 0, math.radians(90))
mat3 = bpy.data.materials.new("V3_Path")
mat3.use_nodes = True
mat3.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.1, 0.2, 0.9, 0.6)
mat3.node_tree.nodes["Principled BSDF"].inputs["Alpha"].default_value = 0.6
try: mat3.surface_render_method = 'DITHERED'
except: pass
arr3.data.materials.append(mat3)

# V3 speed label
bpy.ops.object.text_add(location=(-40, -4.5, 0.3))
s3 = bpy.context.active_object
s3.data.body = "V3 (Truck): 55 mph"
s3.data.size = 0.8
s3.name = "V3_Speed"
s3_mat = bpy.data.materials.new("V3Spd_Mat")
s3_mat.use_nodes = True
s3_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.1, 0.2, 0.9, 1)
s3_mat.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 0.5
s3_mat.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = (0.1, 0.2, 0.9, 1)
s3.data.materials.append(s3_mat)

# V1/V2 stationary labels
bpy.ops.object.text_add(location=(3, 0.5, 0.3))
s1 = bpy.context.active_object
s1.data.body = "V1: STOPPED"
s1.data.size = 0.6
s1.name = "V1_Status"
s1_mat = bpy.data.materials.new("V1Spd_Mat")
s1_mat.use_nodes = True
s1_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.9, 0.15, 0.1, 1)
s1_mat.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 0.5
s1_mat.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = (0.9, 0.15, 0.1, 1)
s1.data.materials.append(s1_mat)

bpy.ops.object.text_add(location=(-4, 0.5, 0.3))
s2 = bpy.context.active_object
s2.data.body = "V2: STOPPED"
s2.data.size = 0.6
s2.name = "V2_Status"
s2_mat = bpy.data.materials.new("V2Spd_Mat")
s2_mat.use_nodes = True
s2_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.5, 0.5, 0.48, 1)
s2_mat.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 0.5
s2_mat.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = (0.5, 0.5, 0.48, 1)
s2.data.materials.append(s2_mat)

# ── Braking distance annotation ──
bpy.ops.object.text_add(location=(-35, -5.5, 0.15))
bd = bpy.context.active_object
bd.data.body = "Braking Distance: 131 ft (40m)"
bd.data.size = 0.55
bd.name = "BrakingDist_Label"
bd_mat = bpy.data.materials.new("BD_Mat")
bd_mat.use_nodes = True
bd_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (1, 0.8, 0, 1)
bd_mat.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 0.4
bd_mat.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = (1, 0.8, 0, 1)
bd.data.materials.append(bd_mat)

# ── Color legend ──
bpy.ops.object.text_add(location=(-50, -9, 0.03))
leg = bpy.context.active_object
leg.data.body = "RED = V1 (Plaintiff)   SILVER = V2   BLUE = V3 (Defendant Truck)"
leg.data.size = 0.5
leg.name = "Color_Legend"
leg_mat = bpy.data.materials.new("Legend_Mat")
leg_mat.use_nodes = True
leg_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.9, 0.9, 0.9, 1)
leg.data.materials.append(leg_mat)

# ── Measurement grid ──
handle_forensic_scene({
    "action": "add_measurement_grid",
    "size": 60,
    "spacing": 10
})

# ── Exhibit overlay ──
handle_forensic_scene({
    "action": "add_exhibit_overlay",
    "case_number": "Case No. 2026-CV-11290",
    "exhibit_id": "Exhibit C — Chain Reaction Analysis",
    "expert_name": "OpenClaw Forensic Animation",
    "firm_name": "Certified Reconstruction Analysis",
    "disclaimer": "DEMONSTRATIVE EXHIBIT — FOR ILLUSTRATIVE PURPOSES ONLY",
    "show_scale_bar": True,
    "scale_bar_length": 20,
    "show_timestamp": True,
    "timestamp": "Incident: 2025-11-22 16:05 EST"
})

# ── Lighting + Render ──
handle_forensic_scene({
    "action": "set_time_of_day",
    "time": "day",
    "sun_energy": 1.5,
    "sky_strength": 0.25,
    "fill_energy": 0.3
})
handle_forensic_scene({
    "action": "setup_courtroom_render",
    "preset": "presentation"
})

# ── Cameras ──
bpy.ops.object.camera_add(location=(-5, 0, 50))
c1 = bpy.context.active_object
c1.name = "Cam_BirdEye"
c1.data.lens = 40
c1.rotation_euler = (0, 0, 0)

bpy.ops.object.camera_add(location=(-50, -2.2, 1.5))
c2 = bpy.context.active_object
c2.name = "Cam_TruckDriverPOV"
c2.data.lens = 35
c2.rotation_euler = (math.radians(88), 0, math.radians(-90))

bpy.ops.object.camera_add(location=(-5, 12, 6))
c3 = bpy.context.active_object
c3.name = "Cam_Witness"
c3.data.lens = 50
bpy.ops.object.empty_add(type="PLAIN_AXES", location=(-3, -1.8, 1))
tgt = bpy.context.active_object
tgt.name = "ChainTarget"
tgt.hide_viewport = True
tgt.hide_render = True
t3 = c3.constraints.new("TRACK_TO")
t3.target = tgt
t3.track_axis = "TRACK_NEGATIVE_Z"
t3.up_axis = "UP_Y"

bpy.ops.object.camera_add(location=(-7, -6, 2))
c4 = bpy.context.active_object
c4.name = "Cam_ImpactCloseup"
c4.data.lens = 35
c4.data.dof.use_dof = True
c4.data.dof.focus_object = tgt
c4.data.dof.aperture_fstop = 3.5
t4 = c4.constraints.new("TRACK_TO")
t4.target = tgt
t4.track_axis = "TRACK_NEGATIVE_Z"
t4.up_axis = "UP_Y"

bpy.ops.object.camera_add(location=(30, -25, 15))
c5 = bpy.context.active_object
c5.name = "Cam_Wide"
c5.data.lens = 24
t5 = c5.constraints.new("TRACK_TO")
t5.target = tgt
t5.track_axis = "TRACK_NEGATIVE_Z"
t5.up_axis = "UP_Y"

# ── Hide signals ──
for obj in bpy.data.objects:
    if "Signal" in obj.name: obj.hide_render = True; obj.hide_viewport = True

# ── Save + Render ──
blend_path = os.path.expanduser("~/claw-architect/openclaw-blender-mcp/renders/portfolio_scene3.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)

render_dir = os.path.expanduser("~/claw-architect/openclaw-blender-mcp/renders/portfolio/")
os.makedirs(render_dir, exist_ok=True)
cameras = ["Cam_BirdEye", "Cam_TruckDriverPOV", "Cam_Witness", "Cam_ImpactCloseup", "Cam_Wide"]
for i, cn in enumerate(cameras):
    co = bpy.data.objects.get(cn)
    if co:
        scene.camera = co
        scene.render.filepath = os.path.join(render_dir, f"scene3_{i+1:02d}_{cn}.png")
        bpy.ops.render.render(write_still=True)
        print(f"Rendered: {cn}")

print("SCENE 3 COMPLETE")
__result__ = {"status": "scene3_complete", "cameras": len(cameras)}
