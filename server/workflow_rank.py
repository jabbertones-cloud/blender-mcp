"""Lexical workflow ranking. No MCP import."""
from __future__ import annotations

from typing import List

try:
    from server.capability_executor import WORKFLOW_DESCRIPTIONS
except ModuleNotFoundError:
    from capability_executor import WORKFLOW_DESCRIPTIONS

def _render_status_query(text: str) -> bool:
    return ("render" in text and any(x in text for x in ("status", "progress", "job id", "job state", "finished"))) or ("check" in text and "render job" in text)


def _render_enqueue_query(text: str) -> bool:
    return not _render_status_query(text) and (
        any(x in text for x in ("background render", "background blender render", "queue render", "queue a render", "async render", "asynchronous render"))
        or ("render" in text and "in the background" in text)
    )


_RULES = (
    ("workflow.render_enqueue", 165.0, ["queue saved scene background Blender render"], _render_enqueue_query, False),
    ("workflow.render_status", 164.0, ["check background Blender render job status"], _render_status_query, False),
    ("workflow.quality_inspect", 159.0, ["inspect saved Blender scene with objective quality gates"],
     lambda t: any(x in t for x in ("inspect quality", "quality audit", "audit scene quality", "check scene quality", "validate scene quality")), False),
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
    (
        "workflow.reference_attach", 135.0,
        ["register the reference before scoring or reconstruction"],
        lambda t: any(x in t for x in ("attach reference", "register reference", "load reference plate", "reference image as plate")),
        False,
    ),
    (
        "workflow.reference_correct", 134.0,
        ["recommend typed correction after reference scoring"],
        lambda t: any(x in t for x in ("reference correction", "correct reference match", "fix reference mismatch", "fix deviations from the scored reference")),
        False,
    ),
    (
        "workflow.sequence", 133.0,
        ["execute a prevalidated sequence of canonical Blender operations"],
        lambda t: any(x in t for x in ("workflow sequence", "sequence of canonical", "batch blender operations", "execute a sequence of")),
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
