# 3D Forge Render Quality Fix Guide

## Diagnosis Summary

Your renders are scoring 1.5/10 from the vision API due to two distinct issues:

1. **Washed Out Lighting & Background** (Primary issue affecting quality score)
2. **shade_smooth Implementation Error** (Secondary issue affecting polish phase)

---

## Issue 1: Washed Out Renders (Vision API 1.5/10)

### Root Causes

#### Problem A: White Background (0.95 instead of 0.18)

Your current setup uses a white background, which the vision API automatically penalizes. Testing data shows:
- **White background (0.95):** Consistent 1.6/10 vision score (washed out, no contrast)
- **Medium gray background (0.18):** 6/10 vision score (proper contrast, acceptable detail visibility)

White backgrounds eliminate shadow definition and make models appear flat and overexposed. The vision API struggles to assess material quality, surface detail, and proportions when the entire render is blown out.

#### Problem B: Insufficient Light Energy (Single 10W Point Light)

Your current setup:
```
Point light at (5,5,5) with energy 10
```

This is **60x too dim**. Blender's default light energy multiplier makes this nearly invisible. The proper studio lighting requires:
- **Key light (main):** 500W area light
- **Fill light (soften shadows):** 200W area light  
- **Rim light (separation):** 300W area light

With only 10W, your model is lit almost entirely by the world background, creating flat, colorless renders that score 1-2/10 on visual quality.

### Corrected Lighting & Background Setup

Replace your current lighting code with this complete studio setup:

```javascript
// Corrected: 3-point area lighting + gray background
await client.call('execute_python', {
  code: `import bpy, mathutils

# Find model center and bounding box for relative positioning
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
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
    center = mathutils.Vector((0,0,0))
    size = 2.0

# CRITICAL: World background must be MEDIUM GRAY (0.18), NOT white
world = bpy.context.scene.world
if not world:
    world = bpy.data.worlds.new('World')
    bpy.context.scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get('Background')
if bg:
    bg.inputs[0].default_value = (0.18, 0.18, 0.2, 1.0)  # Medium gray RGB
    bg.inputs[1].default_value = 1.0  # Strength

# Calculate light distance relative to model size
d = max(size * 2.0, 3.0)

# 3-point AREA lighting with proper energies
lighting_config = [
    ('key_light', (d, d, d*0.8), 500.0),      # Main key light: 500W
    ('fill_light', (-d*0.6, d*0.6, d*0.5), 200.0),  # Fill light: 200W
    ('rim_light', (0, -d*0.8, d*0.5), 300.0)  # Rim light: 300W
]

for name, loc_offset, energy in lighting_config:
    light_data = bpy.data.lights.new(name=name, type='AREA')
    light_data.energy = energy  # Use energy directly (in watts for EEVEE)
    light_data.size = size * 0.5  # Light size proportional to model
    
    light_obj = bpy.data.objects.new(name=name, object_data=light_data)
    bpy.context.scene.collection.objects.link(light_obj)
    
    # Position relative to model center
    light_obj.location = center + mathutils.Vector(loc_offset)
    
    # Aim light at model center
    direction = center - light_obj.location
    rotation_quat = direction.to_track_quat('-Z', 'Y')
    light_obj.rotation_euler = rotation_quat.to_euler()

# Ground plane: size proportional to model, with neutral gray material
bpy.ops.mesh.primitive_plane_add(size=size*4, location=(center.x, center.y, min(zs) - 0.01 if meshes else -0.5))
ground = bpy.context.active_object
ground.name = '_ground_plane'

# Assign gray material to ground plane
ground_mat = bpy.data.materials.new('ground_mat')
ground_mat.use_nodes = True
bsdf = ground_mat.node_tree.nodes.get('Principled BSDF')
if bsdf:
    bsdf.inputs['Base Color'].default_value = (0.6, 0.6, 0.6, 1.0)  # Neutral gray
ground.data.materials.append(ground_mat)

