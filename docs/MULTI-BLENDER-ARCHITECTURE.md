# Multi-Blender Instance Architecture

## Overview

The OpenClaw Blender MCP system supports concurrent AI agent access to multiple Blender instances, each running independently on a different TCP port. This enables parallel animation rendering, asset processing, and scene editing across different projects without conflicts.

---

## Current Single-Instance Design

### How It Works

The current system uses a single hardcoded TCP port (9876) for Blender Bridge communication:

1. **Addon (Bridge)**: Runs inside Blender, listens on `127.0.0.1:9876`
2. **MCP Server**: Connects to the addon via TCP socket, sends JSON commands
3. **Communication Flow**:
   ```
   Agent/Claude → MCP Server → TCP Socket (127.0.0.1:9876) → Blender Bridge Addon → bpy.* execution → Response
   ```

### Configuration

- **Port**: Hardcoded as `9876` in `blender_mcp_server.py`
- **Host**: Defaults to `127.0.0.1` (localhost)
- **Environment Variable**: `OPENCLAW_PORT` (if set, overrides default)
- **Instance ID**: Derived from port (e.g., `blender-9876`)

### Limitations

- Only one Blender instance can be used at a time
- Starting a second Blender instance with the addon would conflict on port 9876
- No way to track or coordinate multiple instances
- Agents cannot work on different scenes/projects in parallel

---

## Multi-Instance Design

### Architecture Overview

Each Blender instance runs the OpenClaw Bridge addon on a **unique port** in the range **9876–9886** (configurable). An optional registry file tracks all running instances and their metadata.

```
┌─────────────────────────────────────────────────────────────┐
│                      Agent Dispatcher                       │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Agent Task 1 │  │ Agent Task 2 │  │ Agent Task 3 │ ... │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
└─────────┼──────────────────┼──────────────────┼────────────┘
          │                  │                  │
    Query Registry      Query Registry    Query Registry
          │                  │                  │
┌─────────▼──────────────────▼──────────────────▼────────────┐
│           Instance Registry (blender-instances.json)        │
│                                                              │
│  [{port: 9876, pid: 1234, file: project-a.blend, ...},    │
│   {port: 9877, pid: 1235, file: project-b.blend, ...},    │
│   {port: 9878, pid: 1236, file: project-c.blend, ...}]    │
└─────────┬──────────────────┬──────────────────┬────────────┘
          │                  │                  │
    ┌─────▼──┐          ┌─────▼──┐          ┌─────▼──┐
    │ Blender│ MCP  │ Blender│ MCP  │ Blender│ MCP
    │ 9876   │ Srv  │ 9877   │ Srv  │ 9878   │ Srv
    │        │      │        │      │        │
    │ Proj-A │      │ Proj-B │      │ Proj-C │
    └────────┘      └────────┘      └────────┘
```

### Port Assignment Strategy

- **Default Range**: `9876–9886` (11 instances max)
- **Environment Variable**: `BLENDER_PORT_RANGE` (e.g., `9876:9900` for 25 instances)
- **Per-Instance Port**: Set via `BLENDER_PORT` environment variable when launching Blender
- **Auto-Discovery**: MCP server can probe the default range to find all running instances

### Port Configuration Methods

#### 1. Environment Variable (Recommended for individual instances)

```bash
# Launch first Blender instance on port 9876
BLENDER_PORT=9876 blender project-a.blend &

# Launch second instance on port 9877
BLENDER_PORT=9877 blender project-b.blend &

# Launch third instance on port 9878
BLENDER_PORT=9878 blender project-c.blend &
```

#### 2. Addon Preferences (GUI)

If Blender is already running, the user can modify the port via:
- **Blender** → **Edit** → **Preferences** → **Add-ons** → **OpenClaw Blender Bridge**
- A text field in the addon's panel allows changing the port (requires restart)

#### 3. Programmatic (Script/Agent)

```python
# In an agent script
import os
import subprocess

ports = [9876, 9877, 9878]
for i, port in enumerate(ports):
    env = os.environ.copy()
    env['BLENDER_PORT'] = str(port)
    subprocess.Popen(['blender', f'project-{i}.blend'], env=env)
```

---

## Registry File Structure

### Location
`config/blender-instances.json`

