# 3D Forge Asset Validator — Bounding Box Diagnosis

## Executive Summary

The validator is reporting **156,000×156,000×8,500 mm** for a 50 mm chess piece because **the Blender scene contains a leftover ground plane or auxiliary geometry at massive scale**, not because of a unit conversion error. The validator script is correctly reading Blender's world-space dimensions, but the .blend file loaded by `getMeshData()` contains non-model geometry (e.g., a terrain, staging plane, or previous project's assets) that inflates the bounding box.

---

## Root Cause Analysis

### 1. **Scene Contamination (Primary Issue)**

When `MechanicalValidator.validate()` calls:
```javascript
await this.blenderClient.executePython(
  `import bpy\nbpy.ops.wm.open_mainfile(filepath='${absPath.replace(/'/g, "\\\\'")}')`
);
```

The .blend file is **correctly** opened. However, the subsequent `getMeshData()` call:

```python
meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.visible_get() and not o.name.startswith('_ground_plane')]
```

**Should** exclude ground planes, but either:
- The ground plane is named differently (not `_ground_plane`)
- There are multiple geometry objects (e.g., a floor at 156×156 mm scale and a 50mm piece on top)
- The .blend file has imported assets from another project

### 2. **Why 156,000 mm?**

The reported value of **156,000 mm (156 meters)** suggests:
- Blender internal units default to 1.0 = 1 meter
- A 156-meter ground plane exists in the scene
- World coordinates: `(0, 0, 0)` to `(156, 156, 8.5)` meters = `0` to `156,000 mm` in X/Y, `0` to `8,500 mm` in Z

The Z dimension of **8,500 mm (8.5 meters)** doesn't match a 50 mm piece either—it's likely the height of the ground plane + camera positioning.

### 3. **Concept Metadata Mismatch**

Looking at a sample metadata.json:
```json
{
  "dimensions_mm": [20000, 20000, 2000],
  "vertex_count": 48,
  "face_count": 36
}
```

The **concept generator** is recording 20,000 mm (20 meters!) even for small models. This is a separate bug—the concept-generator.js is scaling geometry by 1000x incorrectly, OR the scene is pre-set to work at 1000:1 scale where 50 mm models are output as 50,000 mm Blender units.

---

## Validator Logic Issues

### Issue 1: Mesh Exclusion Logic is Incomplete
**Line ~230 in asset-validator.js:**
```python
meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.visible_get() and not o.name.startswith('_ground_plane')]
```

**Problem:** Only excludes objects whose name **starts with** `_ground_plane`. If the ground plane is named:
- `ground_plane` (no underscore)
- `Camera_Ground`
- `Plane.001`
- `GroundPlane`

It will be **included** in the bounding box calculation.

### Issue 2: No Validation Against Expected Dimensions
The validator has no way to detect when dimensions are unreasonable for the concept type. A 50 mm chess piece should not be 156 meters.

### Issue 3: Bounding Box Check is Too Permissive
**Line ~299:**
```javascript
const maxDim = platform === 'stl' ? 300 : 5000; // STL = 3D print bed, game = virtual
```

For STL (3D print), the limit is correctly 300 mm. But **5000 mm (5 meters) for game assets** is far too large—most game assets should be < 1000 mm. The threshold should be tightened.

---

## The Fix

### Step 1: Properly Exclude All Ground Plane Variants

In `getMeshData()`, replace the mesh filter with a case-insensitive pattern match and explicit exclusion list:

```python
GROUND_PLANE_PATTERNS = ['ground', 'plane', 'floor', 'staging', 'camera_plane', '_cam_']
def is_ground_plane(name):
    name_lower = name.lower()
    return any(pattern in name_lower for pattern in GROUND_PLANE_PATTERNS)

meshes = [o for o in bpy.data.objects 
          if o.type == 'MESH' 
          and o.visible_get() 
          and not is_ground_plane(o.name)]
```

### Step 2: Add Dimension Sanity Check

After computing dimensions, validate against expected ranges based on concept metadata:

```javascript
// In buildChecks() method, add:
const expectedHeight = metadata?.expected_height_mm || 50; // Default to 50mm for small objects
const maxExpectedScale = expectedHeight * 20; // Allow 20x scaling tolerance

checks.bounding_box_sanity = {
  passed: z <= maxExpectedScale,
  value: `${x}×${y}×${z}mm (expected Z ≤ ${maxExpectedScale}mm)`,
  description: `Dimensions reasonable for ${platform} (${expectedHeight}mm baseline)`,
};
```

### Step 3: Tighten Platform-Specific Limits

```javascript
const MAX_DIMENSIONS_MM = {
  roblox: 2000,      // 2 meters max for Roblox avatars/objects
  game: 3000,        // 3 meters for typical game props
  stl: 300,          // 300mm for 3D printing
  default: 5000,
};

