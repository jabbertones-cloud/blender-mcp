"""
Portfolio Scene 1: T-Bone Intersection Collision
Case: Smith v. Johnson — 2026-CV-04521
Vehicle 1 (Red sedan) traveling eastbound at 38 mph
Vehicle 2 (Blue SUV) traveling northbound at 25 mph
V1 runs red light, impacts V2 driver-side at intersection center

This builds the FULL scene with:
- Intersection with lane markings
- Two vehicles placed at final rest positions
- Damaged vehicles with impact zones
- Skid marks showing braking
- Debris field at impact point
- Impact point marker
- Measurement grid
- Exhibit overlay (case #, disclaimer, scale bar)
- 5 cameras: BirdEye, DriverPOV_V1, WitnessPOV, ImpactCloseup, Wide
- Courtroom render settings (Cycles 128spl)
"""
import bpy
import math
import os

# ── Clean scene ──
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# ── Helper: send command to bridge handler ──
# We call handle_forensic_scene directly since we're running inside Blender
# First, import the handler
import sys
addon_dir = os.path.expanduser("~/Library/Application Support/Blender/5.1/scripts/addons")
if addon_dir not in sys.path:
    sys.path.insert(0, addon_dir)

# Direct access to Blender API for scene building
from openclaw_blender_bridge import handle_forensic_scene

# ── Step 1: Build intersection ──
road_result = handle_forensic_scene({
    "action": "build_road",
    "road_type": "intersection",
    "lanes": 2,
    "width": 7,
    "length": 60
})

# ── Step 2: Place vehicles at FINAL REST positions ──
# V1: Red sedan — ran red light eastbound, now pushed northeast after impact
v1_result = handle_forensic_scene({
    "action": "place_vehicle",
    "name": "V1_Plaintiff_Sedan",
    "vehicle_type": "sedan",
    "location": [8.5, 4.2, 0],
    "rotation": 35,  # Rotated from heading east (90) by impact
    "color": [0.7, 0.08, 0.05, 1],  # Deep red
    "damaged": True,
    "impact_side": "front_right",
    "severity": "severe",
    "label": "Vehicle 1 - Plaintiff"
})

# V2: Blue SUV — was heading north, T-boned on driver side, pushed east
v2_result = handle_forensic_scene({
    "action": "place_vehicle",
    "name": "V2_Defendant_SUV",
    "vehicle_type": "suv",
    "location": [5.0, 2.5, 0],
    "rotation": 340,  # Rotated from heading north (0) by impact
    "color": [0.05, 0.12, 0.55, 1],  # Deep blue
    "damaged": True,
    "impact_side": "left",
    "severity": "severe",
    "label": "Vehicle 2 - Defendant"
})

# ── Step 3: Skid marks ──
# V1 braking — short skid (late braking, ran red)
handle_forensic_scene({
    "action": "add_impact_marker",
    "marker_type": "skid_mark",
    "start": [-15, -1.8, 0.005],
    "end": [-2, -1.8, 0.005],
    "name": "V1_SkidMark",
    "skid_width": 0.22
})

# V2 braking — longer skid (tried to stop)
handle_forensic_scene({
    "action": "add_impact_marker",
    "marker_type": "skid_mark",
    "start": [1.8, -18, 0.005],
    "end": [1.8, -3, 0.005],
    "name": "V2_SkidMark",
    "skid_width": 0.22
})

# ── Step 4: Impact point marker ──
handle_forensic_scene({
    "action": "add_impact_marker",
    "marker_type": "impact_point",
    "location": [2.0, 0.5, 0],
    "name": "POI_Impact"
})

# ── Step 5: Debris field ──
handle_forensic_scene({
    "action": "add_impact_marker",
    "marker_type": "debris",
    "location": [4, 2, 0],
    "count": 25,
    "radius": 4,
    "debris_type": "mixed"
})

# ── Step 6: Fluid spill ──
handle_forensic_scene({
    "action": "add_impact_marker",
    "marker_type": "fluid_spill",
    "location": [6, 3, 0],
    "spill_type": "coolant",
    "radius": 1.8
})

# ── Step 7: Measurement grid ──
handle_forensic_scene({
    "action": "add_measurement_grid",
    "size": 40,
    "spacing": 5
})

