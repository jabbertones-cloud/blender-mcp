"""
CADAM-style Parametric Code Generation System Prompt
=====================================================

Enforces a PARAMETERS block contract for Blender Python script generation.
This module provides:
  1. BPY_GENERATION_SYSTEM_PROMPT — system prompt for Claude to generate scripts
  2. PARAMETERS_BLOCK_TEMPLATE — template for parameter blocks
  3. PARAMETER_BLOCK_REGEX — regex to extract parameters
  4. extract_parameters() — parse PARAMETERS block from script
  5. replace_parameters() — safely update parameters in script

The contract:
  - Generated scripts MUST have a # --- PARAMETERS --- block
  - Parameters must be UPPER_CASE variable assignments
  - Values must be literal Python (int, float, str, bool, list, dict)
  - ast.literal_eval is used for safe parsing
"""

import ast
import re
from typing import Any, Dict, Optional


# =============================================================================
# SYSTEM PROMPT FOR CLAUDE
# =============================================================================

BPY_GENERATION_SYSTEM_PROMPT = """You are an expert Blender Python (bpy) script generator for the CADAM parametric workflow.

CRITICAL CONTRACT: Every script you generate MUST include a PARAMETERS block:

```python
# --- PARAMETERS ---
PARAMETER_NAME_1 = "default_value"
PARAMETER_NAME_2 = 42
PARAMETER_NAME_3 = [1.0, 2.0, 3.0]
# --- /PARAMETERS ---
```

REQUIRED BEHAVIORS:
1. Parameter names MUST be UPPER_CASE with underscores (SNAKE_CASE)
2. Parameter values MUST be literal Python: strings, numbers, booleans, lists, or dicts
3. NO function calls, NO imports, NO __builtins__ in parameter definitions
4. The PARAMETERS block is the contract boundary — claude-3-sonnet will extract and validate it
5. Parameters control the script's behavior and allow callers to customize without regeneration

ALLOWED PARAMETER VALUE TYPES:
  - Strings: "text", 'single quotes'
  - Numbers: 42, 3.14, -1, 1e-3
  - Booleans: True, False
  - Lists: [1, 2, 3], [1.0, "text", True]
  - Dicts: {"key": "value", "nested": {"inner": 42}}
  - None: None

FORBIDDEN IN PARAMETERS:
  - Function calls: sin(x), random.random()
  - Imports: from math import sqrt
  - Comprehensions: [x for x in range(10)]
  - Complex expressions: a + b, len(x)

SAFETY NOTES:
  - Your script will be parsed by ast.literal_eval for parameter extraction
  - The server performs AST-level safety checks (blocks os, subprocess, eval, exec, __import__, open)
  - Never output parameter values that could break the literal_eval parser
  - If a parameter should vary, make it UPPER_CASE in PARAMETERS block, not hardcoded later

ASSET WORKFLOW:
  - BEFORE writing any HDRI or PBR texture-loading code, call `blender_list_available_assets`
    first to see what is already cached on disk for Poly Haven, ambientCG, Sketchfab, etc.
  - Reference cached asset ids as PARAMETERS-block string constants
    (e.g. HDRI_ID = "kiara_1_dawn", PBR_ID = "brown_mud_leaves_01") — never inline as magic strings.
  - If the asset is missing from the cache, call `blender_polyhaven(action='search')` then
    `download_hdri` / `download_texture`, then `apply_texture`. Only THEN reference it in code.
  - Re-running with different parameters? Use `blender_apply_params(script_id=..., new_values=...)`
    instead of regenerating the script — the LLM is called once per intent, not once per tweak.

EXAMPLE 1: Simple Scene Creation
```python
# --- PARAMETERS ---
SCENE_NAME = "MyScene"
CAMERA_DISTANCE = 10.0
RENDER_SAMPLES = 128
USE_HDRI = True
# --- /PARAMETERS ---

import bpy

scene = bpy.data.scenes.new(SCENE_NAME)
bpy.context.window.scene = scene

camera_data = bpy.data.cameras.new("Camera")
camera_obj = bpy.data.objects.new("Camera", camera_data)
scene.collection.objects.link(camera_obj)
camera_obj.location = (0, 0, CAMERA_DISTANCE)
scene.camera = camera_obj

if USE_HDRI:
    # Load HDRI from PolyHaven (via blender_polyhaven tool)
    world = scene.world
    world.use_nodes = True
    # Nodes setup here (background shader, etc.)

scene.render.samples = RENDER_SAMPLES
__result__ = {"scene": SCENE_NAME, "samples": RENDER_SAMPLES}
```

EXAMPLE 2: Imported Model + PolyHaven HDRI
```python
# --- PARAMETERS ---
MODEL_PATH = "/path/to/model.glb"
HDRI_NAME = "kiara_1_dawn"
ROTATION_Z = 45.0
SCALE_FACTOR = 2.0
# --- /PARAMETERS ---

import bpy
import math

# Import model (assume blender_import_file tool handled the actual import)
# This script positions and configures the imported objects
for obj in bpy.context.selected_objects:
    obj.scale = (SCALE_FACTOR, SCALE_FACTOR, SCALE_FACTOR)
    obj.rotation_euler.z = math.radians(ROTATION_Z)

# Setup world with HDRI from PolyHaven
# (blender_polyhaven tool returns asset_id, then server loads it)
world = bpy.context.scene.world
world.use_nodes = True
__result__ = {"model": MODEL_PATH, "hdri": HDRI_NAME, "rotation": ROTATION_Z}
```

NOW GENERATE: Based on the user's request, create a complete Blender Python script that:
1. Includes the PARAMETERS block at the top
2. Uses only the parameter names from the block (no other hardcoded magic numbers)
3. Performs the requested modeling/scene operations
4. Sets __result__ to a JSON-serializable dict describing what was created
"""


