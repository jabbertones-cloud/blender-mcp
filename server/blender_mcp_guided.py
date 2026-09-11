#!/usr/bin/env python3
"""Minimal search-first Blender MCP surface.

Only five model-facing tools are exposed. The full Blender catalog and workflow
implementations stay behind discovery and canonical execution.
"""
from __future__ import annotations

import json
import os
import socket
import uuid
from typing import Any, Dict

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

try:
    from server.runtime_config import resolve_blender_host, resolve_blender_port
    from server.capability_registry import registry, CapabilityNotFound
    from server.capability_executor import (
        execute_canonical,
        execute_workflow,
        WORKFLOW_SCHEMAS,
        WORKFLOW_DESCRIPTIONS,
    )
except ModuleNotFoundError:
    from runtime_config import resolve_blender_host, resolve_blender_port
    from capability_registry import registry, CapabilityNotFound
    from capability_executor import execute_canonical, execute_workflow, WORKFLOW_SCHEMAS, WORKFLOW_DESCRIPTIONS

HOST = resolve_blender_host()
PORT = resolve_blender_port()
TIMEOUT = float(os.getenv("OPENCLAW_TIMEOUT", "30"))
MAX_RESPONSE_BYTES = int(os.getenv("OPENCLAW_MAX_RESPONSE_BYTES", str(32 * 1024 * 1024)))

mcp = FastMCP(
    "blender_mcp_guided",
    instructions=(
        "For multi-step Blender work, set the goal first. Search capabilities before execution. "
        "Prefer a workflow capability when it matches the user's complete intent. Never invent capability keys. "
        "Inspect one schema, then execute the exact canonical key returned by search. "
        "Appearance-affecting operations automatically return visual postcondition evidence."
    ),
)
_goal_state: Dict[str, Any] = {"goal": None, "last_search": [], "executions": 0}


