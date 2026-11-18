"""Measured baseline-vs-candidate using the same private scene and spec on M3."""
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
source_file = Path(os.environ["BLENDER_GRAPH_DOGFOOD_SOURCE"])
spec_path = Path(os.environ["BLENDER_GRAPH_DOGFOOD_SPEC"])
assert source_file.is_file() and spec_path.is_file()
blender = os.environ.get("BLENDER_BIN", "/Applications/Blender.app/Contents/MacOS/Blender")
baseline_commit = "cdace700ab0bb69673af7d7fca4e6caa001ee8c3"
baseline_source = subprocess.run(
    ["git", "show", f"{baseline_commit}:blender_addon/openclaw_blender_bridge.py"],
    cwd=repo, check=True, capture_output=True, text=True
).stdout

with tempfile.TemporaryDirectory(prefix="blender-baseline-") as tmp:
    old = Path(tmp) / "openclaw_blender_bridge.py"
    old.write_text(baseline_source)
    results = {}
    for mode, module in (("baseline", old), ("candidate", repo / "blender_addon/openclaw_blender_bridge.py")):
        env = dict(os.environ, BLENDER_GRAPH_DOGFOOD_SPEC=str(spec_path),
                   BLENDER_GRAPH_BRIDGE_MODULE=str(module), BLENDER_GRAPH_MODE=mode)
        output = subprocess.run(
            [blender, "-b", "--factory-startup", "--disable-autoexec",
             str(source_file), "--python", str(repo / "tests/geometry_graph_benchmark_probe.py")],
            cwd=repo, capture_output=True, text=True, env=env, timeout=105
        )
        found = re.findall(r"GRAPH_BENCHMARK_PROBE=(\{[^\n]+\})", output.stdout)
        assert output.returncode == 0 and found, (output.stdout[-750:], output.stderr[-750:])
        results[mode] = json.loads(found[-1])
    assert results["baseline"]["action_supported"] is False
    assert results["candidate"]["action_supported"] is True
    print(json.dumps({
        "metric": "correct_active_and_inactive_geometry_frames_after_one_validated_build",
        "baseline": results["baseline"]["frames_matched"],
        "candidate": results["candidate"]["frames_matched"],
        "direction": "higher",
        "original_baseline_commit": baseline_commit,
        "blender_version": "5.3.0",
        "same_source": str(source_file.name),
        "exact_frames": results["candidate"]["frames_total"]
    }, sort_keys=True))
