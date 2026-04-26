"""
Planner-Actor-Critic Agent Loop for OpenClaw Blender MCP
=========================================================
Goal-first routing, multi-step planning, action execution, and verification loop.

Reference: Planner-Actor-Critic agent (arXiv 2601.05016) — maintains goal,
plans steps, executes actions, critiques outcomes, and updates state iteratively.

Install: Standard library + session_state, verify (local project imports).
Usage:
  from agent_loop import register_agent_loop_tools
  tool_names = register_agent_loop_tools(mcp, send_command, format_result)
"""

import json
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass
from pydantic import BaseModel

from session_state import default_store, SessionState, PlanStep, PlanStepStatus
from verify import verify_action, run_gcs


# ─── needs_input helper (mirrors blender_mcp_server.needs_input_payload) ─────
# Local copy so agent_loop stays import-light and doesn't pull the full server
# module when used in isolation. The shape is intentionally identical.

def _needs_input(
    field: str,
    *,
    kind: str,
    description: str,
    default: Any = None,
    choices: Optional[List[Any]] = None,
    hint: Optional[str] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"field": field, "kind": kind, "description": description}
    if default is not None:
        payload["default"] = default
    if choices is not None:
        payload["choices"] = list(choices)
        payload["kind"] = "enum"
    if hint is not None:
        payload["hint"] = hint
    return {"status": "needs_input", "needs_input": payload}


# ============================================================================
# Tool Input Models
# ============================================================================

class SetGoalInput(BaseModel):
    """Input for blender_router_set_goal."""
    goal: str
    profile: str = "default"


class PlanInput(BaseModel):
    """Input for blender_plan."""
    goal: Optional[str] = None
    max_steps: int = 5
    context: Optional[str] = None
    custom_steps: Optional[List[str]] = None


class ActInput(BaseModel):
    """Input for blender_act."""
    step_id: str
    tool_name: str
    tool_args: Dict[str, Any] = {}
    dry_run: bool = False


class CritiqueInput(BaseModel):
    """Input for blender_critique."""
    step_id: str
    expected: str
    constraints: Optional[List[Dict[str, Any]]] = None


class VerifyInput(BaseModel):
    """Input for blender_verify."""
    expected: str
    constraints: Optional[List[Dict[str, Any]]] = None
    use_vlm: bool = True


# ============================================================================
# Tool Implementations
# ============================================================================

async def blender_router_set_goal(
    session_state: SessionState,
    send_command: Callable,
    format_result: Callable,
    input_data: SetGoalInput
) -> Dict[str, Any]:
    """
    Set goal and routing profile for the session.

    Profiles:
    - default: balanced, general-purpose planning
    - llm-guided: use natural language planning with VLM verification
    - power-user: minimal constraints, assume advanced user
    - forensic: strict verification, maximal checkpoints
    """
    goal = input_data.goal
    profile = input_data.profile

    # ─── needs_input: empty/whitespace goal ────────────────────────────────
    if not goal or not str(goal).strip():
        return format_result(_needs_input(
            field="goal",
            kind="string",
            description=(
                "blender_router_set_goal needs a non-empty goal. State the high-level "
                "intent for this session in one sentence (e.g. 'Build a forensic accident "
                "reconstruction with two vehicles and a verified collision angle')."
            ),
            hint="Re-call blender_router_set_goal with goal=<your goal>.",
        ))

    # ─── needs_input: invalid profile ──────────────────────────────────────
    valid_profiles = ["default", "llm-guided", "power-user", "forensic"]
    if profile not in valid_profiles:
        return format_result(_needs_input(
            field="profile",
            kind="enum",
            description=(
                f"profile {profile!r} is not one of the supported routing profiles. "
                f"Pick one — 'default' is balanced, 'llm-guided' uses VLM, "
                f"'power-user' is minimal, 'forensic' is strict."
            ),
            default="default",
            choices=valid_profiles,
            hint="Re-call blender_router_set_goal with profile= one of the listed choices.",
        ))

    session_state.goal = goal
    session_state.profile = profile
    session_state.conversation_turn += 1
    session_state.todo = []
    session_state.completed = []

    return format_result({
        "status": "success",
        "data": {
            "goal": goal,
            "profile": profile,
            "session_id": session_state.session_id,
            "conversation_turn": session_state.conversation_turn
        }
    })


