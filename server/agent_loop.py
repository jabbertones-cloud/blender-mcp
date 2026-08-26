"""Planner-Actor-Critic loop with deterministic capability routing.

The routing layer intentionally decides *which tool family* fits a task before
execution. The client model can still provide scene-specific arguments, but no
longer has to guess among ~80 overlapping Blender tools.
"""

from typing import Optional, List, Dict, Any, Callable
from pydantic import BaseModel, Field

try:
    from server.session_state import default_store, SessionState, PlanStep, PlanStepStatus
    from server.verify import verify_action
    from server.capability_router import recommend, plan_goal
except ModuleNotFoundError:
    from session_state import default_store, SessionState, PlanStep, PlanStepStatus
    from verify import verify_action
    from capability_router import recommend, plan_goal


VALID_PROFILES = {"default", "llm-guided", "power-user", "forensic"}


class SetGoalInput(BaseModel):
    goal: str = Field(..., min_length=1)
    profile: str = "default"


class PlanInput(BaseModel):
    goal: Optional[str] = None
    max_steps: int = Field(default=6, ge=1, le=12)
    context: Optional[str] = None
    custom_steps: Optional[List[str]] = None


class ActInput(BaseModel):
    step_id: str
    tool_name: Optional[str] = None
    tool_args: Dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = False


class CritiqueInput(BaseModel):
    step_id: str
    expected: str
    constraints: Optional[List[Dict[str, Any]]] = None


class VerifyInput(BaseModel):
    expected: str
    constraints: Optional[List[Dict[str, Any]]] = None
    use_vlm: bool = True


class RecommendInput(BaseModel):
    task: str
    limit: int = Field(default=5, ge=1, le=10)


def _bridge_command(tool_name: str) -> str:
    """Convert public MCP tool name to Blender bridge command name."""
    return tool_name[len("blender_"):] if tool_name.startswith("blender_") else tool_name


def _find_step(session_state: SessionState, step_id: str, completed: bool = False):
    source = session_state.completed if completed else session_state.todo
    return next((step for step in source if step.step_id == step_id), None)


async def blender_router_set_goal(session_state, send_command, format_result, input_data: SetGoalInput):
    if input_data.profile not in VALID_PROFILES:
        return format_result({"error": f"Invalid profile. Must be one of: {sorted(VALID_PROFILES)}"})

    session_state.goal = input_data.goal.strip()
    session_state.profile = input_data.profile
    session_state.conversation_turn += 1
    session_state.todo = []
    session_state.completed = []
    session_state.critique_history = []

    routing = recommend(session_state.goal)
    return format_result({
        "goal": session_state.goal,
        "profile": session_state.profile,
        "session_id": session_state.session_id,
        "conversation_turn": session_state.conversation_turn,
        "routing_preview": routing,
        "next": "Call blender_plan; it will produce concrete tool_hint values.",
    })


async def blender_plan(session_state, send_command, format_result, input_data: PlanInput):
    goal = (input_data.goal or session_state.goal or "").strip()
    if not goal:
        return format_result({"error": "No goal set. Call blender_router_set_goal first."})

    session_state.goal = goal
    route_steps = plan_goal(goal, max_steps=input_data.max_steps, profile=session_state.profile)

    # Explicit user-supplied custom steps are also routed; they are never left as
    # generic prose unless no safe capability match exists.
    for text in input_data.custom_steps or []:
        if len(route_steps) >= input_data.max_steps:
            break
        rec = recommend(text)
        route_steps.insert(-1 if route_steps and route_steps[-1].get("kind") == "verify" else len(route_steps), {
            "description": text,
            "tool_hint": rec.get("primary", {}).get("tool"),
            "command_hint": rec.get("primary", {}).get("command"),
            "kind": "custom",
        })

    todo: List[PlanStep] = []
    plan_rows = []
    for index, route in enumerate(route_steps[: input_data.max_steps], start=1):
        step = PlanStep(
            step_id=f"step_{index}",
            description=route["description"],
            tool_hint=route.get("tool_hint"),
            status=PlanStepStatus.pending,
        )
        todo.append(step)
        plan_rows.append({
            "step_id": step.step_id,
            "description": step.description,
            "tool_hint": step.tool_hint,
            "command_hint": route.get("command_hint"),
            "kind": route.get("kind"),
            "status": step.status.value,
        })

    session_state.todo = todo
    session_state.completed = []
    return format_result({
        "goal": goal,
        "profile": session_state.profile,
        "plan": plan_rows,
        "step_count": len(plan_rows),
        "routing_rule": "Use each step.tool_hint by default; override only when scene inspection proves it wrong.",
    })


