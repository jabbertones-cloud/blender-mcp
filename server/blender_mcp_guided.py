#!/usr/bin/env python3
"""Minimal search-first Blender MCP surface.

Only five model-facing tools are exposed. The full Blender catalog and workflow
implementations stay behind discovery and canonical execution.
"""
from __future__ import annotations

import codecs
import json
import os
import socket
import time
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
    from server.workflow_rank import workflow_match as _workflow_match
except ModuleNotFoundError:
    from runtime_config import resolve_blender_host, resolve_blender_port
    from capability_registry import registry, CapabilityNotFound
    from capability_executor import execute_canonical, execute_workflow, WORKFLOW_SCHEMAS, WORKFLOW_DESCRIPTIONS
    from workflow_rank import workflow_match as _workflow_match

HOST = resolve_blender_host()
PORT = resolve_blender_port()
TIMEOUT = float(os.getenv("OPENCLAW_TIMEOUT", "180"))
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
    request_id = uuid.uuid4().hex
    payload = {"id": request_id, "command": command, "params": params or {}}
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(TIMEOUT)
        sock.connect((HOST, PORT))
        sock.sendall(json.dumps(payload).encode("utf-8"))
        deadline = time.monotonic() + TIMEOUT
        bytes_read = 0
        decoder = codecs.getincrementaldecoder("utf-8")()
        decoded = ""
        while True:
            remaining_time = deadline - time.monotonic()
            if remaining_time <= 0:
                return {"error": f"Blender command timed out after {TIMEOUT}s", "code": "TIMEOUT"}
            sock.settimeout(remaining_time)

            remaining_budget = MAX_RESPONSE_BYTES - bytes_read
            read_size = min(1048576, remaining_budget + 1)
            chunk = sock.recv(read_size)
            if not chunk:
                break

            bytes_read += len(chunk)
            if bytes_read > MAX_RESPONSE_BYTES:
                return {
                    "error": f"Blender response exceeded {MAX_RESPONSE_BYTES} bytes",
                    "code": "RESPONSE_TOO_LARGE",
                }
            try:
                decoded += decoder.decode(chunk, final=False)
            except UnicodeDecodeError:
                return {"error": "Invalid UTF-8 sequence in response", "code": "INVALID_UTF8_RESPONSE"}

        try:
            decoded += decoder.decode(b"", final=True)
        except UnicodeDecodeError:
            return {"error": "Invalid UTF-8 sequence in response", "code": "INVALID_UTF8_RESPONSE"}

        if not decoded.strip():
            return {"error": "Empty response from Blender", "code": "EMPTY_RESPONSE"}

        try:
            data = json.loads(decoded)
        except json.JSONDecodeError:
            return {"error": "Malformed JSON in response", "code": "INVALID_JSON_RESPONSE"}

        if not isinstance(data, dict):
            return {"error": "Response must be a JSON object", "code": "INVALID_RESPONSE_SHAPE"}

        response_id = data.get("id")
        if response_id is None:
            return {"error": "Blender response missing id", "code": "RESPONSE_ID_MISSING"}
        if str(response_id) != request_id:
            return {
                "error": f"Blender response id mismatch: expected {request_id}, got {response_id}",
                "code": "RESPONSE_ID_MISMATCH",
            }

        if data.get("error") is not None:
            # Preserve validated structured transport/handler errors instead of
            # discarding stable codes and safe metadata supplied by the addon.
            return {key: value for key, value in data.items() if key != "id"}
        return data.get("result", data)
    except ConnectionRefusedError:
        return {"error": f"Cannot connect to Blender bridge at {HOST}:{PORT}", "code": "CONNECTION_REFUSED"}
    except socket.timeout:
        return {"error": f"Blender command timed out after {TIMEOUT}s", "code": "TIMEOUT"}
    except OSError as exc:
        return {"error": f"Blender socket error: {exc}", "code": "SOCKET_ERROR"}
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
    """Set the Blender goal and identify whether a complete workflow or atomic family should lead."""
    workflows = _workflow_match(input.goal)
    cap = registry.route_intent(input.goal)
    _goal_state.update({"goal": input.goal, "last_search": [], "executions": 0})
    first = workflows[0] if workflows else {"key": cap.key, "family": cap.family, "description": cap.description}
    return {
        "goal": input.goal,
        "recommended_first": first,
        "next": "Call search_capabilities for the concrete workflow/capability before execution.",
    }


@mcp.tool(name="router_get_status")
async def router_get_status() -> dict:
    """Return current goal, recent capability search, and execution count."""
    return dict(_goal_state)


@mcp.tool(name="search_capabilities")
async def search_capabilities(input: SearchInput) -> dict:
    """Search the hidden Blender capability catalog; workflow matches rank before atomic tools."""
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
    """Get the schema for one canonical capability or workflow key."""
    if input.key in WORKFLOW_SCHEMAS:
        return {
            "capability": {
                "key": input.key,
                "family": "workflow",
                "description": WORKFLOW_DESCRIPTIONS[input.key],
                "input_schema": WORKFLOW_SCHEMAS[input.key],
            },
            "next": "Call execute_capability with this exact workflow key.",
        }
    try:
        cap = registry.get_capability_schema(input.key)
        return {"capability": cap, "next": "Call execute_capability with this exact key."}
    except CapabilityNotFound as exc:
        return {"error": str(exc), "code": "CAPABILITY_NOT_FOUND", "next": "Call search_capabilities again."}


@mcp.tool(name="execute_capability")
async def execute_capability(input: ExecuteInput) -> dict:
    """Execute one exact canonical key. Unknown or alias names never reach the Blender socket."""
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
        return {
            "error": f"Use canonical capability key '{cap.key}', not alias '{input.key}'.",
            "code": "NON_CANONICAL_CAPABILITY",
            "next": "Use the key returned by search_capabilities/get_capability_schema.",
        }

    try:
        result = execute_canonical(cap.key, input.arguments, send_command)
    except ValueError as exc:
        return {"error": str(exc), "code": "INVALID_CAPABILITY_ARGUMENTS"}
    _goal_state["executions"] += 1
    return result


if __name__ == "__main__":
    mcp.run()