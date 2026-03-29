"""
Portfolio Scene 4: Parking Lot Hit-and-Run
Case: Davis v. Unknown — 2026-CV-09157
Vehicle 1 (Parked silver sedan) struck while parked
Vehicle 2 (Dark truck) backed out of space, struck V1, fled scene
Security camera perspective reconstruction

Demonstrates: parking lot template, surveillance angle, hit-and-run, different environment
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

# ── Build parking lot template ──
handle_forensic_scene({
    "action": "add_scene_template",
    "template": "parking_lot"
})

# ── Parking space lines ──
line_mat = bpy.data.materials.new("ParkingLine_Mat")
line_mat.use_nodes = True
line_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.95, 0.95, 0.95, 1)
line_mat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.8

# Row of parking spaces (south side)
for i in range(8):
    x = -14 + i * 3.5
    # Vertical lines between spaces
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, -5, 0.008))
    line = bpy.context.active_object
    line.name = f"ParkLine_S_{i}"
    line.scale = (0.06, 2.5, 0.005)
    line.data.materials.append(line_mat)

# Row of parking spaces (north side)
for i in range(8):
    x = -14 + i * 3.5
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, 5, 0.008))
    line = bpy.context.active_object
    line.name = f"ParkLine_N_{i}"
    line.scale = (0.06, 2.5, 0.005)
    line.data.materials.append(line_mat)

# ── V1: Parked silver sedan (victim) ──
handle_forensic_scene({
    "action": "place_vehicle",
    "name": "V1_ParkedSedan_Davis",
    "vehicle_type": "sedan",
    "location": [0, -5, 0],
    "rotation": 0,
    "color": [0.55, 0.55, 0.52, 1],
    "damaged": True,
    "impact_side": "rear_left",
    "severity": "moderate"
})

# ── V2: Dark truck (hit-and-run, shown at moment of impact) ──
handle_forensic_scene({
    "action": "place_vehicle",
    "name": "V2_DarkTruck_Unknown",
    "vehicle_type": "pickup",
    "location": [-1.5, -2, 0],
    "rotation": 200,  # Backing out, angled
    "color": [0.08, 0.08, 0.1, 1],
    "damaged": True,
    "impact_side": "rear_right",
    "severity": "light"
})

# ── Ghost vehicle showing V2's escape path ──
handle_forensic_scene({
    "action": "place_vehicle",
    "name": "V2_Ghost_Escape",
    "vehicle_type": "pickup",
    "location": [8, 0, 0],
    "rotation": 90,
    "color": [0.08, 0.08, 0.1, 0.3]
})

# Make ghost transparent
for obj in bpy.data.objects:
    if obj.name == "V2_Ghost_Escape":
        for child in obj.children_recursive:
            if child.type == 'MESH':
                for mat in child.data.materials:
                    if mat and mat.use_nodes:
                        bsdf = mat.node_tree.nodes.get("Principled BSDF")
                        if bsdf:
                            bsdf.inputs["Alpha"].default_value = 0.25
                            try: mat.surface_render_method = 'DITHERED'
                            except: pass

# ── Escape trajectory arrow ──
# Curved path from impact to exit
points = [(-1.5, -2, 0.15), (2, -1, 0.15), (5, 0, 0.15), (8, 0, 0.15), (15, 0, 0.15)]
escape_mat = bpy.data.materials.new("Escape_Path")
escape_mat.use_nodes = True
escape_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (1, 0.5, 0, 0.6)
escape_mat.node_tree.nodes["Principled BSDF"].inputs["Alpha"].default_value = 0.6
escape_mat.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 0.8
escape_mat.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = (1, 0.5, 0, 1)
try: escape_mat.surface_render_method = 'DITHERED'
except: pass

for i in range(len(points)-1):
    p1, p2 = points[i], points[i+1]
    mid = [(a+b)/2 for a, b in zip(p1, p2)]
    dx, dy = p2[0]-p1[0], p2[1]-p1[1]
    length = math.sqrt(dx*dx + dy*dy)
    angle = math.atan2(dy, dx)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.06, depth=length, location=mid)
    seg = bpy.context.active_object
    seg.name = f"EscapePath_{i}"
    seg.rotation_euler = (math.radians(90), 0, angle)
    seg.data.materials.append(escape_mat)

# Escape arrowhead
bpy.ops.mesh.primitive_cone_add(radius1=0.2, depth=0.5, location=(15, 0, 0.15))
ah = bpy.context.active_object
ah.name = "Escape_Arrowhead"
ah.rotation_euler = (0, math.radians(90), 0)
ah.data.materials.append(escape_mat)

# ── Escape label ──
bpy.ops.object.text_add(location=(10, 1.5, 0.3))
esc_label = bpy.context.active_object
esc_label.data.body = "V2 FLED SCENE"
esc_label.data.size = 0.6
esc_label.name = "Escape_Label"
esc_mat = bpy.data.materials.new("Esc_Label_Mat")
esc_mat.use_nodes = True
esc_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (1, 0.4, 0, 1)
esc_mat.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 0.8
esc_mat.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = (1, 0.4, 0, 1)
esc_label.data.materials.append(esc_mat)

# ── Other parked vehicles (scene context) ──
parked_colors = [
    ([0.3, 0.05, 0.05, 1], "sedan", (3.5, -5, 0)),
    ([0.1, 0.2, 0.4, 1], "suv", (7, -5, 0)),
    ([0.4, 0.35, 0.25, 1], "sedan", (-3.5, -5, 0)),
    ([0.15, 0.3, 0.15, 1], "suv", (-3.5, 5, 0)),
    ([0.5, 0.5, 0.45, 1], "van", (3.5, 5, 0)),
]
for idx, (color, vtype, loc) in enumerate(parked_colors):
    handle_forensic_scene({
        "action": "place_vehicle",
        "name": f"Parked_{idx}",
        "vehicle_type": vtype,
        "location": list(loc),
        "rotation": 0 if loc[1] < 0 else 180,
        "color": color
    })

# ── Impact + debris ──
handle_forensic_scene({
    "action": "add_impact_marker",
    "marker_type": "impact_point",
    "location": [-0.5, -3.5, 0],
    "name": "POI_ParkingImpact"
})

handle_forensic_scene({
    "action": "add_impact_marker",
    "marker_type": "debris",
    "location": [-0.5, -3, 0],
    "count": 10,
    "radius": 1.5,
    "debris_type": "plastic"
})

# ── Security camera timestamp overlay ──
bpy.ops.object.text_add(location=(-18, 14, 0.03))
sec_cam = bpy.context.active_object
sec_cam.data.body = "CAM-04  2026-03-01  21:47:23  REC"
sec_cam.data.size = 0.5
sec_cam.name = "SecurityCam_Overlay"
sec_mat = bpy.data.materials.new("SecCam_Mat")
sec_mat.use_nodes = True
sec_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.8, 0, 0, 1)
sec_mat.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 1.0
sec_mat.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = (0.8, 0, 0, 1)
sec_cam.data.materials.append(sec_mat)

# ── Measurement grid ──
handle_forensic_scene({
    "action": "add_measurement_grid",
    "size": 30,
    "spacing": 5
})

# ── Exhibit overlay ──
handle_forensic_scene({
    "action": "add_exhibit_overlay",
    "case_number": "Case No. 2026-CV-09157",
    "exhibit_id": "Exhibit D — Parking Lot Reconstruction",
    "expert_name": "OpenClaw Forensic Animation",
    "firm_name": "Certified Reconstruction Analysis",
    "disclaimer": "DEMONSTRATIVE EXHIBIT — FOR ILLUSTRATIVE PURPOSES ONLY",
    "show_scale_bar": True,
    "scale_bar_length": 5,
    "show_timestamp": True,
    "timestamp": "Incident: 2026-03-01 21:47 EST"
})

# ── Night lighting (parking lot at night) ──
handle_forensic_scene({
    "action": "set_time_of_day",
    "time": "night"
})

# Add parking lot lights
for pos in [(-10, 0, 6), (0, 0, 6), (10, 0, 6)]:
    bpy.ops.object.light_add(type='POINT', location=pos)
    light = bpy.context.active_object
    light.name = f"ParkingLight_{pos[0]}"
    light.data.energy = 800
    light.data.color = (1, 0.95, 0.85)
    light.data.shadow_soft_size = 0.5
    # Light pole
    bpy.ops.mesh.primitive_cylinder_add(radius=0.08, depth=6, location=(pos[0], pos[1], 3))
    pole = bpy.context.active_object
    pole.name = f"LightPole_{pos[0]}"
    pole_mat = bpy.data.materials.new(f"Pole_{pos[0]}")
    pole_mat.use_nodes = True
    pole_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.3, 0.3, 0.3, 1)
    pole_mat.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = 0.8
    pole.data.materials.append(pole_mat)

# ── Render settings ──
handle_forensic_scene({
    "action": "setup_courtroom_render",
    "preset": "presentation"
})

# ── Cameras ──
# Security camera angle (high, wide, slightly fish-eye)
bpy.ops.object.camera_add(location=(-15, 10, 8))
c1 = bpy.context.active_object
c1.name = "Cam_SecurityCam"
c1.data.lens = 18  # Wide angle like security camera
bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, -3, 0))
sec_tgt = bpy.context.active_object
sec_tgt.name = "SecTarget"
sec_tgt.hide_viewport = True
sec_tgt.hide_render = True
t1 = c1.constraints.new("TRACK_TO")
t1.target = sec_tgt
t1.track_axis = "TRACK_NEGATIVE_Z"
t1.up_axis = "UP_Y"

# Bird's eye
bpy.ops.object.camera_add(location=(0, 0, 30))
c2 = bpy.context.active_object
c2.name = "Cam_BirdEye"
c2.data.lens = 30
c2.rotation_euler = (0, 0, 0)

# Impact close-up
bpy.ops.object.camera_add(location=(3, -6, 1.5))
c3 = bpy.context.active_object
c3.name = "Cam_ImpactCloseup"
c3.data.lens = 35
c3.data.dof.use_dof = True
c3.data.dof.focus_object = sec_tgt
c3.data.dof.aperture_fstop = 3.0
t3 = c3.constraints.new("TRACK_TO")
t3.target = sec_tgt
t3.track_axis = "TRACK_NEGATIVE_Z"
t3.up_axis = "UP_Y"

# Wide shot
bpy.ops.object.camera_add(location=(20, -15, 10))
c4 = bpy.context.active_object
c4.name = "Cam_Wide"
c4.data.lens = 24
t4 = c4.constraints.new("TRACK_TO")
t4.target = sec_tgt
t4.track_axis = "TRACK_NEGATIVE_Z"
t4.up_axis = "UP_Y"

# Escape route view
bpy.ops.object.camera_add(location=(15, 8, 5))
c5 = bpy.context.active_object
c5.name = "Cam_EscapeRoute"
c5.data.lens = 28
bpy.ops.object.empty_add(type="PLAIN_AXES", location=(5, 0, 0))
esc_tgt = bpy.context.active_object
esc_tgt.name = "EscTarget"
esc_tgt.hide_viewport = True
esc_tgt.hide_render = True
t5 = c5.constraints.new("TRACK_TO")
t5.target = esc_tgt
t5.track_axis = "TRACK_NEGATIVE_Z"
t5.up_axis = "UP_Y"

# ── Save + Render ──
blend_path = os.path.expanduser("~/claw-architect/openclaw-blender-mcp/renders/portfolio_scene4.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)

render_dir = os.path.expanduser("~/claw-architect/openclaw-blender-mcp/renders/portfolio/")
os.makedirs(render_dir, exist_ok=True)
cameras = ["Cam_SecurityCam", "Cam_BirdEye", "Cam_ImpactCloseup", "Cam_Wide", "Cam_EscapeRoute"]
for i, cn in enumerate(cameras):
    co = bpy.data.objects.get(cn)
    if co:
        scene.camera = co
        scene.render.filepath = os.path.join(render_dir, f"scene4_{i+1:02d}_{cn}.png")
        bpy.ops.render.render(write_still=True)
        print(f"Rendered: {cn}")

print("SCENE 4 COMPLETE")
__result__ = {"status": "scene4_complete", "cameras": len(cameras)}
