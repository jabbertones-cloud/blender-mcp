"""
Session State Management for OpenClaw Blender MCP
==================================================
Per-client session state tracking, plan persistence, and scene snapshots.

Reference: Planner-Actor-Critic agent loop (arXiv 2601.05016) — maintains
todo list, execution history, critique feedback, and checkpoints across
multiple conversation turns.

Install: Standard library only.
Usage:
  from session_state import default_store, SessionState, PlanStep
  session = default_store().get_or_create("my-session-id")
  session.goal = "render a product"
  default_store().save_snapshot(session.session_id, "before_lighting", {...})
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class PlanStepStatus(str, Enum):
    """Status of a plan step."""
    pending = "pending"
    in_progress = "in_progress"
    done = "done"
    failed = "failed"


@dataclass
class PlanStep:
    """Atomic action in a plan."""
    step_id: str
    description: str
    tool_hint: Optional[str] = None
    status: PlanStepStatus = PlanStepStatus.pending
    result: Optional[Dict[str, Any]] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class SessionState:
    """Per-MCP-client session state: goal, plan, history, snapshots."""
    session_id: str
    goal: Optional[str] = None
    profile: str = "default"
    todo: List[PlanStep] = field(default_factory=list)
    completed: List[PlanStep] = field(default_factory=list)
    snapshots: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    conversation_turn: int = 0
    critique_history: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class SessionStore:
    """
    In-memory session registry with optional persistence.

    Keyed by session_id (from MCP request context or synthesized from pid+time).
    Supports:
    - get_or_create(session_id) -> SessionState
    - reset(session_id)
    - all_sessions() -> list[str]
    - save_snapshot / get_snapshot
    - optional persistence to OPENCLAW_SESSION_PERSIST env var
    """

    def __init__(self, persist_path: Optional[str] = None):
        """
        Args:
            persist_path: If set, save/load sessions to/from this JSONL file.
                         If None, check OPENCLAW_SESSION_PERSIST env var.
        """
        self._sessions: Dict[str, SessionState] = {}
        self._persist_path = persist_path or (
            "/tmp/openclaw-sessions.jsonl"
            if os.getenv("OPENCLAW_SESSION_PERSIST", "").lower() in ("1", "true", "yes")
            else None
        )
        if self._persist_path and os.path.exists(self._persist_path):
            self._load_sessions()

    def get_or_create(self, session_id: str) -> SessionState:
        """Get existing session or create a new one."""
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionState(session_id=session_id)
        return self._sessions[session_id]

    def reset(self, session_id: str) -> None:
        """Clear a session entirely."""
        if session_id in self._sessions:
            self._sessions[session_id] = SessionState(session_id=session_id)

    def all_sessions(self) -> List[str]:
        """List all active session IDs."""
        return list(self._sessions.keys())

    def save_snapshot(
        self, session_id: str, snapshot_id: str, snapshot: Dict[str, Any]
    ) -> None:
        """Save a scene snapshot (with timestamp) to session state."""
        session = self.get_or_create(session_id)
        session.snapshots[snapshot_id] = {
            "data": snapshot,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._persist()

    def get_snapshot(self, session_id: str, snapshot_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a scene snapshot."""
        session = self._sessions.get(session_id)
        if not session or snapshot_id not in session.snapshots:
            return None
        return session.snapshots[snapshot_id].get("data")

    def _persist(self) -> None:
        """Save all sessions to JSONL file (one session per line)."""
        if not self._persist_path:
            return
        try:
            os.makedirs(os.path.dirname(self._persist_path), exist_ok=True)
            with open(self._persist_path, "w") as f:
                for session in self._sessions.values():
                    row = asdict(session)
                    # Convert PlanStepStatus to string and PlanStep objects to dicts
                    row["todo"] = [
                        {
                            **asdict(step),
                            "status": step.status.value,
                        }
                        for step in row["todo"]
                    ]
                    row["completed"] = [
                        {
                            **asdict(step),
                            "status": step.status.value,
                        }
                        for step in row["completed"]
                    ]
                    f.write(json.dumps(row) + "\n")
        except Exception as e:
            # Log but don't crash on persistence failures
            print(f"Warning: session persistence failed: {e}")

    def _load_sessions(self) -> None:
        """Load sessions from JSONL file on startup."""
        if not self._persist_path or not os.path.exists(self._persist_path):
            return
        try:
            with open(self._persist_path, "r") as f:
                for line in f:
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    # Reconstruct PlanStep objects
                    todo = [
                        PlanStep(
                            step_id=step["step_id"],
                            description=step["description"],
                            tool_hint=step.get("tool_hint"),
                            status=PlanStepStatus(step["status"]),
                            result=step.get("result"),
                            created_at=step.get(
                                "created_at",
                                datetime.utcnow().isoformat(),
                            ),
                        )
                        for step in data.get("todo", [])
                    ]
                    completed = [
                        PlanStep(
                            step_id=step["step_id"],
                            description=step["description"],
                            tool_hint=step.get("tool_hint"),
                            status=PlanStepStatus(step["status"]),
                            result=step.get("result"),
                            created_at=step.get(
                                "created_at",
                                datetime.utcnow().isoformat(),
                            ),
                        )
                        for step in data.get("completed", [])
                    ]
                    session = SessionState(
                        session_id=data["session_id"],
                        goal=data.get("goal"),
                        profile=data.get("profile", "default"),
                        todo=todo,
                        completed=completed,
                        snapshots=data.get("snapshots", {}),
                        conversation_turn=data.get("conversation_turn", 0),
                        critique_history=data.get("critique_history", []),
                        created_at=data.get(
                            "created_at", datetime.utcnow().isoformat()
                        ),
                    )
                    self._sessions[session.session_id] = session
        except Exception as e:
            print(f"Warning: failed to load sessions: {e}")


# Module-level default store singleton
_default_store: Optional[SessionStore] = None


def default_store() -> SessionStore:
    """Get the default session store singleton."""
    global _default_store
    if _default_store is None:
        _default_store = SessionStore()
    return _default_store


def reset_default_store() -> None:
    """Reset the default store (for testing)."""
    global _default_store
    _default_store = SessionStore()