def send_command(command: str, params: dict | None = None) -> dict:
    """Send one framed request to the Blender bridge.

    Each call owns its socket, so concurrent MCP calls cannot interleave request
    and response bytes. The receive buffer tolerates both incomplete JSON and a
    UTF-8 code point split across recv() boundaries.
    """
    request_id = uuid.uuid4().hex
    payload = {"id": request_id, "command": command, "params": params or {}}
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(TIMEOUT)
        sock.connect((HOST, PORT))
        sock.sendall(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        buffer = bytearray()
        while True:
            chunk = sock.recv(1024 * 1024)
            if not chunk:
                break
            buffer.extend(chunk)
            if len(buffer) > MAX_RESPONSE_BYTES:
                return {"error": f"Blender response exceeded {MAX_RESPONSE_BYTES} bytes", "code": "RESPONSE_TOO_LARGE"}
            try:
                data = json.loads(buffer.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if isinstance(data, dict) and data.get("id") not in (None, request_id):
                return {"error": "Blender response request id mismatch", "code": "RESPONSE_ID_MISMATCH"}
            return data.get("result", data) if not data.get("error") else {"error": data["error"]}
        return {"error": "Empty response from Blender"}
    except ConnectionRefusedError:
        return {"error": f"Cannot connect to Blender bridge at {HOST}:{PORT}"}
    except socket.timeout:
        return {"error": f"Blender command timed out after {TIMEOUT}s"}
    except OSError as exc:
        return {"error": f"Blender bridge socket error: {exc}", "code": "SOCKET_ERROR"}
    finally:
        sock.close()


class GoalInput(BaseModel):
    goal: str = Field(..., min_length=1)


class SearchInput(BaseModel):
    query: str = Field(..., min_length=1)
    limit: int = Field(default=6, ge=1, le=12)


class SchemaInput(BaseModel):
    key: str = Field(..., min_length=1)


class ExecuteInput(BaseModel):
    key: str = Field(..., min_length=1)
    arguments: Dict[str, Any] = Field(default_factory=dict)


def _workflow_match(query: str) -> list[dict]:
    text = " ".join((query or "").lower().split())
    matches = []
    hero_terms = ("product hero", "hero product", "hero shot", "packshot", "product photography", "product image")
    if any(term in text for term in hero_terms):
        matches.append({"key": "workflow.product_hero", "family": "workflow", "description": WORKFLOW_DESCRIPTIONS["workflow.product_hero"], "score": 150.0, "reason": ["complete multi-step product-hero intent"]})
    if any(term in text for term in ("turntable", "360 spin", "360 product")):
        matches.append({"key": "workflow.turntable", "family": "workflow", "description": WORKFLOW_DESCRIPTIONS["workflow.turntable"], "score": 145.0, "reason": ["complete product turntable intent"]})
    if any(term in text for term in ("forensic", "accident reconstruction", "courtroom")):
        matches.append({"key": "workflow.forensic_recon", "family": "workflow", "description": WORKFLOW_DESCRIPTIONS["workflow.forensic_recon"], "score": 140.0, "reason": ["complete forensic reconstruction intent"]})
    if "amazon" in text or "a+ content" in text or "main listing image" in text:
        matches.insert(0, {"key": "workflow.amazon_packshot", "family": "workflow", "description": WORKFLOW_DESCRIPTIONS["workflow.amazon_packshot"], "score": 160.0, "reason": ["complete Amazon packshot intent"]})
    return matches


@mcp.tool(name="router_set_goal")
async def router_set_goal(input: GoalInput) -> dict:
    workflows = _workflow_match(input.goal)
    cap = registry.route_intent(input.goal)
    _goal_state.update({"goal": input.goal, "last_search": [], "executions": 0})
    first = workflows[0] if workflows else {"key": cap.key, "family": cap.family, "description": cap.description}
    return {"goal": input.goal, "recommended_first": first, "next": "Call search_capabilities for the concrete workflow/capability before execution."}


@mcp.tool(name="router_get_status")
async def router_get_status() -> dict:
    return dict(_goal_state)


@mcp.tool(name="search_capabilities")
async def search_capabilities(input: SearchInput) -> dict:
    results = _workflow_match(input.query)
    seen = {row["key"] for row in results}
    for row in registry.search_capabilities(input.query, limit=input.limit):
        if row["key"] in seen:
            continue
        results.append(row)
        seen.add(row["key"])
        if len(results) >= input.limit:
            break
    _goal_state["last_search"] = [row["key"] for row in results]
    return {"query": input.query, "results": results, "next": "Call get_capability_schema with one returned key."}


@mcp.tool(name="get_capability_schema")
async def get_capability_schema(input: SchemaInput) -> dict:
    if input.key in WORKFLOW_SCHEMAS:
        return {"capability": {"key": input.key, "family": "workflow", "description": WORKFLOW_DESCRIPTIONS[input.key], "input_schema": WORKFLOW_SCHEMAS[input.key]}, "next": "Call execute_capability with this exact workflow key."}
    try:
        cap = registry.get_capability_schema(input.key)
        return {"capability": cap, "next": "Call execute_capability with this exact key."}
    except CapabilityNotFound as exc:
        return {"error": str(exc), "code": "CAPABILITY_NOT_FOUND", "next": "Call search_capabilities again."}


@mcp.tool(name="execute_capability")
async def execute_capability(input: ExecuteInput) -> dict:
    if input.key in WORKFLOW_SCHEMAS:
        try:
            result = execute_workflow(input.key, input.arguments, send_command)
        except (KeyError, ValueError) as exc:
            return {"error": str(exc), "code": "INVALID_WORKFLOW_ARGUMENTS"}
        _goal_state["executions"] += 1
        return result
    try:
        cap = registry.resolve_tool(input.key)
    except CapabilityNotFound as exc:
        return {"error": str(exc), "code": "CAPABILITY_NOT_FOUND", "next": "Call search_capabilities again."}
    if input.key != cap.key:
        return {"error": f"Use canonical capability key '{cap.key}', not alias '{input.key}'.", "code": "NON_CANONICAL_CAPABILITY", "next": "Use the key returned by search_capabilities/get_capability_schema."}
    try:
        result = execute_canonical(cap.key, input.arguments, send_command)
    except ValueError as exc:
        return {"error": str(exc), "code": "INVALID_CAPABILITY_ARGUMENTS"}
    _goal_state["executions"] += 1
    return result


if __name__ == "__main__":
    mcp.run()
