"""V12 Camera Fix — Fix camera positions for scenes with bad framing
Run: Blender --background scene.blend --python v12_fix_cameras.py -- SCENE_NUM"""
import bpy, math, sys, os

argv = sys.argv
sn = int(argv[argv.index('--') + 1]) if '--' in argv else 1
is_night = (sn == 4)
BASE = '/Users/tatsheen/claw-architect/openclaw-blender-mcp'
OUT = f'{BASE}/renders/v12_renders'

print(f'=== V12 CAMERA FIX: Scene {sn} ===')

# Find scene bounding box center
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
if meshes:
    xs = [o.location.x for o in meshes]
    ys = [o.location.y for o in meshes]
    cx = sum(xs)/len(xs)
    cy = sum(ys)/len(ys)
else:
    cx, cy = 0, 0
print(f'Scene center: ({cx:.1f}, {cy:.1f})')

# Camera configs per scene
configs = {
    3: {
        'BirdEye': {'loc': (cx, cy, 40), 'rot': (0, 0, 0), 'lens': 35},
        'DriverPOV': {'loc': (cx-8, cy-3, 1.7), 'rot': (math.radians(80), 0, math.radians(-10)), 'lens': 35},
        'WideAngle': {'loc': (cx+25, cy+15, 8), 'rot': (math.radians(70), 0, math.radians(120)), 'lens': 28},
    },
    4: {
        'BirdEye': {'loc': (cx, cy, 25), 'rot': (0, 0, 0), 'lens': 35},
        'SecurityCam': {'loc': (cx-8, cy-6, 5), 'rot': (math.radians(60), 0, math.radians(-30)), 'lens': 8},
        'WideAngle': {'loc': (cx+15, cy+10, 6), 'rot': (math.radians(70), 0, math.radians(120)), 'lens': 28},
    }
}

# Apply camera fixes
if sn in configs:
    for cam in bpy.data.objects:
        if cam.type != 'CAMERA': continue
        name = cam.name
        cfg = configs[sn].get(name)
        if cfg:
            cam.location = cfg['loc']
            cam.rotation_euler = cfg['rot']
            cam.data.lens = cfg['lens']
            cam.data.clip_start = 0.1
            cam.data.clip_end = 1000
            print(f'Fixed {name}: loc={cfg["loc"]}, lens={cfg["lens"]}mm')
        else:
            print(f'No fix for camera: {name}')

# Scene 4 specific: boost night lighting significantly
if is_night:
    print('Boosting night lights...')
    for obj in bpy.data.objects:
        if obj.type == 'LIGHT':
            obj.data.energy *= 5.0  # Much stronger for night
            print(f'  {obj.name}: energy={obj.data.energy:.0f}')
    # Add extra fill lights for night
    for i, pos in enumerate([(cx-5,cy-5,8),(cx+5,cy+5,8),(cx,cy,12)]):
        bpy.ops.object.light_add(type='AREA', location=pos)
        l = bpy.context.active_object
        l.name = f'NightFill_{i}'
        l.data.energy = 300
        l.data.size = 5.0
        l.data.color = (1.0, 0.85, 0.6)  # Warm sodium
        l.rotation_euler = (math.radians(90), 0, 0)
        print(f'  Added {l.name} at {pos}, 300W')
    # Boost world background for night slightly
    w = bpy.context.scene.world
    if w and w.use_nodes:
        for n in w.node_tree.nodes:
            if n.type == 'BACKGROUND':
                n.inputs['Color'].default_value = (0.02, 0.02, 0.04, 1)
                n.inputs['Strength'].default_value = 0.3

# Now apply the standard v12 fixes (materials, markers etc)
# ... reuse the main fix script content
s = bpy.context.scene

# Render engine
if bpy.app.version >= (5, 0, 0):
    s.render.engine = 'BLENDER_EEVEE'
elif bpy.app.version >= (4, 0, 0):
    s.render.engine = 'BLENDER_EEVEE_NEXT'
s.render.resolution_x = 1920
s.render.resolution_y = 1080
try: s.eevee.taa_render_samples = 64
except: pass
try: s.view_settings.view_transform = 'AgX'
except:
    try: s.view_settings.view_transform = 'Filmic'
    except: pass
s.view_settings.exposure = 1.5 if is_night else 0.5

# World (only set if not already done)
w = s.world
if not w:
    w = bpy.data.worlds.new('World'); s.world = w
    w.use_nodes = True
    t = w.node_tree
    for n in t.nodes: t.nodes.remove(n)
    bg = t.nodes.new('ShaderNodeBackground')
    o = t.nodes.new('ShaderNodeOutputWorld')
    t.links.new(bg.outputs['Background'], o.inputs['Surface'])
    if is_night:
        bg.inputs['Color'].default_value = (0.02, 0.02, 0.04, 1)
        bg.inputs['Strength'].default_value = 0.3
    else:
        bg.inputs['Color'].default_value = (0.55, 0.65, 0.8, 1)
        bg.inputs['Strength'].default_value = 1.8

# Materials
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
    if any(k in nm for k in ['road','ground','plane','floor','asphalt','highway','parking']):
        if obj.data.materials: obj.data.materials[0] = asph
        else: obj.data.materials.append(asph)
    elif not hm and any(k in nm for k in ['vehicle','car','sedan','suv','truck','van','body','spoiler']):
        p = paints[pi%4]; pi+=1
        if obj.data.materials: obj.data.materials[0] = p
        else: obj.data.materials.append(p)

# Evidence markers
for i, pos in enumerate([(cx,cy,0.4),(cx+3,cy-2,0.4),(cx-2,cy+1,0.4)]):
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

# Label
bpy.ops.object.text_add(location=(cx,cy-12,0.01), rotation=(math.radians(-90),0,0))
txt = bpy.context.active_object; txt.name = 'ExhibitLabel'
txt.data.body = f'Case #2026-CV-DEMO  Exhibit {sn}-A\nDEMONSTRATIVE AID'
txt.data.size = 0.8
lm = bpy.data.materials.new('LblW'); lm.use_nodes = True
b = lm.node_tree.nodes.get('Principled BSDF')
if b: b.inputs['Base Color'].default_value = (1,1,1,1)
txt.data.materials.append(lm)

# Render all cameras
cameras = [o for o in bpy.data.objects if o.type == 'CAMERA']
name_map = {'Camera_BirdEye':'BirdEye','Camera_DriverPOV':'DriverPOV','Camera_Wide':'Wide',
    'Camera_WideAngle':'Wide','Camera_SightLine':'SightLine','Camera_SecurityCam':'SecurityCam'}
for cam in cameras:
    clean = name_map.get(cam.name, cam.name.replace('Camera_',''))
    outpath = f'{OUT}/v12_s{sn}_{clean}.png'
    s.camera = cam
    s.render.filepath = outpath
    print(f'Rendering {cam.name} -> {os.path.basename(outpath)} ...')
    bpy.ops.render.render(write_still=True)
    print(f'  Done')

print(f'=== SCENE {sn} CAMERA FIX COMPLETE ===')
