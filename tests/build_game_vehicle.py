"""Build a popular game-ready low-poly sports car in Blender."""
import socket, json, time, math

def send_cmd(cmd, timeout=30):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(('127.0.0.1', 9876))
        msg = json.dumps(cmd) + '\n'
        s.sendall(msg.encode())
        data = b''
        while True:
            chunk = s.recv(16384)
            if not chunk:
                break
            data += chunk
            try:
                json.loads(data.decode())
                break
            except:
                continue
        result = json.loads(data.decode())
        return result.get('result', result)
    except Exception as e:
        return {'error': str(e)}
    finally:
        s.close()

def run(code, timeout=15):
    """Execute Python in Blender and return result."""
    r = send_cmd({'command': 'execute_python', 'params': {'code': code}}, timeout)
    if isinstance(r, dict) and r.get('error'):
        print(f"  ERROR: {r['error'][:100]}")
    return r

print("=" * 60)
print("  BUILDING GAME-READY LOW-POLY SPORTS CAR")
print("=" * 60)

# Clear scene
run("""
import bpy
for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
for c in list(bpy.data.collections): bpy.data.collections.remove(c)
for m in list(bpy.data.meshes): bpy.data.meshes.remove(m)
for mat in list(bpy.data.materials): bpy.data.materials.remove(mat)
print("CLEARED")
""")
time.sleep(0.3)

