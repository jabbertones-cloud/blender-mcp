import os
from typing import Mapping, MutableMapping, Optional


DEFAULT_BLENDER_HOST = "127.0.0.1"
DEFAULT_BLENDER_PORT = 9876


def resolve_blender_host(env: Optional[Mapping[str, str]] = None) -> str:
    source = env or os.environ
    return source.get("OPENCLAW_HOST", DEFAULT_BLENDER_HOST)


def resolve_blender_port(
    env: Optional[Mapping[str, str]] = None, default: int = DEFAULT_BLENDER_PORT
) -> int:
    source = env or os.environ
    raw_value = source.get("BLENDER_PORT") or source.get("OPENCLAW_PORT") or str(default)
    return int(raw_value)


def resolve_port(
    env: Optional[Mapping[str, str]] = None, default: int = DEFAULT_BLENDER_PORT
) -> int:
    return resolve_blender_port(env=env, default=default)


def resolve_host(env: Optional[Mapping[str, str]] = None, default: str = DEFAULT_BLENDER_HOST) -> str:
    source = env or os.environ
    return source.get("OPENCLAW_HOST") or source.get("BLENDER_HOST") or default


def resolve_port(env: Optional[Mapping[str, str]] = None, default: int = DEFAULT_BLENDER_PORT) -> int:
    return resolve_blender_port(env, default)


def build_mcp_server_env(
    port: int, extra_env: Optional[Mapping[str, str]] = None
) -> MutableMapping[str, str]:
    port_value = str(port)
    env = {
        "BLENDER_PORT": port_value,
        "OPENCLAW_PORT": port_value,
    }
    if extra_env:
        env.update(extra_env)
    return env