### Schema

```json
{
  "instances": [
    {
      "instance_id": "blender-9876",
      "port": 9876,
      "host": "127.0.0.1",
      "pid": 12345,
      "blender_version": "4.1.1",
      "file": "/path/to/project-a.blend",
      "scene": "Scene",
      "objects": 42,
      "status": "idle",
      "claimed_by": null,
      "last_heartbeat": "2026-03-24T10:15:32.123Z",
      "created_at": "2026-03-24T09:00:00.000Z"
    },
    {
      "instance_id": "blender-9877",
      "port": 9877,
      "host": "127.0.0.1",
      "pid": 12346,
      "blender_version": "4.1.1",
      "file": "/path/to/project-b.blend",
      "scene": "Scene",
      "objects": 67,
      "status": "rendering",
      "claimed_by": "animation-agent-task-123",
      "last_heartbeat": "2026-03-24T10:15:30.456Z",
      "created_at": "2026-03-24T09:05:00.000Z"
    }
  ],
  "last_updated": "2026-03-24T10:15:32.500Z"
}
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `instance_id` | string | Unique identifier (e.g., `blender-9876`) |
| `port` | int | TCP port (9876–9886) |
| `host` | string | Hostname/IP (typically `127.0.0.1`) |
| `pid` | int | OS process ID |
| `blender_version` | string | Blender version (e.g., `4.1.1`) |
| `file` | string | Full path to loaded .blend file |
| `scene` | string | Active scene name |
| `objects` | int | Total object count in scene |
| `status` | string | `idle`, `rendering`, `processing`, `error` |
| `claimed_by` | string or null | Task/agent ID that claimed this instance, or `null` if free |
| `last_heartbeat` | ISO 8601 | Last successful ping from this instance |
| `created_at` | ISO 8601 | When this instance was registered |

---

## Instance Lifecycle & Claiming

### 1. Discovery

When the MCP server starts (or on demand):

```python
discovered = discover_instances(port_range=(9876, 9886))
# Returns: {"blender-9876": {...}, "blender-9877": {...}, ...}
```

The discovery probe:
- Tries to connect to each port in the range
- Sends a `ping` command
- Records metadata from the response
- Updates the registry file

### 2. Claiming (Reservation)

Before an agent uses an instance:

```python
claim_instance(instance_id="blender-9876", agent_id="animation-task-xyz")
# Returns: success | error if already claimed
```

Claiming:
- Marks the instance as `claimed_by: "animation-task-xyz"`
- Updates `last_heartbeat` timestamp
- Writes the registry file
- Returns error if instance is already claimed by another agent

### 3. Using

The agent sends commands to the claimed port:

```python
send_command_to(port=9876, command="render_animation", params={...})
```

### 4. Releasing

When done, the agent releases the instance:

```python
release_instance(instance_id="blender-9876")
# Clears claimed_by, resets status to "idle"
```

Release:
- Sets `claimed_by = null`
- Updates `last_heartbeat`
- Writes the registry file

---

## Code Integration Points

### Addon (openclaw_blender_bridge.py)

The addon already reads `BLENDER_PORT` via:
```python
PORT = int(os.environ.get("OPENCLAW_PORT", "9876"))
INSTANCE_ID = os.environ.get("OPENCLAW_INSTANCE", f"blender-{PORT}")
```

No changes needed if users set `OPENCLAW_PORT` before launching Blender.

**Optional enhancement**: Add an addon preference UI to change port without restarting.

### MCP Server (blender_mcp_server.py)

The server already has partial multi-instance support via:
- `discover_instances(port_range)` function
- `send_command_to(port, command, params)` function
- `_instance_registry` dictionary

**Modifications needed**:
1. Add registry file I/O (`load_registry()`, `save_registry()`)
2. Add claiming/releasing functions
3. Add heartbeat monitoring
4. Update tools to accept `instance_id` parameter

### Agents / Tasks

Agents should:
1. Call `discover_instances()` at startup
2. Choose or query for a free instance
3. Call `claim_instance()` before using
4. Send commands to the claimed port
5. Call `release_instance()` when done

---

## Example Agent Workflow

```python
from blender_mcp_server import discover_instances, claim_instance, release_instance, send_command_to