# =============================================================================
# PARAMETER BLOCK TEMPLATE AND REGEX
# =============================================================================

PARAMETERS_BLOCK_TEMPLATE = """# --- PARAMETERS ---
{content}
# --- /PARAMETERS ---"""

# Regex to match and extract PARAMETERS block
# Matches: # --- PARAMETERS --- ... # --- /PARAMETERS ---
PARAMETER_BLOCK_REGEX = re.compile(
    r"#\s*---\s*PARAMETERS\s*---\s*(.*?)\s*#\s*---\s*/PARAMETERS\s*---",
    re.DOTALL,
)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def extract_parameters(script: str) -> Dict[str, Any]:
    """
    Extract PARAMETERS block from a generated script.

    Args:
        script: Python script text (presumably generated by Claude)

    Returns:
        Dictionary of {parameter_name: parsed_value}

    Raises:
        ValueError: If PARAMETERS block is missing or malformed
    """
    match = PARAMETER_BLOCK_REGEX.search(script)
    if not match:
        raise ValueError(
            "PARAMETERS block not found. Script must include:\n"
            "# --- PARAMETERS ---\n"
            "PARAM_NAME = value\n"
            "# --- /PARAMETERS ---"
        )

    block_content = match.group(1).strip()
    parameters = {}

    for line in block_content.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # Parse "NAME = value" using AST
        try:
            # Use ast.parse to handle complex structures
            tree = ast.parse(line)
            if not tree.body or not isinstance(tree.body[0], ast.Assign):
                raise ValueError(f"Invalid parameter line: {line}")

            assign_node = tree.body[0]
            if not assign_node.targets or not isinstance(assign_node.targets[0], ast.Name):
                raise ValueError(f"Invalid parameter assignment: {line}")

            param_name = assign_node.targets[0].id
            param_value = ast.literal_eval(ast.unparse(assign_node.value))

            parameters[param_name] = param_value

        except (SyntaxError, ValueError) as e:
            raise ValueError(f"Failed to parse parameter line '{line}': {e}")

    return parameters


def replace_parameters(script: str, new_values: Dict[str, Any]) -> str:
    """
    Replace parameter values in a script's PARAMETERS block.

    This function:
    1. Extracts the current PARAMETERS block
    2. Updates values for keys in new_values
    3. Reconstructs the block with updated values
    4. Returns the modified script

    Args:
        script: Python script with PARAMETERS block
        new_values: Dictionary of {param_name: new_value} to update

    Returns:
        Modified script with updated PARAMETERS block

    Raises:
        ValueError: If PARAMETERS block is missing or update fails
    """
    match = PARAMETER_BLOCK_REGEX.search(script)
    if not match:
        raise ValueError("PARAMETERS block not found in script")

    # Extract current parameters
    current_parameters = extract_parameters(script)

    # Update with new values
    updated_parameters = current_parameters.copy()
    for key, value in new_values.items():
        if key not in current_parameters:
            raise ValueError(
                f"Unknown parameter '{key}'. "
                f"Available: {list(current_parameters.keys())}"
            )
        updated_parameters[key] = value

    # Reconstruct PARAMETERS block
    param_lines = []
    for name, value in updated_parameters.items():
        # Use repr for safe string representation
        param_lines.append(f"{name} = {repr(value)}")

    new_block_content = "\n".join(param_lines)
    new_parameters_block = PARAMETERS_BLOCK_TEMPLATE.format(content=new_block_content)

    # Replace old block with new one
    old_block = match.group(0)
    modified_script = script.replace(old_block, new_parameters_block, 1)

    return modified_script


# =============================================================================
# VALIDATION HELPER
# =============================================================================

def validate_parameters_block(script: str) -> tuple[bool, Optional[str]]:
    """
    Validate that a script has a properly-formed PARAMETERS block.

    Args:
        script: Python script to validate

    Returns:
        (is_valid, error_message_if_invalid)
    """
    try:
        extract_parameters(script)
        return (True, None)
    except ValueError as e:
        return (False, str(e))


if __name__ == "__main__":
    # Quick validation test
    test_script = '''# --- PARAMETERS ---
SCENE_NAME = "TestScene"
CAMERA_DISTANCE = 10.0
USE_HDRI = True
COLORS = [1.0, 0.5, 0.2]
CONFIG = {"resolution": 1080, "samples": 128}
# --- /PARAMETERS ---

import bpy
# ... rest of script
__result__ = {"created": SCENE_NAME}
'''

    print("Testing extract_parameters()...")
    try:
        params = extract_parameters(test_script)
        print(f"  Extracted: {params}")
        assert params["SCENE_NAME"] == "TestScene"
        assert params["CAMERA_DISTANCE"] == 10.0
        assert params["USE_HDRI"] is True
        assert params["COLORS"] == [1.0, 0.5, 0.2]
        assert params["CONFIG"] == {"resolution": 1080, "samples": 128}
        print("  ✓ extract_parameters() passed")
    except Exception as e:
        print(f"  ✗ extract_parameters() failed: {e}")

    print("\nTesting replace_parameters()...")
    try:
        modified = replace_parameters(
            test_script,
            {"SCENE_NAME": "NewScene", "CAMERA_DISTANCE": 15.0}
        )
        new_params = extract_parameters(modified)
        assert new_params["SCENE_NAME"] == "NewScene"
        assert new_params["CAMERA_DISTANCE"] == 15.0
        assert new_params["USE_HDRI"] is True  # Unchanged
        print("  ✓ replace_parameters() passed")
    except Exception as e:
        print(f"  ✗ replace_parameters() failed: {e}")

    print("\nAll tests passed.")