async def blender_plan(
    session_state: SessionState,
    send_command: Callable,
    format_result: Callable,
    input_data: PlanInput
) -> Dict[str, Any]:
    """
    Generate a plan (todo list) for the current goal using template rules.

    Returns a structured plan with step_id, description, and tool_hint.
    """
    goal = input_data.goal or session_state.goal
    max_steps = input_data.max_steps
    custom_steps = input_data.custom_steps or []

    if not goal:
        return format_result(_needs_input(
            field="goal",
            kind="string",
            description=(
                "blender_plan needs a goal. Either pass goal=<...> directly, or call "
                "blender_router_set_goal(goal=<...>) first to anchor the session."
            ),
            hint="Call blender_router_set_goal first, or pass goal= explicitly to blender_plan.",
        ))

    # Simple rule-based planner
    profile_rules = {
        "default": [
            "Analyze scene and objects",
            "Plan spatial arrangement",
            "Execute main task",
            "Verify constraints",
        ],
        "llm-guided": [
            "Understand natural language goal",
            "Generate creative steps",
            "Execute and verify with VLM",
        ],
        "power-user": [
            "Execute optimized steps",
        ],
        "forensic": [
            "Snapshot initial state",
            "Plan with detailed checkpoints",
            "Execute with verification at each step",
            "Final comprehensive verification",
        ]
    }

    profile = session_state.profile
    base_steps = profile_rules.get(profile, profile_rules["default"])
    all_steps = base_steps + custom_steps
    limited_steps = all_steps[:max_steps]

    # Create PlanStep objects
    todo = []
    for i, desc in enumerate(limited_steps):
        step = PlanStep(
            step_id=f"step_{i+1}",
            description=desc,
            tool_hint=None,
            status=PlanStepStatus.pending
        )
        todo.append(step)

    session_state.todo = todo
    session_state.completed = []

    return format_result({
        "status": "success",
        "data": {
            "goal": goal,
            "profile": profile,
            "plan": [
                {
                    "step_id": s.step_id,
                    "description": s.description,
                    "status": s.status.value
                }
                for s in todo
            ],
            "step_count": len(todo)
        }
    })


async def blender_act(
    session_state: SessionState,
    send_command: Callable,
    format_result: Callable,
    input_data: ActInput
) -> Dict[str, Any]:
    """
    Execute a specific step by calling a Blender tool.

    Marks step as in_progress, executes tool, then marks done/failed.
    """
    step_id = input_data.step_id
    tool_name = input_data.tool_name
    tool_args = input_data.tool_args
    dry_run = input_data.dry_run

    # Find step in todo
    step = None
    for s in session_state.todo:
        if s.step_id == step_id:
            step = s
            break

    if not step:
        return format_result({
            "status": "error",
            "data": {"error": f"Step {step_id} not found in todo"}
        })

    step.status = PlanStepStatus.in_progress

    if dry_run:
        return format_result({
            "status": "success",
            "data": {
                "step_id": step_id,
                "tool_name": tool_name,
                "dry_run": True,
                "message": "Dry run completed (no action taken)"
            }
        })

    # Execute tool
    try:
        result = send_command(tool_name, tool_args)
        step.result = result.get("data", {})
        step.status = PlanStepStatus.done

        # Move to completed
        session_state.todo.remove(step)
        session_state.completed.append(step)

        return format_result({
            "status": "success",
            "data": {
                "step_id": step_id,
                "tool_name": tool_name,
                "result": step.result,
                "status": "done"
            }
        })

    except Exception as e:
        step.status = PlanStepStatus.failed
        step.result = {"error": str(e)}

        return format_result({
            "status": "error",
            "data": {
                "step_id": step_id,
                "tool_name": tool_name,
                "error": str(e),
                "status": "failed"
            }
        })


async def blender_critique(
    session_state: SessionState,
    send_command: Callable,
    format_result: Callable,
    input_data: CritiqueInput
) -> Dict[str, Any]:
    """
    Verify a completed step against expected outcome and constraints.

    Stores critique in critique_history. If failed, suggests correction steps.
    """
    step_id = input_data.step_id
    expected = input_data.expected
    constraints = input_data.constraints or []

    # Find step
    step = None
    for s in session_state.completed:
        if s.step_id == step_id:
            step = s
            break

    if not step:
        return format_result({
            "status": "error",
            "data": {"error": f"Step {step_id} not found in completed"}
        })

    # Run verification
    verification = verify_action(
        send_command,
        expected=expected,
        constraints=constraints,
        use_vlm=True
    )

    critique_entry = {
        "step_id": step_id,
        "expected": expected,
        "verification": verification,
        "passed": verification["passed"],
        "confidence": verification["final_confidence"]
    }

    session_state.critique_history.append(critique_entry)

    result_data = {
        "step_id": step_id,
        "passed": verification["passed"],
        "confidence": verification["final_confidence"],
        "detail": verification["detail"]
    }

    # Suggest fixes if verification failed
    if not verification["passed"] and verification["final_confidence"] < 0.5:
        fix_steps = [
            PlanStep(
                step_id=f"{step_id}_fix_1",
                description="Analyze failure and adjust approach",
                tool_hint="Use get_scene_state to diagnose issue"
            ),
            PlanStep(
                step_id=f"{step_id}_fix_2",
                description="Re-execute corrected action",
                tool_hint=None
            )
        ]
        session_state.todo.extend(fix_steps)
        result_data["suggested_fixes"] = [
            {"step_id": s.step_id, "description": s.description}
            for s in fix_steps
        ]

    return format_result({
        "status": "success",
        "data": result_data
    })


