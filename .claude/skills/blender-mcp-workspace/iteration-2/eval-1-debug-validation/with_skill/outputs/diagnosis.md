# 3D Forge Validator Diagnosis: 156000mm Bounding Box Bug

## Executive Summary

**Problem:** The asset validator is reporting a bounding box of 156000×156000×8500mm for a chess piece that should be ~50mm tall, causing mechanical checks to fail.

**Root Cause:** The validator is measuring a **stale scene** left over from a previous Blender session, not the model that was just produced. This is a **Scene Persistence Gotcha** documented in the Blender MCP skill (section 3.3).

**Why this happens:** After the producer script disconnects from the MCP socket, Blender does NOT keep the scene the producer built. It reverts to whatever was previously loaded—undo history, auto-save recovery, or a completely different project file (in your case, a 152-object scene from a previous failed attempt, which includes massive geometry). When the validator connects and queries `bpy.data.objects` without explicitly loading the `.blend` file, it measures the stale scene, producing garbage results.

**Fix:** The validator MUST call `bpy.ops.wm.open_mainfile(filepath=...)` to explicitly load the saved `.blend` file before running `getMeshData()`. This is already attempted in the code (line ~270) but **the implementation has a critical bug**: the file path escaping is broken.

---

## Detailed Diagnosis

### 1. The Bug in Current Code

**Location:** `asset-validator.js`, lines 267–272

```javascript
// Current code (BROKEN)
const absPath = path.resolve(filePath);
logger.info(`Opening ${absPath} in Blender for validation...`);
await this.blenderClient.executePython(
  `import bpy\nbpy.ops.wm.open_mainfile(filepath='${absPath.replace(/'/g, "\\\\'")}')\n__result__ = {'opened': '${path.basename(filePath)}', 'objects': len(bpy.data.objects)}`
);
```

**The problem:**

1. **Path escaping is wrong.** The code does `.replace(/'/g, "\\\\'")` which produces `\\'` in the Python string. But `\\'` in a Python string literal is:
   - `\\` → a literal backslash
   - `\'` → an escaped single quote
   
   This results in the path having actual backslashes in it, which breaks on macOS/Linux (Windows paths use backslashes intentionally, but this code is escaping them incorrectly).

2. **String concatenation is brittle.** Embedding a file path directly into a template literal that will be JSON-stringified is fragile. If the path contains special characters (spaces, newlines, unicode), the escaping breaks.

3. **The file path may not exist or may be malformed.** If `filePath` passed to `validate()` is not an absolute path or points to a non-existent file, Blender's `open_mainfile` will fail silently or error, leaving the stale scene loaded.

### 2. Why You See 156000mm

The skill document (Section 3.3) notes:

> We've seen 152 leftover objects from a traffic accident scene cause 200000mm bounding boxes and garbage validation.

Your 156000mm bounding box is coming from a massive object (likely a ground plane or auxiliary geometry) left in the Blender scene from a previous run. The validator's `getMeshData()` function does filter out `_ground_plane` objects:

```python
meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.visible_get() and not o.name.startswith('_ground_plane')]
```

But if the stale scene contains unlabeled massive objects (or objects named differently), they will be included in the bounding box calculation.

### 3. Why This Happens Every Time

The producer script (which you're presumably running before the validator) does cleanup correctly:

```javascript
// Producer cleanup (working correctly)
await client.call('save_file', { action: 'new', use_empty: true });
await client.call('execute_python', { code: `import bpy\nfor obj in list(bpy.data.objects): ...` });
```

But once the producer **disconnects from the MCP socket**, Blender's scene is NOT persisted. Blender reverts to whatever scene was auto-saved or previously loaded. The validator then connects to a fresh socket, but Blender still has the old scene in memory.

**The validator MUST load the `.blend` file from disk to see the model the producer created.**

---

## Root Cause Chain

```
Producer creates model → saves as model.blend → disconnects
    ↓
Blender reverts to stale scene (from undo history or previous load)
    ↓
Validator connects to MCP
    ↓
Validator calls getMeshData() WITHOUT loading model.blend
    ↓
getMeshData() queries bpy.data.objects in the stale scene
    ↓
Bounding box includes 152 massive leftover objects
    ↓
Result: 156000mm bounding box ← BUG
```

---

## The Fix

### Step 1: Fix the File Path Escaping

**Current (broken):**
```javascript
await this.blenderClient.executePython(
  `import bpy\nbpy.ops.wm.open_mainfile(filepath='${absPath.replace(/'/g, "\\\\'")}')\n__result__ = {'opened': '${path.basename(filePath)}', 'objects': len(bpy.data.objects)}`
);
```

**Fixed:**

Use proper single-quote escaping. In Python, the standard way to include a single quote in a single-quoted string is to escape it as `\'`. In a JavaScript template literal, that becomes `\\'` (double backslash + single quote) to account for JSON string escaping.

But the **cleanest approach** is to use triple-quoted strings in Python (which don't need escaping) or to use a backtick-quoted approach:

**Option A: Triple-quoted Python string (recommended)**

```javascript
const pythonCode = `
import bpy
filepath = '''${absPath}'''
bpy.ops.wm.open_mainfile(filepath=filepath)
__result__ = {'opened': '${path.basename(filePath)}', 'objects': len(bpy.data.objects)}
`;
await this.blenderClient.executePython(pythonCode);
```

Triple-quoted strings in Python automatically handle both single and double quotes, and the file path is interpolated directly without escaping.

**Option B: Properly escaped single quotes**

If you must keep it inline, use proper escaping:

```javascript
const escapedPath = absPath.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
await this.blenderClient.executePython(
  `import bpy\nbpy.ops.wm.open_mainfile(filepath='${escapedPath}')\n__result__ = {'opened': '${path.basename(filePath)}', 'objects': len(bpy.data.objects)}`
);
```

### Step 2: Add File Existence Check

Add validation before attempting to open the file:

```javascript
const absPath = path.resolve(filePath);
if (!fs.existsSync(absPath)) {
  throw new Error(`Model file not found: ${absPath}. Producer may have failed to save.`);
}
```

### Step 3: Enhance getMeshData() to Report the Open Status

Currently, `getMeshData()` runs Python code to measure the scene, but it doesn't confirm that the correct file was actually loaded. Add a validation step:

```python
import bpy
import os

