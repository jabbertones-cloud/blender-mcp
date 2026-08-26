"""Planner-Actor-Critic loop backed by the canonical capability registry."""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

try:
    from server.session_state import default_store, PlanStep, PlanStepStatus
    from server.verify import verify_action
    from server.capability_registry import registry, CapabilityNotFound
except ModuleNotFoundError:
    from session_state import default_store, PlanStep, PlanStepStatus
    from verify import verify_action
    from capability_registry import registry, CapabilityNotFound

VALID_PROFILES = {"default", "llm-guided", "power-user", "forensic"}


class SetGoalInput(BaseModel):
    goal: str = Field(..., min_length=1)
    profile: str = "default"


class PlanInput(BaseModel):
    goal: Optional[str] = None
    max_steps: int = Field(default=8, ge=1, le=16)
    context: Optional[str] = None
    custom_steps: Optional[List[str]] = None


class ActInput(BaseModel):
    step_id: str
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
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


def _find_step(session, step_id: str, completed: bool = False):
    source = session.completed if completed else session.todo
    return next((step for step in source if step.step_id == step_id), None)


def _route_step(text: str, args: Optional[dict] = None) -> dict:
    cap = registry.route_intent(text)
    return {"description": text, "tool_hint": cap.key, "args": args or {}}


def _build_plan(goal: str, max_steps: int, profile: str, custom_steps: List[str]) -> List[dict]:
    """Deterministic floor plan.

    Reserve the final two slots for quality audit + final render when the goal is
    render-oriented so max_steps cannot silently truncate the finish.
    """
    lower = goal.lower()
    wants_render = any(word in lower for word in ("render", "image", "product shot", "packshot", "hero shot"))
    steps: List[dict] = []

    if profile != "power-user":
        steps.append({"description": "Inspect current scene state", "tool_hint": "scene.info", "args": {}})

    # Route the whole goal plus explicit custom steps. No stored step may have a
    # null or unknown tool hint.
    main = registry.route_intent(goal)
    if main.key != "scene.info" or not steps:
        steps.append({"description": goal, "tool_hint": main.key, "args": {}})
    for text in custom_steps:
        steps.append(_route_step(text))

    if profile == "forensic":
        steps.append({"description": "Inspect scene after forensic mutations", "tool_hint": "scene.info", "args": {}})

    if wants_render:
        # Reserve finish slots; dedupe if already selected by routing.
        finish = [
            {"description": "Audit render quality before final output", "tool_hint": "scene.render_audit", "args": {}},
            {"description": "Render final output", "tool_hint": "scene.render", "args": {}},
        ]
        room = max(0, max_steps - len(finish))
        steps = steps[:room] + finish
    else:
        steps = steps[:max_steps]

    # Verify registry integrity at plan boundary.
    for step in steps:
        registry.resolve_tool(step["tool_hint"])
    return steps


async def blender_router_set_goal(session, send_command, format_result, input_data: SetGoalInput):
    if input_data.profile not in VALID_PROFILES:
        return format_result({"error": f"Invalid profile. Must be one of: {sorted(VALID_PROFILES)}"})
    session.goal = input_data.goal.strip()
    session.profile = input_data.profile
    session.conversation_turn += 1
    session.todo = []
    session.completed = []
    session.critique_history = []
    cap = registry.route_intent(session.goal)
    return format_result({
        "goal": session.goal,
        "profile": session.profile,
        "session_id": session.session_id,
        "routing_preview": {"key": cap.key, "family": cap.family, "description": cap.description},
        "next": "Call blender_plan.",
    })


async def blender_plan(session, send_command, format_result, input_data: PlanInput):
    goal = (input_data.goal or session.goal or "").strip()
    if not goal:
        return format_result({"error": "No goal set. Call blender_router_set_goal first."})
    session.goal = goal
    routed = _build_plan(goal, input_data.max_steps, session.profile, input_data.custom_steps or [])
    todo = []
    rows = []
    for index, route in enumerate(routed, 1):
        step = PlanStep(
            step_id=f"step_{index}",
            description=route["description"],
            tool_hint=route["tool_hint"],
            args=route.get("args") or {},
            status=PlanStepStatus.pending,
        )
        todo.append(step)
        cap = registry.resolve_tool(step.tool_hint)
        rows.append({
            "step_id": step.step_id,
            "description": step.description,
            "tool_hint": step.tool_hint,
            "family": cap.family,
            "args": step.args,
            "status": step.status.value,
        })
    session.todo = todo
    session.completed = []
    return format_result({"goal": goal, "profile": session.profile, "plan": rows, "step_count": len(rows)})


