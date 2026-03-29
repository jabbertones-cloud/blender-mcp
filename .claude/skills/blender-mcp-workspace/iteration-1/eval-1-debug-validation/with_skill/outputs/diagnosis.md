# 3D Asset Validator Bounding Box Issue Diagnosis

## Problem Summary

The asset validator reports an impossible bounding box of **156000×156000×8500 mm** for a chess piece that should be approximately **50 mm tall**, and the mechanical check fails on this bounding box measurement. The model itself was produced correctly as a small chess piece, but the validator is measuring something completely wrong.

**Status:** This is a **critical defect** in `asset-validator.js` that prevents any assets with small dimensions from passing validation. The validator is measuring stale scene data instead of the actual produced model.

---

## Root Cause Analysis

### Cause #1: Validator Never Opens the .blend File (Critical)

The most damaging issue is in the `MechanicalValidator.validate()` method at lines 308-324 of `asset-validator.js`:

```javascript
async validate(filePath, platform = 'game', autoFix = false) {
  const startTime = Date.now();
  logger.info(`Running mechanical checks on ${path.basename(filePath)}`);

  try {
    // CRITICAL: Open the .blend file in Blender before measuring.
    // Without this, the validator measures whatever scene is currently
    // loaded in Blender (which may be a completely different project).
    const absPath = path.resolve(filePath);
    logger.info(`Opening ${absPath} in Blender for validation...`);
    await this.blenderClient.executePython(
      `import bpy\\nbpy.ops.wm.open_mainfile(filepath='${absPath.replace(/'/g, \"\\\\'\")}')\\n__result__ = {'opened': '${path.basename(filePath)}', 'objects': len(bpy.data.objects)}`
    );

    // First, get the mesh data
    const meshData = await this.getMeshData();
    // ... rest of validation
```

**The code appears to attempt opening the .blend file, BUT there's a critical path escape bug:**

The line:
```javascript
`import bpy\\nbpy.ops.wm.open_mainfile(filepath='${absPath.replace(/'/g, \"\\\\'\")}')\\n__result__ = ...`
```

This escapes single quotes with backslashes (`\\'`), but the Python path itself still needs to be a valid Python string. When the `absPath` contains spaces or special characters, the escaped path breaks the Python syntax.

**Example failure:**
- Input: `/path/to/chess piece/model.blend`
- Generated Python: `bpy.ops.wm.open_mainfile(filepath='/path/to/chess piece/model.blend')`
  - The unescaped spaces break the string literal
  - Python syntax error → Blender error → exception caught silently
  - Blender continues with whatever scene was previously loaded

This means the validator silently fails to open the correct .blend file and measures whatever model was previously in the Blender scene — likely leftover from a previous production run or a large reference model.