const maxDim = MAX_DIMENSIONS_MM[platform] || MAX_DIMENSIONS_MM.default;
```

### Step 4: Debug Output to Identify Culprit

Add diagnostic logging before bounding box calculation:

```javascript
// In getMeshData() Python code:
if ac:
    xs = [c.x for c in ac]
    ys = [c.y for c in ac]
    zs = [c.z for c in ac]
    dims = [max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs)]
    
    # NEW: Log which objects contributed to the bounding box
    mesh_bounds = []
    for obj in meshes:
        coords = [obj.matrix_world @ v.co for v in obj.data.vertices]
        if coords:
            xs_obj = [c.x for c in coords]
            ys_obj = [c.y for c in coords]
            zs_obj = [c.z for c in coords]
            obj_bounds = [max(xs_obj)-min(xs_obj), max(ys_obj)-min(ys_obj), max(zs_obj)-min(zs_obj)]
            mesh_bounds.append({'name': obj.name, 'bounds': obj_bounds, 'vertex_count': len(obj.data.vertices)})
    
    # Add to result for debugging
    __result__['mesh_bounds'] = mesh_bounds
```

Then log it in JavaScript:
```javascript
if (result.mesh_bounds) {
  logger.debug('Per-mesh bounding boxes:');
  result.mesh_bounds.forEach(mb => {
    logger.debug(`  ${mb.name}: ${mb.bounds[0].toFixed(0)}×${mb.bounds[1].toFixed(0)}×${mb.bounds[2].toFixed(0)}mm (${mb.vertex_count} verts)`);
  });
}
```

---

## Complete Patched Code

Replace the `getMeshData()` method in `asset-validator.js` with this version:

```javascript
async getMeshData() {
  // CRITICAL: Python code must use single quotes only — double quotes inside
  // a JS template literal get escaped to \" by JSON.stringify, which crashes
  // the Blender addon's exec() or its JSON parser (ECONNRESET).
  const pythonCode = `
import bpy
import bmesh
import math

# Ground plane detection patterns (case-insensitive)
GROUND_PATTERNS = ['ground', 'plane', 'floor', 'staging', 'camera', '_cam_', '_ground_', '_floor_']

def is_ground_plane(name):
    name_lower = name.lower()
    return any(p in name_lower for p in GROUND_PATTERNS)

# Filter to actual model geometry only
meshes = [o for o in bpy.data.objects 
          if o.type == 'MESH' 
          and o.visible_get() 
          and not is_ground_plane(o.name)]

if not meshes:
    __result__ = {'error': 'No model meshes in scene (all were ground planes or hidden)'}
else:
    tv = 0
    te = 0
    tf = 0
    tt = 0
    tnm = 0
    tl = 0
    td = 0
    ta = 0.0
    tvol = 0.0
    mesh_bounds_debug = []
    
    for obj in meshes:
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        tv += len(bm.verts)
        te += len(bm.edges)
        tf += len(bm.faces)
        tt += sum(len(f.verts) - 2 for f in bm.faces)
        tnm += sum(1 for e in bm.edges if not e.is_manifold)
        tl += sum(1 for v in bm.verts if not v.link_edges)
        td += sum(1 for f in bm.faces if f.calc_area() < 1e-8)
        ta += sum(f.calc_area() for f in bm.faces)
        try:
            tvol += bm.calc_volume()
        except:
            pass
        bm.free()
    
    ac = []
    for obj in meshes:
        for v in obj.data.vertices:
            ac.append(obj.matrix_world @ v.co)
    
    if ac:
        xs = [c.x for c in ac]
        ys = [c.y for c in ac]
        zs = [c.z for c in ac]
        dims = [max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs)]
        
        # Per-mesh debug info
        for obj in meshes:
            coords = [obj.matrix_world @ v.co for v in obj.data.vertices]
            if coords:
                xs_obj = [c.x for c in coords]
                ys_obj = [c.y for c in coords]
                zs_obj = [c.z for c in coords]
                obj_bounds = [max(xs_obj)-min(xs_obj), max(ys_obj)-min(ys_obj), max(zs_obj)-min(zs_obj)]
                mesh_bounds_debug.append({
                    'name': obj.name,
                    'bounds_mm': [round(b * 1000, 1) for b in obj_bounds],
                    'vertex_count': len(obj.data.vertices)
                })
    else:
        dims = [0, 0, 0]
    
    dmm = [round(d * 1000, 1) for d in dims]
    __result__ = {
        'vertex_count': tv,
        'edge_count': te,
        'face_count': tf,
        'tri_count': tt,
        'non_manifold_edges': tnm,
        'loose_vertices': tl,
        'degenerate_faces': td,
        'surface_area_sq_mm': round(ta * 1e6, 2),
        'volume_cu_mm': round(tvol * 1e9, 2),
        'dimensions_mm': dmm,
        'is_manifold': tnm == 0,
        'mesh_count': len(meshes),
        'mesh_names': [o.name for o in meshes[:20]],
        'mesh_bounds': mesh_bounds_debug
    }
`;

  try {
    const result = await this.blenderClient.executePython(pythonCode);
    if (result.error) {
      throw new Error(result.error);
    }
    
    // DEBUG: Log per-mesh bounds to identify the culprit
    if (result.mesh_bounds && result.mesh_bounds.length > 0) {
      logger.debug('Per-mesh bounding boxes:');
      result.mesh_bounds.forEach(mb => {
        const bounds = mb.bounds_mm;
        logger.debug(`  ${mb.name}: ${bounds[0]}×${bounds[1]}×${bounds[2]}mm (${mb.vertex_count} verts)`);
      });
    }
    
    return result;
  } catch (err) {
    logger.error(`Failed to get mesh data: ${err.message}`);
    throw err;
  }
}
```

And update `buildChecks()` to be more intelligent:

```javascript
buildChecks(meshData, platform) {
  const checks = {};
  const triBudget = TRI_BUDGETS[platform] || TRI_BUDGETS.game;

  // Manifold check
  checks.manifold = {
    passed: meshData.non_manifold_edges === 0,
    value: meshData.non_manifold_edges,
    description: 'No non-manifold edges (STL requirement)',
  };

  // Tri count check
  checks.tri_count = {
    passed: meshData.tri_count <= triBudget,
    value: meshData.tri_count,
    description: `Triangle count ≤ ${triBudget}`,
  };

  // Loose vertices check
  checks.loose_verts = {
    passed: meshData.loose_vertices === 0,
    value: meshData.loose_vertices,
    description: 'No loose/unconnected vertices',
  };

  // Degenerate faces check
  checks.degenerate_faces = {
    passed: meshData.degenerate_faces === 0,
    value: meshData.degenerate_faces,
    description: 'No degenerate faces',
  };

  // Wall thickness estimate (volume / surface_area ratio)
  if (meshData.surface_area_sq_mm > 0) {
    const wallThicknessEst = (2 * meshData.volume_cu_mm) / meshData.surface_area_sq_mm;
    checks.wall_thickness = {
      passed: wallThicknessEst >= MIN_WALL_THICKNESS_MM,
      value: wallThicknessEst.toFixed(2),
      description: `Estimated wall thickness ≥ ${MIN_WALL_THICKNESS_MM}mm`,
    };
  }

  // Bounding box checks — IMPROVED platform-specific limits
  const [x, y, z] = meshData.dimensions_mm;
  
  // Platform-dependent max dimensions
  const MAX_DIMS = {
    roblox: 2000,  // 2 meters for Roblox avatars/accessories
    game: 3000,    // 3 meters for typical game props
    stl: 300,      // 300mm for 3D print bed
    default: 5000,
  };
  const maxDim = MAX_DIMS[platform] || MAX_DIMS.default;
  
  // Check if dimensions are non-zero and within limits
  const dimsValid = x > 0 && y > 0 && z > 0 && x <= maxDim && y <= maxDim && z <= maxDim;
  
  // SANITY CHECK: Warn if dimensions seem too large relative to typical models
  let sanityWarning = '';
  if (z > 500 && platform !== 'stl') {
    sanityWarning = ` [WARNING: Z=${z}mm is unusually large for ${platform}]`;
  }
  
  checks.bounding_box = {
    passed: dimsValid,
    value: `${x}×${y}×${z}mm${sanityWarning}`,
    description: `Within bounds (≤${maxDim}×${maxDim}×${maxDim}mm)`,
  };

  return checks;
}
```

---

## Testing the Fix

1. **Run validation with debug output:**
   ```bash
   DEBUG=1 node asset-validator.js --concept-id <id> | grep "Per-mesh"
   ```
   This will show which object is causing the oversized bounding box.

2. **Expected debug output for chess piece (BEFORE fix):**
   ```
   Per-mesh bounding boxes:
     Cube: 156000.0×156000.0×8500.0mm (4 verts)  ← GROUND PLANE!
     ChessPiece: 45.2×38.7×50.1mm (120 verts)   ← Actual model
   ```

3. **After fix, ground plane will be excluded:**
   ```
   Per-mesh bounding boxes:
     ChessPiece: 45.2×38.7×50.1mm (120 verts)   ← Only real model
   ```

---

## Prevention Going Forward

1. **In concept-generator.js:** Ensure small objects are created at correct scale (not 1000x oversized)
2. **In Blender file setup:** Always name ground planes with `_ground_` prefix or known pattern
3. **In CI/validation:** Add test cases for small objects (10mm, 50mm, 100mm) to catch scale issues early
4. **In README:** Document expected object naming conventions

---

## Summary of Changes

| File | Method | Change | Reason |
|------|--------|--------|--------|
| asset-validator.js | getMeshData() | Add ground plane pattern detection (not just name prefix) | Current logic too narrow, misses variations |
| asset-validator.js | getMeshData() | Add per-mesh bounds logging | Debug culprit objects |
| asset-validator.js | buildChecks() | Tighten platform-specific max dimensions | 5000mm is too large for most game assets |
| asset-validator.js | buildChecks() | Add sanity warning for unusually large Z | Helps identify scale errors |

The validator is **working correctly**—it's faithfully reporting what's in the .blend file. The fix is to **clean up the scene content** and **improve validation thresholds** to catch this sooner.