async def blender_act(session_state, send_command, format_result, input_data: ActInput):
    step = _find_step(session_state, input_data.step_id)
    if not step:
        return format_result({"error": f"Step {input_data.step_id} not found in todo"})

    # Tool choice defaults to the router's recommendation. If a caller overrides
    # it, surface that fact in the result so bad routing can be evaluated later.
    chosen_tool = input_data.tool_name or step.tool_hint
    if not chosen_tool:
        return format_result({
            "error": "This step has no safe tool recommendation. Inspect/clarify instead of guessing.",
            "step_id": step.step_id,
            "description": step.description,
        })

    routed_tool = step.tool_hint
    override = bool(input_data.tool_name and routed_tool and input_data.tool_name != routed_tool)
    command = _bridge_command(chosen_tool)

    if chosen_tool == "blender_verify":
        return format_result({
            "error": "Verification is not a Blender bridge mutation. Call blender_verify directly for this plan step.",
            "step_id": step.step_id,
        })

    if input_data.dry_run:
        return format_result({
            "step_id": step.step_id,
            "tool_name": chosen_tool,
            "bridge_command": command,
            "routed_tool": routed_tool,
            "routing_override": override,
            "dry_run": True,
        })

    step.status = PlanStepStatus.in_progress
    try:
        result = send_command(command, input_data.tool_args)
        if isinstance(result, dict) and result.get("error"):
            step.status = PlanStepStatus.failed
            step.result = result
            return format_result({
                "error": result["error"],
                "step_id": step.step_id,
                "tool_name": chosen_tool,
                "bridge_command": command,
                "routed_tool": routed_tool,
                "routing_override": override,
            })

        step.result = result if isinstance(result, dict) else {"result": result}
        step.status = PlanStepStatus.done
        session_state.todo.remove(step)
        session_state.completed.append(step)
        return format_result({
            "step_id": step.step_id,
            "tool_name": chosen_tool,
            "bridge_command": command,
            "routed_tool": routed_tool,
            "routing_override": override,
            "result": step.result,
            "status": "done",
            "next": "Critique after mutations; do not chain more than three unchecked changes.",
        })
    except Exception as exc:
        step.status = PlanStepStatus.failed
        step.result = {"error": str(exc)}
        return format_result({"error": str(exc), "step_id": step.step_id, "tool_name": chosen_tool})


async def blender_critique(session_state, send_command, format_result, input_data: CritiqueInput):
    step = _find_step(session_state, input_data.step_id, completed=True)
    if not step:
        return format_result({"error": f"Step {input_data.step_id} not found in completed"})

    verification = verify_action(
        send_command,
        expected=input_data.expected,
        constraints=input_data.constraints or [],
        use_vlm=True,
    )
    entry = {
        "step_id": step.step_id,
        "expected": input_data.expected,
        "verification": verification,
        "passed": verification["passed"],
        "confidence": verification["final_confidence"],
    }
    session_state.critique_history.append(entry)

    data = {
        "step_id": step.step_id,
        "passed": verification["passed"],
        "confidence": verification["final_confidence"],
        "detail": verification["detail"],
    }
    if not verification["passed"]:
        rec = recommend(f"inspect scene to diagnose why {input_data.expected} failed")
        fix = PlanStep(
            step_id=f"{step.step_id}_fix_1",
            description=f"Diagnose and correct failed outcome: {input_data.expected}",
            tool_hint=rec.get("primary", {}).get("tool", "blender_get_scene_info"),
        )
        session_state.todo.insert(0, fix)
        data["suggested_fix"] = {"step_id": fix.step_id, "tool_hint": fix.tool_hint, "description": fix.description}
    return format_result(data)