# ── Step 8: Exhibit overlay ──
handle_forensic_scene({
    "action": "add_exhibit_overlay",
    "case_number": "Case No. 2026-CV-04521",
    "exhibit_id": "Exhibit A — Accident Reconstruction Overview",
    "expert_name": "OpenClaw Forensic Animation",
    "firm_name": "Certified Reconstruction Analysis",
    "disclaimer": "DEMONSTRATIVE EXHIBIT — FOR ILLUSTRATIVE PURPOSES ONLY",
    "show_scale_bar": True,
    "scale_bar_length": 10,
    "show_timestamp": True,
    "timestamp": "Incident: 2026-01-15 17:42 EST"
})

# ── Step 9: Trajectory arrows (pre-impact paths) ──
# V1 eastbound trajectory arrow
bpy.ops.mesh.primitive_cylinder_add(radius=0.08, depth=20, location=(-8, -1.8, 0.15))
arrow_v1 = bpy.context.active_object
arrow_v1.name = "V1_Trajectory"
arrow_v1.rotation_euler = (math.radians(90), 0, math.radians(90))
mat_v1_path = bpy.data.materials.new("V1_Path_Mat")
mat_v1_path.use_nodes = True
bsdf = mat_v1_path.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (1, 0.2, 0.1, 0.7)
bsdf.inputs["Alpha"].default_value = 0.7
try:
    mat_v1_path.surface_render_method = 'DITHERED'
except:
    pass
arrow_v1.data.materials.append(mat_v1_path)

# V1 arrowhead
bpy.ops.mesh.primitive_cone_add(radius1=0.25, depth=0.6, location=(-0.5, -1.8, 0.15))
ah1 = bpy.context.active_object
ah1.name = "V1_Arrowhead"
ah1.rotation_euler = (0, math.radians(90), 0)
ah1.data.materials.append(mat_v1_path)

# V2 northbound trajectory arrow
bpy.ops.mesh.primitive_cylinder_add(radius=0.08, depth=18, location=(1.8, -12, 0.15))
arrow_v2 = bpy.context.active_object
arrow_v2.name = "V2_Trajectory"
arrow_v2.rotation_euler = (0, 0, 0)
mat_v2_path = bpy.data.materials.new("V2_Path_Mat")
mat_v2_path.use_nodes = True
bsdf2 = mat_v2_path.node_tree.nodes["Principled BSDF"]
bsdf2.inputs["Base Color"].default_value = (0.1, 0.3, 1, 0.7)
bsdf2.inputs["Alpha"].default_value = 0.7
try:
    mat_v2_path.surface_render_method = 'DITHERED'
except:
    pass
arrow_v2.data.materials.append(mat_v2_path)

# V2 arrowhead
bpy.ops.mesh.primitive_cone_add(radius1=0.25, depth=0.6, location=(1.8, -1.5, 0.15))
ah2 = bpy.context.active_object
ah2.name = "V2_Arrowhead"
ah2.rotation_euler = (math.radians(-90), 0, 0)
ah2.data.materials.append(mat_v2_path)

# ── Step 10: Speed labels ──
bpy.ops.object.text_add(location=(-12, -3.5, 0.3))
spd1 = bpy.context.active_object
spd1.data.body = "V1: 38 mph"
spd1.data.size = 0.7
spd1.name = "V1_Speed_Label"
spd1_mat = bpy.data.materials.new("SpeedLabel_V1")
spd1_mat.use_nodes = True
spd1_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (1, 0.2, 0.1, 1)
spd1_mat.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 0.5
spd1_mat.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = (1, 0.2, 0.1, 1)
spd1.data.materials.append(spd1_mat)

bpy.ops.object.text_add(location=(3.5, -15, 0.3))
spd2 = bpy.context.active_object
spd2.data.body = "V2: 25 mph"
spd2.data.size = 0.7
spd2.name = "V2_Speed_Label"
spd2_mat = bpy.data.materials.new("SpeedLabel_V2")
spd2_mat.use_nodes = True
spd2_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.1, 0.3, 1, 1)
spd2_mat.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 0.5
spd2_mat.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = (0.1, 0.3, 1, 1)
spd2.data.materials.append(spd2_mat)

# ── Step 11: Color Legend ──
bpy.ops.object.text_add(location=(-19, -18, 0.03))
legend = bpy.context.active_object
legend.data.body = "RED = Vehicle 1 (Plaintiff)    BLUE = Vehicle 2 (Defendant)"
legend.data.size = 0.45
legend.name = "Color_Legend"
legend_mat = bpy.data.materials.new("Legend_Mat")
legend_mat.use_nodes = True
legend_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.9, 0.9, 0.9, 1)
legend.data.materials.append(legend_mat)