# Step 1: Discover all running Blender instances
instances = discover_instances()
print(f"Found {len(instances)} instances: {list(instances.keys())}")

# Step 2: Find a free instance (claimed_by is null)
free_instance = None
for inst_id, inst in instances.items():
    if inst.get("claimed_by") is None:
        free_instance = inst_id
        break

if not free_instance:
    print("No free Blender instances available")
    exit(1)

port = instances[free_instance]["port"]
print(f"Claiming instance {free_instance} on port {port}")

# Step 3: Claim the instance
claim_instance(free_instance, agent_id="my-animation-task-001")

# Step 4: Use the instance
try:
    result = send_command_to(port, "render_animation", {"frames": 100})
    print(f"Render result: {result}")
finally:
    # Step 5: Release the instance
    release_instance(free_instance)
    print(f"Released instance {free_instance}")
```

---

## Monitoring & Health Checks

### Heartbeat

Each instance records a `last_heartbeat` timestamp when:
- Responding to a `ping` command
- Completing a render or operation
- Updating scene metadata

### Stale Instance Detection

The registry loader should detect and mark instances as stale if:
- `last_heartbeat` is older than 5 minutes
- Port connection fails during discovery

### Cleanup

Optionally, agents can:
1. Probe for stale instances
2. Attempt to reconnect
3. Remove from registry if truly dead

Example:
```python
def prune_dead_instances(registry_path, heartbeat_timeout_sec=300):
    """Remove instances with stale heartbeats."""
    now = datetime.utcnow()
    registry = load_registry(registry_path)
    
    alive = []
    for inst in registry["instances"]:
        last_beat = datetime.fromisoformat(inst["last_heartbeat"])
        age = (now - last_beat).total_seconds()
        if age < heartbeat_timeout_sec:
            alive.append(inst)
    
    registry["instances"] = alive
    save_registry(registry_path, registry)
```

---

## Configuration via .env

Users can set in `.env`:

```env
# Default port for a single Blender instance
BLENDER_PORT=9876

# Host (if not localhost)
OPENCLAW_HOST=127.0.0.1

# Port range for discovery (optional)
BLENDER_PORT_RANGE=9876:9900

# Registry location (optional)
BLENDER_REGISTRY_PATH=config/blender-instances.json

# Heartbeat timeout in seconds
BLENDER_HEARTBEAT_TIMEOUT=300
```

---

## Future Enhancements

1. **Persistence**: Save registry to JSON file and reload at server startup
2. **Auto-cleanup**: Periodically prune dead instances based on heartbeat
3. **Addon GUI**: Port configuration in Blender preferences UI
4. **Distributed**: Support multiple machines (change BLENDER_HOST per instance)
5. **Queuing**: If no free instance, queue agent task and auto-retry
6. **Metrics**: Track total instances, claim/release rates, average utilization
7. **Failover**: If claimed instance dies, auto-release and notify agent

---

## Troubleshooting

### Port Already in Use

```bash
# Find process using port 9876
lsof -i :9876

# Kill it if needed
kill -9 <PID>
```

### No Free Instances

```python
# Check status of all instances
from blender_mcp_server import discover_instances
instances = discover_instances()
for inst_id, inst in instances.items():
    print(f"{inst_id}: claimed_by={inst.get('claimed_by')}, status={inst.get('status')}")
```

### Connection Refused

Ensure Blender is running:
```bash
ps aux | grep blender
# Should see process with BLENDER_PORT=9876 (or other port)
```

### Registry Out of Sync

Manually regenerate:
```python
from blender_mcp_server import discover_instances, save_registry
instances = discover_instances(port_range=(9876, 9886))
save_registry("config/blender-instances.json", instances)
```

---

## Summary

Multi-instance support is achieved through:

1. **Environment-based port assignment**: Each Blender instance sets `BLENDER_PORT` on launch
2. **Registry file**: Tracks all instances, their status, and claims
3. **Claiming/releasing protocol**: Agents reserve instances to avoid conflicts
4. **Auto-discovery**: MCP server probes port range to find running instances
5. **Heartbeat monitoring**: Detects stale instances and enables health tracking

This design allows unlimited agents to work on different Blender projects in parallel without conflicts.
