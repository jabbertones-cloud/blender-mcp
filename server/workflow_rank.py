"""Lexical workflow ranking. No MCP import."""
from __future__ import annotations

from typing import List

try:
    from server.capability_executor import WORKFLOW_DESCRIPTIONS
except ModuleNotFoundError:
    from capability_executor import WORKFLOW_DESCRIPTIONS

_RULES = (
    (
        "workflow.amazon_packshot",
        160.0,
        ["complete Amazon packshot intent"],
        lambda t: "amazon" in t or "a+ content" in t or "main listing image" in t,
        True,
    ),
    (
        "workflow.image_to_asset",
        155.0,
        ["complete image-to-asset intent"],
        lambda t: any(x in t for x in ("image to 3d", "image to asset", "photo to mesh", "reconstruct from image")),
        False,
    ),
    (
        "workflow.image_to_scene",
        154.0,
        ["complete image-to-scene intent"],
        lambda t: any(x in t for x in ("image to scene", "scene from photo", "recreate the photo")),
        False,
    ),
    (
        "workflow.character_from_image",
        153.0,
        ["complete character-from-image intent"],
        lambda t: any(x in t for x in ("character from image", "rig from photo", "mixamo from image")),
        False,
    ),
    (
        "workflow.motion_from_video",
        152.0,
        ["complete motion-from-video intent"],
        lambda t: any(x in t for x in ("motion from video", "mocap from video", "matchmove")),
        False,
    ),
    (
        "workflow.reference_score",
        151.0,
        ["complete reference score intent"],
        lambda t: any(x in t for x in ("reference score", "score against reference", "psnr", "compare to reference")),
        False,
    ),
    (
        "workflow.reference_score_sequence",
        151.0,
        ["complete sequence score intent"],
        lambda t: any(x in t for x in ("score sequence", "score frames", "temporal score")),
        False,
    ),
    (
        "workflow.match_reference_lighting",
        151.0,
        ["complete lighting-match intent"],
        lambda t: any(x in t for x in ("match lighting", "match the hdr", "reference lighting")),
        False,
    ),
    (
        "workflow.product_hero",
        150.0,
        ["complete multi-step product-hero intent"],
        lambda t: any(
            x in t
            for x in ("product hero", "hero product", "hero shot", "packshot", "product photography", "product image")
        ),
        False,
    ),
    (
        "workflow.turntable",
        145.0,
        ["complete product turntable intent"],
        lambda t: any(x in t for x in ("turntable", "360 spin", "360 product")),
        False,
    ),
    (
        "workflow.forensic_recon",
        140.0,
        ["complete forensic reconstruction intent"],
        lambda t: any(x in t for x in ("forensic", "accident reconstruction", "courtroom")),
        False,
    ),
    (
        "workflow.viewport_multiview",
        138.0,
        ["complete multiview capture intent"],
        lambda t: any(x in t for x in ("multiview", "multi view", "front right top iso")),
        False,
    ),
    (
        "workflow.reference_camera_solve",
        137.0,
        ["complete camera-solve intent"],
        lambda t: any(x in t for x in ("solve camera", "camera solve", "libmv")),
        False,
    ),
    (
        "workflow.motion_qa",
        136.0,
        ["complete motion qa intent"],
        lambda t: any(x in t for x in ("foot skate", "motion qa", "bone pops")),
        False,
    ),
)


def workflow_match(query: str) -> List[dict]:
    text = " ".join((query or "").lower().split())
    matches: List[dict] = []
    for key, score, reason, pred, insert_front in _RULES:
        if key not in WORKFLOW_DESCRIPTIONS:
            continue
        if not pred(text):
            continue
        row = {
            "key": key,
            "family": "workflow",
            "description": WORKFLOW_DESCRIPTIONS[key],
            "score": score,
            "reason": reason,
        }
        if insert_front:
            matches.insert(0, row)
        else:
            matches.append(row)
    return matches
