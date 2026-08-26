"""Bounded detect -> repair -> recapture -> verify controller.

This controller is MCP-independent and delegates every mutation to the existing
canonical executor supplied by capability_executor. It never auto-repairs
semantic/aesthetic review findings.
"""
from __future__ import annotations

from typing import Callable

try:
    from server.quality_repair import next_objective_repair, repair_budget
except ModuleNotFoundError:
    from quality_repair import next_objective_repair, repair_budget


def run_quality_loop(
    *,
    workflow: str,
    target_object: str,
    review_once: Callable[[], dict],
    execute_canonical: Callable[[str, dict], dict],
    max_repairs: int | None = None,
) -> dict:
    budget = repair_budget() if max_repairs is None else max(0, int(max_repairs))
    attempts: list[dict] = []
    review = review_once()

    for iteration in range(budget + 1):
        if review.get("status") != "fail":
            return {**review, "repair_attempts": attempts, "repair_count": len(attempts), "repair_budget": budget}
        if iteration >= budget:
            break
        action = next_objective_repair(review, workflow=workflow, target_object=target_object)
        if action is None:
            break
        if not action.repairable or not action.capability:
            attempts.append({"iteration": iteration + 1, "finding_code": action.finding_code, "status": "not_repairable", "reason": action.reason})
            break
        if action.capability == "scene.viewport_capture":
            # NO_PIXELS is an observation retry, not a scene mutation. review_once
            # performs the fresh base64 capture immediately below.
            outcome = {"status": "ok", "observation_retry": True}
        else:
            outcome = execute_canonical(action.capability, action.arguments)
        attempt = {"iteration": iteration + 1, "finding_code": action.finding_code, "capability": action.capability, "arguments": action.arguments, "outcome_status": outcome.get("status") if isinstance(outcome, dict) else None}
        attempts.append(attempt)
        if not isinstance(outcome, dict) or outcome.get("status") not in {"ok", "review_required", "pass"}:
            attempt["status"] = "repair_failed"
            break
        attempt["status"] = "executed"
        # Mandatory recapture/re-diagnosis after exactly one repair.
        review = review_once()

    return {**review, "repair_attempts": attempts, "repair_count": len(attempts), "repair_budget": budget}
