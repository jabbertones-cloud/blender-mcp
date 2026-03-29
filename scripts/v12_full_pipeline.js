#!/usr/bin/env node
// V12 Full Pipeline — self-contained, writes results to file
const net = require('net');
const fs = require('fs');
const path = require('path');
const BASE = '/Users/tatsheen/claw-architect/openclaw-blender-mcp';
const OUT = `${BASE}/renders/v12_renders`;
const LOG = `${BASE}/renders/v12_renders/pipeline_log.txt`;
fs.mkdirSync(OUT, { recursive: true });
let msgId=0, client=null, buf='', pending=new Map();
function log(msg) { const line = `[${new Date().toISOString()}] ${msg}`; console.log(line); fs.appendFileSync(LOG, line+'\n'); }
function connect() {
  return new Promise((res,rej) => {
    client = net.createConnection(9876,'127.0.0.1',()=>res());
    client.on('data',d=>{buf+=d.toString();const ls=buf.split('\n');buf=ls.pop();
      for(const l of ls){if(!l.trim())continue;try{const m=JSON.parse(l);if(m.id&&pending.has(m.id)){
        const h=pending.get(m.id);pending.delete(m.id);clearTimeout(h.to);h.res(m);}}catch(e){}}});
    client.on('error',rej);
  });
}
function py(code,t=180000){return new Promise((res,rej)=>{msgId++;const id=msgId;
  const to=setTimeout(()=>{pending.delete(id);rej(new Error(`timeout id=${id}`));},t);
  pending.set(id,{res,rej,to});client.write(JSON.stringify({id,command:'execute_python',params:{code}})+'\n');});}

