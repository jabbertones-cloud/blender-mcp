#!/usr/bin/env python3
"""
Headless Blender render launcher.
Runs blender -b <blend_file> -P inline_script.py -- args
No bridge socket needed; crash-isolated subprocess.
"""
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

BLENDER_BIN = "/Applications/Blender.app/Contents/MacOS/Blender"
RENDER_QUALITY_PATH = Path(__file__).parent / "render_quality.py"

INLINE_RENDER_SCRIPT = '''
import bpy
import sys
import os

argv = sys.argv
try:
    idx = argv.index("--") + 1
    script_args = argv[idx:]
except ValueError:
    script_args = []

output_path = None
quality = "standard"
i = 0
while i < len(script_args):
    if script_args[i] == "--output" and i + 1 < len(script_args):
        output_path = script_args[i + 1]; i += 2
    elif script_args[i] == "--quality" and i + 1 < len(script_args):
        quality = script_args[i + 1]; i += 2
    else:
        i += 1

# Apply quality settings from bundled utility
render_quality_path = {render_quality_path!r}
if os.path.exists(render_quality_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("render_quality", render_quality_path)
    rq = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rq)
    rq.apply_quality_settings(preset=quality)

scene = bpy.context.scene
if output_path:
    scene.render.filepath = output_path
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

try:
    with bpy.context.temp_override(**bpy.context.copy()):
        result = bpy.ops.render.render(write_still=bool(output_path))
    if result != {{"FINISHED"}}:
        print(f"[headless_render] WARNING: render returned {{result}}")
        sys.exit(1)
except Exception as e:
    print(f"[headless_render] ERROR: {{e}}")
    sys.exit(2)

print(f"[headless_render] Done: {{output_path}}")
'''


def render_headless(blend_file, output_path, quality="standard", timeout=300):
    """
    Render blend_file to output_path using blender -b.
    Returns: {"success": bool, "output": str, "returncode": int, "elapsed": float, "stderr_tail": str}
    """
    blend_file = str(blend_file)
    output_path = str(output_path)

    # Write inline render script to temp file
    script_content = INLINE_RENDER_SCRIPT.format(
        render_quality_path=str(RENDER_QUALITY_PATH)
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix="_render.py", delete=False) as f:
        f.write(script_content)
        script_path = f.name

    cmd = [
        BLENDER_BIN, "-b", blend_file,
        "--python", script_path,
        "--",
        "--output", output_path,
        "--quality", quality,
    ]

    t0 = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": output_path,
            "returncode": -1,
            "elapsed": time.time() - t0,
            "stderr_tail": f"Timed out after {timeout}s",
        }
    except FileNotFoundError:
        return {
            "success": False,
            "output": output_path,
            "returncode": -1,
            "elapsed": time.time() - t0,
            "stderr_tail": f"Blender not found: {BLENDER_BIN}",
        }
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass

    elapsed = time.time() - t0
    out_path = Path(output_path)
    file_ok = out_path.exists() and out_path.stat().st_size > 50_000

    stderr_tail = (result.stderr or "")[-2000:]

    return {
        "success": result.returncode == 0 and file_ok,
        "output": output_path,
        "returncode": result.returncode,
        "elapsed": round(elapsed, 2),
        "stderr_tail": stderr_tail,
        "file_exists": out_path.exists(),
        "file_size": out_path.stat().st_size if out_path.exists() else 0,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Headless Blender render")
    parser.add_argument("--blend", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--quality", default="standard", choices=["draft", "standard", "high"])
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()
    result = render_headless(args.blend, args.output, args.quality, args.timeout)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["success"] else 1)
