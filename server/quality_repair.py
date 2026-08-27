"""Deterministic objective-quality repair policy.

Only objective error findings are repairable here. Semantic/aesthetic review
findings are deliberately never converted into automatic mutations.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

DEFAULT_MAX_REPAIRS = 3


@dataclass(frozen=True)
class RepairAction:
    finding_code: str
    capability: str | None
    arguments: dict
    repairable: bool
    reason: str


def repair_budget() -> int:
    raw = os.getenv("OPENCLAW_QUALITY_REPAIR_MAX", str(DEFAULT_MAX_REPAIRS)).strip()
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_MAX_REPAIRS
    return max(0, min(value, 10))


def repair_for_finding(finding: dict[str, Any], *, workflow: str, target_object: str) -> RepairAction:
    code = str(finding.get("code") or "")
    severity = str(finding.get("severity") or "")
    if severity == "review":
        return RepairAction(code, None, {}, False, "semantic/aesthetic review requires client-visible pixels")
    if code == "NO_CAMERA":
        style = "turntable" if workflow == "workflow.turntable" else "hero_reveal"
        return RepairAction(code, "product.camera", {"style": style, "target_object": target_object}, True, "create workflow-appropriate product camera")
    if code == "NO_LIGHTS":
        return RepairAction(code, "product.lighting", {"preset": "product_studio", "shadow_catcher": True}, True, "create deterministic studio lighting")
    if code == "NO_PIXELS":
        return RepairAction(code, "scene.viewport_capture", {"base64": True}, True, "recapture model-visible pixels")
    if code == "TARGET_MISSING":
        return RepairAction(code, None, {}, False, "target identity cannot be safely invented")
    return RepairAction(code, None, {}, False, "no deterministic repair policy")


def next_objective_repair(review: dict[str, Any], *, workflow: str, target_object: str) -> RepairAction | None:
    """Return at most one repair for the current critique iteration."""
    for finding in review.get("findings") or []:
        if not isinstance(finding, dict) or finding.get("severity") != "error":
            continue
        action = repair_for_finding(finding, workflow=workflow, target_object=target_object)
        if action.repairable:
            return action
        # An objective error with no safe repair is fail-closed; do not skip past
        # it and mutate some other aspect of the scene.
        return action
    return None
