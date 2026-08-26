import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "scripts" / "render_quality.py").read_text()
TREE = ast.parse(SOURCE)
PRESETS = None
for node in TREE.body:
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "PRESETS":
                PRESETS = ast.literal_eval(node.value)
assert PRESETS is not None


def test_standard_preset_matches_v22_gold():
    cfg = PRESETS["standard"]
    assert cfg["samples"] == 256
    assert cfg["use_adaptive_sampling"] is True
    assert cfg["adaptive_threshold"] == 0.002
    assert cfg["denoiser"] == "OPENIMAGEDENOISE"
    assert cfg["caustics_reflective"] is False
    assert cfg["caustics_refractive"] is False
    assert cfg["denoising_normal_pass"] is True
    assert cfg["denoising_albedo_pass"] is True


def test_draft_and_high_sample_counts():
    assert PRESETS["draft"]["samples"] == 64
    assert PRESETS["high"]["samples"] == 512
