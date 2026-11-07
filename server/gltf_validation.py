"""Fail-closed Khronos glTF validation for local GLB exports."""
from __future__ import annotations
import json
import shutil
import subprocess
from pathlib import Path

_VALIDATOR = Path(__file__).resolve().parents[1] / "scripts" / "validate_glb.cjs"

def file_signature(filepath: str):
    try:
        stat = Path(filepath).stat()
        return (stat.st_size, stat.st_mtime_ns)
    except OSError:
        return None

def validate_export(filepath: str, previous=None) -> dict:
    path = Path(filepath).expanduser()
    if not path.is_absolute() or path.suffix.lower() != ".glb":
        return {"valid": False, "error": "GLB export must use an absolute .glb destination"}
    try:
        path = path.resolve(strict=True)
        stat = path.stat()
        if not path.is_file() or stat.st_size == 0:
            return {"valid": False, "error": "GLB export is missing or empty"}
        if previous == (stat.st_size, stat.st_mtime_ns):
            return {"valid": False, "error": "GLB export did not update the existing file"}
        result = subprocess.run([shutil.which("node") or "/opt/homebrew/bin/node", str(_VALIDATOR), str(path)], capture_output=True,
                                text=True, timeout=45, check=False)
        report = json.loads(result.stdout)
        if result.returncode or report.get("valid") is not True:
            return {"valid": False, "error": "Khronos validator rejected exported GLB", "report": report}
        return {"valid": True, "report": report}
    except (OSError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        return {"valid": False, "error": f"GLB validation unavailable: {type(exc).__name__}"}
