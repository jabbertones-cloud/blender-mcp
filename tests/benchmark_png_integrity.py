"""Reproducible PNG integrity negative-control comparison."""
import json
import tempfile
from pathlib import Path

from PIL import Image

from server.render_artifact import valid_png


def main():
    with tempfile.TemporaryDirectory(prefix="blender-png-benchmark-") as directory:
        root = Path(directory)
        valid = root / "valid.png"
        Image.new("RGBA", (32, 32), (30, 40, 60, 255)).save(valid)
        original = valid.read_bytes()
        inputs = {
            "signature_only": b"\x89PNG\r\n\x1a\nINVALID",
            "truncated": original[:len(original) // 2],
            "bad_crc": original[:18] + bytes([original[18] ^ 255]) + original[19:],
        }
        baseline = sum(data.startswith(b"\x89PNG\r\n\x1a\n") for data in inputs.values())
        decoded = 0
        for name, data in inputs.items():
            path = root / (name + ".png")
            path.write_bytes(data)
            decoded += int(valid_png(path))
        passed = valid_png(valid)
    result = {"invalid_cases": len(inputs), "legacy_false_accepts": baseline,
              "decoded_false_accepts": decoded, "valid_png_accepted": passed}
    print(json.dumps(result, sort_keys=True))
    assert baseline == 3 and decoded == 0 and passed


if __name__ == "__main__":
    main()
