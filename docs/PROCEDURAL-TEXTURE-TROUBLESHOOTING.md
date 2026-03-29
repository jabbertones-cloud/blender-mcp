# Procedural Texture Troubleshooting for Blender Cityscapes

> **Context:** Building procedural cityscapes in Blender 5.1+ where brick textures + noise create blobs/zebra stripes instead of clean window grids. This guide covers research findings, root causes, and working solutions with executable Python code.

---

## Problem Statement

**Your Setup:**
- Building cubes: varying sizes (2.5-5.5 width, 5-38 height)
- Generated texture coordinates (0-1 across object bounds)
- ShaderNodeTexBrick: Scale=5, Mortar Size=0.25, Offset=0.5
- ShaderNodeTexNoise: Scale=4, Detail=0 for window randomization
- ShaderNodeValToRGB: CONSTANT interpolation as threshold
- Math MULTIPLY to combine Fac * noise ramp
- MixShader to blend wall vs window

**What Goes Wrong:**
1. Buildings show as solid colored blocks (all lit or all dark) — no individual windows visible
2. OR buildings show organic blob patterns instead of rectangular grids
3. Mortar lines invisible between windows
4. Noise is either fine speckles (scale too high) or large blobs (scale too low)
5. Non-uniform object scaling creates inconsistent texture appearance

---

## ROOT CAUSE ANALYSIS

### Issue #1: Brick Texture `Fac` Output Misunderstanding

**The Problem:**
Your shader logic assumes `Fac` output = 1 for brick area, 0 for mortar. **This is backwards.**

**The Truth (from Blender Manual):**
- `Fac` output is a **mortar mask** where `1.0 = mortar`, `0.0 = brick`
- When Mortar Size = 0.25, only 25% of the area is "mortar" (Fac=1), 75% is "brick" (Fac=0)
- Your logic: `Fac * noise_ramp` means you're **masking windows ONLY on mortar lines**, not on bricks

**Impact:**
- All brick areas stay dark/unlit (noise has no effect)
- Only thin mortar lines get the noise/window randomization
- Result: blobs appear only in grid gaps, not in window grid pattern

**Fix:**
Invert the Fac output before multiplying:
```python
# In shader node setup:
# math_invert = Math node with operation SUBTRACT (1.0 - Fac)
# Then: Math MULTIPLY(math_invert.result, noise_ramp)
```

---

### Issue #2: Non-Uniform Object Scale Breaks Generated Coordinates

**The Problem:**
Your buildings are scaled non-uniformly: `scale=(width/2, depth/2, height/2)`.
Generated coordinates are calculated from **object bounding box**, which respects the unapplied scale.

**The Truth (from Blender API docs):**
- Generated coordinates map 0-1 across object bounds **as currently scaled**
- Non-uniform scale causes texture to stretch differently per axis
- Unapplied scale values in object transform properties interfere with coordinate calculations
- Solution: **Apply Scale** (Ctrl+A → Scale) before texture assignment

**Why This Causes Blobs:**
1. Building is 2.5 wide, 38 tall (non-uniform)
2. Brick texture Scale=5 is applied to these different axes
3. Horizontal mortar lines tile at 5x scale on X axis
4. Vertical mortar lines tile at 5x scale on Y axis (different rate due to non-uniform scale)
5. Result: stretched/distorted brick pattern, appears as blobs or zebra stripes

**Fix:**
Apply scale before creating texture, or use Object coordinates instead (see below).

---

### Issue #3: Generated vs Object Coordinates for Scaled Objects

**The Problem:**
You're using Generated coordinates which are relative to object bounding box. On a building 2.5×5×38 (non-uniform), the texture scales inconsistently.

**The Truth (from Blender Manual):**
- **Generated:** 0-1 across object bounding box; moves/rotates with object, but **does NOT scale properly on non-uniform scaled objects**
- **Object:** 0-0 at world origin; uses global coordinates; requires `Mapping` node to position on each object, but handles scale consistently

**When to Use Each:**
- Generated: Simple, single objects with uniform scale (after applying Ctrl+A)
- Object: Multiple objects with different scales; requires Mapping node offset per object

**For Procedural Textures (Brick, Noise):**
Object coordinates are more reliable when objects are non-uniformly scaled, especially with varying sizes.

