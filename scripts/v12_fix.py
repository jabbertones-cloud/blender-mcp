"""V12 Fix Script — Run via: Blender --background scene.blend --python v12_fix.py -- SCENE_NUM"""
import bpy, math, sys, os

# Parse scene number
argv = sys.argv
sn = int(argv[argv.index('--') + 1]) if '--' in argv else 1
is_night = (sn == 4)
BASE = '/Users/tatsheen/claw-architect/openclaw-blender-mcp'
OUT = f'{BASE}/renders/v12_renders'
os.makedirs(OUT, exist_ok=True)
print(f'=== V12 FIX: Scene {sn}, night={is_night} ===')

# 1. Render engine — use correct EEVEE for this version
s = bpy.context.scene
if bpy.app.version >= (5, 0, 0):
    s.render.engine = 'BLENDER_EEVEE'
elif bpy.app.version >= (4, 0, 0):
    s.render.engine = 'BLENDER_EEVEE_NEXT'
else:
    s.render.engine = 'BLENDER_EEVEE'
print(f'Engine: {s.render.engine} (Blender {bpy.app.version_string})')

s.render.resolution_x = 1920
s.render.resolution_y = 1080
s.render.resolution_percentage = 100
try: s.eevee.taa_render_samples = 64
except: pass

# Color management
try: s.view_settings.view_transform = 'AgX'
except:
    try: s.view_settings.view_transform = 'Filmic'
    except: pass
s.view_settings.exposure = 1.0 if is_night else 0.5
print(f'Color: {s.view_settings.view_transform}, exp={s.view_settings.exposure}')

# 2. World background
w = s.world
if not w:
    w = bpy.data.worlds.new('World'); s.world = w
w.use_nodes = True
t = w.node_tree
bg = None
for n in t.nodes:
    if n.type == 'BACKGROUND': bg = n
if not bg:
    for n in t.nodes: t.nodes.remove(n)
    bg = t.nodes.new('ShaderNodeBackground')
    o = t.nodes.new('ShaderNodeOutputWorld')
    t.links.new(bg.outputs['Background'], o.inputs['Surface'])
if is_night:
    bg.inputs['Color'].default_value = (0.01, 0.01, 0.02, 1.0)
    bg.inputs['Strength'].default_value = 0.1
else:
    bg.inputs['Color'].default_value = (0.55, 0.65, 0.8, 1.0)
    bg.inputs['Strength'].default_value = 1.8
print(f'World: night={is_night}')

# 3. Gentle light boost (30%) + fix zero-energy lights
for obj in bpy.data.objects:
    if obj.type == 'LIGHT':
        if obj.data.energy < 1: obj.data.energy = 5.0
        obj.data.energy *= 1.3
        print(f'  Light: {obj.name} energy={obj.data.energy:.1f}')

# 4. PBR Materials
def mk(name, col, met, rou):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    if b:
        b.inputs['Base Color'].default_value = col
        b.inputs['Metallic'].default_value = met
        b.inputs['Roughness'].default_value = rou
    return m
paints = [mk('P_Red',(0.6,0.05,0.05,1),0.9,0.15), mk('P_Blue',(0.05,0.1,0.5,1),0.9,0.15),
          mk('P_White',(0.8,0.8,0.82,1),0.9,0.15), mk('P_Silver',(0.5,0.5,0.52,1),0.9,0.2)]
asph = mk('Asphalt',(0.05,0.05,0.055,1),0.0,0.75)
pi = 0
for obj in bpy.data.objects:
    if obj.type != 'MESH': continue
    nm = obj.name.lower()
    hm = obj.data.materials and any(m and m.name != 'Material' for m in obj.data.materials)
    if any(k in nm for k in ['road','ground','plane','floor','asphalt']):
        if obj.data.materials: obj.data.materials[0] = asph
        else: obj.data.materials.append(asph)
    elif not hm and any(k in nm for k in ['vehicle','car','sedan','suv','truck','van']):
        p = paints[pi%4]; pi+=1
        if obj.data.materials: obj.data.materials[0] = p
        else: obj.data.materials.append(p)
print(f'Materials assigned, {pi} vehicles colored')

# 5. Evidence markers
for i, pos in enumerate([(0,0,0.4),(3,-2,0.4),(-2,1,0.4)]):
    bpy.ops.mesh.primitive_cone_add(radius1=0.3, depth=0.8, location=pos)
    m = bpy.context.active_object; m.name = f'Marker_{chr(65+i)}'
    mat = bpy.data.materials.new(f'Mk{chr(65+i)}'); mat.use_nodes = True
    b = mat.node_tree.nodes.get('Principled BSDF')
    cols = [(1,0,0,1),(0,0,1,1),(1,1,0,1)]
    if b:
        b.inputs['Base Color'].default_value = cols[i]
        try: b.inputs['Emission Strength'].default_value = 3.0
        except: pass
    m.data.materials.append(mat)
print('Markers added')

# 6. Exhibit label
bpy.ops.object.text_add(location=(0,-12,0.01), rotation=(math.radians(-90),0,0))
txt = bpy.context.active_object; txt.name = 'ExhibitLabel'
txt.data.body = f'Case #2026-CV-DEMO  Exhibit {sn}-A\nDEMONSTRATIVE AID'
txt.data.size = 0.8
lm = bpy.data.materials.new('LblW'); lm.use_nodes = True
b = lm.node_tree.nodes.get('Principled BSDF')
if b: b.inputs['Base Color'].default_value = (1,1,1,1)
txt.data.materials.append(lm)
print('Label added')

# 7. Render all cameras
cameras = [o for o in bpy.data.objects if o.type == 'CAMERA']
print(f'Found {len(cameras)} cameras: {[c.name for c in cameras]}')
name_map = {'Camera_BirdEye':'BirdEye','Camera_DriverPOV':'DriverPOV','Camera_Wide':'Wide',
    'Camera_WideAngle':'Wide','Camera_SightLine':'SightLine','Camera_SecurityCam':'SecurityCam',
    'Camera_WitnessView':'WitnessView','Camera_TruckPOV':'TruckPOV'}
for cam in cameras:
    clean = name_map.get(cam.name, cam.name.replace('Camera_',''))
    outpath = f'{OUT}/v12_s{sn}_{clean}.png'
    s.camera = cam
    s.render.filepath = outpath
    print(f'Rendering {cam.name} -> {os.path.basename(outpath)} ...')
    bpy.ops.render.render(write_still=True)
    print(f'  Done: {outpath}')

print(f'=== SCENE {sn} COMPLETE ===')
