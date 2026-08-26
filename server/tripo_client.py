"""Tripo v3 client. Endpoints from developers.tripo3d.ai (2026-08-26)."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, Optional

BASE = "https://openapi.tripo3d.ai/v3"


class TripoError(RuntimeError):
    pass


class UrllibTransport:
    def __init__(self, api_key: str, timeout: float = 45.0):
        self.api_key = api_key
        self.timeout = timeout

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json", "Accept": "application/json"}

    def post(self, path: str, body: dict) -> dict:
        req = urllib.request.Request(
            BASE + path,
            data=json.dumps(body).encode("utf-8"),
            method="POST",
            headers=self._headers(),
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def get(self, path: str) -> dict:
        req = urllib.request.Request(BASE + path, method="GET", headers=self._headers())
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def download(self, url: str, dest: str) -> str:
        urllib.request.urlretrieve(url, dest)
        return dest


_override: Optional[Any] = None


def set_transport(transport: Any) -> None:
    global _override
    _override = transport


def _transport():
    if _override is not None:
        return _override
    key = os.getenv("TRIPO_API_KEY", "").strip()
    if not key:
        raise TripoError("TRIPO_API_KEY not set")
    return UrllibTransport(key)


def _data(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise TripoError(f"unexpected Tripo payload: {payload!r}")
    if payload.get("code") not in (None, 0):
        raise TripoError(payload.get("message") or str(payload))
    return payload.get("data") or payload


def poll_task(task_id: str, *, sleep: Callable[[float], None] = time.sleep, max_polls: Optional[int] = None) -> dict:
    transport = _transport()
    limit = int(os.getenv("TRIPO_MAX_POLLS", str(max_polls or 60)))
    for _ in range(limit):
        data = _data(transport.get(f"/tasks/{task_id}"))
        status = str(data.get("status") or "").lower()
        if status == "success":
            return data
        if status in {"failed", "cancelled", "error"}:
            raise TripoError(f"Tripo task {task_id} {status}")
        sleep(2.0)
    raise TripoError(f"Tripo task {task_id} timed out")


def _ensure_success(payload: dict) -> dict:
    data = _data(payload)
    status = str(data.get("status") or "").lower()
    if status in {"failed", "cancelled", "error"}:
        raise TripoError(f"Tripo task {data.get('task_id')} {status}")
    if status == "success":
        return data
    if data.get("riggable") is not None or data.get("rig_type"):
        return data
    if data.get("task_id"):
        return poll_task(data["task_id"])
    return data


def run_character_pipeline(image_url: str, dest_dir: str = "/tmp/openclaw_tripo") -> dict:
    transport = _transport()
    os.makedirs(dest_dir, exist_ok=True)
    gen = _ensure_success(
        transport.post(
            "/generation/image-to-model",
            {
                "input": image_url,
                "model": "P1-20260311",
                "face_limit": 5000,
                "texture": True,
            },
        )
    )
    model_task = gen.get("task_id")
    check = _ensure_success(transport.post("/animations/rig-check", {"input": model_task}))
    output = check.get("output") if isinstance(check.get("output"), dict) else {}
    riggable = check.get("riggable", output.get("riggable", True))
    rig_type = check.get("rig_type") or output.get("rig_type") or "biped"
    if not riggable:
        raise TripoError(f"model not riggable (rig_type={rig_type})")
    rig = _ensure_success(
        transport.post(
            "/animations/rig",
            {"input": model_task, "rig_type": rig_type, "spec": "mixamo", "out_format": "glb"},
        )
    )
    rig_id = rig.get("task_id")
    anim = _ensure_success(
        transport.post(
            "/animations/retarget",
            {"input": rig_id, "animations": ["preset:walk", "preset:idle", "preset:run"]},
        )
    )
    out = anim.get("output") or {}
    urls = out.get("model_urls") or []
    url = urls[0] if urls else out.get("model_url")
    if not url:
        raise TripoError("retarget succeeded but no model_url")
    dest = os.path.join(dest_dir, f"{rig_id or 'character'}.glb")
    transport.download(url, dest)
    return {
        "filepath": dest,
        "model_task_id": model_task,
        "rig_task_id": rig_id,
        "anim_task_id": anim.get("task_id"),
        "rig_type": rig_type,
    }