# Build the sports car with detailed modeling via Blender Python
print("\n  [building car body]...", end=" ", flush=True)
run("""
import bpy, bmesh, math

# --- Materials ---
def mat(name, color, metallic=0.0, roughness=0.5, emission=0.0):
    m = bpy.data.materials.new(name=name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if emission > 0:
        try:
            bsdf.inputs["Emission Strength"].default_value = emission
            bsdf.inputs["Emission Color"].default_value = (*color, 1)
        except:
            pass
    return m

# Car colors — sporty orange
mat_body = mat("CarBody", (0.95, 0.35, 0.05), metallic=0.85, roughness=0.15)
mat_glass = mat("Glass", (0.15, 0.2, 0.3), metallic=0.0, roughness=0.05)
mat_glass.use_nodes = True
bsdf = mat_glass.node_tree.nodes["Principled BSDF"]
try:
    bsdf.inputs["Transmission Weight"].default_value = 0.8
except:
    try:
        bsdf.inputs["Transmission"].default_value = 0.8
    except:
        pass
bsdf.inputs["Alpha"].default_value = 0.4
mat_glass.blend_method = "BLEND" if hasattr(mat_glass, "blend_method") else None

mat_chrome = mat("Chrome", (0.9, 0.9, 0.9), metallic=1.0, roughness=0.05)
mat_rubber = mat("Rubber", (0.02, 0.02, 0.02), metallic=0.0, roughness=0.9)
mat_rim = mat("Rim", (0.7, 0.7, 0.75), metallic=0.95, roughness=0.1)
mat_headlight = mat("Headlight", (1.0, 0.95, 0.85), emission=3.0)
mat_taillight = mat("Taillight", (0.9, 0.05, 0.02), emission=2.0)
mat_interior = mat("Interior", (0.05, 0.05, 0.05), roughness=0.8)
mat_carbon = mat("CarbonFiber", (0.03, 0.03, 0.03), metallic=0.3, roughness=0.3)
mat_underbody = mat("Underbody", (0.08, 0.08, 0.08), roughness=0.9)
mat_grille = mat("Grille", (0.02, 0.02, 0.02), metallic=0.5, roughness=0.4)
mat_brake = mat("BrakeCaliper", (0.8, 0.1, 0.05), metallic=0.7, roughness=0.3)

# --- Parent empty ---
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
car = bpy.context.active_object
car.name = "SportsCar"

# --- Helper: create mesh, parent, assign mat ---
def add_part(name, material):
    obj = bpy.context.active_object
    obj.name = name
    obj.parent = car
    if material:
        obj.data.materials.append(material)
    return obj

# ===== MAIN BODY (sculpted from cube) =====
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.45))
body = add_part("Body_Main", mat_body)
body.scale = (0.95, 2.2, 0.4)

# Hood (sloped front)
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 1.4, 0.5))
hood = add_part("Body_Hood", mat_body)
hood.scale = (0.9, 0.8, 0.08)
hood.rotation_euler = (math.radians(-5), 0, 0)

# Front bumper
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 2.15, 0.3))
add_part("Bumper_Front", mat_carbon)
bpy.context.active_object.scale = (0.95, 0.15, 0.25)

# Rear bumper
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -2.15, 0.35))
add_part("Bumper_Rear", mat_carbon)
bpy.context.active_object.scale = (0.95, 0.15, 0.25)

# Front splitter
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 2.25, 0.12))
add_part("Splitter_Front", mat_carbon)
bpy.context.active_object.scale = (1.0, 0.08, 0.03)

# Cabin/roof
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -0.1, 0.85))
cabin = add_part("Body_Cabin", mat_body)
cabin.scale = (0.8, 0.9, 0.3)

# Windshield
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0.65, 0.82))
ws = add_part("Windshield", mat_glass)
ws.scale = (0.75, 0.02, 0.35)
ws.rotation_euler = (math.radians(25), 0, 0)

# Rear window
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -0.75, 0.78))
rw = add_part("RearWindow", mat_glass)
rw.scale = (0.7, 0.02, 0.3)
rw.rotation_euler = (math.radians(-30), 0, 0)

# Side windows (L & R)
for side, sx in [("L", -0.82), ("R", 0.82)]:
    bpy.ops.mesh.primitive_cube_add(size=1, location=(sx, -0.1, 0.82))
    sw = add_part(f"SideWindow_{side}", mat_glass)
    sw.scale = (0.02, 0.7, 0.22)

# Rear deck / trunk
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -1.4, 0.55))
add_part("Body_RearDeck", mat_body)
bpy.context.active_object.scale = (0.88, 0.6, 0.12)

# Rear spoiler
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -1.85, 0.75))
add_part("Spoiler", mat_carbon)
bpy.context.active_object.scale = (0.9, 0.08, 0.04)
# Spoiler mounts
for sx in [-0.35, 0.35]:
    bpy.ops.mesh.primitive_cube_add(size=1, location=(sx, -1.8, 0.68))
    add_part(f"SpoilerMount", mat_carbon)
    bpy.context.active_object.scale = (0.04, 0.04, 0.12)

# Headlights (L & R)
for side, sx in [("L", -0.65), ("R", 0.65)]:
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.12, location=(sx, 2.15, 0.4))
    add_part(f"Headlight_{side}", mat_headlight)

# Taillights (L & R)
for side, sx in [("L", -0.7), ("R", 0.7)]:
    bpy.ops.mesh.primitive_cube_add(size=1, location=(sx, -2.15, 0.4))
    tl = add_part(f"Taillight_{side}", mat_taillight)
    tl.scale = (0.2, 0.04, 0.08)

# Taillight bar (connecting strip)
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -2.16, 0.4))
add_part("Taillight_Bar", mat_taillight)
bpy.context.active_object.scale = (0.6, 0.02, 0.03)

# Front grille
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 2.18, 0.35))
add_part("Grille_Front", mat_grille)
bpy.context.active_object.scale = (0.6, 0.03, 0.12)

# Side mirrors
for side, sx, rot in [("L", -0.95, 0.15), ("R", 0.95, -0.15)]:
    # Stalk
    bpy.ops.mesh.primitive_cylinder_add(radius=0.02, depth=0.15, location=(sx, 0.5, 0.7))
    stk = add_part(f"Mirror_Stalk_{side}", mat_chrome)
    stk.rotation_euler = (0, math.radians(90), rot)
    # Mirror head
    bpy.ops.mesh.primitive_cube_add(size=1, location=(sx + (0.08 if sx > 0 else -0.08), 0.5, 0.72))
    mh = add_part(f"Mirror_{side}", mat_body)
    mh.scale = (0.06, 0.08, 0.05)

# Exhaust pipes (dual)
for sx in [-0.3, 0.3]:
    bpy.ops.mesh.primitive_cylinder_add(radius=0.05, depth=0.12, location=(sx, -2.25, 0.2))
    ex = add_part(f"Exhaust", mat_chrome)
    ex.rotation_euler = (math.radians(90), 0, 0)

# Side air intakes
for side, sx in [("L", -0.96), ("R", 0.96)]:
    bpy.ops.mesh.primitive_cube_add(size=1, location=(sx, 0.8, 0.35))
    add_part(f"SideIntake_{side}", mat_grille)
    bpy.context.active_object.scale = (0.02, 0.3, 0.1)

# Underbody plate
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.08))
add_part("Underbody", mat_underbody)
bpy.context.active_object.scale = (0.9, 2.1, 0.04)

# ===== WHEELS (4) =====
wheel_positions = [
    ("FL", -0.75, 1.4, 0.25),
    ("FR", 0.75, 1.4, 0.25),
    ("RL", -0.75, -1.3, 0.25),
    ("RR", 0.75, -1.3, 0.25),
]

for tag, wx, wy, wz in wheel_positions:
    # Tire
    bpy.ops.mesh.primitive_torus_add(
        major_radius=0.25, minor_radius=0.1,
        major_segments=24, minor_segments=12,
        location=(wx, wy, wz)
    )
    tire = add_part(f"Tire_{tag}", mat_rubber)
    tire.rotation_euler = (0, math.radians(90), 0) if abs(wx) > 0 else (0, 0, 0)

    # Rim
    bpy.ops.mesh.primitive_cylinder_add(radius=0.16, depth=0.08, location=(wx, wy, wz))
    rim = add_part(f"Rim_{tag}", mat_rim)
    rim.rotation_euler = (0, math.radians(90), 0) if abs(wx) > 0 else (0, 0, 0)

    # Brake caliper (visible through rim)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(wx, wy, wz))
    bc = add_part(f"Brake_{tag}", mat_brake)
    bc.scale = (0.03, 0.08, 0.12)

    # Wheel arch
    bpy.ops.mesh.primitive_cube_add(size=1, location=(wx, wy, wz + 0.15))
    wa = add_part(f"WheelArch_{tag}", mat_body)
    wa.scale = (0.06, 0.22, 0.15)

# ===== INTERIOR (visible through glass) =====
# Dashboard
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0.4, 0.7))
add_part("Dashboard", mat_interior)
bpy.context.active_object.scale = (0.7, 0.15, 0.15)

# Seats
for sx in [-0.3, 0.3]:
    # Seat base
    bpy.ops.mesh.primitive_cube_add(size=1, location=(sx, -0.1, 0.6))
    add_part("Seat", mat_interior)
    bpy.context.active_object.scale = (0.2, 0.25, 0.05)
    # Seat back
    bpy.ops.mesh.primitive_cube_add(size=1, location=(sx, -0.22, 0.75))
    add_part("SeatBack", mat_interior)
    bpy.context.active_object.scale = (0.18, 0.04, 0.18)

# Steering wheel
bpy.ops.mesh.primitive_torus_add(major_radius=0.1, minor_radius=0.015, location=(-0.3, 0.32, 0.72))
sw = add_part("SteeringWheel", mat_interior)
sw.rotation_euler = (math.radians(65), 0, 0)

print("CAR_BUILT")
""")
print("OK")