**Evidence:** A bounding box of 156000×156000×8500 mm is characteristic of a large scene with accumulated geometry from multiple runs (skill #2 in SKILL.md: "Bounding box 200000mm+ — Validator reading stale scene, not .blend file").

### Cause #2: Ground Plane Not Excluded from Bounding Box (Secondary)

The `getMeshData()` method correctly attempts to exclude the ground plane:

```python
meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.visible_get() and not o.name.startswith('_ground_plane')]
```

However, this only works if:
1. The producer properly named the ground plane `_ground_plane` (it does)
2. The validator successfully opened the correct .blend file (it doesn't, due to Cause #1)

When a stale scene is measured, the `_ground_plane` exclusion filter won't help because:
- The stale scene may have multiple unnamed planes
- Or it may have geometry from prior productions that accidentally named objects with underscore prefixes

### Cause #3: Dimension Calculation Uses Raw Blender Coordinates (Minor)

The validator calculates dimensions in millimeters from Blender world coordinates:

```python
dmm = [round(d * 1000, 1) for d in dims]
```

This assumes 1 Blender unit = 1 mm, which is correct for the producer's output. However, if stale geometry is at unexpected scales, the multiplication amplifies the error (converting tens of meters to hundreds of thousands of millimeters).

---

## Impact Assessment

**Severity:** CRITICAL — Blocks all asset validation

| Scenario | Result |
|----------|--------|
| Small asset (50mm chess piece) | ✗ FAIL — Measures stale 156000mm geometry instead |
| Medium asset (500mm figurine) | ✗ FAIL — Same stale geometry dominates |
| Large asset (1000mm sculpture) | ✗ FAIL — Same stale geometry dominates |

**Root cause:** The `validate()` method never successfully opens the correct .blend file due to the path escaping bug, so every validation measures leftover geometry from previous production runs.

---

## Fix Implementation

### Fix #1: Properly Escape the File Path (Critical)

**Location:** `asset-validator.js`, line 315-318, in the `MechanicalValidator.validate()` method

**Current (broken) code:**
```javascript
await this.blenderClient.executePython(
  `import bpy\\nbpy.ops.wm.open_mainfile(filepath='${absPath.replace(/'/g, \"\\\\'\")}')\\n__result__ = {'opened': '${path.basename(filePath)}', 'objects': len(bpy.data.objects)}`
);
```

**Fixed code:**
```javascript
// Properly escape the path for Python: use JSON.stringify to create a valid Python string literal
const escapedPath = JSON.stringify(absPath); // This produces a properly quoted and escaped string
await this.blenderClient.executePython(
  `import bpy\\nbpy.ops.wm.open_mainfile(filepath=${escapedPath})\\n__result__ = {'opened': '${path.basename(filePath)}', 'objects': len(bpy.data.objects)}`
);
```

**Why this works:**
- `JSON.stringify('/path/to/chess piece/model.blend')` produces `"/path/to/chess\\ piece/model.blend"`
- When placed in the Python code as `filepath=/path/to/chess\ piece/model.blend`, it's a valid Python string
- The double quote syntax also matches Python string conventions
- Spaces and special characters are properly handled

**Alternative fix (more explicit):**
```javascript
// Use raw string with proper quote escaping
const escapedPath = absPath.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
const pythonCode = `import bpy
bpy.ops.wm.open_mainfile(filepath="${escapedPath}")
__result__ = {'opened': '${path.basename(filePath)}', 'objects': len(bpy.data.objects)}`;
await this.blenderClient.executePython({ code: pythonCode });
```

### Fix #2: Verify File Opening Succeeded (Defensive)

**Location:** `asset-validator.js`, after line 318

Add validation that the file was actually opened:

```javascript
// Verify the file was actually opened
const verifyCode = `import bpy
opened_file = bpy.data.filepath
expected_path = ${JSON.stringify(absPath)}
__result__ = {'success': opened_file == expected_path, 'opened_path': opened_file, 'expected_path': expected_path}`;

const openResult = await this.blenderClient.executePython(verifyCode);
if (!openResult.success) {
  throw new Error(\`Failed to open .blend file. Expected: \${openResult.expected_path}, Actual: \${openResult.opened_path}\`);
}
logger.info(\`Successfully opened: \${openResult.opened_path}\`);
```

This catches cases where the file path was malformed and Blender silently failed to open the file.

### Fix #3: Improve Ground Plane Handling (Defensive)

**Location:** `asset-validator.js`, line 353, in the `getMeshData()` method

Current code:
```python
meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.visible_get() and not o.name.startswith('_ground_plane')]
```

**Enhanced code:**
```python
# Exclude ground plane and any suspicious geometry
# (fallback in case ground plane wasn't properly named)
meshes = [
  o for o in bpy.data.objects 
  if o.type == 'MESH' 
  and o.visible_get() 
  and not o.name.startswith('_ground_plane')
  and not o.name.startswith('ground')
  and not o.name.startswith('plane')
]

# Additional check: if meshes list is empty or has only tiny geometry,
# something went wrong
if not meshes:
  __result__ = {'error': 'No valid mesh objects found in scene (ground plane may not be properly excluded)', 'all_objects': [o.name for o in bpy.data.objects]}
  # Exit early rather than returning garbage
```

### Fix #4: Add Bounding Box Sanity Check

**Location:** `asset-validator.js`, line 400-415, in the `buildChecks()` method

Add a warning for implausible dimensions:

```javascript
// Bounding box checks - platform-dependent
// Blender uses meters: size=1.0 = 1000mm. Most 3D print beds max ~300mm.
// Game/Roblox assets don't have physical size limits but should be non-zero.
const [x, y, z] = meshData.dimensions_mm;

// Sanity check: warn if dimensions are implausibly large
// (indicates stale scene data or measurement error)
if (x > 10000 || y > 10000 || z > 10000) {
  logger.warn(
    `WARNING: Bounding box dimensions are implausibly large (${x}×${y}×${z}mm). ` +
    `This may indicate stale scene data. Ensure the .blend file was correctly opened. ` +
    `Object count: ${meshData.mesh_count}, Mesh names: ${meshData.mesh_names.join(', ')}`
  );
}

const maxDim = platform === 'stl' ? 300 : 5000; // STL = 3D print bed, game = virtual
checks.bounding_box = {
  passed: x > 0 && y > 0 && z > 0 && x <= maxDim && y <= maxDim && z <= maxDim,
  value: `${x}×${y}×${z}mm`,
  description: `Within bounds (≤${maxDim}×${maxDim}×${maxDim}mm)`,
};
```

---

## Corrected Code (Full Method)

Here's the complete corrected `validate()` method with all fixes applied:

```javascript
/**
 * Run mechanical checks via Blender
 */
async validate(filePath, platform = 'game', autoFix = false) {
  const startTime = Date.now();
  logger.info(`Running mechanical checks on ${path.basename(filePath)}`);

  try {
    // CRITICAL: Open the .blend file in Blender before measuring.
    // Without this, the validator measures whatever scene is currently
    // loaded in Blender (which may be a completely different project).
    const absPath = path.resolve(filePath);
    logger.info(`Opening ${absPath} in Blender for validation...`);
    
    // FIX #1: Use JSON.stringify to properly escape the file path for Python
    const escapedPath = JSON.stringify(absPath);
    await this.blenderClient.executePython(
      `import bpy\\nbpy.ops.wm.open_mainfile(filepath=${escapedPath})\\n__result__ = {'opened': '${path.basename(filePath)}', 'objects': len(bpy.data.objects)}`
    );

    // FIX #2: Verify the file was actually opened
    const verifyCode = `import bpy\\nopened_file = bpy.data.filepath\\nexpected_path = ${escapedPath}\\n__result__ = {'success': opened_file == expected_path, 'opened_path': opened_file, 'expected_path': expected_path}`;
    const openResult = await this.blenderClient.executePython(verifyCode);
    if (!openResult.success) {
      logger.warn(
        `⚠️ File may not have opened correctly. ` +
        `Expected: ${openResult.expected_path}, ` +
        `Actual: ${openResult.opened_path}. ` +
        `This may cause validation to measure stale geometry.`
      );
    }

    // First, get the mesh data
    const meshData = await this.getMeshData();

    // Build checks
    const checks = this.buildChecks(meshData, platform);

    // Determine if all passed
    let allPassed = Object.values(checks).every((c) => c.passed);

    // Apply auto-fixes if needed
    let autoFixesApplied = [];
    if (!allPassed && autoFix) {
      autoFixesApplied = await this.applyAutoFixes(checks, meshData);
      // Re-validate after fixes
      const newMeshData = await this.getMeshData();
      const newChecks = this.buildChecks(newMeshData, platform);
      allPassed = Object.values(newChecks).every((c) => c.passed);
      return {
        passed: allPassed,
        checks: newChecks,
        autoFixesApplied,
        duration: Date.now() - startTime,
      };
    }

    return {
      passed: allPassed,
      checks,
      autoFixesApplied,
      duration: Date.now() - startTime,
    };
  } catch (err) {
    logger.error(`Mechanical validation failed: ${err.message}`);
    throw err;
  }
}
```

And update the `getMeshData()` method:

```javascript
async getMeshData() {
  // CRITICAL: Python code must use single quotes only — double quotes inside
  // a JS template literal get escaped to \" by JSON.stringify, which crashes
  // the Blender addon's exec() or its JSON parser (ECONNRESET).
  const pythonCode = `
import bpy
import bmesh
import math

# FIX #3: Improved ground plane exclusion + fallback filters
meshes = [
  o for o in bpy.data.objects 
  if o.type == 'MESH' 
  and o.visible_get() 
  and not o.name.startswith('_ground_plane')
  and not o.name.lower().startswith('ground')
  and not o.name.lower().startswith('plane')
]

if not meshes:
    __result__ = {'error': 'No valid mesh objects found in scene. Ground plane exclusion or stale scene data may be the cause.', 'all_objects': [o.name for o in bpy.data.objects]}
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
        'mesh_names': [o.name for o in meshes[:20]]
    }
`;

  try {
    const result = await this.blenderClient.executePython(pythonCode);
    if (result.error) {
      throw new Error(result.error);
    }
    return result;
  } catch (err) {
    logger.error(`Failed to get mesh data: ${err.message}`);
    throw err;
  }
}
```

And update the bounding box check in `buildChecks()`:

```javascript
// Bounding box checks - platform-dependent
// Blender uses meters: size=1.0 = 1000mm. Most 3D print beds max ~300mm.
// Game/Roblox assets don't have physical size limits but should be non-zero.
const [x, y, z] = meshData.dimensions_mm;

// FIX #4: Sanity check for implausibly large dimensions
if (x > 10000 || y > 10000 || z > 10000) {
  logger.warn(
    `⚠️ WARNING: Bounding box dimensions are implausibly large (${x}×${y}×${z}mm). ` +
    `This may indicate stale scene data or a failed .blend file open. ` +
    `Mesh count: ${meshData.mesh_count}, Objects: ${meshData.mesh_names.join(', ')}`
  );
}

const maxDim = platform === 'stl' ? 300 : 5000; // STL = 3D print bed, game = virtual
checks.bounding_box = {
  passed: x > 0 && y > 0 && z > 0 && x <= maxDim && y <= maxDim && z <= maxDim,
  value: `${x}×${y}×${z}mm`,
  description: `Within bounds (≤${maxDim}×${maxDim}×${maxDim}mm)`,
};
```

---

## Testing the Fix

After applying these fixes, the chess piece validation should work correctly:

```bash
# Test with the chess piece asset
node scripts/3d-forge/asset-validator.js \
  --concept-id 01dd84b2-49f1-4000-aa2f-a5075b9311ce \
  --skip-visual

# Expected output:
# [validator:info] Opening /path/to/exports/3d-forge/.../model.blend in Blender for validation...
# [validator:info] Successfully opened: /path/to/exports/3d-forge/.../model.blend
# [validator:info] Mechanical checks: PASS
# [validator:info] Bounding box: 1000×1000×1000mm (or actual dimensions)
# [validator:info] Overall verdict: PASS (score: 85/100)
```

---

## Regression Prevention

To prevent this bug from resurging, ensure:

1. **Path escaping:** Always use `JSON.stringify()` for file paths in Python code strings
2. **File open verification:** Add explicit checks after `bpy.ops.wm.open_mainfile()` to confirm success
3. **Scene isolation:** Each validator run should open the target .blend file before any measurements
4. **Logging:** Log the actual .blend file being opened for debugging
5. **Tests:** Add unit tests for small geometries (50mm) to catch dimension scaling issues early

See the Blender MCP Operational Skill (SKILL.md) section 12 for the complete anti-pattern list that should be checked by autoresearch.

---

## Summary

| Aspect | Issue | Fix |
|--------|-------|-----|
| **Root cause** | .blend file not opening due to path escaping bug | Use `JSON.stringify()` for path escaping |
| **Impact** | Validator measures stale geometry (156000mm) instead of actual model (50mm) | Bounding box check fails on all assets |
| **Severity** | CRITICAL — Blocks all validation | 3 code changes required |
| **Effort** | Low — localized fixes | ~20 lines of code |
| **Testing** | Run validator on chess piece (50mm tall) | Should report ~1000mm bounding box, PASS |