# ── Step 12: Set time of day (afternoon) ──
handle_forensic_scene({
    "action": "set_time_of_day",
    "time": "day",
    "sun_energy": 1.5,
    "sky_strength": 0.25,
    "fill_energy": 0.3,
    "exposure": 0.3
})

# ── Step 13: Setup courtroom render ──
handle_forensic_scene({
    "action": "setup_courtroom_render",
    "preset": "presentation"
})

# ── Step 14: Setup 5 cameras ──
# Camera 1: Bird's Eye (overhead)
bpy.ops.object.camera_add(location=(0, 0, 45))
cam_bird = bpy.context.active_object
cam_bird.name = "Cam_BirdEye"
cam_bird.data.lens = 35
cam_bird.rotation_euler = (0, 0, 0)  # Looking straight down

# Camera 2: V1 Driver POV (what V1 driver saw approaching)
bpy.ops.object.camera_add(location=(-20, -1.8, 1.5))
cam_v1pov = bpy.context.active_object
cam_v1pov.name = "Cam_V1_DriverPOV"
cam_v1pov.data.lens = 35
# Look toward intersection
dx, dy = 2 - (-20), 0.5 - (-1.8)
cam_v1pov.rotation_euler = (math.radians(90), 0, math.atan2(dy, dx) - math.radians(90))

# Camera 3: Witness perspective (from sidewalk)
bpy.ops.object.camera_add(location=(-12, 12, 1.7))
cam_witness = bpy.context.active_object
cam_witness.name = "Cam_Witness"
cam_witness.data.lens = 50
# Track to impact point
bpy.ops.object.empty_add(type="PLAIN_AXES", location=(2, 0.5, 0.5))
target = bpy.context.active_object
target.name = "Cam_Target_Impact"
target.hide_viewport = True
target.hide_render = True
track = cam_witness.constraints.new("TRACK_TO")
track.target = target
track.track_axis = "TRACK_NEGATIVE_Z"
track.up_axis = "UP_Y"

# Camera 4: Impact close-up (low angle, dramatic)
bpy.ops.object.camera_add(location=(6, -4, 1.0))
cam_impact = bpy.context.active_object
cam_impact.name = "Cam_ImpactCloseup"
cam_impact.data.lens = 28
cam_impact.data.dof.use_dof = True
cam_impact.data.dof.focus_object = target
cam_impact.data.dof.aperture_fstop = 4.0
track2 = cam_impact.constraints.new("TRACK_TO")
track2.target = target
track2.track_axis = "TRACK_NEGATIVE_Z"
track2.up_axis = "UP_Y"

# Camera 5: Wide establishing shot
bpy.ops.object.camera_add(location=(25, -20, 18))
cam_wide = bpy.context.active_object
cam_wide.name = "Cam_Wide"
cam_wide.data.lens = 24
track3 = cam_wide.constraints.new("TRACK_TO")
track3.target = target
track3.track_axis = "TRACK_NEGATIVE_Z"
track3.up_axis = "UP_Y"

# ── Step 15: Hide traffic signal poles (they render badly) ──
for obj in bpy.data.objects:
    if "Signal" in obj.name or "signal" in obj.name:
        obj.hide_render = True
        obj.hide_viewport = True

# ── Save blend file ──
blend_path = os.path.expanduser("~/claw-architect/openclaw-blender-mcp/renders/portfolio_scene1.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)

# ── Render each camera ──
render_dir = os.path.expanduser("~/claw-architect/openclaw-blender-mcp/renders/portfolio/")
os.makedirs(render_dir, exist_ok=True)

cameras = ["Cam_BirdEye", "Cam_V1_DriverPOV", "Cam_Witness", "Cam_ImpactCloseup", "Cam_Wide"]
for i, cam_name in enumerate(cameras):
    cam_obj = bpy.data.objects.get(cam_name)
    if cam_obj:
        scene.camera = cam_obj
        scene.render.filepath = os.path.join(render_dir, f"scene1_{i+1:02d}_{cam_name}.png")
        bpy.ops.render.render(write_still=True)
        print(f"Rendered: {cam_name}")

print("SCENE 1 COMPLETE")

__result__ = {"status": "scene1_complete", "cameras": len(cameras)}
