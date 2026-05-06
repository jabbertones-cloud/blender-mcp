"""
CADAM Reference Image Extraction Module
========================================

Two-pass extraction workflow for converting reference images to Blender scenes:
  1. Extraction Pass: Claude analyzes image → structured JSON
  2. Build Pass: Server validates JSON → seed parameters → bpy script generation

This module provides:
  - IMAGE_EXTRACTION_PROMPT: detailed prompt for Claude image analysis
  - IMAGE_EXTRACTION_SCHEMA: strict JSON structure contract
  - validate_extraction(): validate extracted JSON payload
  - build_seed_params(): map extraction fields to Blender generation parameters
"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple


# =============================================================================
# EXTRACTION PROMPT FOR CLAUDE
# =============================================================================

IMAGE_EXTRACTION_PROMPT = """You are an expert 3D scene analyst for Blender.

TASK: Analyze the provided reference image and extract a structured description that can drive Blender scene generation.

REQUIRED OUTPUT FORMAT: Return a JSON object matching this exact structure:

{
  "dimensions": {
    "width_estimate_cm": <number>,
    "height_estimate_cm": <number>,
    "depth_estimate_cm": <number>,
    "description": "<brief dimension notes>"
  },
  "materials": [
    {
      "name": "<material name>",
      "base_color": "<hex or name>",
      "metallic": <0.0-1.0>,
      "roughness": <0.0-1.0>,
      "notes": "<how to achieve this look>"
    }
  ],
  "lighting": {
    "key_light": "<direction and intensity>",
    "fill_light": "<if present>",
    "rim_light": "<if present>",
    "environment": "<HDRI or color>",
    "notes": "<overall lighting mood>"
  },
  "camera": {
    "position": "<approximate position relative to subject>",
    "focal_length": "<normal/wide/telephoto>",
    "depth_of_field": "<shallow/moderate/deep>",
    "notes": "<framing and composition>"
  },
  "scene_notes": "<3-5 sentence description of the overall scene, key objects, and spatial relationships>",
  "confidence": <0.0-1.0>
}

EXTRACTION RULES:
1. dimensions: Estimate physical dimensions in centimeters. Include description of measuring approach.
2. materials: List 2-5 key materials visible in the image. Use standard Blender material parameters.
3. lighting: Describe light sources, directions, intensities, and overall mood. Reference HDRI if applicable.
4. camera: Position relative to subject, lens type (normal ~50mm, wide <35mm, telephoto >85mm), DOF state.
5. scene_notes: Narrative description that captures spatial layout, key objects, and spatial relationships.
6. confidence: 0.0-1.0 confidence in extraction (1.0 = very confident, 0.5 = moderate ambiguity, 0.2 = highly speculative).

CONFIDENCE SCORING:
- 0.9-1.0: Clear reference with good lighting, visible details
- 0.7-0.8: Mostly clear with some ambiguity in materials or dimensions
- 0.5-0.6: Moderate ambiguity; some details inferred
- 0.3-0.4: Heavy inference; significant missing information
- <0.3: Very speculative; image is unclear or completely foreign to reference