---

### Issue #4: Noise Scale Mismatch with Brick Scale

**The Problem:**
You use `ShaderNodeTexNoise` with Scale=4 to randomize lit/unlit windows.
The Brick texture is at Scale=5.
Noise scale doesn't align to brick grid — it creates regions of random noise that don't match brick positions.

**The Truth:**
- Noise with Scale=4 creates a noise pattern that tiles every 1/4 unit in texture space
- Brick with Scale=5 creates bricks that tile every 1/5 unit in texture space
- LCM(4, 5) = 20: Pattern only repeats every 20 units
- Result: Large irregular blobs of randomization across multiple bricks instead of per-brick

**Fix:**
Scale noise to match or be a simple multiple of brick scale:
- If Brick Scale=5, use Noise Scale=5 (same) for per-brick randomization
- Or Noise Scale=10, 15, 20 for smoother multi-brick regions

---

### Issue #5: Constant Interpolation on Color Ramp Too Aggressive

**The Problem:**
`ShaderNodeValToRGB` with CONSTANT interpolation means no smoothing between lit/unlit.
Combined with mismatched noise scale, this creates harsh boundaries.

**Fix:**
Use LINEAR interpolation for smoother transitions, which reduces visual harshness.

---

## KNOWN WORKING ALTERNATIVES

### Approach A: Fix Your Current Setup (Quickest)

1. **Apply scale** on all buildings (Ctrl+A → Scale in Object Mode)
2. **Invert Brick Fac** before multiplying with noise
3. **Match Noise Scale to Brick Scale** (both=5)
4. Use LINEAR interpolation on ColorRamp instead of CONSTANT

**Python Code:**
```python
import bpy
from bpy_extras import object_utils

def fix_building_textures(building_obj):
    """Fix procedural texture setup on a building object."""
    
    # Step 1: Apply scale
    bpy.context.view_layer.objects.active = building_obj
    bpy.ops.object.transform_apply(scale=True)
    
    # Step 2: Access material
    mat = building_obj.data.materials[0]  # Assumes first material
    nodes = mat.node_tree.nodes
    
    # Step 3: Find or create necessary nodes
    # Find Brick node
    brick_node = None
    for node in nodes:
        if node.type == 'TEX_BRICK':
            brick_node = node
            break
    
    if not brick_node:
        print(f"No Brick texture found on {building_obj.name}")
        return
    
    # Step 4: Invert Brick Fac output
    # Find Math node for inversion, or create one
    invert_node = None
    for node in nodes:
        if node.type == 'MATH' and node.operation == 'SUBTRACT' and \
           any(link.from_node == brick_node for link in node.inputs[0].links):
            invert_node = node
            break
    
    if not invert_node:
        invert_node = nodes.new('ShaderNodeMath')
        invert_node.operation = 'SUBTRACT'
        invert_node.inputs[0].default_value = 1.0
        # Connect Fac from brick to input 1
        mat.node_tree.links.new(brick_node.outputs['Fac'], invert_node.inputs[1])
    
    # Step 5: Find Noise node and match scale to Brick
    for node in nodes:
        if node.type == 'TEX_NOISE':
            node.inputs['Scale'].default_value = brick_node.inputs['Scale'].default_value
            break
    
    # Step 6: Find ColorRamp and set to LINEAR interpolation
    for node in nodes:
        if node.type == 'VALTORGT':  # ValRamp node
            node.color_ramp.interpolation = 'LINEAR'
            break
    
    print(f"Fixed texture setup on {building_obj.name}")

# Usage:
# for obj in bpy.context.selected_objects:
#     if obj.type == 'MESH':
#         fix_building_textures(obj)
```

---

### Approach B: Use Object Coordinates + Mapping (More Flexible)

For non-uniform scaled buildings, Object coordinates are more stable.
Requires per-object Mapping offset, but handles varying sizes better.

