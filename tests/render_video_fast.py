"""Render a shorter animation (every 3rd frame) then convert to MP4."""
import socket, json, subprocess, os

def send_cmd(cmd, timeout=300):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(('127.0.0.1', 9876))
        msg = json.dumps(cmd) + '\n'
        s.sendall(msg.encode())
        data = b''
        while True:
            chunk = s.recv(16384)
            if not chunk:
                break
            data += chunk
            try:
                json.loads(data.decode())
                break
            except:
                continue
        result = json.loads(data.decode())
        return result.get('result', result)
    except Exception as e:
        return {'error': str(e)}
    finally:
        s.close()

renders_dir = "/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders"
frames_dir = f"{renders_dir}/anim_frames"
os.makedirs(frames_dir, exist_ok=True)

# Render every 3rd frame at 25% resolution for speed
print("Rendering every 3rd frame (48 frames) at 480x270...")
code = f"""
import bpy, os
scene = bpy.context.scene
cam = bpy.data.objects.get("Cam_BirdEye")
if cam:
    scene.camera = cam
os.makedirs("{frames_dir}", exist_ok=True)
scene.render.image_settings.file_format = "PNG"
scene.render.resolution_percentage = 25
idx = 0
for f in range(1, 145, 3):
    scene.frame_set(f)
    scene.render.filepath = "{frames_dir}/frame_" + str(idx).zfill(4)
    bpy.ops.render.render(write_still=True)
    idx += 1
print("DONE", idx, "frames")
"""
r = send_cmd({'command': 'execute_python', 'params': {'code': code}}, timeout=300)
print(f"Result: {str(r)[:100]}")

# Check frames
frame_count = len([f for f in os.listdir(frames_dir) if f.endswith('.png')])
print(f"Frames rendered: {frame_count}")

# Convert to MP4
print("Converting to MP4...")
try:
    result = subprocess.run([
        'ffmpeg', '-y',
        '-framerate', '8',
        '-i', f'{frames_dir}/frame_%04d.png',
        '-c:v', 'libx264',
        '-pix_fmt', 'yuv420p',
        '-crf', '23',
        '-vf', 'scale=960:540',
        f'{renders_dir}/physics_crash.mp4'
    ], capture_output=True, text=True, timeout=60)
    if result.returncode == 0:
        size = os.path.getsize(f'{renders_dir}/physics_crash.mp4')
        print(f"Video saved: physics_crash.mp4 ({size/1024:.0f} KB)")
    else:
        print(f"ffmpeg error: {result.stderr[:300]}")
except FileNotFoundError:
    print("ffmpeg not found. Frames are saved for manual conversion.")
except Exception as e:
    print(f"Error: {e}")