async def blender_act(session, send_command, format_result, input_data: ActInput):
    step = _find_step(session, input_data.step_id)
    if not step:
        return format_result({"error": f"Step {input_data.step_id} not found in todo"})
    name = input_data.tool_name or step.tool_hint
    if not name:
        return format_result({"error": "no tool_hint on step; router must set it", "step_id": step.step_id})
    try:
        cap = registry.resolve_tool(name)
    except CapabilityNotFound as exc:
        return format_result({"error": str(exc), "code": "CAPABILITY_NOT_FOUND", "step_id": step.step_id})

    # If the caller names an alias/MCP tool, resolution is allowed but execution
    # still occurs via the canonical registry and bridge_command only.
    routed = registry.resolve_tool(step.tool_hint) if step.tool_hint else None
    override = bool(routed and cap.key != routed.key)
    params = input_data.tool_args if input_data.tool_args is not None else (step.args or {})

    if input_data.dry_run:
        return format_result({
            "step_id": step.step_id,
            "capability": cap.key,
            "bridge_command": cap.bridge_command,
            "args": params,
            "routing_override": override,
            "dry_run": True,
        })

    step.status = PlanStepStatus.in_progress
    try:
        result = registry.execute(cap.key, params, send_command)
        if isinstance(result, dict) and result.get("error"):
            step.status = PlanStepStatus.failed
            step.result = result
            return format_result({
                "error": result["error"], "step_id": step.step_id,
                "capability": cap.key, "bridge_command": cap.bridge_command,
                "routing_override": override,
            })
        step.result = result if isinstance(result, dict) else {"result": result}
        step.status = PlanStepStatus.done
        session.todo.remove(step)
        session.completed.append(step)
        return format_result({
            "step_id": step.step_id,
            "capability": cap.key,
            "bridge_command": cap.bridge_command,
            "routing_override": override,
            "result": step.result,
            "status": "done",
        })
    except Exception as exc:
        step.status = PlanStepStatus.failed
        step.result = {"error": str(exc)}
        return format_result({"error": str(exc), "step_id": step.step_id, "capability": cap.key})


async def blender_critique(session, send_command, format_result, input_data: CritiqueInput):
    step = _find_step(session, input_data.step_id, completed=True)
    if not step:
        return format_result({"error": f"Step {input_data.step_id} not found in completed"})
    verification = verify_action(send_command, expected=input_data.expected, constraints=input_data.constraints or [], use_vlm=True)
    entry = {
        "step_id": step.step_id,
        "expected": input_data.expected,
        "verification": verification,
        "passed": verification["passed"],
        "confidence": verification["final_confidence"],
    }
    session.critique_history.append(entry)
    data = {"step_id": step.step_id, "passed": verification["passed"], "confidence": verification["final_confidence"], "detail": verification["detail"]}
    if not verification["passed"]:
        fix = PlanStep(
            step_id=f"{step.step_id}_fix_1",
            description=f"Inspect scene to diagnose failed outcome: {input_data.expected}",
            tool_hint="scene.info",
            args={},
        )
        session.todo.insert(0, fix)
        data["suggested_fix"] = {"step_id": fix.step_id, "tool_hint": fix.tool_hint, "description": fix.description}
    return format_result(data)


async def blender_verify(session, send_command, format_result, input_data: VerifyInput):
    result = verify_action(send_command, expected=input_data.expected, constraints=input_data.constraints or [], use_vlm=input_data.use_vlm)
    return format_result({
        "passed": result["passed"],
        "confidence": result["final_confidence"],
        "detail": result["detail"],
        "gcs_score": result["gcs_result"].get("score") if result.get("gcs_result") else None,
        "vlm_confidence": result["vlm_result"].get("confidence") if result.get("vlm_result") else None,
    })


async def blender_session_status(session, send_command, format_result):
    total = len(session.todo) + len(session.completed)
    failures = sum(1 for c in session.critique_history if not c.get("passed", False))
    return format_result({
        "session_id": session.session_id,
        "goal": session.goal,
        "profile": session.profile,
        "todo_count": len(session.todo),
        "completed_count": len(session.completed),
        "progress_pct": int(len(session.completed) / max(total, 1) * 100),
        "critique_failures": failures,
    })


def register_agent_loop_tools(mcp_instance, send_command, format_result, session_store=None, drift_registry=None):
    store = session_store or default_store()

    @mcp_instance.tool()
    async def blender_router_set_goal(input: SetGoalInput):
        """Set a goal before planning or executing Blender work."""
        return await globals()["blender_router_set_goal"](store.get_or_create("default"), send_command, format_result, input)

    @mcp_instance.tool()
    async def blender_plan(input: PlanInput):
        """Build a deterministic plan whose every step has a canonical capability key."""
        return await globals()["blender_plan"](store.get_or_create("default"), send_command, format_result, input)

    @mcp_instance.tool()
    async def blender_act(input: ActInput):
        """Execute a planned step through the canonical capability registry."""
        return await globals()["blender_act"](store.get_or_create("default"), send_command, format_result, input)

    @mcp_instance.tool()
    async def blender_critique(input: CritiqueInput):
        """Critique a completed mutation and inject a concrete inspect fix on failure."""
        return await globals()["blender_critique"](store.get_or_create("default"), send_command, format_result, input)

    @mcp_instance.tool()
    async def blender_verify(input: VerifyInput):
        """Verify final scene constraints/appearance."""
        return await globals()["blender_verify"](store.get_or_create("default"), send_command, format_result, input)

    @mcp_instance.tool()
    async def blender_session_status():
        """Return current routed plan progress."""
        return await globals()["blender_session_status"](store.get_or_create("default"), send_command, format_result)

    return ["blender_router_set_goal", "blender_plan", "blender_act", "blender_critique", "blender_verify", "blender_session_status"]