async def blender_verify(session_state, send_command, format_result, input_data: VerifyInput):
    result = verify_action(
        send_command,
        expected=input_data.expected,
        constraints=input_data.constraints or [],
        use_vlm=input_data.use_vlm,
    )
    return format_result({
        "passed": result["passed"],
        "confidence": result["final_confidence"],
        "detail": result["detail"],
        "gcs_score": result["gcs_result"].get("score") if result.get("gcs_result") else None,
        "vlm_confidence": result["vlm_result"].get("confidence") if result.get("vlm_result") else None,
    })


async def blender_session_status(session_state, send_command, format_result):
    todo_count = len(session_state.todo)
    completed_count = len(session_state.completed)
    total_steps = todo_count + completed_count
    failed_critiques = sum(1 for c in session_state.critique_history if not c.get("passed", False))
    return format_result({
        "session_id": session_state.session_id,
        "goal": session_state.goal,
        "profile": session_state.profile,
        "conversation_turn": session_state.conversation_turn,
        "todo_count": todo_count,
        "completed_count": completed_count,
        "total_steps": total_steps,
        "progress_pct": int((completed_count / max(total_steps, 1)) * 100),
        "drift_score": failed_critiques / max(len(session_state.critique_history), 1),
        "critique_count": len(session_state.critique_history),
        "snapshot_count": len(session_state.snapshots),
        "next_tool_hint": session_state.todo[0].tool_hint if session_state.todo else None,
    })


def register_agent_loop_tools(mcp_instance, send_command: Callable, format_result: Callable, session_store=None, drift_registry=None) -> List[str]:
    store = session_store or default_store()

    @mcp_instance.tool()
    async def blender_router_set_goal(input: SetGoalInput) -> Dict[str, Any]:
        """Start a Blender task. Stores the goal and previews the best tool family before planning."""
        return await globals()["blender_router_set_goal"](store.get_or_create("default"), send_command, format_result, input)

    @mcp_instance.tool()
    async def blender_recommend_tools(input: RecommendInput) -> Dict[str, Any]:
        """Use BEFORE acting when tool choice is unclear. Ranks the most specific Blender tools, explains matches, and flags ambiguity instead of guessing."""
        return recommend(input.task, limit=input.limit)

    @mcp_instance.tool()
    async def blender_plan(input: PlanInput) -> Dict[str, Any]:
        """Plan the current Blender goal with concrete tool_hint values. Prefer this over manually choosing among low-level tools for multi-step work."""
        return await globals()["blender_plan"](store.get_or_create("default"), send_command, format_result, input)

    @mcp_instance.tool()
    async def blender_act(input: ActInput) -> Dict[str, Any]:
        """Execute one planned step. Omit tool_name to use the planner's recommended tool; overriding it is recorded for evaluation."""
        return await globals()["blender_act"](store.get_or_create("default"), send_command, format_result, input)

    @mcp_instance.tool()
    async def blender_critique(input: CritiqueInput) -> Dict[str, Any]:
        """Check a completed mutation before chaining further scene changes."""
        return await globals()["blender_critique"](store.get_or_create("default"), send_command, format_result, input)

    @mcp_instance.tool()
    async def blender_verify(input: VerifyInput) -> Dict[str, Any]:
        """Verify the final scene against visual and geometric constraints."""
        return await globals()["blender_verify"](store.get_or_create("default"), send_command, format_result, input)

    @mcp_instance.tool()
    async def blender_session_status() -> Dict[str, Any]:
        """Inspect current goal, progress, critique state, and next routed tool."""
        return await globals()["blender_session_status"](store.get_or_create("default"), send_command, format_result)

    return [
        "blender_router_set_goal",
        "blender_recommend_tools",
        "blender_plan",
        "blender_act",
        "blender_critique",
        "blender_verify",
        "blender_session_status",
    ]
