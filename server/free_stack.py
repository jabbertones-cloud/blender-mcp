"""Free recreate-from-reference asset sources. No paid generation APIs."""
from __future__ import annotations

import os
import re
from typing import Iterable, List, Tuple

_STOP = {
    "a", "an", "the", "to", "from", "of", "and", "or", "for", "with",
    "photo", "image", "picture", "reconstruct", "subject", "reference",
    "mesh", "asset", "scene", "3d", "model", "generate", "create",
}

_PRODUCT_TERMS = ("bottle", "can", "jar", "box", "chair")
_CHARACTER_TERMS = ("statue", "armor", "bust", "sword")
_INTERIOR_TERMS = ("chair", "table", "sofa", "bed", "lamp")
_VEHICLE_TERMS = ("car", "bike", "boat")

_INTENT_ALIASES: Tuple[Tuple[Tuple[str, ...], Tuple[str, ...]], ...] = (
    (("character", "person", "human", "people", "rig", "mixamo", "body"), _CHARACTER_TERMS),
    (("bottle", "product", "cosmetic", "packshot", "can", "jar"), _PRODUCT_TERMS),
    (("room", "interior", "furniture", "chair", "table", "sofa"), _INTERIOR_TERMS),
    (("car", "vehicle", "truck", "bike"), _VEHICLE_TERMS),
)

_HDRI_ALIASES: Tuple[Tuple[Tuple[str, ...], str], ...] = (
    (("studio", "product", "packshot", "cosmetic", "bottle"), "studio"),
    (("outdoor", "street", "park", "sky"), "outdoor"),
    (("indoor", "room", "interior", "kitchen"), "indoor"),
    (("night", "dark"), "night"),
)


def _tokens(text: str) -> List[str]:
    return [t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if t not in _STOP and len(t) > 1]


def polyhaven_search_terms(prompt: str, *, character: bool = False) -> List[str]:
    tokens = _tokens(prompt)
    ordered: List[str] = []
    seen = set()

    def add(term: str) -> None:
        term = term.strip().lower()
        if not term or term in seen:
            return
        seen.add(term)
        ordered.append(term)

    for token in tokens:
        add(token)
    blob = " ".join(tokens)
    for keys, terms in _INTENT_ALIASES:
        if any(k in blob or k in tokens for k in keys):
            for term in terms:
                add(term)
    if character or any(k in blob for k in ("character", "person", "human", "rig")):
        for term in _CHARACTER_TERMS:
            add(term)
    else:
        for term in _PRODUCT_TERMS:
            add(term)
        for term in _INTERIOR_TERMS:
            add(term)
    return ordered


def hdri_search_terms(prompt: str) -> List[str]:
    tokens = _tokens(prompt)
    blob = " ".join(tokens)
    ordered: List[str] = []
    seen = set()

    def add(term: str) -> None:
        if term and term not in seen:
            seen.add(term)
            ordered.append(term)

    for keys, term in _HDRI_ALIASES:
        if any(k in blob or k in tokens for k in keys):
            add(term)
    for token in tokens:
        add(token)
    add("studio")
    return ordered


def mixamo_fbx_path(args: dict | None = None) -> str:
    args = args or {}
    return str(args.get("mixamo_fbx") or os.getenv("MIXAMO_FBX_PATH") or "").strip()


def sketchfab_enabled() -> bool:
    return bool(os.getenv("SKETCHFAB_API_TOKEN", "").strip())


def source_order() -> Tuple[str, ...]:
    return (
        "local_filepath",
        "IMAGE_TO_3D_WORKER_URL",
        "polyhaven_cc0_models",
        "sketchfab_downloadable",
        "mixamo_local_fbx",
    )


def fail_hints() -> dict:
    return {
        "next": [
            "Pass filepath to a local glTF/FBX/OBJ.",
            "Set IMAGE_TO_3D_WORKER_URL to a self-hosted TRELLIS.2 or TripoSR (MIT) worker that POSTs {image_url} → {filepath}.",
            "Retry with keyword matching a Poly Haven model (bottle, chair, table, statue).",
            "Optional free Sketchfab downloadable search if SKETCHFAB_API_TOKEN is set (no paid generation).",
            "For walk cycles: Mixamo.com manual FBX + MIXAMO_FBX_PATH or mixamo_fbx.",
        ],
        "order": list(source_order()),
    }


def unique_terms(terms: Iterable[str]) -> List[str]:
    seen = set()
    out = []
    for term in terms:
        t = str(term or "").strip().lower()
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out
