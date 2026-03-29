"""
Portfolio Scene 2: Pedestrian Crosswalk Incident
Case: Martinez v. City Transit — 2026-CV-07833
Vehicle 1 (White delivery van) traveling westbound at 32 mph in 25 mph zone
Pedestrian crossing at marked crosswalk — struck in crosswalk
Key evidence: sight-line obstruction by parked SUV

Demonstrates: sight-line analysis, pedestrian placement, speed zone violation
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

# ── Build straight road with crosswalk ──
handle_forensic_scene({
    "action": "build_road",
    "road_type": "straight",
    "lanes": 2,
    "width": 7,
    "start": [-40, 0, 0],
    "end": [40, 0, 0]
})

# ── Crosswalk stripes ──
crosswalk_mat = bpy.data.materials.new("Crosswalk_Mat")
crosswalk_mat.use_nodes = True
crosswalk_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.95, 0.95, 0.95, 1)
crosswalk_mat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.7

for i in range(6):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -3 + i * 1.2, 0.008))
    stripe = bpy.context.active_object
    stripe.name = f"Crosswalk_Stripe_{i}"
    stripe.scale = (0.4, 0.5, 0.005)
    stripe.data.materials.append(crosswalk_mat)

# ── Delivery Van (V1) — at final rest position, past crosswalk ──
v1_result = handle_forensic_scene({
    "action": "place_vehicle",
    "name": "V1_DeliveryVan",
    "vehicle_type": "van",
    "location": [12, -1.8, 0],
    "rotation": 265,  # Heading west, slightly swerved
    "color": [0.85, 0.85, 0.82, 1],  # White
    "damaged": True,
    "impact_side": "front",
    "severity": "moderate"
})

# ── Parked SUV (sight-line obstruction) ──
handle_forensic_scene({
    "action": "place_vehicle",
    "name": "Parked_SUV_Obstruction",
    "vehicle_type": "suv",
    "location": [-4, -4.5, 0],
    "rotation": 270,  # Parked facing west
    "color": [0.15, 0.15, 0.15, 1],  # Dark gray
    "label": "Parked Vehicle (Sight Obstruction)"
})

# ── Pedestrian figure at impact point ──
handle_forensic_scene({
    "action": "place_figure",
    "name": "Pedestrian_Martinez",
    "location": [1.5, -0.5, 0],
    "pose": "walking",
    "shirt_color": [0.8, 0.2, 0.1, 1],  # Red shirt for visibility
    "pants_color": [0.15, 0.15, 0.25, 1],
    "label": "Pedestrian — A. Martinez"
})

# ── Sight-line visualization ──
# Line from van driver to pedestrian (BLOCKED by parked SUV)
# Red line = obstructed view
bpy.ops.mesh.primitive_cylinder_add(radius=0.03, depth=1, location=(0, 0, 1.5))
sight_blocked = bpy.context.active_object
sight_blocked.name = "SightLine_Blocked"
# Position from van approach to pedestrian through parked SUV
start_pt = [-8, -1.8, 1.5]
end_pt = [1.5, -0.5, 1.0]
mid = [(s+e)/2 for s, e in zip(start_pt, end_pt)]
dx = end_pt[0] - start_pt[0]
dy = end_pt[1] - start_pt[1]
dz = end_pt[2] - start_pt[2]
length = math.sqrt(dx*dx + dy*dy + dz*dz)
sight_blocked.location = mid
sight_blocked.scale = (1, 1, length/2)
angle_xy = math.atan2(dy, dx)
angle_z = math.atan2(math.sqrt(dx*dx + dy*dy), dz)
sight_blocked.rotation_euler = (angle_z, 0, angle_xy + math.radians(90))
blocked_mat = bpy.data.materials.new("SightBlocked_Mat")
blocked_mat.use_nodes = True
blocked_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (1, 0, 0, 0.5)
blocked_mat.node_tree.nodes["Principled BSDF"].inputs["Alpha"].default_value = 0.5
blocked_mat.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 1.0
blocked_mat.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = (1, 0, 0, 1)
try:
    blocked_mat.surface_render_method = 'DITHERED'
except:
    pass
sight_blocked.data.materials.append(blocked_mat)

# Green line = clear view (further back, before obstruction)
bpy.ops.mesh.primitive_cylinder_add(radius=0.03, depth=1, location=(0, 0, 1.5))
sight_clear = bpy.context.active_object
sight_clear.name = "SightLine_Clear"
start_clear = [-18, -1.8, 1.5]
end_clear = [1.5, -0.5, 1.0]
mid_c = [(s+e)/2 for s, e in zip(start_clear, end_clear)]
dx_c = end_clear[0] - start_clear[0]
dy_c = end_clear[1] - start_clear[1]
dz_c = end_clear[2] - start_clear[2]
length_c = math.sqrt(dx_c*dx_c + dy_c*dy_c + dz_c*dz_c)
sight_clear.location = mid_c
sight_clear.scale = (1, 1, length_c/2)
angle_xy_c = math.atan2(dy_c, dx_c)
angle_z_c = math.atan2(math.sqrt(dx_c*dx_c + dy_c*dy_c), dz_c)
sight_clear.rotation_euler = (angle_z_c, 0, angle_xy_c + math.radians(90))
clear_mat = bpy.data.materials.new("SightClear_Mat")
clear_mat.use_nodes = True
clear_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0, 1, 0.3, 0.5)
clear_mat.node_tree.nodes["Principled BSDF"].inputs["Alpha"].default_value = 0.5
clear_mat.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 1.0
clear_mat.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = (0, 1, 0.3, 1)
try:
    clear_mat.surface_render_method = 'DITHERED'
except:
    pass
sight_clear.data.materials.append(clear_mat)

# ── Sight-line labels ──
bpy.ops.object.text_add(location=(-14, -3.5, 2.0))
sl_label = bpy.context.active_object
sl_label.data.body = "OBSTRUCTED\nSIGHT LINE"
sl_label.data.size = 0.5
sl_label.name = "SightLine_Label"
sl_mat = bpy.data.materials.new("SL_Label_Mat")
sl_mat.use_nodes = True
sl_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (1, 0.2, 0.1, 1)
sl_mat.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 0.8
sl_mat.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = (1, 0.2, 0.1, 1)
sl_label.data.materials.append(sl_mat)

# ── Speed zone sign text ──
bpy.ops.object.text_add(location=(-25, -5, 2.5))
speed_sign = bpy.context.active_object
speed_sign.data.body = "SPEED\nLIMIT\n25"
speed_sign.data.size = 0.5
speed_sign.name = "SpeedLimit_Sign"
speed_sign.rotation_euler = (math.radians(90), 0, 0)
sign_mat = bpy.data.materials.new("SpeedSign_Mat")
sign_mat.use_nodes = True
sign_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.9, 0.9, 0.9, 1)
speed_sign.data.materials.append(sign_mat)

# V1 speed label (over limit)
bpy.ops.object.text_add(location=(-15, 0, 0.3))
spd_label = bpy.context.active_object
spd_label.data.body = "V1: 32 mph (7 over limit)"
spd_label.data.size = 0.6
spd_label.name = "V1_Speed"
spd_mat = bpy.data.materials.new("V1Speed_Mat")
spd_mat.use_nodes = True
spd_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (1, 0.3, 0, 1)
spd_mat.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 0.5
spd_mat.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = (1, 0.3, 0, 1)
spd_label.data.materials.append(spd_mat)

# ── Skid marks ──
handle_forensic_scene({
    "action": "add_impact_marker",
    "marker_type": "skid_mark",
    "start": [18, -1.8, 0.005],
    "end": [5, -1.8, 0.005],
    "name": "V1_SkidMark"
})

# ── Impact marker ──
handle_forensic_scene({
    "action": "add_impact_marker",
    "marker_type": "impact_point",
    "location": [1.5, -0.5, 0],
    "name": "POI_PedestrianImpact"
})

# ── Debris ──
handle_forensic_scene({
    "action": "add_impact_marker",
    "marker_type": "debris",
    "location": [3, -1, 0],
    "count": 12,
    "radius": 2.5,
    "debris_type": "plastic"
})

# ── Measurement grid ──
handle_forensic_scene({
    "action": "add_measurement_grid",
    "size": 40,
    "spacing": 5
})

# ── Exhibit overlay ──
handle_forensic_scene({
    "action": "add_exhibit_overlay",
    "case_number": "Case No. 2026-CV-07833",
    "exhibit_id": "Exhibit B — Pedestrian Crosswalk Analysis",
    "expert_name": "OpenClaw Forensic Animation",
    "firm_name": "Certified Reconstruction Analysis",
    "disclaimer": "DEMONSTRATIVE EXHIBIT — FOR ILLUSTRATIVE PURPOSES ONLY",
    "show_scale_bar": True,
    "scale_bar_length": 10,
    "show_timestamp": True,
    "timestamp": "Incident: 2026-02-08 08:15 EST"
})

# ── Sidewalk / curb ──
curb_mat = bpy.data.materials.new("Curb_Mat")
curb_mat.use_nodes = True
curb_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.55, 0.55, 0.5, 1)
curb_mat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9
for side in [-1, 1]:
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, side * 4.5, 0.08))
    curb = bpy.context.active_object
    curb.name = f"Curb_{'N' if side > 0 else 'S'}"
    curb.scale = (80, 0.15, 0.16)
    curb.data.materials.append(curb_mat)

# ── Time of day + render settings ──
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
# Overhead
bpy.ops.object.camera_add(location=(0, 0, 40))
cam1 = bpy.context.active_object
cam1.name = "Cam_BirdEye"
cam1.data.lens = 35
cam1.rotation_euler = (0, 0, 0)

# Driver POV (what van driver saw)
bpy.ops.object.camera_add(location=(-15, -1.8, 1.5))
cam2 = bpy.context.active_object
cam2.name = "Cam_DriverPOV"
cam2.data.lens = 35
cam2.rotation_euler = (math.radians(88), 0, math.radians(-90))

# Pedestrian perspective (looking at oncoming van)
bpy.ops.object.camera_add(location=(1.5, 2, 1.6))
cam3 = bpy.context.active_object
cam3.name = "Cam_PedestrianPOV"
cam3.data.lens = 35
bpy.ops.object.empty_add(type="PLAIN_AXES", location=(-8, -1.8, 1))
ped_target = bpy.context.active_object
ped_target.name = "PedTarget"
ped_target.hide_viewport = True
ped_target.hide_render = True
track_p = cam3.constraints.new("TRACK_TO")
track_p.target = ped_target
track_p.track_axis = "TRACK_NEGATIVE_Z"
track_p.up_axis = "UP_Y"

# Sight-line analysis view (from above, showing obstruction)
bpy.ops.object.camera_add(location=(-5, -8, 12))
cam4 = bpy.context.active_object
cam4.name = "Cam_SightLineAnalysis"
cam4.data.lens = 30
bpy.ops.object.empty_add(type="PLAIN_AXES", location=(-2, -2, 0))
sl_target = bpy.context.active_object
sl_target.name = "SLTarget"
sl_target.hide_viewport = True
sl_target.hide_render = True
track_sl = cam4.constraints.new("TRACK_TO")
track_sl.target = sl_target
track_sl.track_axis = "TRACK_NEGATIVE_Z"
track_sl.up_axis = "UP_Y"

# Wide establishing
bpy.ops.object.camera_add(location=(20, -15, 12))
cam5 = bpy.context.active_object
cam5.name = "Cam_Wide"
cam5.data.lens = 24
bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 0))
wide_target = bpy.context.active_object
wide_target.name = "WideTarget"
wide_target.hide_viewport = True
wide_target.hide_render = True
track_w = cam5.constraints.new("TRACK_TO")
track_w.target = wide_target
track_w.track_axis = "TRACK_NEGATIVE_Z"
track_w.up_axis = "UP_Y"

# ── Hide signals ──
for obj in bpy.data.objects:
    if "Signal" in obj.name or "signal" in obj.name:
        obj.hide_render = True
        obj.hide_viewport = True

# ── Save ──
blend_path = os.path.expanduser("~/claw-architect/openclaw-blender-mcp/renders/portfolio_scene2.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)

# ── Render ──
render_dir = os.path.expanduser("~/claw-architect/openclaw-blender-mcp/renders/portfolio/")
os.makedirs(render_dir, exist_ok=True)
cameras = ["Cam_BirdEye", "Cam_DriverPOV", "Cam_PedestrianPOV", "Cam_SightLineAnalysis", "Cam_Wide"]
for i, cn in enumerate(cameras):
    co = bpy.data.objects.get(cn)
    if co:
        scene.camera = co
        scene.render.filepath = os.path.join(render_dir, f"scene2_{i+1:02d}_{cn}.png")
        bpy.ops.render.render(write_still=True)
        print(f"Rendered: {cn}")

print("SCENE 2 COMPLETE")
__result__ = {"status": "scene2_complete", "cameras": len(cameras)}
