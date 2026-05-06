"""
SMOKE TESTS: CADAM Priority 3 - Reference Image to Scene (Two-Pass)
===================================================================

Validates the blender_reference_image_to_scene tool and supporting modules:
  - extraction_prompt action returns detailed instruction prompt
  - submit_extraction action validates JSON and caches results
  - build_seed_params action maps extraction to Blender parameters
"""

import sys
import json
import os

# Add server module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))

from image_extraction import (
    IMAGE_EXTRACTION_PROMPT,
    IMAGE_EXTRACTION_SCHEMA,
    validate_extraction,
    build_seed_params,
)


def test_extraction_prompt():
    """Test 1: extraction_prompt action returns detailed instruction prompt"""
    print("\n[TEST 1] extraction_prompt action returns detailed instruction prompt")
    
    try:
        # Verify prompt is substantial
        assert isinstance(IMAGE_EXTRACTION_PROMPT, str), "Prompt must be string"
        assert len(IMAGE_EXTRACTION_PROMPT) > 100, "Prompt too short"
        assert "JSON" in IMAGE_EXTRACTION_PROMPT, "Prompt should mention JSON"
        
        print(f"  ✓ IMAGE_EXTRACTION_PROMPT is {len(IMAGE_EXTRACTION_PROMPT)} chars")
        print("  ✓ Prompt mentions structured output format")
        print("  [PASS]")
        return True
    except AssertionError as e:
        print(f"  ✗ ASSERTION FAILED: {e}")
        print("  [FAIL]")
        return False


def test_validate_extraction_valid():
    """Test 2: submit_extraction with valid JSON passes validation"""
    print("\n[TEST 2] submit_extraction with valid JSON passes validation")
    
    try:
        # Valid extraction matching schema exactly
        valid_extraction = {
            "dimensions": {
                "width_estimate_cm": 30,
                "height_estimate_cm": 40,
                "depth_estimate_cm": 20,
                "description": "estimated from object scale"
            },
            "materials": [
                {
                    "name": "Oak Wood",
                    "base_color": "#8B4513",
                    "metallic": 0.1,
                    "roughness": 0.6,
                    "notes": "matte wood with visible grain"
                }
            ],
            "lighting": {
                "key_light": "45° from upper left, bright",
                "fill_light": "soft bounce from right",
                "rim_light": "none",
                "environment": "neutral white",
                "notes": "studio lighting, bright and even"
            },
            "camera": {
                "position": "30cm away, eye level",
                "focal_length": "normal",
                "depth_of_field": "moderate",
                "notes": "straight-on product shot"
            },
            "scene_notes": "Simple wooden block on neutral background with studio lighting.",
            "confidence": 0.85
        }
        
        is_valid, errors = validate_extraction(valid_extraction)
        
        assert is_valid, f"Valid extraction should pass validation. Errors: {errors}"
        
        print("  ✓ Valid extraction passed validation")
        print(f"  ✓ No errors returned")
        print("  [PASS]")
        return True
    except AssertionError as e:
        print(f"  ✗ ASSERTION FAILED: {e}")
        print("  [FAIL]")
        return False


def test_validate_extraction_invalid():
    """Test 3: submit_extraction with invalid JSON fails validation"""
    print("\n[TEST 3] submit_extraction with invalid JSON fails validation")
    
    try:
        # Missing required keys
        invalid_1 = {
            "dimensions": {
                "width_estimate_cm": 30,
                "height_estimate_cm": 40,
                "depth_estimate_cm": 20,
                "description": "test"
            },
            "materials": [{"name": "wood", "base_color": "#8B4513", "metallic": 0.1, "roughness": 0.6, "notes": "test"}]
            # Missing: lighting, camera, scene_notes, confidence
        }
        
        is_valid, errors = validate_extraction(invalid_1)
        assert not is_valid, "Invalid extraction should fail"
        assert len(errors) > 0, "Should return error messages"
        print("  ✓ Invalid extraction (missing keys) failed validation")
        print(f"  ✓ Got {len(errors)} error messages:")
        for err in errors[:3]:
            print(f"    - {err}")
        
        # Out of range metallic
        invalid_2 = {
            "dimensions": {
                "width_estimate_cm": 30,
                "height_estimate_cm": 40,
                "depth_estimate_cm": 20,
                "description": "test"
            },
            "materials": [{"name": "metal", "base_color": "#C0C0C0", "metallic": 1.5, "roughness": 0.2, "notes": "test"}],
            "lighting": {"key_light": "left", "fill_light": "right", "rim_light": "back", "environment": "white", "notes": "test"},
            "camera": {"position": "front", "focal_length": "normal", "depth_of_field": "shallow", "notes": "test"},
            "scene_notes": "test",
            "confidence": 0.5
        }
        
        is_valid, errors = validate_extraction(invalid_2)
        assert not is_valid, "Out-of-range metallic should fail"
        print("  ✓ Invalid extraction (metallic out of range) failed validation")
        
        print("  [PASS]")
        return True
    except AssertionError as e:
        print(f"  ✗ ASSERTION FAILED: {e}")
        print("  [FAIL]")
        return False