MATERIAL COLOR CODES:
- Use CSS color names (white, black, red, blue, etc.) or hex codes (#FF0000)
- When unsure, use neutral (gray #808080, white #FFFFFF)

DIMENSION ESTIMATES:
- Reference common objects (e.g., "cup is ~10cm wide")
- If no reference available, estimate based on apparent detail level
- Always include measurement notes (e.g., "estimated from shadows")

OUTPUT VALIDATION:
- Return ONLY the JSON object, no markdown, no extra text
- All required keys (dimensions, materials, lighting, camera, scene_notes, confidence) must be present
- confidence must be a number 0.0-1.0
- materials must be a non-empty array
- No trailing commas, valid JSON only

Example output (concise):
{
  "dimensions": {"width_estimate_cm": 30, "height_estimate_cm": 40, "depth_estimate_cm": 20, "description": "estimated from object scale"},
  "materials": [{"name": "ceramic", "base_color": "#E8D4C4", "metallic": 0.0, "roughness": 0.4, "notes": "matte ceramic with slight texture"}],
  "lighting": {"key_light": "45° from upper left, bright", "fill_light": "soft bounce from right", "rim_light": "none", "environment": "neutral white", "notes": "studio lighting, bright and even"},
  "camera": {"position": "30cm away, eye level", "focal_length": "normal", "depth_of_field": "moderate", "notes": "straight-on product shot"},
  "scene_notes": "Simple white ceramic cup on neutral background with studio lighting. Cup is centered in frame, slightly tilted to show rim.",
  "confidence": 0.85
}
"""


# =============================================================================
# EXTRACTION SCHEMA
# =============================================================================

IMAGE_EXTRACTION_SCHEMA = {
    "type": "object",
    "required": ["dimensions", "materials", "lighting", "camera", "scene_notes", "confidence"],
    "properties": {
        "dimensions": {
            "type": "object",
            "required": ["width_estimate_cm", "height_estimate_cm", "depth_estimate_cm", "description"],
            "properties": {
                "width_estimate_cm": {"type": "number"},
                "height_estimate_cm": {"type": "number"},
                "depth_estimate_cm": {"type": "number"},
                "description": {"type": "string"},
            },
        },
        "materials": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["name", "base_color", "metallic", "roughness", "notes"],
                "properties": {
                    "name": {"type": "string"},
                    "base_color": {"type": "string"},
                    "metallic": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "roughness": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "notes": {"type": "string"},
                },
            },
        },
        "lighting": {
            "type": "object",
            "required": ["key_light", "fill_light", "rim_light", "environment", "notes"],
            "properties": {
                "key_light": {"type": "string"},
                "fill_light": {"type": "string"},
                "rim_light": {"type": "string"},
                "environment": {"type": "string"},
                "notes": {"type": "string"},
            },
        },
        "camera": {
            "type": "object",
            "required": ["position", "focal_length", "depth_of_field", "notes"],
            "properties": {
                "position": {"type": "string"},
                "focal_length": {"type": "string"},
                "depth_of_field": {"type": "string"},
                "notes": {"type": "string"},
            },
        },
        "scene_notes": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    },
}


# =============================================================================
# VALIDATION
# =============================================================================


def validate_extraction(payload: Any) -> Tuple[bool, List[str]]:
    """
    Validate extracted JSON against the extraction schema.

    Args:
        payload: The extraction JSON object (parsed dict or raw string)

    Returns:
        (is_valid, error_messages): bool and list of validation errors
    """
    errors = []

    # Parse if string
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as e:
            return False, [f"Invalid JSON: {str(e)}"]

    if not isinstance(payload, dict):
        return False, ["Extraction must be a JSON object (dict)"]

    # Check required top-level keys
    required_keys = {"dimensions", "materials", "lighting", "camera", "scene_notes", "confidence"}
    missing = required_keys - set(payload.keys())
    if missing:
        errors.append(f"Missing required keys: {', '.join(sorted(missing))}")

    # Validate dimensions
    if "dimensions" in payload:
        dims = payload["dimensions"]
        if not isinstance(dims, dict):
            errors.append("dimensions must be a dict")
        else:
            for key in ["width_estimate_cm", "height_estimate_cm", "depth_estimate_cm"]:
                if key not in dims:
                    errors.append(f"dimensions missing key: {key}")
                elif not isinstance(dims[key], (int, float)):
                    errors.append(f"dimensions.{key} must be a number")
            if "description" not in dims:
                errors.append("dimensions missing key: description")
            elif not isinstance(dims["description"], str):
                errors.append("dimensions.description must be a string")

    # Validate materials (non-empty array)
    if "materials" in payload:
        mats = payload["materials"]
        if not isinstance(mats, list):
            errors.append("materials must be an array")
        elif len(mats) == 0:
            errors.append("materials array must have at least 1 item")
        else:
            for i, mat in enumerate(mats):
                if not isinstance(mat, dict):
                    errors.append(f"materials[{i}] must be a dict")
                else:
                    for key in ["name", "base_color", "notes"]:
                        if key not in mat:
                            errors.append(f"materials[{i}] missing key: {key}")
                        elif not isinstance(mat[key], str):
                            errors.append(f"materials[{i}].{key} must be a string")
                    for key in ["metallic", "roughness"]:
                        if key not in mat:
                            errors.append(f"materials[{i}] missing key: {key}")
                        elif not isinstance(mat[key], (int, float)):
                            errors.append(f"materials[{i}].{key} must be a number")
                        elif not (0.0 <= mat[key] <= 1.0):
                            errors.append(
                                f"materials[{i}].{key} must be between 0.0 and 1.0, got {mat[key]}"
                            )

    # Validate lighting
    if "lighting" in payload:
        light = payload["lighting"]
        if not isinstance(light, dict):
            errors.append("lighting must be a dict")
        else:
            for key in ["key_light", "fill_light", "rim_light", "environment", "notes"]:
                if key not in light:
                    errors.append(f"lighting missing key: {key}")
                elif not isinstance(light[key], str):
                    errors.append(f"lighting.{key} must be a string")

    # Validate camera
    if "camera" in payload:
        cam = payload["camera"]
        if not isinstance(cam, dict):
            errors.append("camera must be a dict")
        else:
            for key in ["position", "focal_length", "depth_of_field", "notes"]:
                if key not in cam:
                    errors.append(f"camera missing key: {key}")
                elif not isinstance(cam[key], str):
                    errors.append(f"camera.{key} must be a string")

    # Validate scene_notes (string)
    if "scene_notes" in payload:
        if not isinstance(payload["scene_notes"], str):
            errors.append("scene_notes must be a string")

    # Validate confidence (0.0-1.0)
    if "confidence" in payload:
        conf = payload["confidence"]
        if not isinstance(conf, (int, float)):
            errors.append("confidence must be a number")
        elif not (0.0 <= conf <= 1.0):
            errors.append(f"confidence must be between 0.0 and 1.0, got {conf}")

    return len(errors) == 0, errors


# =============================================================================
# SEED PARAMETER BUILDING
# =============================================================================


def build_seed_params(extraction: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """
    Convert extraction JSON to seed parameters for Blender generation.

    Maps extraction fields to Blender generation parameters suitable for passing
    to blender_generate_bpy_script as the seeds parameter.

    Args:
        extraction: Validated extraction dict (assume validate_extraction passed)

    Returns:
        (seed_params, warnings): dict of seed parameters and list of warning messages
    """
    warnings = []
    seeds = {}

    # Dimensions
    dims = extraction.get("dimensions", {})
    seeds["SCENE_WIDTH_CM"] = dims.get("width_estimate_cm", 30)
    seeds["SCENE_HEIGHT_CM"] = dims.get("height_estimate_cm", 40)
    seeds["SCENE_DEPTH_CM"] = dims.get("depth_estimate_cm", 20)

    # Materials (pick primary material)
    materials = extraction.get("materials", [])
    if materials:
        primary_mat = materials[0]
        seeds["PRIMARY_MATERIAL"] = primary_mat.get("name", "material")
        seeds["PRIMARY_BASE_COLOR"] = primary_mat.get("base_color", "#808080")
        seeds["PRIMARY_METALLIC"] = float(primary_mat.get("metallic", 0.0))
        seeds["PRIMARY_ROUGHNESS"] = float(primary_mat.get("roughness", 0.5))

        # Secondary material if available
        if len(materials) > 1:
            secondary_mat = materials[1]
            seeds["SECONDARY_MATERIAL"] = secondary_mat.get("name", "material_2")
            seeds["SECONDARY_BASE_COLOR"] = secondary_mat.get("base_color", "#FFFFFF")
    else:
        warnings.append("No materials in extraction; using defaults")
        seeds["PRIMARY_MATERIAL"] = "material"
        seeds["PRIMARY_BASE_COLOR"] = "#808080"
        seeds["PRIMARY_METALLIC"] = 0.0
        seeds["PRIMARY_ROUGHNESS"] = 0.5

    # Lighting
    lighting = extraction.get("lighting", {})
    key_light = lighting.get("key_light", "upper left")
    if "45" in key_light.lower() or "upper" in key_light.lower():
        seeds["KEY_LIGHT_ANGLE"] = 45
    elif "direct" in key_light.lower() or "straight" in key_light.lower():
        seeds["KEY_LIGHT_ANGLE"] = 0
    else:
        seeds["KEY_LIGHT_ANGLE"] = 45
        warnings.append(f"Inferred key light angle from description: {key_light}")

    env = lighting.get("environment", "neutral white").lower()
    seeds["USE_HDRI"] = "hdri" in env or "environment" in env
    seeds["LIGHTING_MOOD"] = "studio" if "studio" in env else "natural"

    # Camera (simplified)
    camera = extraction.get("camera", {})
    focal_len = camera.get("focal_length", "normal").lower()
    if "wide" in focal_len or "<35" in focal_len:
        seeds["CAMERA_FOCAL_LENGTH"] = 28
    elif "telephoto" in focal_len or ">85" in focal_len:
        seeds["CAMERA_FOCAL_LENGTH"] = 100
    else:
        seeds["CAMERA_FOCAL_LENGTH"] = 50  # normal

    # DOF
    dof = camera.get("depth_of_field", "moderate").lower()
    seeds["USE_DOF"] = "deep" in dof or "shallow" in dof
    seeds["DOF_APERTURE"] = 2.8 if "shallow" in dof else 5.6

    # Scene overall
    confidence = extraction.get("confidence", 0.5)
    if confidence < 0.5:
        warnings.append(f"Low confidence ({confidence}); results may need manual refinement")

    seeds["SCENE_DESCRIPTION"] = extraction.get("scene_notes", "Generated from reference")

    return seeds, warnings
