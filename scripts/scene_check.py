#!/usr/bin/env python3
import socket, json
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(30)
try:
    sock.connect(('127.0.0.1', 9876))
    cmd = {'command': 'execute_python', 'code': 'import bpy\nresult = str(len(bpy.data.objects))'}
    sock.sendall(json.dumps(cmd).encode('utf-8'))
    data = b''
    while True:
        chunk = sock.recv(8192)
        if not chunk:
            break
        data += chunk
    sock.close()
    print("Connected! Response:", data.decode('utf-8')[:500])
except Exception as e:
    print(f"ERROR: {e}")