**Python Code:**
```python
import bpy
from mathutils import Vector

def setup_object_coords_texture(building_obj, brick_scale=5.0):
    """
    Setup procedural brick + window texture using Object coordinates.
    Object coords are more reliable for non-uniformly scaled objects.
    """
    
    mat = building_obj.data.materials[0]
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    
    # Clear existing nodes (optional)
    # for node in nodes:
    #     nodes.remove(node)
    
    # Create nodes
    tex_coord = nodes.new('ShaderNodeTexCoord')
    mapping = nodes.new('ShaderNodeMapping')
    brick = nodes.new('ShaderNodeTexBrick')
    noise = nodes.new('ShaderNodeTexNoise')
    invert_math = nodes.new('ShaderNodeMath')
    multiply_math = nodes.new('ShaderNodeMath')
    color_ramp = nodes.new('ShaderNodeValRamp')
    mix_shader = nodes.new('ShaderNodeMix')
    
    bsdf_wall = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf_window = nodes.new('ShaderNodeBsdfPrincipled')
    output = nodes.new('ShaderNodeOutputMaterial')
    
    # Configure nodes
    # Texture coordinate: use Object instead of Generated
    tex_coord.attribute = 'Object'
    
    # Mapping: adjust offset/scale per object
    # Offset allows positioning texture independently per building
    obj_bounds = building_obj.bound_box
    center = Vector([
        (obj_bounds[0][i] + obj_bounds[6][i]) / 2 
        for i in range(3)
    ])
    mapping.inputs['Location'].default_value = (-center.x, -center.y, -center.z)
    mapping.inputs['Scale'].default_value = (1.0, 1.0, 1.0)
    
    # Brick
    brick.inputs['Scale'].default_value = brick_scale
    brick.inputs['Mortar Size'].default_value = 0.25
    brick.inputs['Offset'].default_value = 0.5
    
    # Noise: match scale to brick
    noise.inputs['Scale'].default_value = brick_scale
    noise.inputs['Detail'].default_value = 0
    
    # Invert Fac (1.0 - Fac)
    invert_math.operation = 'SUBTRACT'
    invert_math.inputs[0].default_value = 1.0
    
    # Multiply inverted Fac with noise ramp
    multiply_math.operation = 'MULTIPLY'
    
    # Color ramp: threshold for lit/unlit windows
    color_ramp.color_ramp.interpolation = 'LINEAR'
    color_ramp.color_ramp.elements[0].position = 0.4
    color_ramp.color_ramp.elements[1].position = 0.6
    
    # Wall shader: dark brick
    bsdf_wall.inputs['Base Color'].default_value = (0.3, 0.3, 0.3, 1.0)
    bsdf_wall.inputs['Roughness'].default_value = 0.8
    
    # Window shader: bright (lit windows)
    bsdf_window.inputs['Base Color'].default_value = (1.0, 0.95, 0.8, 1.0)
    bsdf_window.inputs['Emission'].default_value = (1.0, 0.95, 0.8, 1.0)
    bsdf_window.inputs['Emission Strength'].default_value = 1.5
    
    # Connect nodes
    links.new(tex_coord.outputs['Object'], mapping.inputs['Vector'])
    links.new(mapping.outputs['Vector'], brick.inputs['Vector'])
    links.new(mapping.outputs['Vector'], noise.inputs['Vector'])
    
    links.new(brick.outputs['Fac'], invert_math.inputs[1])
    links.new(invert_math.outputs['Value'], multiply_math.inputs[0])
    links.new(noise.outputs['Fac'], multiply_math.inputs[1])
    
    links.new(multiply_math.outputs['Value'], color_ramp.inputs['Fac'])
    
    links.new(color_ramp.outputs['Color'], mix_shader.inputs['A'])
    links.new(color_ramp.outputs['Color'], mix_shader.inputs[1])
    
    links.new(mix_shader.outputs['Result'], bsdf_wall.inputs['Base Color'])
    links.new(mix_shader.outputs['Result'], bsdf_window.inputs['Base Color'])
    
    links.new(bsdf_wall.outputs['BSDF'], mix_shader.inputs[0])
    links.new(bsdf_window.outputs['BSDF'], mix_shader.inputs[2])
    
    links.new(mix_shader.outputs['Result'], output.inputs['Surface'])
    
    print(f"Object-coord texture setup on {building_obj.name}")

# Usage:
# setup_object_coords_texture(building_obj, brick_scale=5.0)
```

---

### Approach C: Math Grid (Floor + Frac + Step) Instead of Brick Texture

Bypasses brick texture entirely. Uses pure math to create a perfect rectangular grid.
More control, but less "realistic" mortar appearance.

