const net = require('net');
const fs = require('fs');
const path = require('path');

// MCP connection helper - executes Python in Blender on port 9876
function mcpCall(command, params = {}) {
  return new Promise((resolve, reject) => {
    const s = new net.Socket();
    s.setTimeout(30000);
    s.connect(9876, '127.0.0.1', () => {
      const msg = JSON.stringify({ id: 1, command, params });
      s.write(msg);
    });
    let data = '';
    let depth = 0;
    s.on('data', chunk => {
      data += chunk.toString();
      for (const c of chunk.toString()) {
        if (c === '{') depth++;
        else if (c === '}') depth--;
      }
      if (depth === 0) {
        s.destroy();
        try {
          resolve(JSON.parse(data));
        } catch (e) {
          reject(new Error(`Invalid JSON: ${data}`));
        }
      }
    });
    s.on('error', reject);
    s.on('timeout', () => {
      s.destroy();
      reject(new Error('MCP timeout after 30s'));
    });
  });
}

// EXERCISE CATALOG - ordered by difficulty and relevance to forensic scenes
const EXERCISES = [
  {
    id: 'EX_001_3POINT_LIGHTING',
    name: '3-Point Area Lighting Setup',
    difficulty: 'beginner',
    category: 'lighting',
    youtube_ref: 'Cinematic Lighting in Blender (Superhive)',
    description: 'Set up key (500W), fill (200W), rim (300W) area lights around a test object',
    code: `import bpy, mathutils
# Clean scene
for obj in list(bpy.data.objects): bpy.data.objects.remove(obj, do_unlink=True)
# Add test cube
bpy.ops.mesh.primitive_cube_add(size=2, location=(0,0,1))
# 3-point lighting
for name, loc, energy in [('key', (4,4,4), 500), ('fill', (-3,3,3), 200), ('rim', (0,-4,3), 300)]:
    ld = bpy.data.lights.new(name=name, type='AREA')
    ld.energy = energy
    ld.size = 2.0
    lo = bpy.data.objects.new(name=name, object_data=ld)
    bpy.context.scene.collection.objects.link(lo)
    lo.location = mathutils.Vector(loc)
    d = mathutils.Vector((0,0,1)) - lo.location
    lo.rotation_euler = d.to_track_quat('-Z','Y').to_euler()
lights = [o for o in bpy.data.objects if o.type == 'LIGHT']
__result__ = {'lights': len(lights), 'total_energy': sum(o.data.energy for o in lights)}`,
    validate: (result) => result.lights === 3 && result.total_energy === 1000,
    skill_gained: '3_point_lighting'
  },
  {
    id: 'EX_002_PBR_MATERIALS',
    name: 'PBR Material Application',
    difficulty: 'beginner',
    category: 'materials',
    youtube_ref: '3D Cars: Inside and Out (CG Masters)',
    description: 'Create metallic car paint, glass, and rubber materials',
    code: `import bpy
# Create metallic paint
paint = bpy.data.materials.new('Car_Paint')
paint.use_nodes = True
bsdf = paint.node_tree.nodes['Principled BSDF']
bsdf.inputs['Base Color'].default_value = (0.8, 0.1, 0.1, 1.0)
bsdf.inputs['Metallic'].default_value = 0.9
bsdf.inputs['Roughness'].default_value = 0.2
bsdf.inputs['Coat Weight'].default_value = 1.0
bsdf.inputs['Coat Roughness'].default_value = 0.1
# Create glass
glass = bpy.data.materials.new('Vehicle_Glass')
glass.use_nodes = True
gb = glass.node_tree.nodes['Principled BSDF']
gb.inputs['Transmission Weight'].default_value = 0.95
gb.inputs['IOR'].default_value = 1.52
gb.inputs['Roughness'].default_value = 0.0
# Create rubber
rubber = bpy.data.materials.new('Tire_Rubber')
rubber.use_nodes = True
rb = rubber.node_tree.nodes['Principled BSDF']
rb.inputs['Base Color'].default_value = (0.02, 0.02, 0.02, 1.0)
rb.inputs['Roughness'].default_value = 0.95
mats = list(bpy.data.materials)
__result__ = {'materials_created': len([m for m in mats if m.name in ['Car_Paint','Vehicle_Glass','Tire_Rubber']]), 'names': [m.name for m in mats if not m.name.startswith('Dots')]}`,
    validate: (result) => result.materials_created === 3,
    skill_gained: 'pbr_materials'
  },
  {
    id: 'EX_003_NIGHT_LIGHTING',
    name: 'Night Scene Sodium Vapor Lighting',
    difficulty: 'intermediate',
    category: 'lighting',
    youtube_ref: 'Lighting a Night Street Scene (BlenderNation)',
    description: 'Create a night parking lot with sodium vapor lamps and ambient moonlight',
    code: `import bpy, mathutils, math
# Clean
for obj in list(bpy.data.objects): bpy.data.objects.remove(obj, do_unlink=True)
# Ground
bpy.ops.mesh.primitive_plane_add(size=40, location=(0,0,0))
ground = bpy.context.active_object
ground.name = '_ground_plane'
mat = bpy.data.materials.new('asphalt')
mat.use_nodes = True
bsdf = mat.node_tree.nodes['Principled BSDF']
bsdf.inputs['Base Color'].default_value = (0.08, 0.08, 0.09, 1.0)
bsdf.inputs['Roughness'].default_value = 0.9
ground.data.materials.append(mat)
# Dark world
world = bpy.context.scene.world or bpy.data.worlds.new('World')
bpy.context.scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes['Background']
bg.inputs[0].default_value = (0.005, 0.005, 0.015, 1.0)
bg.inputs[1].default_value = 0.5
# Sodium vapor lamps (2700K warm)
lamp_positions = [(-8,-8,6), (8,-8,6), (-8,8,6), (8,8,6), (0,0,7)]
for i, pos in enumerate(lamp_positions):
    ld = bpy.data.lights.new(name=f'sodium_{i}', type='SPOT')
    ld.energy = 800
    ld.color = (1.0, 0.65, 0.2)
    ld.spot_size = math.radians(120)
    ld.spot_blend = 0.5
    ld.shadow_soft_size = 0.5
    lo = bpy.data.objects.new(name=f'sodium_{i}', object_data=ld)
    bpy.context.scene.collection.objects.link(lo)
    lo.location = mathutils.Vector(pos)
    lo.rotation_euler = (0, 0, 0)
    d = mathutils.Vector((pos[0], pos[1], 0)) - lo.location
    if d.length > 0.001:
        lo.rotation_euler = d.to_track_quat('-Z','Y').to_euler()
lights = [o for o in bpy.data.objects if o.type == 'LIGHT']
__result__ = {'lights': len(lights), 'total_energy': sum(o.data.energy for o in lights), 'has_dark_world': bg.inputs[1].default_value < 1.0}`,
    validate: (result) => result.lights >= 5 && result.has_dark_world,
    skill_gained: 'night_lighting'
  },
  {
    id: 'EX_004_HDRI_ENVIRONMENT',
    name: 'HDRI Environment Setup',
    difficulty: 'intermediate',
    category: 'environment',
    youtube_ref: 'Polyhaven HDRI Tutorial',
    description: 'Load and configure an HDRI for realistic outdoor lighting',
    code: `import bpy, os
# Check for downloaded HDRIs
hdri_dir = '/Users/tatsheen/claw-architect/openclaw-blender-mcp/assets/hdri'
os.makedirs(hdri_dir, exist_ok=True)
hdri_files = [f for f in os.listdir(hdri_dir) if f.endswith(('.exr','.hdr'))] if os.path.exists(hdri_dir) else []
# Setup world nodes for HDRI (even without file, create the node setup)
world = bpy.context.scene.world or bpy.data.worlds.new('World')
bpy.context.scene.world = world
world.use_nodes = True
nodes = world.node_tree.nodes
links = world.node_tree.links
# Clear existing
for n in list(nodes): nodes.remove(n)
# Create HDRI node chain
bg = nodes.new('ShaderNodeBackground')
env_tex = nodes.new('ShaderNodeTexEnvironment')
mapping = nodes.new('ShaderNodeMapping')
tex_coord = nodes.new('ShaderNodeTexCoord')
output = nodes.new('ShaderNodeOutputWorld')
links.new(tex_coord.outputs['Generated'], mapping.inputs['Vector'])
links.new(mapping.outputs['Vector'], env_tex.inputs['Vector'])
links.new(env_tex.outputs['Color'], bg.inputs['Color'])
links.new(bg.outputs['Background'], output.inputs['Surface'])
bg.inputs['Strength'].default_value = 1.0
if hdri_files:
    env_tex.image = bpy.data.images.load(os.path.join(hdri_dir, hdri_files[0]))
__result__ = {'hdri_node_setup': True, 'hdri_files_found': len(hdri_files), 'node_count': len(nodes)}`,
    validate: (result) => result.hdri_node_setup && result.node_count >= 5,
    skill_gained: 'hdri_environment'
  },
  {
    id: 'EX_005_IMPACT_DEFORMATION',
    name: 'Vehicle Impact Deformation',
    difficulty: 'advanced',
    category: 'forensic',
    youtube_ref: 'Blender Full Car Crash Simulation (BlenderNation)',
    description: 'Apply mesh deformation to simulate vehicle collision damage',
    code: `import bpy, mathutils
# Create test vehicle (cube proxy)
for obj in list(bpy.data.objects): bpy.data.objects.remove(obj, do_unlink=True)
bpy.ops.mesh.primitive_cube_add(size=4, location=(0,0,1))
vehicle = bpy.context.active_object
vehicle.name = 'test_vehicle'
# Subdivide for deformation detail
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.subdivide(number_cuts=4)
bpy.ops.object.mode_set(mode='OBJECT')
# Apply impact deformation at front
impact_point = mathutils.Vector((2, 0, 0.8))
mesh = vehicle.data
for v in mesh.vertices:
    world_co = vehicle.matrix_world @ v.co
    dist = (world_co - impact_point).length
    if dist < 2.0:
        falloff = 1.0 - (dist / 2.0)
        v.co.x -= falloff * 0.5
        v.co.z -= falloff * 0.15
        v.co.y += (0.5 - abs(v.co.y)) * falloff * 0.1
mesh.update()
# Add crumple modifier
sub = vehicle.modifiers.new('Crumple_Detail', 'SUBSURF')
sub.levels = 2
__result__ = {'deformed': True, 'vertex_count': len(mesh.vertices), 'has_subsurf': len(vehicle.modifiers) > 0}`,
    validate: (result) => result.deformed && result.vertex_count > 100,
    skill_gained: 'impact_deformation'
  }
];

