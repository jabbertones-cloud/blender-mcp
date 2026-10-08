"""Read-only outcome guidance for the five-tool guided MCP interface.

Guides are packaged alongside the server and never execute arbitrary file paths.
"""
from __future__ import annotations

from pathlib import Path

_GUIDE_DIR = Path(__file__).resolve().parents[1] / "guides"
_GUIDES = {
    "modeling": "modeling.md",
    "materials": "materials.md",
    "lighting": "lighting.md",
    "camera": "camera.md",
    "render": "render.md",
    "animation": "animation.md",
    "rigging": "rigging.md",
    "retopology": "retopology.md",
    "product-shot": "product-shot.md",
}
_KEYWORDS = {
    "modeling": ("model", "mesh", "sculpt", "object", "geometry"),
    "materials": ("material", "shader", "texture", "pbr", "uv"),
    "lighting": ("light", "softbox", "hdri", "exposure"),
    "camera": ("camera", "frame", "lens", "composition"),
    "render": ("render", "output", "image", "png", "quality"),
    "animation": ("animate", "motion", "turntable", "keyframe"),
    "rigging": ("rig", "bone", "skin", "deform", "weight"),
    "retopology": ("retopo", "topology", "edge flow"),
    "product-shot": ("product shot", "packshot", "hero product", "product photo"),
}


def list_workflow_guides(query: str = "") -> list[dict[str, str]]:
    q = query.strip().lower()
    matches = []
    for key, filename in _GUIDES.items():
        if not q or q in key or any(term in q for term in _KEYWORDS[key]):
            matches.append({"key": key, "path": f"guides/{filename}"})
    return matches


def get_workflow_guide(key: str) -> dict[str, str]:
    if key not in _GUIDES:
        return {"error": f"Unknown guide: {key}", "code": "GUIDE_NOT_FOUND"}
    path = _GUIDE_DIR / _GUIDES[key]
    try:
        return {"key": key, "content": path.read_text(encoding="utf-8")}
    except OSError:
        return {"error": f"Guide unavailable: {key}", "code": "GUIDE_UNAVAILABLE"}