# Verify file was opened correctly
if bpy.data.filepath != '${absPath}':
    __result__ = {'error': f'Failed to open file. Current scene: {bpy.data.filepath}'}
else:
    # Proceed with measurements
    meshes = [...]
    ...
```

---

## Complete Fixed Code

### Fixed `validate()` method in `MechanicalValidator` class

Replace the section starting at line 267:

```javascript
async validate(filePath, platform = 'game', autoFix = false) {
  const startTime = Date.now();
  logger.info(`Running mechanical checks on ${path.basename(filePath)}`);

  try {
    // Verify file exists before attempting to open
    const absPath = path.resolve(filePath);
    if (!fs.existsSync(absPath)) {
      throw new Error(`Model file not found: ${absPath}. Producer may have failed to save the .blend file.`);
    }

    // CRITICAL: Open the .blend file in Blender before measuring.
    // Without this, the validator measures whatever scene is currently
    // loaded in Blender (which may be a completely different project).
    logger.info(`Opening ${absPath} in Blender for validation...`);
    
    // Use triple-quoted Python string to avoid escaping issues
    const openCode = `
import bpy
import os

filepath = '''${absPath}'''

# Verify file exists on disk
if not os.path.exists(filepath):
    __result__ = {'error': f'File does not exist: {filepath}'}
else:
    # Open the .blend file
    bpy.ops.wm.open_mainfile(filepath=filepath)
    
    # Verify it actually opened
    if bpy.data.filepath != filepath:
        __result__ = {'error': f'Failed to open {filepath}. Current: {bpy.data.filepath}'}
    else:
        __result__ = {
            'opened': '${path.basename(filePath)}',
            'objects': len(bpy.data.objects),
            'filepath': bpy.data.filepath
        }
`;

    const openResult = await this.blenderClient.executePython(openCode);
    
    if (openResult.error) {
      throw new Error(`Failed to open .blend file: ${openResult.error}`);
    }
    
    logger.info(`Loaded scene with ${openResult.objects} objects from ${path.basename(absPath)}`);

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

### Key Changes:

1. **File existence check** before attempting to open (line with `fs.existsSync()`)
2. **Triple-quoted Python string** to avoid escaping issues
3. **Filepath validation inside Python** to confirm the file actually opened
4. **Better error messages** that distinguish between file-not-found and open-failure
5. **Log the object count** after opening to help diagnose stale scenes

---

## Testing the Fix

To verify the fix works:

1. Run the producer normally (it will create `model.blend`)
2. Run the validator with the fixed code:
   ```bash
   node asset-validator.js --concept-id <id>
   ```
3. Check the logs:
   - Should see: `Loaded scene with N objects from model.blend`
   - Should NOT see: `Loaded scene with 152 objects...` (the stale count)
4. Verify bounding box is now ~50mm tall (not 156000mm)

---

## Additional Safeguards

Consider adding these to `MechanicalValidator` constructor or config:

### 1. Validate Scene Before Measurements

Add a pre-check to ensure we have a reasonable scene:

```javascript
async validateSceneHealth() {
  const healthCode = `
import bpy
meshes = [o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('_ground_plane')]
if not meshes:
    __result__ = {'warning': 'No mesh objects found after opening file'}
else:
    all_coords = []
    for obj in meshes:
        for v in obj.data.vertices:
            all_coords.append(obj.matrix_world @ v.co)
    
    if not all_coords:
        __result__ = {'warning': 'Meshes have no vertices'}
    else:
        xs = [c.x for c in all_coords]
        ys = [c.y for c in all_coords]
        zs = [c.z for c in all_coords]
        size_mm = [(max(xs) - min(xs)) * 1000, (max(ys) - min(ys)) * 1000, (max(zs) - min(zs)) * 1000]
        
        # Sanity check: if any dimension is > 10 meters, likely a stale scene
        if any(s > 10000 for s in size_mm):
            __result__ = {'warning': f'Scene dimensions unusually large: {size_mm}mm. May be stale.', 'size_mm': size_mm}
        else:
            __result__ = {'ok': True, 'size_mm': size_mm}
`;
  
  return await this.blenderClient.executePython(healthCode);
}
```

Call this right after opening the file and log warnings if the scene looks stale.

### 2. Add Timeout / Retry Logic

If opening the file fails (network blip, Blender crash), retry once:

```javascript
let openResult;
let retries = 2;
while (retries > 0) {
  try {
    openResult = await this.blenderClient.executePython(openCode);
    if (!openResult.error) break;
  } catch (err) {
    retries--;
    if (retries === 0) throw err;
    logger.warn(`Open failed, retrying... (${retries} left)`);
    await new Promise(r => setTimeout(r, 1000));
  }
}
```

---

## Summary of Changes to `asset-validator.js`

| Issue | Line(s) | Fix |
|-------|---------|-----|
| Path escaping broken | 271 | Use triple-quoted Python string |
| No file existence check | Before 267 | Add `fs.existsSync(absPath)` |
| No verification file opened | After open call | Check `bpy.data.filepath` in Python |
| Confusing error messages | Error handling | Distinguish file-not-found from open-failure |
| No scene health check | After open | Log object count and verify reasonable dimensions |

---

## Why This Bug Wasn't Caught

1. **Timing:** The bug only manifests when the validator runs *after* the producer disconnects. If both ran in the same process, Blender would keep the scene.
2. **Path luck:** On some systems, the escaping might accidentally work (e.g., if the path has no special characters).
3. **Stale scenes:** Previous runs left large geometry in the scene, so measurements were always wrong but the error pattern was invisible until you noticed the 156000mm number.

---

## References

- **Skill Document Section 3.3:** Scene Persistence Gotcha
- **Skill Document Section 8:** Validation (includes ground plane exclusion pattern)
- **Skill Document Section 12:** Common Errors and Fixes → "Bounding box 200000mm+" row