// Run a specific exercise by ID
async function runExercise(exerciseId) {
  const exercise = EXERCISES.find(e => e.id === exerciseId);
  if (!exercise) {
    throw new Error(`Exercise not found: ${exerciseId}`);
  }

  const startTime = Date.now();
  try {
    const result = await mcpCall('execute_python', { code: exercise.code });
    const elapsedMs = Date.now() - startTime;
    const isValid = exercise.validate(result);

    return {
      exerciseId: exercise.id,
      name: exercise.name,
      success: isValid,
      result: result,
      elapsedMs: elapsedMs,
      skill_gained: isValid ? exercise.skill_gained : null,
      timestamp: new Date().toISOString()
    };
  } catch (error) {
    return {
      exerciseId: exercise.id,
      name: exercise.name,
      success: false,
      error: error.message,
      elapsedMs: Date.now() - startTime,
      timestamp: new Date().toISOString()
    };
  }
}

// Get next unpracticed exercise based on skill_progress.json
async function runNextUnpracticed() {
  const progressFile = '/Users/tatsheen/claw-architect/openclaw-blender-mcp/data/skill_progress.json';
  let progress = {
    version: '1.0',
    exercises_completed: [],
    skills_mastered: [],
    skills_in_progress: [],
    total_practice_minutes: 0,
    last_practice: null,
    exercise_history: []
  };

  if (fs.existsSync(progressFile)) {
    progress = JSON.parse(fs.readFileSync(progressFile, 'utf8'));
  }

  // Find next exercise not yet completed
  const nextEx = EXERCISES.find(e => !progress.exercises_completed.includes(e.id));
  if (!nextEx) {
    return {
      message: 'All exercises completed!',
      progress: progress
    };
  }

  console.log(`[SKILL] Running exercise: ${nextEx.name}`);
  const result = await runExercise(nextEx.id);

  // Update progress
  if (result.success) {
    progress.exercises_completed.push(nextEx.id);
    if (!progress.skills_in_progress.includes(result.skill_gained)) {
      progress.skills_in_progress.push(result.skill_gained);
    }
  }

  progress.exercise_history.push(result);
  progress.last_practice = new Date().toISOString();
  progress.total_practice_minutes += Math.round(result.elapsedMs / 60000);

  fs.writeFileSync(progressFile, JSON.stringify(progress, null, 2));

  return {
    exerciseResult: result,
    progress: progress
  };
}

// Get current skill progress
function getSkillProgress() {
  const progressFile = '/Users/tatsheen/claw-architect/openclaw-blender-mcp/data/skill_progress.json';
  if (!fs.existsSync(progressFile)) {
    return {
      version: '1.0',
      exercises_completed: [],
      skills_mastered: [],
      skills_in_progress: [],
      total_practice_minutes: 0,
      last_practice: null,
      exercise_history: []
    };
  }
  return JSON.parse(fs.readFileSync(progressFile, 'utf8'));
}

module.exports = {
  EXERCISES,
  mcpCall,
  runExercise,
  runNextUnpracticed,
  getSkillProgress
};