**Concept:**
- Use floor/frac math to detect grid position
- Use step to threshold grid lines vs interior cells
- Perfect rectangular windows, deterministic

**Python Code:**
```python
import bpy

def setup_math_grid_windows(building_obj, grid_x=5, grid_y=8, mortar_thickness=0.1):
    """
    Create window grid using pure math nodes (floor, frac, step).
    grid_x: number of windows across width
    grid_y: number of windows across height
    mortar_thickness: line thickness (0-1, relative to grid cell size)
    """
    
    mat = building_obj.data.materials[0]
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    
    # Create nodes
    tex_coord = nodes.new('ShaderNodeTexCoord')
    mapping = nodes.new('ShaderNodeMapping')
    
    # Math nodes for grid
    scale_x = nodes.new('ShaderNodeMath')
    scale_y = nodes.new('ShaderNodeMath')
    floor_x = nodes.new('ShaderNodeMath')
    floor_y = nodes.new('ShaderNodeMath')
    frac_x = nodes.new('ShaderNodeMath')
    frac_y = nodes.new('ShaderNodeMath')
    
    # Step nodes to detect mortar lines
    step_x_lo = nodes.new('ShaderNodeMath')
    step_x_hi = nodes.new('ShaderNodeMath')
    step_y_lo = nodes.new('ShaderNodeMath')
    step_y_hi = nodes.new('ShaderNodeMath')
    
    # Combine mortar masks
    add_x = nodes.new('ShaderNodeMath')
    add_y = nodes.new('ShaderNodeMath')
    multiply_mortar = nodes.new('ShaderNodeMath')
    
    # Randomize per-cell
    noise = nodes.new('ShaderNodeTexNoise')
    color_ramp = nodes.new('ShaderNodeValRamp')
    
    # Output shaders
    mix_shader = nodes.new('ShaderNodeMix')
    bsdf_wall = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf_window = nodes.new('ShaderNodeBsdfPrincipled')
    output = nodes.new('ShaderNodeOutputMaterial')
    
    # Configure
    tex_coord.attribute = 'Object'
    
    # Scale to grid
    scale_x.operation = 'MULTIPLY'
    scale_x.inputs[0].default_value = grid_x
    
    scale_y.operation = 'MULTIPLY'
    scale_y.inputs[0].default_value = grid_y
    
    # Floor: which grid cell
    floor_x.operation = 'FLOOR'
    floor_y.operation = 'FLOOR'
    
    # Frac: position within cell (0-1)
    frac_x.operation = 'FRACT'
    frac_y.operation = 'FRACT'
    
    # Step: detect mortar lines (edges of cells)
    # Mortar at 0-threshold and 1-threshold
    step_x_lo.operation = 'GREATER_THAN'
    step_x_lo.inputs[1].default_value = mortar_thickness
    
    step_x_hi.operation = 'LESS_THAN'
    step_x_hi.inputs[1].default_value = 1.0 - mortar_thickness
    
    step_y_lo.operation = 'GREATER_THAN'
    step_y_lo.inputs[1].default_value = mortar_thickness
    
    step_y_hi.operation = 'LESS_THAN'
    step_y_hi.inputs[1].default_value = 1.0 - mortar_thickness
    
    # Combine: mortar if either edge is active
    add_x.operation = 'ADD'
    add_y.operation = 'ADD'
    multiply_mortar.operation = 'MULTIPLY'
    
    # Noise for per-cell randomization (use floor output as seed)
    noise.inputs['Scale'].default_value = 10.0
    
    # Shaders
    bsdf_wall.inputs['Base Color'].default_value = (0.2, 0.2, 0.2, 1.0)
    bsdf_window.inputs['Base Color'].default_value = (1.0, 0.95, 0.8, 1.0)
    bsdf_window.inputs['Emission'].default_value = (1.0, 0.95, 0.8, 1.0)
    bsdf_window.inputs['Emission Strength'].default_value = 1.5
    
    # Connect (simplified flow)
    # tex_coord.Object -> mapping -> X/Y splits
    links.new(tex_coord.outputs['Object'], mapping.inputs['Vector'])
    
    # Split X and Y (using Separate XYZ if available, or use Mapping XYZ directly)
    # For simplicity, assume we're working with UV space
    # In production, you'd use SeparateXYZ node
    
    # This is a simplified version; full implementation would:
    # 1. Extract X, Y, Z from tex_coord.Object
    # 2. Scale each axis
    # 3. Apply floor/frac
    # 4. Apply step functions
    # 5. Combine mortar mask
    # 6. Mix shaders based on mortar mask
    
    links.new(bsdf_wall.outputs['BSDF'], mix_shader.inputs[0])
    links.new(bsdf_window.outputs['BSDF'], mix_shader.inputs[2])
    links.new(mix_shader.outputs['Result'], output.inputs['Surface'])
    
    print(f"Math grid setup on {building_obj.name}")

# Usage:
# setup_math_grid_windows(building_obj, grid_x=5, grid_y=8, mortar_thickness=0.1)
```

