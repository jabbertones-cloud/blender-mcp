# Render Quality Fix Guide: Diagnosis and Solutions

## Executive Summary

You have **two distinct issues** affecting your 3D forge renders:

1. **Washed-out renders (vision API: 1.5/10)** — Multiple compounding causes: white background, insufficient light energy, and possibly hardcoded camera position missing the model
2. **shade_smooth bpy_prop_collection error** — You're using `blender_cleanup` with `action: 'shade_smooth'`, which violates the MCP protocol rules and doesn't have the correct implementation

Both are fixable with code changes. Neither is a Blender geometry problem.

---

## Issue 1: Washed-Out Renders (Vision API 1.5/10)

### Root Cause Analysis

Your current setup:
- **Background**: White (`(1.0, 1.0, 1.0)` or similar)
- **Light**: Point light at `(5, 5, 5)` with energy `10`
- **Render**: 2048×2048 EEVEE
- **Result**: Vision API scores 1.5/10 — completely washed out

**Why this fails:**

1. **White background washes out everything.** White is the brightest possible color. When combined with even modest lighting, the entire render becomes blown-out white with no contrast. The model becomes invisible or barely visible. Production testing shows white backgrounds score 1.6/10; gray (0.18) scores 6/10 — a 3.75x improvement just from background color.

2. **Point light energy of 10 is insufficient.** Default Blender point light energy is meant for scene fill, not key lighting. You need **area lights** with much higher energy (200-500W per light) to properly illuminate a model. A single point light at energy 10 is too weak and creates harsh shadows.

3. **Hardcoded light position (5, 5, 5) is scale-dependent.** If your model is 50mm, that position is 100× the model away. If it's 500mm, the light is nearby but positioning. More importantly, it's not relative to your model's actual bounding box. The light might be positioned correctly by coincidence, or it might miss entirely.

4. **Hardcoded camera position likely misses the model.** You haven't mentioned a camera setup, which means Blender is using a default camera. Default cameras are often at fixed world-space positions like `(7.5, 7.5, 7.5)` or similar and may be pointed at the origin. If your model is anywhere else, the render is blank or captures empty space.

### Diagnostic Checklist

Before implementing fixes, verify all of these:

- [ ] Open one of your washed-out renders. Can you see the model at all, or is it just white/blown out?
- [ ] Check your Blender world background node tree. Is it set to white (1.0, 1.0, 1.0)?
- [ ] Check your light setup. How many lights? What type (point, area, sun)? What energy values?
- [ ] Check your camera. Is there a camera object in the scene? What is its position and rotation?
- [ ] Run a quick test render with your current setup and check the pixel data — is it RGB (255, 255, 255) everywhere, or is there color variation?

### Fix: Complete Lighting & Camera Setup

Replace your manual lighting setup with this production-tested code that handles background, 3-point lighting, ground plane, and camera auto-framing:

```javascript
// Step 1: Set render engine (EEVEE with correct params)
await client.call('set_render_settings', {
  engine: 'eevee',           // lowercase — critical
  resolution_x: 2048,
  resolution_y: 2048,
  samples: 64,
  output_format: 'PNG'
});

// Step 2: Build studio lighting + gray background (REQUIRED)
await client.call('execute_python', {
  code: `import bpy, mathutils

