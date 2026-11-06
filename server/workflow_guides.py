"""Read-only outcome guidance for the five-tool guided MCP interface.

Guides are packaged alongside the server and never execute arbitrary file paths.
"""
from __future__ import annotations

from pathlib import Path

_GUIDE_DIR = Path(__file__).resolve().parents[1] / "guides"
_GUIDES = {name: f"{name}.md" for name in (
    "modeling", "materials", "lighting", "camera", "render", "animation",
    "rigging", "retopology", "product-shot", "inspection", "assets",
    "file-io", "nodes", "physics", "spatial", "reconstruction", "forensic", "workflow",
)}
_KEYWORDS = {
    "modeling": ("model", "mesh", "sculpt", "object", "geometry"),
    "materials": ("material", "shader", "texture", "pbr", "uv"),
    "lighting": ("light", "softbox", "hdri", "exposure"),
    "camera": ("camera", "frame", "lens", "composition"),
    "render": ("render", "output", "image", "png", "quality"),
    "animation": ("animate", "motion", "turntable", "keyframe"),
    "rigging": ("rig", "bone", "skin", "deform", "weight"),
    "retopology": ("retopo", "topology", "edge flow"),
    "product-shot": ("product shot", "packshot", "hero product", "product hero", "product photo", "ecommerce image"),
    "inspection": ("inspect", "diagnose", "scene info", "what is", "list object", "multiview"),
    "assets": ("asset", "polyhaven", "sketchfab", "search model", "import library"),
    "file-io": ("import", "export", "save", "gltf", "fbx", "blend file"),
    "nodes": ("geometry nodes", "procedural node", "node group", "compositor graph"),
    "physics": ("physics", "rigid body", "cloth", "fluid", "particles", "force field"),
    "spatial": ("distance", "collision", "clearance", "floor plan", "place object"),
    "reconstruction": ("reference", "reconstruct", "photo to", "image to", "score", "correct"),
    "forensic": ("forensic", "accident", "courtroom", "evidence"),
    "workflow": ("workflow sequence", "batch operations", "rollback", "steps", "compose"),
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


# Stage-appropriate guidance is surfaced during schema inspection, not left
# dependent on whether an MCP client happens to browse resources.
_FAMILY_GUIDES = {
    "create": "modeling", "mutate": "modeling", "material": "materials",
    "lighting": "lighting", "camera": "camera", "render": "render",
    "animation": "animation", "rigging": "rigging", "product": "product-shot",
    "uv": "materials", "physics": "physics", "inspect": "inspection",
    "discover": "inspection", "io": "file-io", "assets": "assets",
    "spatial": "spatial", "procedural": "nodes", "world": "lighting",
    "forensic": "forensic", "generation": "reconstruction",
}
_WORKFLOW_GUIDES = {
    "workflow.product_hero": "product-shot", "workflow.amazon_packshot": "product-shot",
    "workflow.turntable": "animation", "workflow.forensic_recon": "forensic",
    "workflow.reference_attach": "reconstruction", "workflow.reference_score": "reconstruction",
    "workflow.reference_score_sequence": "reconstruction", "workflow.reference_correct": "reconstruction",
    "workflow.reference_camera_solve": "reconstruction", "workflow.image_to_asset": "reconstruction",
    "workflow.character_from_image": "reconstruction", "workflow.match_reference_lighting": "reconstruction",
    "workflow.motion_from_video": "animation", "workflow.motion_qa": "animation",
    "workflow.image_to_scene": "reconstruction", "workflow.viewport_multiview": "inspection",
    "workflow.sequence": "workflow",
}


def guide_for_capability(key: str, family: str) -> dict | None:
    name = _WORKFLOW_GUIDES.get(key) or _FAMILY_GUIDES.get(family)
    return get_workflow_guide(name) if name else None