# Set up a nice studio render
print("  [setting up studio lighting]...", end=" ", flush=True)
run("""
import bpy, math

scene = bpy.context.scene

# HDRI-style studio lighting
scene.render.engine = 'BLENDER_EEVEE_NEXT' if hasattr(bpy.types, 'EEVEE_NEXT') else 'BLENDER_EEVEE'

# Ground plane (showroom floor)
bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, 0))
floor = bpy.context.active_object
floor.name = "ShowroomFloor"
mat_floor = bpy.data.materials.new("ShowroomFloor")
mat_floor.use_nodes = True
bsdf = mat_floor.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.12, 0.12, 0.14, 1)
bsdf.inputs["Metallic"].default_value = 0.0
bsdf.inputs["Roughness"].default_value = 0.15
floor.data.materials.append(mat_floor)

# Key light
bpy.ops.object.light_add(type='AREA', location=(3, 4, 5))
key = bpy.context.active_object
key.name = "Key_Light"
key.data.energy = 500
key.data.size = 4
key.data.color = (1, 0.97, 0.92)
key.rotation_euler = (math.radians(-50), math.radians(20), math.radians(15))

# Fill light
bpy.ops.object.light_add(type='AREA', location=(-4, -2, 3))
fill = bpy.context.active_object
fill.name = "Fill_Light"
fill.data.energy = 200
fill.data.size = 3
fill.data.color = (0.85, 0.9, 1.0)
fill.rotation_euler = (math.radians(-40), math.radians(-30), 0)

# Rim light (behind car)
bpy.ops.object.light_add(type='AREA', location=(0, -5, 4))
rim = bpy.context.active_object
rim.name = "Rim_Light"
rim.data.energy = 350
rim.data.size = 5
rim.data.color = (0.9, 0.95, 1.0)
rim.rotation_euler = (math.radians(-30), 0, 0)

# World background (dark gradient)
world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs["Color"].default_value = (0.02, 0.025, 0.035, 1)
    bg.inputs["Strength"].default_value = 0.3

# Render settings
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"

print("STUDIO_SETUP_DONE")
""")
print("OK")

