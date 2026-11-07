"""Quantitative GLB QA: official validator versus header-only check."""
from __future__ import annotations
import json
from pathlib import Path
import statistics
import struct
import tempfile
import time
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server.gltf_validation import validate_export


def make_valid_glb() -> bytes:
    doc = b'{"asset":{"version":"2.0"}}'
    doc += b" " * (-len(doc) % 4)
    return b"glTF" + struct.pack("<II", 2, 20 + len(doc)) + struct.pack("<I", len(doc)) + b"JSON" + doc


def main():
    with tempfile.TemporaryDirectory(prefix="blender-glb-qa-") as directory:
        valid = Path(directory) / "valid.glb"
        valid.write_bytes(make_valid_glb())
        bad = Path(directory) / "bad.glb"
        bad.write_bytes(b"glTF" + b"X" * 64)
        header_times, validator_times, outcomes = [], [], []
        for _ in range(5):
            start = time.perf_counter_ns()
            header_ok = valid.read_bytes()[:4] == b"glTF"
            header_times.append((time.perf_counter_ns() - start) / 1e6)
            start = time.perf_counter_ns()
            result = validate_export(str(valid))
            validator_times.append((time.perf_counter_ns() - start) / 1e6)
            outcomes.append(result["valid"])
        result = {
            "metric": "invalid_glb_detection_rate",
            "direction": "higher",
            "baseline": float(bad.read_bytes()[:4] != b"glTF"),
            "candidate": float(validate_export(str(bad))["valid"] is False),
            "samples": len(outcomes),
            "header_only_p50_ms": round(statistics.median(header_times), 3),
            "khronos_p50_ms": round(statistics.median(validator_times), 3),
            "true_positive": all(outcomes) and header_ok,
            "header_only_false_positive": bad.read_bytes()[:4] == b"glTF",
            "khronos_true_negative": validate_export(str(bad))["valid"] is False,
        }
        print(json.dumps(result, sort_keys=True))
        assert result["true_positive"] and result["header_only_false_positive"] and result["khronos_true_negative"]


if __name__ == "__main__":
    main()