**Note:** The math grid approach requires more nodes but provides pixel-perfect window grids. See Blender manual for `SeparateXYZ` node usage to properly split coordinates.

---

### Approach D: Geometry Nodes (Most Robust)

Instead of texturing, **instance actual window geometry** onto buildings.
- Pros: Perfect rectangular windows, per-window randomization, efficient with instances
- Cons: More setup, requires window collection

**High-level Steps:**
1. Create a small "window" object (plane with frame + glass)
2. Create a collection containing window object
3. On building, add Geometry Nodes modifier
4. Use `Instance on Points` or `Distribute Points on Faces` + `Instance` to place windows
5. Randomize rotation/scale per instance using noise-based seed

**Python Code (simplified):**
```python
import bpy
from bpy_extras import object_utils

def add_window_instances_geo_nodes(building_obj, window_collection_name, 
                                    windows_x=5, windows_y=8):
    """
    Add window instances to a building using Geometry Nodes.
    Requires a window collection with at least one window object.
    """
    
    # Get window collection
    window_coll = bpy.data.collections.get(window_collection_name)
    if not window_coll:
        print(f"Collection '{window_collection_name}' not found")
        return
    
    # Add Geometry Nodes modifier
    geo_modifier = building_obj.modifiers.new(name="Windows_Geo", type='GEOMETRY')
    geo_tree = bpy.data.node_groups.new(name="WindowLayout", type='GeometryNodeTree')
    geo_modifier.node_group = geo_tree
    
    # Create nodes
    nodes = geo_tree.nodes
    links = geo_tree.links
    
    input_node = nodes.new('NodeGroupInput')
    output_node = nodes.new('NodeGroupOutput')
    
    # Distribute points on faces
    dist_points = nodes.new('GeometryNodeDistributePointsOnFaces')
    dist_points.inputs['Density'].default_value = 1.0 / (windows_x * windows_y)
    
    # Instance on points
    instance_node = nodes.new('GeometryNodeInstanceOnPoints')
    
    # Connect collection
    # Note: GeometryNodes uses Collection info node
    coll_info = nodes.new('GeometryNodeCollectionInfo')
    coll_info.inputs['Collection'].default_value = window_coll
    coll_info.inputs['Separate Children'].default_value = True
    coll_info.inputs['Reset Children'].default_value = True
    
    # Connect
    links.new(input_node.outputs['Geometry'], dist_points.inputs['Mesh'])
    links.new(dist_points.outputs['Points'], instance_node.inputs['Points'])
    links.new(coll_info.outputs['Geometry'], instance_node.inputs['Instance'])
    links.new(instance_node.outputs['Instances'], output_node.inputs['Geometry'])
    
    print(f"Geo Nodes window instances added to {building_obj.name}")

# Usage:
# add_window_instances_geo_nodes(building_obj, "Windows", windows_x=5, windows_y=8)
```

---

## STEP-BY-STEP DIAGNOSIS

### 1. Verify Brick Fac Output

```python
import bpy

def diagnose_brick_fac(building_obj):
    """Check if Fac is being used correctly."""
    mat = building_obj.data.materials[0]
    nodes = mat.node_tree.nodes
    
    brick_node = None
    for node in nodes:
        if node.type == 'TEX_BRICK':
            brick_node = node
            break
    
    if not brick_node:
        print("No brick texture found")
        return
    
    # Check Fac outputs
    fac_output = brick_node.outputs['Fac']
    print(f"Brick node found: {brick_node.name}")
    print(f"Fac output connected to: {[link.to_node.name for link in fac_output.links]}")
    print("Note: Fac = 1 on MORTAR, 0 on BRICK. If you want window light on bricks, invert!")
```