# Camera angles
print("\n  [setting up cameras]...", end=" ", flush=True)
run("""
import bpy, math

car = bpy.data.objects.get("SportsCar")
target_loc = (0, 0, 0.5)

# Empty for camera tracking
bpy.ops.object.empty_add(type='PLAIN_AXES', location=target_loc)
target = bpy.context.active_object
target.name = "CamTarget"
target.hide_viewport = True
target.hide_render = True

def add_cam(name, loc, lens=50):
    bpy.ops.object.camera_add(location=loc)
    cam = bpy.context.active_object
    cam.name = name
    cam.data.lens = lens
    track = cam.constraints.new("TRACK_TO")
    track.target = target
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"
    return cam

# 3/4 front (hero shot)
add_cam("Cam_Hero", (4.5, 5, 2.5), lens=45)

# Side profile
add_cam("Cam_Side", (6, 0, 1.5), lens=60)

# Rear 3/4
add_cam("Cam_Rear", (-4.5, -5, 2.5), lens=45)

# Low front dramatic
add_cam("Cam_LowFront", (2, 5, 0.5), lens=35)

print("CAMERAS_DONE")
""")
print("OK")

# Render all views
print("\n" + "=" * 60)
print("  RENDERING GAME VEHICLE — 4 VIEWS")
print("=" * 60)

renders_dir = "/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders"

for cam_name in ["Cam_Hero", "Cam_Side", "Cam_Rear", "Cam_LowFront"]:
    filepath = f"{renders_dir}/gamecar_{cam_name.lower()}.png"
    code = f"""
import bpy
cam = bpy.data.objects.get("{cam_name}")
if cam:
    bpy.context.scene.camera = cam
    bpy.context.scene.render.filepath = "{filepath}"
    bpy.ops.render.render(write_still=True)
    print("RENDERED: {cam_name}")
else:
    print("NOT_FOUND: {cam_name}")
"""
    print(f"  [render {cam_name}]...", end=" ", flush=True)
    r = send_cmd({'command': 'execute_python', 'params': {'code': code}}, timeout=60)
    if isinstance(r, dict) and r.get('error'):
        print(f"SKIP: {r['error'][:50]}")
    else:
        print("OK")

# Save .blend
print("\n  [saving .blend]...", end=" ", flush=True)
blend_path = f"{renders_dir}/game_sports_car.blend"
run(f'import bpy; bpy.ops.wm.save_as_mainfile(filepath="{blend_path}"); print("SAVED")')
print("OK")

# Export FBX for game engines
print("  [exporting .fbx]...", end=" ", flush=True)
fbx_path = f"{renders_dir}/game_sports_car.fbx"
run(f"""
import bpy
# Select only the car and its children
bpy.ops.object.select_all(action='DESELECT')
car = bpy.data.objects.get("SportsCar")
if car:
    car.select_set(True)
    for child in car.children_recursive:
        child.select_set(True)
    bpy.ops.export_scene.fbx(
        filepath="{fbx_path}",
        use_selection=True,
        apply_scale_options='FBX_SCALE_ALL',
        mesh_smooth_type='FACE'
    )
    print("FBX_EXPORTED")
""")
print("OK")

# Export OBJ as well
print("  [exporting .obj]...", end=" ", flush=True)
obj_path = f"{renders_dir}/game_sports_car.obj"
run(f"""
import bpy
bpy.ops.object.select_all(action='DESELECT')
car = bpy.data.objects.get("SportsCar")
if car:
    car.select_set(True)
    for child in car.children_recursive:
        child.select_set(True)
    bpy.ops.wm.obj_export(
        filepath="{obj_path}",
        export_selected_objects=True
    )
    print("OBJ_EXPORTED")
""")
print("OK")

print(f"\n{'=' * 60}")
print("  DONE! Game vehicle files:")
print(f"  - game_sports_car.blend")
print(f"  - game_sports_car.fbx (game engine import)")
print(f"  - game_sports_car.obj (universal)")
print(f"  - gamecar_cam_hero.png")
print(f"  - gamecar_cam_side.png")
print(f"  - gamecar_cam_rear.png")
print(f"  - gamecar_cam_lowfront.png")
print(f"{'=' * 60}")
