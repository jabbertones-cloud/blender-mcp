#!/usr/bin/env python3
"""
Master launcher: Sends each portfolio scene script to Blender bridge for execution.
Runs sequentially (each scene wipes the scene clean).
Logs progress to renders/portfolio_render_log.txt
"""
import socket
import json
import time
import os

BRIDGE_HOST = "127.0.0.1"
BRIDGE_PORT = 9876
LOG_FILE = os.path.expanduser("~/claw-architect/openclaw-blender-mcp/renders/portfolio_render_log.txt")
SCRIPTS_DIR = os.path.expanduser("~/claw-architect/openclaw-blender-mcp/tests")

def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def send_to_bridge(code, timeout=1200):
    """Send Python code to Blender bridge, wait for result."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect((BRIDGE_HOST, BRIDGE_PORT))
    msg = json.dumps({"command": "execute_python", "params": {"code": code}})
    s.sendall(msg.encode() + b"\n")
    
    data = b""
    while True:
        try:
            chunk = s.recv(65536)
            if not chunk:
                break
            data += chunk
            # Try to parse — if valid JSON, we're done
            try:
                json.loads(data.decode())
                break
            except json.JSONDecodeError:
                continue
        except socket.timeout:
            log("WARNING: Socket timeout, returning partial data")
            break
    s.close()
    
    if data:
        try:
            return json.loads(data.decode())
        except json.JSONDecodeError:
            return {"error": f"Invalid JSON response: {data[:200]}"}
    return {"error": "No data received"}

def run_scene(scene_num):
    """Load and execute a scene script via bridge."""
    script_path = os.path.join(SCRIPTS_DIR, f"portfolio_scene_{scene_num}.py")
    if not os.path.exists(script_path):
        log(f"ERROR: {script_path} not found")
        return False
    
    with open(script_path, "r") as f:
        code = f.read()
    
    log(f"=== Starting Scene {scene_num} ===")
    log(f"Script: {script_path}")
    log(f"Sending to bridge ({len(code)} chars)...")
    
    start = time.time()
    result = send_to_bridge(code, timeout=1200)  # 20 min timeout per scene
    elapsed = time.time() - start
    
    if "error" in result and result.get("error"):
        log(f"ERROR Scene {scene_num}: {result['error'][:200]}")
        return False
    
    r = result.get("result", {})
    log(f"Scene {scene_num} result: {r}")
    log(f"Scene {scene_num} completed in {elapsed:.0f}s")
    return True

# ── Main ──
if __name__ == "__main__":
    log("=" * 60)
    log("PORTFOLIO RENDER — 4 SCENES, 20 CAMERAS")
    log("=" * 60)
    
    os.makedirs(os.path.expanduser("~/claw-architect/openclaw-blender-mcp/renders/portfolio/"), exist_ok=True)
    
    total_start = time.time()
    results = {}
    
    for scene_num in range(1, 5):
        success = run_scene(scene_num)
        results[f"scene_{scene_num}"] = "OK" if success else "FAILED"
        if scene_num < 4:
            log("Cooling down 5s before next scene...")
            time.sleep(5)
    
    total_elapsed = time.time() - total_start
    
    log("=" * 60)
    log(f"ALL DONE in {total_elapsed:.0f}s ({total_elapsed/60:.1f} min)")
    for k, v in results.items():
        log(f"  {k}: {v}")
    log("=" * 60)
    
    # Check renders
    render_dir = os.path.expanduser("~/claw-architect/openclaw-blender-mcp/renders/portfolio/")
    renders = sorted([f for f in os.listdir(render_dir) if f.endswith(".png")])
    log(f"Total renders: {len(renders)}")
    for r in renders:
        size = os.path.getsize(os.path.join(render_dir, r))
        log(f"  {r}: {size/1024/1024:.1f} MB")
