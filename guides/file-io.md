# File Io — outcome guide

**Outcome:** Import, save or export reliable Blender files.

## When to use
Use io.import for validated local files, inspect scene context, then use io.save or io.export with the exact target format, output path and coordinate/UV/material requirements. Save before destructive edits.

## When not to use
Do not use an export tool to save an editable Blender project or claim output succeeded merely because a call returned OK. Do not overwrite unrelated files.

## Preconditions
Existing source file, supported format, output target, export options and intended scene ownership

## Verification
Verify file exists, size is nonzero, expected objects survived and the produced file can reopen or be inspected.

## Failure policy
Stop on unsupported or missing prerequisites, record the exact tool error and preserve existing scene content. Retry only the narrowest approved correction; do not claim a final result without readback.
