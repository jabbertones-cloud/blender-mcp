#!/usr/bin/env python3
"""
Diagnostic and lighting fix script for v11 day scenes.
Connects to Blender MCP on port 9876.
"""
import socket
import json
import time
import sys

def mcp_send(cmd, params=None):
    """Send JSON-RPC command to Blender MCP"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(60)
    s.connect(('127.0.0.1', 9876))
    
    request = {
        'jsonrpc': '2.0',
        'id': 1,
        'method': cmd,
        'params': params or {}
    }
    
    msg = json.dumps(request) + '\n'
    s.sendall(msg.encode())
    
    # Read response
    response_data = b''
    while True:
        try:
            chunk = s.recv(4096)
            if not chunk:
                break
            response_data += chunk
        except socket.timeout:
            break
    
    s.close()
    
    if not response_data:
        return None
    
    try:
        return json.loads(response_data.decode())
    except:
        return {'raw': response_data.decode()[:500]}

# Test connection
print("Testing MCP connection...")
resp = mcp_send('test')
print(f"Response: {resp}")
