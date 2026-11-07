"""Decode the entire Blender PNG before replay, publication, or status success."""
from pathlib import Path

from PIL import Image


def valid_png(path: Path) -> bool:
    try:
        with Image.open(path) as image:
            if image.format != "PNG" or min(image.size) < 1:
                return False
            image.verify()
        with Image.open(path) as image:
            image.load()
        return True
    except (OSError, ValueError, SyntaxError):
        return False
