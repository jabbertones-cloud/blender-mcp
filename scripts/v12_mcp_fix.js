#!/usr/bin/env node
/**
 * V12 MCP Fix & Render — Uses proven TCP protocol to apply fixes to v11 scenes
 * Usage: node v12_mcp_fix.js [1|2|3|4|all]
 */
const net = require('net');
const fs = require('fs');
const path = require('path');

const HOST = '127.0.0.1';
const PORT = 9876;
const BASE = '/Users/tatsheen/claw-architect/openclaw-blender-mcp';
const RENDERS_OUT = `${BASE}/renders/v12_renders`;

let msgId = 0, client = null, buffer = '', pending = new Map();

function connect() {
  return new Promise((resolve, reject) => {
    client = net.createConnection(PORT, HOST, () => { resolve(); });
    client.on('data', d => {
      buffer += d.toString();
      const lines = buffer.split('\n');
      buffer = lines.pop();
      for (const line of lines) {
        if (!line.trim()) continue;
        try {
          const msg = JSON.parse(line);
          if (msg.id && pending.has(msg.id)) {
            const h = pending.get(msg.id);
            pending.delete(msg.id);
            clearTimeout(h.timeout);
            h.resolve(msg);
          }
        } catch(e) {}
      }
    });
    client.on('error', reject);
  });
}

function runPy(code, timeoutMs = 60000) {
  return new Promise((resolve, reject) => {
    msgId++;
    const id = msgId;
    const timeout = setTimeout(() => { pending.delete(id); reject(new Error(`Timeout msg ${id}`)); }, timeoutMs);
    pending.set(id, { resolve, reject, timeout });
    client.write(JSON.stringify({ id, command: 'execute_python', params: { code } }) + '\n');
  });
}