__result__ = {'center': [center.x, center.y, center.z], 'size': size, 'light_distance': d, 'background': '0.18 gray', 'lights': ['key:500W', 'fill:200W', 'rim:300W']}`
});
```

### Key Changes Explained

| Parameter | Old Value | New Value | Impact |
|-----------|-----------|-----------|---------|
| Background color | (1.0, 1.0, 1.0) white | (0.18, 0.18, 0.2) gray | Eliminates washout; improves vision API by ~4 points |
| Light type | Point | Area | Softer shadows; more professional look |
| Key light energy | 10W | 500W | 50x brighter; proper exposure |
| Fill light energy | none | 200W | Fills shadows; reduces harsh contrast |
| Rim light energy | none | 300W | Separates model from background |
| Light size | N/A | size × 0.5 | Proportional soft shadows |
| Ground plane size | varies | size × 4 | Proportional to model; not inflating bounding box |

### Expected Improvement

After applying this corrected setup:
- **Vision API score:** Should improve from 1.5/10 → 6-7/10 (assuming geometry is solid)
- **Render appearance:** Professional three-point studio lighting with proper contrast
- **Shadow definition:** Soft, realistic shadows from area lights

---

## Issue 2: shade_smooth Implementation Error

### Root Cause

Your code is using:
```javascript
await client.call('blender_cleanup', { action: 'shade_smooth' });
```

This fails 100% of the time with a `bpy_prop_collection` error because:
1. **`blender_cleanup` is not the right tool** for smooth shading
2. The MCP tool `save_file` handles cleanup actions, but `shade_smooth` requires object selection context
3. Trying to smooth-shade all objects without proper per-object selection leads to Blender's property collection validation errors

### Corrected shade_smooth Implementation

Use `execute_python` with explicit per-object selection:

```javascript
// CORRECT: shade_smooth via execute_python with per-object selection
await client.call('execute_python', {
  code: `import bpy

for obj in bpy.data.objects:
    if obj.type == 'MESH' and not obj.name.startswith('_ground_plane'):
        # Select this object and make it active
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        
        # Apply smooth shading
        bpy.ops.object.shade_smooth()
        
        # Deselect for next iteration
        obj.select_set(False)

__result__ = {'shaded': True, 'objects_processed': len([o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('_ground_plane')])}`
});
```

### Key Implementation Details

| Aspect | Requirement | Reason |
|--------|-------------|--------|
| Per-object selection | Must set `bpy.context.view_layer.objects.active = obj` and `obj.select_set(True)` before shading | Blender requires active context and selection for `bpy.ops.object.shade_smooth()` |
| Ground plane exclusion | Filter `not obj.name.startswith('_ground_plane')` | Ground planes don't need smooth shading and should remain flat |
| Deselection | Call `obj.select_set(False)` after each object | Prevents state leakage between iterations |
| Tool choice | `execute_python` only, never `blender_cleanup` | Cleanup actions don't support shade_smooth; direct Python necessary |

### Why Previous Approach Failed

```javascript
// WRONG - This fails with bpy_prop_collection error
await client.call('blender_cleanup', { action: 'shade_smooth' });
```

The `blender_cleanup` tool with `action: 'shade_smooth'` internally tries to call `bpy.ops.object.shade_smooth()` without proper selection context, causing the property collection validation error.

---

## Integration Into Your Production Pipeline

### 1. Scene Setup (Beginning of Production)

```javascript
// Start with clean scene
await client.call('save_file', { action: 'new', use_empty: true });

// Apply corrected studio lighting
await client.call('execute_python', {
  code: `import bpy, mathutils
# ... [use the corrected lighting code above] ...
`
});
```

### 2. Polish Phase (After Geometry Steps)

```javascript
// Apply subdivision surface (before smooth shading)
await client.call('execute_python', {
  code: `import bpy
for obj in bpy.data.objects:
    if obj.type == 'MESH':
        mod = obj.modifiers.new('Subsurf', 'SUBSURF')
        mod.levels = 2
        mod.render_levels = 2