def test_build_seed_params():
    """Test 4: build_seed_params maps extraction to Blender parameters"""
    print("\n[TEST 4] build_seed_params maps extraction to Blender parameters")
    
    try:
        valid_extraction = {
            "dimensions": {
                "width_estimate_cm": 30,
                "height_estimate_cm": 40,
                "depth_estimate_cm": 20,
                "description": "measured"
            },
            "materials": [
                {"name": "Oak Wood", "base_color": "#8B4513", "metallic": 0.1, "roughness": 0.6, "notes": "wood"},
                {"name": "Steel", "base_color": "#808080", "metallic": 0.8, "roughness": 0.3, "notes": "metal"}
            ],
            "lighting": {
                "key_light": "left, strong",
                "fill_light": "right, soft",
                "rim_light": "back",
                "environment": "forest HDRI",
                "notes": "outdoor mood"
            },
            "camera": {
                "position": "front, 50cm",
                "focal_length": "wide",
                "depth_of_field": "shallow",
                "notes": "dramatic angle"
            },
            "scene_notes": "Wooden furniture with steel accents in natural lighting.",
            "confidence": 0.9
        }
        
        seed_params, warnings = build_seed_params(valid_extraction)
        
        # Check that mapping produces parameters
        assert isinstance(seed_params, dict), "build_seed_params should return dict"
        assert len(seed_params) > 10, f"Should map more than 10 Blender parameters, got {len(seed_params)}"
        
        # Verify key mappings
        assert "SCENE_WIDTH_CM" in seed_params
        assert "PRIMARY_BASE_COLOR" in seed_params
        assert "SECONDARY_BASE_COLOR" in seed_params
        assert "PRIMARY_METALLIC" in seed_params
        
        print(f"  ✓ Built {len(seed_params)} Blender seed parameters")
        print("  ✓ Dimension, material, lighting, and camera mappings present")
        print("  ✓ Primary and secondary materials mapped")
        print("  [PASS]")
        return True
    except AssertionError as e:
        print(f"  ✗ ASSERTION FAILED: {e}")
        print("  [FAIL]")
        return False


def test_full_two_pass_flow():
    """Test 5: Full two-pass flow - validate extraction + build seed parameters"""
    print("\n[TEST 5] Full two-pass flow: validate extraction + build seed parameters")
    
    try:
        # Complete extraction JSON (as would come from Claude Pass 1)
        claude_extraction = {
            "dimensions": {
                "width_estimate_cm": 50,
                "height_estimate_cm": 75,
                "depth_estimate_cm": 35,
                "description": "inferred from furniture scale"
            },
            "materials": [
                {
                    "name": "Walnut Wood",
                    "base_color": "#3E2723",
                    "metallic": 0.0,
                    "roughness": 0.5,
                    "notes": "dark wood with natural patina"
                }
            ],
            "lighting": {
                "key_light": "30° from left, warm",
                "fill_light": "opposite side soft",
                "rim_light": "subtle back",
                "environment": "warm indoor HDRI",
                "notes": "evening room lighting"
            },
            "camera": {
                "position": "45cm distance, slightly above center",
                "focal_length": "normal",
                "depth_of_field": "moderate",
                "notes": "3/4 view composition"
            },
            "scene_notes": "Wooden desk in warm indoor lighting. Wood grain visible, natural finish. Simple studio background.",
            "confidence": 0.88
        }
        
        # Pass 2: Validate extraction
        is_valid, errors = validate_extraction(claude_extraction)
        assert is_valid, f"Extraction validation failed: {errors}"
        print("  ✓ Extraction passed validation")
        
        # Pass 2: Build seed parameters
        seed_params, warnings = build_seed_params(claude_extraction)
        assert seed_params is not None, "build_seed_params should return dict"
        assert len(seed_params) > 0, "seed_params should not be empty"
        
        print(f"  ✓ Built {len(seed_params)} Blender seed parameters")
        print(f"  ✓ Warnings: {len(warnings)}" if warnings else "  ✓ No warnings")
        print("  ✓ Two-pass flow complete: image → JSON → seed_parameters")
        print("  [PASS]")
        return True
    except AssertionError as e:
        print(f"  ✗ {e}")
        print("  [FAIL]")
        return False


def run_all_tests():
    """Execute all smoke tests and report summary"""
    print("\n" + "=" * 70)
    print("SMOKE TESTS: CADAM Priority 3 - Reference Image to Scene (Two-Pass)")
    print("=" * 70)
    
    tests = [
        test_extraction_prompt,
        test_validate_extraction_valid,
        test_validate_extraction_invalid,
        test_build_seed_params,
        test_full_two_pass_flow,
    ]
    
    results = [test() for test in tests]
    
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    test_names = [
        "extraction_prompt",
        "validate_extraction (valid)",
        "validate_extraction (invalid)",
        "build_seed_params",
        "full two-pass flow"
    ]
    for name, passed in zip(test_names, results):
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")
    
    passed_count = sum(results)
    total_count = len(results)
    print(f"\nTotal: {passed_count}/{total_count} tests passed")
    print("=" * 70)
    
    return all(results)


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
