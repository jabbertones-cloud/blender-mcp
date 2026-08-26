#!/usr/bin/env python3
"""Minimal LLM-guided MCP surface.

This entrypoint intentionally exposes only five model-facing tools. The full
Blender catalog remains internal behind CapabilityRegistry.
"""
from __future__ import annotations

import json
import os
import socket
from typing import Any, Dict

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

try:
    from server.runtime_config import resolve_blender_host, resolve_blender_port
    from server.capability_registry import registry, CapabilityNotFound
except ModuleNotFoundError:
    from runtime_config import resolve_blender_host, resolve_blender_port
    from capability_registry import registry, CapabilityNotFound

HOST = resolve_blender_host()
PORT = resolve_blender_port()
TIMEOUT = float(os.getenv("OPENCLAW_TIMEOUT", "30"))

mcp = FastMCP(
    "blender_mcp_guided",
    instructions=(
        "Use router_set_goal first for multi-step work. Search capabilities before execution. "
        "Never invent capability keys. After search, inspect the schema, then execute the canonical key. "
        "If execution returns CAPABILITY_NOT_FOUND, search again."
    ),
)
_goal_state: Dict[str, Any] = {"goal": None, "last_search": [], "executions": 0}
_request_id = 0


def send_command(command: str, params: dict | None = None) -> dict:
    global _request_id
    _request_id += 1
    payload = {"id": str(_request_id), "command": command, "params": params or {}}
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(TIMEOUT)
        sock.connect((HOST, PORT))
        sock.sendall(json.dumps(payload).encode("utf-8"))
        chunks = []
        while True:
            chunk = sock.recv(1048576)
            if not chunk:
                break
            chunks.append(chunk)
            try:
                data = json.loads(b"".join(chunks).decode("utf-8"))
                return data.get("result", data) if not data.get("error") else {"error": data["error"]}
            except json.JSONDecodeError:
                continue
        return {"error": "Empty response from Blender"}
    except ConnectionRefusedError:
        return {"error": f"Cannot connect to Blender bridge at {HOST}:{PORT}"}
    except socket.timeout:
        return {"error": f"Blender command timed out after {TIMEOUT}s"}
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


@mcp.tool(name="router_set_goal")
async def router_set_goal(input: GoalInput) -> dict:
    """Set the user's Blender goal and return the deterministic first capability family."""
    cap = registry.route_intent(input.goal)
    _goal_state.update({"goal": input.goal, "last_search": [], "executions": 0})
    return {
        "goal": input.goal,
        "recommended_first": {"key": cap.key, "family": cap.family, "description": cap.description},
        "next": "Call search_capabilities for the concrete operation before execution.",
    }


@mcp.tool(name="router_get_status")
async def router_get_status() -> dict:
    """Return current goal, recent capability search, and execution count."""
    return dict(_goal_state)


@mcp.tool(name="search_capabilities")
async def search_capabilities(input: SearchInput) -> dict:
    """Search the hidden Blender capability catalog. Returns summaries, not full schemas."""
    results = registry.search_capabilities(input.query, limit=input.limit)
    _goal_state["last_search"] = [row["key"] for row in results]
    return {"query": input.query, "results": results, "next": "Call get_capability_schema with one returned key."}


@mcp.tool(name="get_capability_schema")
async def get_capability_schema(input: SchemaInput) -> dict:
    """Get dispatch metadata and argument schema for one canonical capability key."""
    try:
        cap = registry.get_capability_schema(input.key)
        return {"capability": cap, "next": "Call execute_capability with this exact key."}
    except CapabilityNotFound as exc:
        return {"error": str(exc), "code": "CAPABILITY_NOT_FOUND", "next": "Call search_capabilities again."}


@mcp.tool(name="execute_capability")
async def execute_capability(input: ExecuteInput) -> dict:
    """Execute a canonical capability. Guessed/unknown keys are rejected before the Blender socket."""
    try:
        cap = registry.resolve_tool(input.key)
    except CapabilityNotFound as exc:
        return {"error": str(exc), "code": "CAPABILITY_NOT_FOUND", "next": "Call search_capabilities again."}

    # Guided mode requires the canonical key specifically. MCP names and bridge
    # aliases can resolve internally but are not accepted as execution identity.
    if input.key != cap.key:
        return {
            "error": f"Use canonical capability key '{cap.key}', not alias '{input.key}'.",
            "code": "NON_CANONICAL_CAPABILITY",
            "next": "Use the key returned by search_capabilities/get_capability_schema.",
        }
    result = registry.execute(cap.key, input.arguments, send_command)
    _goal_state["executions"] += 1
    return {"capability": cap.key, "bridge_command": cap.bridge_command, "result": result}


if __name__ == "__main__":
    mcp.run()