__result__ = {'applied': True}`
});

// Apply smooth shading (CORRECT approach)
await client.call('execute_python', {
  code: `import bpy

for obj in bpy.data.objects:
    if obj.type == 'MESH' and not obj.name.startswith('_ground_plane'):
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.shade_smooth()
        obj.select_set(False)

__result__ = {'shaded': True}`
});
```

### 3. Render Settings (Before Rendering)

```javascript
// Render settings with LOWERCASE engine name
await client.call('set_render_settings', {
  engine: 'eevee',  // lowercase, NOT 'EEVEE'
  resolution_x: 2048,
  resolution_y: 2048,
  samples: 64,
  output_format: 'PNG'
});

// Execute render to output_path (NOT filepath)
await client.call('render', {
  output_path: path.join(outputDir, 'hero.png')  // output_path, not filepath
});
```

---

## Expected Quality Improvement Summary

### Before Fixes
- **Background:** White (washed out)
- **Lighting:** Single 10W point light (nearly invisible)
- **Smooth shading:** Not applied (fails with error)
- **Vision API score:** 1.5/10 (REJECT)
- **Overall quality:** Flat, overexposed, no surface definition

### After Fixes
- **Background:** Medium gray (0.18) with proper contrast
- **Lighting:** 3-point studio setup (500W + 200W + 300W area lights)
- **Smooth shading:** Applied to all geometry (no errors)
- **Vision API score:** 6-7/10 (NEEDS_REVISION → borderline PASS)
- **Overall quality:** Professional studio lighting, proper shadow definition, geometry detail visible

### Performance Baselines (from skill documentation)

| Metric | Before | After |
|--------|--------|-------|
| Visual score | 1.6/10 | 6/10 |
| Overall quality score | 47/100 (REJECT) | 80/100 (NEEDS_REVISION) |
| Shade_smooth success | 0% (errors) | 100% |
| Render appearance | Flat, washed out | Professional, lit |

---

## Anti-Patterns to Avoid

Based on the skill's autoresearch regression checks:

1. **Do NOT use uppercase engine names**
   - ❌ `engine: 'EEVEE'`
   - ✅ `engine: 'eevee'`

2. **Do NOT use double quotes in Python code strings**
   - ❌ `code: "...obj.get(\"Cube\")..."`
   - ✅ `code: "...obj.get('Cube')..."`

3. **Do NOT use `filepath` parameter in render calls**
   - ❌ `render({ filepath: '/path/to/output.png' })`
   - ✅ `render({ output_path: '/path/to/output.png' })`

4. **Do NOT use white background**
   - ❌ `(1.0, 1.0, 1.0)` or `(0.95, 0.95, 0.95)`
   - ✅ `(0.18, 0.18, 0.2)` medium gray

5. **Do NOT use `blender_cleanup` for shade_smooth**
   - ❌ `save_file({ action: 'shade_smooth' })`
   - ✅ `execute_python` with per-object selection

---

## Testing Checklist

After implementing these fixes:

- [ ] Scene cleanup with `save_file({ action: 'new', use_empty: true })`
- [ ] Studio lighting applied with corrected code
- [ ] Background color verified as (0.18, 0.18, 0.2)
- [ ] All three lights present (key, fill, rim) with correct energies (500, 200, 300W)
- [ ] Ground plane named `_ground_plane` and size proportional to model
- [ ] Render settings use lowercase `engine: 'eevee'`
- [ ] Smooth shading applied via `execute_python` loop (not `blender_cleanup`)
- [ ] Render call uses `output_path` parameter (not `filepath`)
- [ ] Test render saved successfully to output directory
- [ ] Vision API score improved from 1.5 → 6+/10

---

## References

From the Blender MCP Skill documentation:

- **Section 7 (Rendering):** Studio lighting setup and camera auto-framing
- **Section 5 (Polish Phase):** Shade smooth implementation
- **Section 12 (Common Errors):** Washed out renders root cause and fix
- **Performance Baselines:** White vs gray background scoring data