async function processScene(sn) {
  const isNight = sn === 4;
  const blendFile = `${BASE}/renders/v11_scene${sn}_restored.blend`;
  if (!fs.existsSync(blendFile)) { log(`SKIP scene ${sn}: no file`); return; }

  log(`=== SCENE ${sn} START ===`);

  // Load scene
  let r = await py(`import bpy\nbpy.ops.wm.open_mainfile(filepath='${blendFile}')\n__result__ = len(bpy.data.objects)`);
  log(`Loaded scene ${sn}: ${r.result?.result} objects`);

  // Render engine + settings
  r = await py(`
import bpy
s = bpy.context.scene
for eng in ['BLENDER_EEVEE_NEXT','BLENDER_EEVEE','EEVEE']:
    try: s.render.engine = eng; break
    except: continue
s.render.resolution_x = 1920
s.render.resolution_y = 1080
try: s.eevee.taa_render_samples = 64
except: pass
try: s.view_settings.view_transform = 'AgX'
except:
    try: s.view_settings.view_transform = 'Filmic'
    except: pass
s.view_settings.exposure = ${isNight ? 1.0 : 0.5}
__result__ = s.render.engine
`);
  log(`Engine: ${r.result?.result}`);

  // World background
  r = await py(`
import bpy
w = bpy.context.scene.world
if not w:
    w = bpy.data.worlds.new('World')
    bpy.context.scene.world = w
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
bg.inputs['Color'].default_value = ${isNight ? '(0.01, 0.01, 0.02, 1.0)' : '(0.55, 0.65, 0.8, 1.0)'}
bg.inputs['Strength'].default_value = ${isNight ? 0.05 : 1.8}
__result__ = 'world_ok'
`);
  log(`World: ${r.result?.result}`);

  // Boost lights 30%
  r = await py(`
import bpy
ls = []
for o in bpy.data.objects:
    if o.type == 'LIGHT':
        if o.data.energy < 1: o.data.energy = 5.0
        o.data.energy *= 1.3
        ls.append(f'{o.name}={o.data.energy:.0f}')
__result__ = ls
`);
  log(`Lights: ${JSON.stringify(r.result?.result)}`);

  // PBR Materials
  r = await py(`
import bpy
def mk(name,col,met,rou):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    if b:
        b.inputs['Base Color'].default_value = col
        b.inputs['Metallic'].default_value = met
        b.inputs['Roughness'].default_value = rou
    return m
ps = [mk('P_Red',(0.6,0.05,0.05,1),0.9,0.15), mk('P_Blue',(0.05,0.1,0.5,1),0.9,0.15),
      mk('P_White',(0.8,0.8,0.82,1),0.9,0.15), mk('P_Silver',(0.5,0.5,0.52,1),0.9,0.2)]
asph = mk('Asphalt',(0.05,0.05,0.055,1),0.0,0.75)
pi = 0; ap = []
for o in bpy.data.objects:
    if o.type != 'MESH': continue
    nm = o.name.lower()
    hm = o.data.materials and any(m and m.name != 'Material' for m in o.data.materials)
    if any(k in nm for k in ['road','ground','plane','floor','asphalt']):
        if o.data.materials: o.data.materials[0] = asph
        else: o.data.materials.append(asph)
        ap.append(o.name+'->asph')
    elif not hm and any(k in nm for k in ['vehicle','car','sedan','suv','truck','van']):
        p = ps[pi%4]; pi+=1
        if o.data.materials: o.data.materials[0] = p
        else: o.data.materials.append(p)
        ap.append(o.name+'->'+p.name)
__result__ = ap[:8]
`);
  log(`Materials: ${JSON.stringify(r.result?.result)}`);

  // Evidence markers
  r = await py(`
import bpy
ms = []
for i,pos in enumerate([(0,0,0.4),(3,-2,0.4),(-2,1,0.4)]):
    bpy.ops.mesh.primitive_cone_add(radius1=0.3, depth=0.8, location=pos)
    m = bpy.context.active_object
    m.name = f'Marker_{chr(65+i)}'
    mat = bpy.data.materials.new(f'MkMat_{chr(65+i)}')
    mat.use_nodes = True
    b = mat.node_tree.nodes.get('Principled BSDF')
    cols = [(1,0,0,1),(0,0,1,1),(1,1,0,1)]
    if b:
        b.inputs['Base Color'].default_value = cols[i]
        try: b.inputs['Emission Strength'].default_value = 3.0
        except: pass
    m.data.materials.append(mat)
    ms.append(m.name)
__result__ = ms
`);
  log(`Markers: ${JSON.stringify(r.result?.result)}`);

  // Exhibit label
  r = await py(`
import bpy, math
bpy.ops.object.text_add(location=(0,-12,0.01), rotation=(math.radians(-90),0,0))
t = bpy.context.active_object
t.name = 'ExhibitLabel'
t.data.body = 'Case #2026-CV-DEMO  Exhibit ${sn}-A\\nDEMONSTRATIVE AID'
t.data.size = 0.8
mat = bpy.data.materials.new('LabelW')
mat.use_nodes = True
b = mat.node_tree.nodes.get('Principled BSDF')
if b: b.inputs['Base Color'].default_value = (1,1,1,1)
t.data.materials.append(mat)
__result__ = 'label_ok'
`);
  log(`Label: ${r.result?.result}`);

  // Get cameras and render
  r = await py(`
import bpy
__result__ = [o.name for o in bpy.data.objects if o.type=='CAMERA']
`);
  const cameras = r.result?.result || [];
  log(`Cameras: ${JSON.stringify(cameras)}`);

  const nameMap = {'Camera_BirdEye':'BirdEye','Camera_DriverPOV':'DriverPOV','Camera_Wide':'Wide',
    'Camera_WideAngle':'Wide','Camera_SightLine':'SightLine','Camera_SecurityCam':'SecurityCam',
    'Camera_WitnessView':'WitnessView','Camera_TruckPOV':'TruckPOV'};

  for (const cam of cameras) {
    const clean = nameMap[cam] || cam.replace('Camera_','');
    const outPath = `${OUT}/v12_s${sn}_${clean}.png`;
    log(`Rendering ${cam} -> v12_s${sn}_${clean}.png ...`);
    r = await py(`
import bpy
c = bpy.data.objects.get('${cam}')
if c:
    bpy.context.scene.camera = c
    bpy.context.scene.render.filepath = '${outPath}'
    bpy.ops.render.render(write_still=True)
    __result__ = 'ok'
else:
    __result__ = 'not_found'
`);
    log(`  Result: ${r.result?.result}`);
  }

  // Save v12 blend
  r = await py(`import bpy\nbpy.ops.wm.save_as_mainfile(filepath='${BASE}/renders/v12_scene${sn}.blend')\n__result__='saved'`);
  log(`Saved v12_scene${sn}.blend`);
  log(`=== SCENE ${sn} DONE ===`);
}

async function main() {
  fs.writeFileSync(LOG, `V12 Pipeline Start: ${new Date().toISOString()}\n`);
  try {
    await connect();
    log('Connected to Blender MCP');
    for (const sn of [1,2,3,4]) {
      await processScene(sn);
    }
    log('ALL SCENES COMPLETE');

    // Score all renders
    const { execSync } = require('child_process');
    const scores = {};
    const files = fs.readdirSync(OUT).filter(f => f.startsWith('v12_s') && f.endsWith('.png'));
    for (const f of files) {
      try {
        const out = execSync(`node ${BASE}/scripts/3d-forge/render-quality-scorer.js --image ${OUT}/${f} --tier 1 2>&1`, {timeout:30000}).toString();
        const m = out.match(/score=(\d+)/);
        scores[f] = m ? parseInt(m[1]) : 'parse_err';
      } catch(e) { scores[f] = 'err'; }
    }
    log(`\nSCORES: ${JSON.stringify(scores, null, 2)}`);
    fs.writeFileSync(`${OUT}/V12_SCORES.json`, JSON.stringify(scores, null, 2));
    log('Scores saved to V12_SCORES.json');
    log(`PIPELINE COMPLETE: ${new Date().toISOString()}`);
  } catch(e) {
    log(`FATAL ERROR: ${e.message}`);
  }
  fs.writeFileSync(`${OUT}/DONE`, 'done');
  process.exit(0);
}
main();
