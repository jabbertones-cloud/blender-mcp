"""
Session State Management for OpenClaw Blender MCP
==================================================
Per-client session state tracking, plan persistence, and scene snapshots.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class PlanStepStatus(str, Enum):
    pending = "pending"
    in_progress = "in_progress"
    done = "done"
    failed = "failed"


@dataclass
class PlanStep:
    """Atomic action in a plan.

    tool_hint is always a canonical capability key (for example
    ``scene.create_object``), never an arbitrary MCP or bridge name. ``args`` is
    persisted with the step so planning cannot silently drop router arguments.
    """
    step_id: str
    description: str
    tool_hint: Optional[str] = None
    args: Dict[str, Any] = field(default_factory=dict)
    status: PlanStepStatus = PlanStepStatus.pending
    result: Optional[Dict[str, Any]] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class SessionState:
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
    def __init__(self, persist_path: Optional[str] = None):
        self._sessions: Dict[str, SessionState] = {}
        self._persist_path = persist_path or (
            "/tmp/openclaw-sessions.jsonl"
            if os.getenv("OPENCLAW_SESSION_PERSIST", "").lower() in ("1", "true", "yes")
            else None
        )
        if self._persist_path and os.path.exists(self._persist_path):
            self._load_sessions()

    def get_or_create(self, session_id: str) -> SessionState:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionState(session_id=session_id)
        return self._sessions[session_id]

    def reset(self, session_id: str) -> None:
        if session_id in self._sessions:
            self._sessions[session_id] = SessionState(session_id=session_id)

    def all_sessions(self) -> List[str]:
        return list(self._sessions.keys())

    def save_snapshot(self, session_id: str, snapshot_id: str, snapshot: Dict[str, Any]) -> None:
        session = self.get_or_create(session_id)
        session.snapshots[snapshot_id] = {
            "data": snapshot,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._persist()

    def get_snapshot(self, session_id: str, snapshot_id: str) -> Optional[Dict[str, Any]]:
        session = self._sessions.get(session_id)
        if not session or snapshot_id not in session.snapshots:
            return None
        return session.snapshots[snapshot_id].get("data")

    def _persist(self) -> None:
        if not self._persist_path:
            return
        try:
            os.makedirs(os.path.dirname(self._persist_path), exist_ok=True)
            with open(self._persist_path, "w") as f:
                for session in self._sessions.values():
                    row = asdict(session)
                    row["todo"] = [
                        {**asdict(step), "status": step.status.value}
                        for step in session.todo
                    ]
                    row["completed"] = [
                        {**asdict(step), "status": step.status.value}
                        for step in session.completed
                    ]
                    f.write(json.dumps(row) + "\n")
        except Exception as e:
            print(f"Warning: session persistence failed: {e}")

    def _load_sessions(self) -> None:
        if not self._persist_path or not os.path.exists(self._persist_path):
            return
        try:
            with open(self._persist_path, "r") as f:
                for line in f:
                    if not line.strip():
                        continue
                    data = json.loads(line)

                    def _restore(step):
                        return PlanStep(
                            step_id=step["step_id"],
                            description=step["description"],
                            tool_hint=step.get("tool_hint"),
                            args=step.get("args") or {},
                            status=PlanStepStatus(step["status"]),
                            result=step.get("result"),
                            created_at=step.get("created_at", datetime.utcnow().isoformat()),
                        )

                    session = SessionState(
                        session_id=data["session_id"],
                        goal=data.get("goal"),
                        profile=data.get("profile", "default"),
                        todo=[_restore(step) for step in data.get("todo", [])],
                        completed=[_restore(step) for step in data.get("completed", [])],
                        snapshots=data.get("snapshots", {}),
                        conversation_turn=data.get("conversation_turn", 0),
                        critique_history=data.get("critique_history", []),
                        created_at=data.get("created_at", datetime.utcnow().isoformat()),
                    )
                    self._sessions[session.session_id] = session
        except Exception as e:
            print(f"Warning: failed to load sessions: {e}")


_default_store: Optional[SessionStore] = None


def default_store() -> SessionStore:
    global _default_store
    if _default_store is None:
        _default_store = SessionStore()
    return _default_store


def reset_default_store() -> None:
    global _default_store
    _default_store = SessionStore()