# Find model center and size (excludes ground plane if present)
meshes = [o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('_ground_plane')]
if meshes:
    all_coords = []
    for obj in meshes:
        for corner in obj.bound_box:
            wc = obj.matrix_world @ mathutils.Vector(corner)
            all_coords.append(wc)
    xs = [c.x for c in all_coords]
    ys = [c.y for c in all_coords]
    zs = [c.z for c in all_coords]
    center = mathutils.Vector(((min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (min(zs)+max(zs))/2))
    size = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
else:
    center = mathutils.Vector((0, 0, 0))
    size = 2.0

# World background: MEDIUM GRAY (0.18), NOT WHITE
world = bpy.context.scene.world
if not world:
    world = bpy.data.worlds.new('World')
    bpy.context.scene.world = world
world.use_nodes = True
bg_node = world.node_tree.nodes.get('Background')
if bg_node:
    bg_node.inputs[0].default_value = (0.18, 0.18, 0.2, 1.0)
    bg_node.inputs[1].default_value = 1.0

# 3-point area lighting relative to model size
# Key light: 500W, Fill light: 200W, Rim light: 300W
d = max(size * 2.0, 3.0)  # Distance scales with model size
light_configs = [
    ('key_light', (d, d, d*0.8), 500.0),
    ('fill_light', (-d*0.6, d*0.6, d*0.5), 200.0),
    ('rim_light', (0, -d*0.8, d*0.5), 300.0)
]

for name, loc_offset, energy in light_configs:
    # Remove old light if it exists
    old = bpy.data.objects.get(name)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    
    # Create area light
    light_data = bpy.data.lights.new(name=name, type='AREA')
    light_data.energy = energy
    light_data.size = size * 0.5  # Soft shadows proportional to model
    light_obj = bpy.data.objects.new(name=name, object_data=light_data)
    bpy.context.scene.collection.objects.link(light_obj)
    light_obj.location = center + mathutils.Vector(loc_offset)
    
    # Aim light at model center
    direction = center - light_obj.location
    rot_quat = direction.to_track_quat('-Z', 'Y')
    light_obj.rotation_euler = rot_quat.to_euler()

# Ground plane: neutral gray, large enough to catch shadows
# Name MUST be _ground_plane (used for filtering in validator)
ground_old = bpy.data.objects.get('_ground_plane')
if ground_old:
    bpy.data.objects.remove(ground_old, do_unlink=True)

bpy.ops.mesh.primitive_plane_add(size=size*4, location=(center.x, center.y, min(zs) - 0.01 if meshes else -0.5))
ground = bpy.context.active_object
ground.name = '_ground_plane'

# Ground material: neutral gray (0.6)
mat = bpy.data.materials.new('ground_mat')
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get('Principled BSDF')
if bsdf:
    bsdf.inputs['Base Color'].default_value = (0.6, 0.6, 0.6, 1.0)
ground.data.materials.append(mat)

__result__ = {'center': [center.x, center.y, center.z], 'size': size, 'light_distance': d, 'background': 'gray_0.18'}`
});

// Step 3: Auto-frame camera based on model bounding box
await client.call('execute_python', {
  code: `import bpy, mathutils

# Recalculate model center and size (same as lighting setup)
meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.name != '_ground_plane']
if meshes:
    all_coords = []
    for obj in meshes:
        for corner in obj.bound_box:
            world_corner = obj.matrix_world @ mathutils.Vector(corner)
            all_coords.append(world_corner)
    xs = [c.x for c in all_coords]
    ys = [c.y for c in all_coords]
    zs = [c.z for c in all_coords]
    center = mathutils.Vector(((min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (min(zs)+max(zs))/2))
    size = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
else:
    center = mathutils.Vector((0, 0, 0))
    size = 2.0

d = max(size * 2.5, 3.0)

# Create or update camera
cam = bpy.data.objects.get('Camera')
if not cam:
    bpy.ops.object.camera_add()
    cam = bpy.context.active_object

# Position camera for "hero" 3/4 view (frontmost + slightly rotated)
# Produces the best render for marketplace products
cam.location = center + mathutils.Vector((d*0.6, d*0.6, d*0.45))

# Aim camera at model center using to_track_quat (standard Blender method)
direction = center - cam.location
rot_quat = direction.to_track_quat('-Z', 'Y')
cam.rotation_euler = rot_quat.to_euler()

# Set as active camera
bpy.context.scene.camera = cam

__result__ = {'camera_center': [center.x, center.y, center.z], 'camera_distance': d, 'view': 'hero_3_4'}`
});
```

**Critical details in this fix:**

1. **Background is (0.18, 0.18, 0.2)** — medium gray, not white. This is the single biggest improvement.
2. **Light energy values: 500W (key), 200W (fill), 300W (rim)** — much higher than your point light's 10.
3. **Area lights with size = model_size × 0.5** — soft shadows that look professional.
4. **All positions are relative to the model's bounding box** — scales automatically for 50mm or 500mm models.
5. **Camera uses bounding box framing** — automatically points at the model center.
6. **Ground plane is named _ground_plane** — required for validator exclusion.

### Expected Improvement

After applying these fixes:
- **Vision API score: 1.5/10 → 6-7/10** (gray background alone is 3.75× improvement)
- **Render appearance: Blown-out white → Well-lit, properly exposed 3/4 view**
- **Compatibility: Works for 50mm chess pieces and 500mm sculptures with zero code changes**

---

## Issue 2: shade_smooth bpy_prop_collection Error

### Root Cause Analysis

You're calling:
```javascript
await client.call('blender_cleanup', { action: 'shade_smooth' });
```

This fails because of **two violations**:

1. **`blender_cleanup` violates the MCP protocol no-prefix rule.** The MCP server registers the tool as `cleanup`, NOT `blender_cleanup`. When you send `blender_cleanup`, the MCP client either fails silently or throws an error. This is a fundamental protocol rule in the blender-mcp skill (§1): "NO `blender_` prefix on ANY command — this is a universal rule."

2. **There is no `action: 'shade_smooth'` in the cleanup tool.** The cleanup tool is for scene-level operations like removing unused data blocks. Shade smooth is a per-object mesh operation that requires selecting each object and calling `bpy.ops.object.shade_smooth()`.

The `bpy_prop_collection` error you're seeing is likely the cleanup tool failing when you pass an unsupported action, or it's a cascading error from the MCP protocol violation (the command not being recognized).

### Fix: Use execute_python for shade_smooth

Replace the cleanup call with this direct Python implementation:

```javascript
// CORRECT: Use execute_python, not blender_cleanup
await client.call('execute_python', {
  code: `import bpy

# Shade smooth for all mesh objects (except ground plane)
for obj in bpy.data.objects:
    if obj.type == 'MESH' and not obj.name.startswith('_ground_plane'):
        # Set as active and select
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        
        # Apply shade smooth
        bpy.ops.object.shade_smooth()
        
        # Deselect for cleanliness
        obj.select_set(False)

__result__ = {'shaded_smooth': True, 'objects_processed': len([o for o in bpy.data.objects if o.type == 'MESH'])}`
});
```

**Key details:**

1. **`execute_python` not `blender_cleanup`** — correct MCP command name
2. **Loop through each object individually** — shade_smooth operates on the active object; you can't select-all and smooth-all at once
3. **Set active AND select before calling shade_smooth** — both are required by Blender's operator
4. **Exclude _ground_plane** — ground plane doesn't need smoothing
5. **Deselect after processing** — keeps the scene clean
6. **Always set `__result__`** — MCP won't return data without it

### Why This Works

- `bpy.ops.object.shade_smooth()` is a Blender operator that runs in object mode
- It must be called on an active, selected object
- It's not available via the cleanup tool (cleanup only does data block removal)
- The skill documentation explicitly recommends this pattern (§5, Polish Phase: "DO NOT use `blender_cleanup` with `action: 'shade_smooth'`. This fails 100% of the time with a `bpy_prop_collection` error. Use direct Python instead")

### Expected Result

After this fix:
- **No more bpy_prop_collection errors**
- **All mesh objects (except ground plane) are shade-smooth**
- **Renders have smooth, professional appearance instead of faceted/blocky**

---

## Integration: Complete Production Flow

Here's the corrected sequence for your 3D forge producer (all three issues fixed):

```javascript
async function produceAsset(conceptId) {
  // 1. CLEANUP: Start fresh
  await client.call('save_file', { action: 'new', use_empty: true });
  await client.call('execute_python', {
    code: `import bpy
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
for mesh in list(bpy.data.meshes):
    bpy.data.meshes.remove(mesh)
for mat in list(bpy.data.materials):
    bpy.data.materials.remove(mat)
__result__ = {'cleared': True}`
  });

  // 2. GEOMETRY: Create your model (concept steps here)
  // ... concept.blender_steps iteration ...

  // 3. POLISH: Subdivision + Shade Smooth
  await client.call('execute_python', {
    code: `import bpy
for obj in bpy.data.objects:
    if obj.type == 'MESH':
        mod = obj.modifiers.new('Subsurf', 'SUBSURF')
        mod.levels = 2
        mod.render_levels = 2
__result__ = {'subsurf_applied': True}`
  });

  // Shade smooth (FIXED: use execute_python, not blender_cleanup)
  await client.call('execute_python', {
    code: `import bpy
for obj in bpy.data.objects:
    if obj.type == 'MESH' and not obj.name.startswith('_ground_plane'):
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.shade_smooth()
        obj.select_set(False)
__result__ = {'shaded_smooth': True}`
  });

  // 4. LIGHTING & CAMERA (FIXED: gray bg, 3-point lights, auto-framed camera)
  await client.call('set_render_settings', {
    engine: 'eevee',
    resolution_x: 2048,
    resolution_y: 2048,
    samples: 64,
    output_format: 'PNG'
  });

  await client.call('execute_python', {
    code: `import bpy, mathutils
meshes = [o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('_ground_plane')]
if meshes:
    all_coords = []
    for obj in meshes:
        for corner in obj.bound_box:
            wc = obj.matrix_world @ mathutils.Vector(corner)
            all_coords.append(wc)
    xs = [c.x for c in all_coords]
    ys = [c.y for c in all_coords]
    zs = [c.z for c in all_coords]
    center = mathutils.Vector(((min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (min(zs)+max(zs))/2))
    size = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
else:
    center = mathutils.Vector((0, 0, 0))
    size = 2.0

world = bpy.context.scene.world
if not world:
    world = bpy.data.worlds.new('World')
    bpy.context.scene.world = world
world.use_nodes = True
bg_node = world.node_tree.nodes.get('Background')
if bg_node:
    bg_node.inputs[0].default_value = (0.18, 0.18, 0.2, 1.0)
    bg_node.inputs[1].default_value = 1.0

d = max(size * 2.0, 3.0)
for name, loc_offset, energy in [('key_light', (d, d, d*0.8), 500.0), ('fill_light', (-d*0.6, d*0.6, d*0.5), 200.0), ('rim_light', (0, -d*0.8, d*0.5), 300.0)]:
    old = bpy.data.objects.get(name)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    light_data = bpy.data.lights.new(name=name, type='AREA')
    light_data.energy = energy
    light_data.size = size * 0.5
    light_obj = bpy.data.objects.new(name=name, object_data=light_data)
    bpy.context.scene.collection.objects.link(light_obj)
    light_obj.location = center + mathutils.Vector(loc_offset)
    direction = center - light_obj.location
    rot_quat = direction.to_track_quat('-Z', 'Y')
    light_obj.rotation_euler = rot_quat.to_euler()

ground_old = bpy.data.objects.get('_ground_plane')
if ground_old:
    bpy.data.objects.remove(ground_old, do_unlink=True)
bpy.ops.mesh.primitive_plane_add(size=size*4, location=(center.x, center.y, min(zs) - 0.01 if meshes else -0.5))
ground = bpy.context.active_object
ground.name = '_ground_plane'
mat = bpy.data.materials.new('ground_mat')
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get('Principled BSDF')
if bsdf:
    bsdf.inputs['Base Color'].default_value = (0.6, 0.6, 0.6, 1.0)
ground.data.materials.append(mat)

__result__ = {'lighting_ready': True}`
  });

  // Camera auto-frame
  await client.call('execute_python', {
    code: `import bpy, mathutils
meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.name != '_ground_plane']
if meshes:
    all_coords = []
    for obj in meshes:
        for corner in obj.bound_box:
            world_corner = obj.matrix_world @ mathutils.Vector(corner)
            all_coords.append(world_corner)
    xs = [c.x for c in all_coords]
    ys = [c.y for c in all_coords]
    zs = [c.z for c in all_coords]
    center = mathutils.Vector(((min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (min(zs)+max(zs))/2))
    size = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
else:
    center = mathutils.Vector((0, 0, 0))
    size = 2.0

d = max(size * 2.5, 3.0)
cam = bpy.data.objects.get('Camera')
if not cam:
    bpy.ops.object.camera_add()
    cam = bpy.context.active_object
cam.location = center + mathutils.Vector((d*0.6, d*0.6, d*0.45))
direction = center - cam.location
rot_quat = direction.to_track_quat('-Z', 'Y')
cam.rotation_euler = rot_quat.to_euler()
bpy.context.scene.camera = cam
__result__ = {'camera_ready': True}`
  });

  // 5. EXPORT
  const outputDir = `/path/to/exports/${conceptId}`;
  await client.call('save_file', {
    action: 'save_as',
    filepath: path.join(outputDir, 'model.blend')
  });

  // 6. RENDER
  await client.call('render', {
    output_path: path.join(outputDir, 'hero.png')  // NOT filepath
  });

  return { success: true, outputDir };
}
```

---

## Summary Table: Before & After

| Issue | Before | After | Root Cause | Fix |
|-------|--------|-------|-----------|-----|
| Washed-out renders (1.5/10) | White background + weak point light + hardcoded camera | Gray (0.18) + 3-point area lights (500/200/300W) + auto-framed camera | Multiple: white background, insufficient light energy, possible camera miss | Complete lighting/camera setup from skill |
| shade_smooth error | `blender_cleanup` with `action: 'shade_smooth'` causing `bpy_prop_collection` error | `execute_python` with per-object loop | Wrong MCP command name (has `blender_` prefix) + wrong tool (cleanup isn't for shade_smooth) | Use direct execute_python with proper operator calls |

---

## Implementation Checklist

- [ ] Replace white background with gray (0.18, 0.18, 0.2) in world nodes
- [ ] Replace point light(s) with 3-point area lighting (500W key, 200W fill, 300W rim)
- [ ] Implement auto-framing camera that calculates position from bounding box
- [ ] Replace `blender_cleanup` shade_smooth call with `execute_python` loop
- [ ] Ensure all lights and camera positions are relative to model center/size
- [ ] Verify ground plane is named `_ground_plane` for validator exclusion
- [ ] Test with a sample model and verify vision API score improves to 6+/10
- [ ] Run full production cycle with updated code (cleanup → geometry → polish → lighting → render)
- [ ] Check that no `bpy_prop_collection` errors appear in logs

---

## Key Learnings

1. **Background color is 50% of visual quality** — white vs. gray is a 3.75× difference in vision API scores
2. **Light energy compounds with background** — weak lights on white are invisible; strong lights on gray look professional
3. **MCP protocol violations are silent** — sending `blender_cleanup` instead of `cleanup` can fail without clear error messages
4. **Shade smooth requires per-object loops** — Blender's operator doesn't support batch operations; you must select, apply, deselect for each object
5. **Camera auto-framing beats hardcoding** — calculating from bounding box works for any model size; hardcoded positions miss frequently

---

## Production Testing Results

Baseline (white background, point light energy 10, hardcoded camera):
- Vision API: 1.6/10
- Render: blown-out white, model barely visible
- Status: REJECT

With fixes (gray background, 3-point area lights 500/200/300W, auto-framed camera):
- Vision API: 6.0/10
- Render: well-exposed, model clearly visible with proper shadows
- Status: NEEDS_REVISION (ready for material/detail improvements)

The ceiling for improvement is visual quality of the model geometry itself — the lighting/background setup now properly exposes whatever you build.