async function run() {
  const arg = process.argv[2] || 'all';
  const scenes = arg === 'all' ? [1,2,3,4] : [parseInt(arg)];
  
  fs.mkdirSync(RENDERS_OUT, { recursive: true });
  await connect();
  console.log('Connected to Blender MCP');

  for (const sn of scenes) {
    console.log(`\n=== SCENE ${sn} ===`);
    const blendFile = `${BASE}/renders/v11_scene${sn}_restored.blend`;
    if (!fs.existsSync(blendFile)) {
      console.log(`  SKIP: ${blendFile} not found`);
      continue;
    }

    // STEP 1: Load scene
    console.log('  Loading blend file...');
    let r = await runPy(`import bpy\nbpy.ops.wm.open_mainfile(filepath='${blendFile}')\n__result__ = {'objects': len(bpy.data.objects), 'scene': bpy.context.scene.name}`);
    console.log('  Loaded:', r.result?.result);

    // STEP 2: Set render engine (EEVEE — proven to work)
    console.log('  Setting render engine...');
    r = await runPy(`
import bpy
s = bpy.context.scene
engines = ['BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE', 'EEVEE']
for eng in engines:
    try:
        s.render.engine = eng
        break
    except:
        continue
s.render.resolution_x = 1920
s.render.resolution_y = 1080
s.render.resolution_percentage = 100
try:
    s.eevee.taa_render_samples = 64
except:
    pass
# Color management
try:
    s.view_settings.view_transform = 'AgX'
except:
    try:
        s.view_settings.view_transform = 'Filmic'
    except:
        pass
s.view_settings.exposure = ${sn === 4 ? '1.0' : '0.5'}
__result__ = {'engine': s.render.engine, 'color': s.view_settings.view_transform, 'exposure': s.view_settings.exposure}
`);
    console.log('  Engine:', r.result?.result);

    // STEP 3: World background
    const isNight = sn === 4;
    console.log('  Setting world background...');
    r = await runPy(`
import bpy
world = bpy.context.scene.world
if not world:
    world = bpy.data.worlds.new('World')
    bpy.context.scene.world = world
world.use_nodes = True
tree = world.node_tree
bg = None
out = None
for n in tree.nodes:
    if n.type == 'BACKGROUND': bg = n
    if n.type == 'OUTPUT_WORLD': out = n
if not bg:
    for n in tree.nodes: tree.nodes.remove(n)
    bg = tree.nodes.new('ShaderNodeBackground')
    out = tree.nodes.new('ShaderNodeOutputWorld')
    tree.links.new(bg.outputs['Background'], out.inputs['Surface'])
${isNight ? `
bg.inputs['Color'].default_value = (0.01, 0.01, 0.02, 1.0)
bg.inputs['Strength'].default_value = 0.05
` : `
bg.inputs['Color'].default_value = (0.55, 0.65, 0.8, 1.0)
bg.inputs['Strength'].default_value = 1.8
`}
__result__ = 'world set night=${isNight}'
`);
    console.log('  World:', r.result?.result);

    // STEP 4: Gentle light boost (30%)
    console.log('  Adjusting lights...');
    r = await runPy(`
import bpy
lights = []
for obj in bpy.data.objects:
    if obj.type == 'LIGHT':
        if obj.data.energy < 1.0:
            obj.data.energy = 5.0
        obj.data.energy *= 1.3
        lights.append(f'{obj.name}={obj.data.energy:.1f}')
__result__ = lights
`);
    console.log('  Lights:', r.result?.result);

    // STEP 5: PBR Materials
    console.log('  Applying PBR materials...');
    r = await runPy(`
import bpy
applied = []

def make_mat(name, color, metallic, roughness):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    if bsdf:
        bsdf.inputs['Base Color'].default_value = color
        bsdf.inputs['Metallic'].default_value = metallic
        bsdf.inputs['Roughness'].default_value = roughness
    return mat

paints = [
    make_mat('Paint_Red', (0.6, 0.05, 0.05, 1), 0.9, 0.15),
    make_mat('Paint_Blue', (0.05, 0.1, 0.5, 1), 0.9, 0.15),
    make_mat('Paint_White', (0.8, 0.8, 0.82, 1), 0.9, 0.15),
    make_mat('Paint_Silver', (0.5, 0.5, 0.52, 1), 0.9, 0.2),
]
asphalt = make_mat('Asphalt', (0.05, 0.05, 0.055, 1), 0.0, 0.75)

pi = 0
for obj in bpy.data.objects:
    if obj.type != 'MESH': continue
    nm = obj.name.lower()
    has_mat = obj.data.materials and any(m and m.name != 'Material' for m in obj.data.materials)
    if 'road' in nm or 'ground' in nm or 'plane' in nm or 'floor' in nm or 'asphalt' in nm:
        if obj.data.materials: obj.data.materials[0] = asphalt
        else: obj.data.materials.append(asphalt)
        applied.append(f'{obj.name}->asphalt')
    elif not has_mat and ('vehicle' in nm or 'car' in nm or 'sedan' in nm or 'suv' in nm or 'truck' in nm or 'van' in nm):
        p = paints[pi % len(paints)]
        pi += 1
        if obj.data.materials: obj.data.materials[0] = p
        else: obj.data.materials.append(p)
        applied.append(f'{obj.name}->{p.name}')
__result__ = applied[:10]
`);
    console.log('  Materials:', r.result?.result);

    // STEP 6: Evidence markers
    console.log('  Adding evidence markers...');
    r = await runPy(`
import bpy
markers_added = []
positions = [(0, 0, 0.4), (3, -2, 0.4), (-2, 1, 0.4)]
colors = [(1,0,0,1), (0,0,1,1), (1,1,0,1)]
names = ['A','B','C']
for i, pos in enumerate(positions[:3]):
    bpy.ops.mesh.primitive_cone_add(radius1=0.3, depth=0.8, location=pos)
    m = bpy.context.active_object
    m.name = f'Evidence_Marker_{names[i]}'
    mat = bpy.data.materials.new(f'Marker_{names[i]}')
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    if bsdf:
        bsdf.inputs['Base Color'].default_value = colors[i]
        try: bsdf.inputs['Emission Color'].default_value = colors[i]
        except: pass
        try: bsdf.inputs['Emission Strength'].default_value = 3.0
        except: pass
    m.data.materials.append(mat)
    markers_added.append(m.name)
__result__ = markers_added
`);
    console.log('  Markers:', r.result?.result);

    // STEP 7: Exhibit label
    console.log('  Adding exhibit label...');
    r = await runPy(`
import bpy, math
bpy.ops.object.text_add(location=(0, -12, 0.01), rotation=(math.radians(-90), 0, 0))
txt = bpy.context.active_object
txt.name = 'Exhibit_Label'
txt.data.body = 'Case #2026-CV-DEMO  Exhibit ${sn}-A\\nDEMONSTRATIVE AID - NOT TO SCALE'
txt.data.size = 0.8
mat = bpy.data.materials.new('Label_White')
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get('Principled BSDF')
if bsdf:
    bsdf.inputs['Base Color'].default_value = (1,1,1,1)
    try: bsdf.inputs['Emission Strength'].default_value = 1.0
    except: pass
txt.data.materials.append(mat)
__result__ = 'label added'
`);
    console.log('  Label:', r.result?.result);

    // STEP 8: List cameras and render each
    console.log('  Finding cameras...');
    r = await runPy(`
import bpy
cams = []
for obj in bpy.data.objects:
    if obj.type == 'CAMERA':
        cams.append(obj.name)
__result__ = cams
`);
    const cameras = r.result?.result || [];
    console.log('  Cameras:', cameras);

    // Map camera names to clean output names
    const camNameMap = {
      'Camera_BirdEye': 'BirdEye', 'Camera_DriverPOV': 'DriverPOV',
      'Camera_Wide': 'Wide', 'Camera_WideAngle': 'Wide',
      'Camera_SightLine': 'SightLine', 'Camera_SecurityCam': 'SecurityCam',
      'Camera_WitnessView': 'WitnessView', 'Camera_TruckPOV': 'TruckPOV',
      'BirdEye': 'BirdEye', 'DriverPOV': 'DriverPOV', 'Wide': 'Wide',
      'WideAngle': 'Wide', 'SightLine': 'SightLine', 'SecurityCam': 'SecurityCam'
    };

    for (const cam of cameras) {
      const cleanName = camNameMap[cam] || cam.replace('Camera_','');
      const outPath = `${RENDERS_OUT}/v12_scene${sn}_${cleanName}.png`;
      console.log(`  Rendering ${cam} -> ${path.basename(outPath)}...`);
      r = await runPy(`
import bpy
scene = bpy.context.scene
cam = bpy.data.objects.get('${cam}')
if cam:
    scene.camera = cam
    scene.render.filepath = '${outPath}'
    bpy.ops.render.render(write_still=True)
    __result__ = 'rendered ${cam}'
else:
    __result__ = 'camera not found: ${cam}'
`, 120000);
      console.log(`    ${r.result?.result}`);
    }

    // Save as v12
    const v12Path = `${BASE}/renders/v12_scene${sn}.blend`;
    r = await runPy(`import bpy\nbpy.ops.wm.save_as_mainfile(filepath='${v12Path}')\n__result__ = 'saved'`);
    console.log(`  Saved: ${v12Path}`);
  }

  client.end();
  console.log('\n=== ALL DONE ===');
}

run().catch(e => { console.error(e); process.exit(1); });
