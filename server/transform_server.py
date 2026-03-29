#!/usr/bin/env python3
"""
Transformation script to add token-optimization to blender_mcp_server.py
"""
import re
import os

script_dir = os.path.dirname(os.path.abspath(__file__))
server_file = os.path.join(script_dir, 'blender_mcp_server.py')

# Read the original file
with open(server_file, 'r') as f:
    content = f.read()

# 1. Add 'os' to imports
content = content.replace(
    'import sys\nfrom typing import Optional',
    'import sys\nimport os\nfrom typing import Optional'
)

# 2. Add configuration variables after SOCKET_TIMEOUT
config_lines = '''BLENDER_HOST = "127.0.0.1"
BLENDER_PORT = 9876
SOCKET_TIMEOUT = 30.0
COMPACT_MODE = os.getenv("OPENCLAW_COMPACT", "").lower() in ("1", "true", "yes")
MAX_RESPONSE_CHARS = 4000'''

content = re.sub(
    r'BLENDER_HOST = "127\.0\.0\.1"\nBLENDER_PORT = 9876\nSOCKET_TIMEOUT = 30\.0',
    config_lines,
    content
)

# 3. Replace the format_result function
old_format_result = '''def format_result(result: dict) -> str:
    """Format a result dict as a readable JSON string."""
    if isinstance(result, dict) and "error" in result:
        error_msg = f"Error: {result['error']}"
        if result.get("traceback"):
            error_msg += f"\\n\\nTraceback:\\n{result['traceback']}"
        return error_msg
    return json.dumps(result, indent=2, default=str)'''

new_format_result = '''def estimate_tokens(text: str) -> int:
    """Estimate token count as roughly 1 token per 4 characters."""
    return max(1, len(text) // 4)


def _summarize_scene_info(data: dict) -> dict:
    """Smart summarization for get_scene_info: count objects, list only names/types, full details for active object."""
    if "error" in data:
        return data
    
    summary = {
        "summary": {
            "total_objects": len(data.get("objects", [])),
            "meshes": len([o for o in data.get("objects", []) if o.get("type") == "MESH"]),
            "lights": len([o for o in data.get("objects", []) if o.get("type") == "LIGHT"]),
            "cameras": len([o for o in data.get("objects", []) if o.get("type") == "CAMERA"]),
            "materials": len(data.get("materials", [])),
        },
        "objects": [
            {"name": o.get("name"), "type": o.get("type")}
            for o in data.get("objects", [])
        ],
        "active_object": data.get("active_object"),
        "render_engine": data.get("render_engine"),
        "frame_range": data.get("frame_range"),
    }
    return summary


def format_result(result: dict, command: Optional[str] = None, compact: Optional[bool] = None) -> str:
    """Format a result dict as JSON with optional compaction, truncation, and response envelope.
    
    Args:
        result: The result dict from send_command()
        command: Optional command name (used to apply smart summarization)
        compact: Override COMPACT_MODE setting. If None, uses env var.
    
    Returns:
        Formatted JSON string, possibly compact and truncated with envelope.
    """
    use_compact = compact if compact is not None else COMPACT_MODE
    
    # Handle errors first
    if isinstance(result, dict) and "error" in result:
        error_msg = f"Error: {result['error']}"
        if result.get("traceback"):
            error_msg += f"\\n\\nTraceback:\\n{result['traceback']}"
        return error_msg
    
    # Apply smart summarization for get_scene_info
    if command == "get_scene_info" and isinstance(result, dict):
        result = _summarize_scene_info(result)
    
    # Format JSON
    if use_compact:
        json_str = json.dumps(result, separators=(',', ':'), default=str)
    else:
        json_str = json.dumps(result, indent=2, default=str)
    
    # Truncate if needed
    if len(json_str) > MAX_RESPONSE_CHARS:
        # Count items in top-level array/dict for summary
        item_count = len(result) if isinstance(result, dict) else len(result) if isinstance(result, list) else 1
        truncated = json_str[:MAX_RESPONSE_CHARS - 50]
        json_str = truncated + f"... [truncated, {item_count} total items]"
    
    # Wrap in response envelope
    tokens_est = estimate_tokens(json_str)
    envelope = {
        "status": "ok",
        "tokens_est": tokens_est,
        "data": result,
    }
    
    if use_compact:
        return json.dumps(envelope, separators=(',', ':'), default=str)
    else:
        return json.dumps(envelope, indent=2, default=str)'''

content = content.replace(old_format_result, new_format_result)

# Write the modified file
with open(server_file, 'w') as f:
    f.write(content)

print("✓ Successfully transformed blender_mcp_server.py")
print("  - Added 'os' import")
print("  - Added COMPACT_MODE and MAX_RESPONSE_CHARS configuration")
print("  - Added estimate_tokens() utility function")
print("  - Added _summarize_scene_info() smart summarization")
print("  - Updated format_result() with envelope, compact mode, and truncation")