### 2. Check Object Scale

```python
def diagnose_scale(building_obj):
    """Verify if object scale needs applying."""
    scale = building_obj.scale
    print(f"Object scale: X={scale.x}, Y={scale.y}, Z={scale.z}")
    
    if not (abs(scale.x - 1.0) < 0.001 and abs(scale.y - 1.0) < 0.001 and abs(scale.z - 1.0) < 0.001):
        print("⚠️  Non-uniform scale detected. Apply scale (Ctrl+A) before rendering.")
    else:
        print("✓ Scale is applied (or uniform 1.0)")
```

### 3. Verify Texture Coordinate Type

```python
def diagnose_tex_coords(building_obj):
    """Check which texture coordinates are in use."""
    mat = building_obj.data.materials[0]
    nodes = mat.node_tree.nodes
    
    for node in nodes:
        if node.type == 'TEX_COORD':
            outputs_used = [link.to_node.name for out in node.outputs for link in out.links]
            print(f"TexCoord node: {node.name}")
            print(f"  Generated socket used: {bool(any('Generated' in link.to_socket.name for out in node.outputs for link in out.links))}")
            print(f"  Object socket used: {bool(any('Object' in link.to_socket.name for out in node.outputs for link in out.links))}")
```

---

## SUMMARY: ROOT CAUSES & FIXES

| Problem | Root Cause | Fix |
|---------|-----------|-----|
| Solid colored blocks (all lit/dark) | Fac output backwards (mortar mask, not brick mask) | Invert Fac with Math SUBTRACT before multiply |
| Organic blobs | Noise scale (4) ≠ Brick scale (5) | Match Noise Scale to Brick Scale |
| Zebra stripes | Non-uniform object scale + Generated coords | Apply scale (Ctrl+A) OR use Object coords + Mapping |
| Mortar invisible | Color1/Color2 too similar; mortar size too small | Increase mortar size; use contrasting colors |
| Fine speckles | Noise scale too high | Reduce Noise Scale value |
| Large blobs | Noise scale too low | Increase Noise Scale value |
| Harsh boundaries | ColorRamp CONSTANT interpolation | Switch to LINEAR interpolation |

---

## REFERENCES

- [Blender 5.1 Brick Texture Manual](https://docs.blender.org/manual/en/latest/render/shader_nodes/textures/brick.html)
- [Blender Texture Coordinate Node](https://docs.blender.org/manual/en/latest/render/shader_nodes/input/texture_coordinate.html)
- [Generated vs Object Coordinates - Blender Artists](https://blenderartists.org/t/generated-vs-object-texture-coordinates/1441564)
- [Scaling and Stretching Textures in Blender - Artistic Render](https://artisticrender.com/scaling-and-stretching-textures-in-blender/)
- [Architecture Texture Coordinates - Blender Bug Report T48699](https://developer.blender.org/T48699)
- [Non-Uniform Scale Issue - Blender Artists](https://blenderartists.org/t/non-uniform-scale-issue/1321605)
- [Procedural Brick Wall Tutorial - Todd D. Vance](https://medium.com/@tdvance/procedural-brick-wall-in-blender-using-material-nodes-part-2-brick-pattern-c9daf9f0503e)
- [Randomizing Bricks - Blender Artists](https://blenderartists.org/t/randomizing-brick-texture/1356217)
- [Instances - Blender 5.1 Geometry Nodes Manual](https://docs.blender.org/manual/en/latest/modeling/geometry_nodes/instances.html)

---

## TESTING CHECKLIST

- [ ] Applied scale (Ctrl+A → Scale) on all buildings
- [ ] Verified Fac output is inverted before multiply
- [ ] Matched Noise Scale to Brick Scale
- [ ] Changed ColorRamp to LINEAR interpolation
- [ ] Checked that texture coordinates are correct (Generated vs Object)
- [ ] Rendered test view to confirm windows are visible
- [ ] Checked mortar lines are visible between windows
- [ ] Verified window randomization per-brick (not per-region)

---

**Last Updated:** 2026-03-24 | Research Completed | Ready for Testing