async def blender_verify(
    session_state: SessionState,
    send_command: Callable,
    format_result: Callable,
    input_data: VerifyInput
) -> Dict[str, Any]:
    """
    Thin wrapper around verify_action for on-demand verification.
    """
    expected = input_data.expected
    constraints = input_data.constraints or []
    use_vlm = input_data.use_vlm

    result = verify_action(
        send_command,
        expected=expected,
        constraints=constraints,
        use_vlm=use_vlm
    )

    return format_result({
        "status": "success",
        "data": {
            "passed": result["passed"],
            "confidence": result["final_confidence"],
            "detail": result["detail"],
            "gcs_score": result["gcs_result"].get("score") if result["gcs_result"] else None,
            "vlm_confidence": result["vlm_result"].get("confidence") if result["vlm_result"] else None
        }
    })


async def blender_session_status(
    session_state: SessionState,
    send_command: Callable,
    format_result: Callable
) -> Dict[str, Any]:
    """
    Return current session state and progress summary.
    """
    todo_count = len(session_state.todo)
    completed_count = len(session_state.completed)
    total_steps = todo_count + completed_count

    # Calculate drift score (critique failures)
    failed_critiques = sum(
        1 for c in session_state.critique_history if not c.get("passed", False)
    )
    drift_score = failed_critiques / max(len(session_state.critique_history), 1)

    return format_result({
        "status": "success",
        "data": {
            "session_id": session_state.session_id,
            "goal": session_state.goal,
            "profile": session_state.profile,
            "conversation_turn": session_state.conversation_turn,
            "todo_count": todo_count,
            "completed_count": completed_count,
            "total_steps": total_steps,
            "progress_pct": int((completed_count / max(total_steps, 1)) * 100),
            "drift_score": drift_score,
            "critique_count": len(session_state.critique_history),
            "snapshot_count": len(session_state.snapshots)
        }
    })


# ============================================================================
# Registration
# ============================================================================

def register_agent_loop_tools(
    mcp_instance,
    send_command: Callable,
    format_result: Callable,
    session_store=None,
    drift_registry=None
) -> List[str]:
    """
    Register all agent loop tools with FastMCP instance.

    Args:
        mcp_instance: FastMCP server instance
        send_command: Blender command sender (socket)
        format_result: Response formatter
        session_store: Optional SessionStore override
        drift_registry: Optional drift tracking (unused, forward-compat)

    Returns:
        List of registered tool names: [
            'blender_router_set_goal',
            'blender_plan',
            'blender_act',
            'blender_critique',
            'blender_verify',
            'blender_session_status'
        ]
    """
    store = session_store or default_store()

    @mcp_instance.tool()
    async def blender_router_set_goal(input: SetGoalInput) -> Dict[str, Any]:
        """Set goal and routing profile for the session."""
        session = store.get_or_create("default")
        return await globals()["blender_router_set_goal"](
            session, send_command, format_result, input
        )

    @mcp_instance.tool()
    async def blender_plan(input: PlanInput) -> Dict[str, Any]:
        """Generate a plan (todo list) for the current goal."""
        session = store.get_or_create("default")
        return await globals()["blender_plan"](
            session, send_command, format_result, input
        )

    @mcp_instance.tool()
    async def blender_act(input: ActInput) -> Dict[str, Any]:
        """Execute a specific step by calling a Blender tool."""
        session = store.get_or_create("default")
        return await globals()["blender_act"](
            session, send_command, format_result, input
        )

    @mcp_instance.tool()
    async def blender_critique(input: CritiqueInput) -> Dict[str, Any]:
        """Verify a completed step against expected outcome and constraints."""
        session = store.get_or_create("default")
        return await globals()["blender_critique"](
            session, send_command, format_result, input
        )

    @mcp_instance.tool()
    async def blender_verify(input: VerifyInput) -> Dict[str, Any]:
        """On-demand verification of action outcome."""
        session = store.get_or_create("default")
        return await globals()["blender_verify"](
            session, send_command, format_result, input
        )

    @mcp_instance.tool()
    async def blender_session_status() -> Dict[str, Any]:
        """Return current session state and progress summary."""
        session = store.get_or_create("default")
        return await globals()["blender_session_status"](
            session, send_command, format_result
        )

    return [
        "blender_router_set_goal",
        "blender_plan",
        "blender_act",
        "blender_critique",
        "blender_verify",
        "blender_session_status"
    ]
