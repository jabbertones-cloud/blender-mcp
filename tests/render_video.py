"""Render the physics crash as PNG frames then convert to MP4."""
import socket, json, time, subprocess

def send_cmd(cmd, timeout=600):
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

print("Rendering 144 frames at 50% res (960x540)...")
code = f"""
import bpy, os
scene = bpy.context.scene
cam = bpy.data.objects.get("Cam_BirdEye")
if cam:
    scene.camera = cam
os.makedirs("{frames_dir}", exist_ok=True)
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = "{frames_dir}/frame_"
scene.render.resolution_percentage = 50
scene.frame_start = 1
scene.frame_end = 144
bpy.ops.render.render(animation=True)
print("FRAMES_DONE")
"""
r = send_cmd({'command': 'execute_python', 'params': {'code': code}}, timeout=600)
print(f"Blender result: {str(r)[:100]}")

# Convert to MP4 with ffmpeg
print("\nConverting to MP4 with ffmpeg...")
try:
    result = subprocess.run([
        'ffmpeg', '-y',
        '-framerate', '24',
        '-i', f'{frames_dir}/frame_%04d.png',
        '-c:v', 'libx264',
        '-pix_fmt', 'yuv420p',
        '-crf', '20',
        f'{renders_dir}/physics_crash.mp4'
    ], capture_output=True, text=True, timeout=120)
    if result.returncode == 0:
        print(f"Video saved: {renders_dir}/physics_crash.mp4")
    else:
        print(f"ffmpeg error: {result.stderr[:200]}")
except FileNotFoundError:
    print("ffmpeg not found — trying with Blender's bundled ffmpeg or alternative")
    # Try with system ffmpeg path
    import shutil
    ffmpeg_path = shutil.which('ffmpeg')
    if not ffmpeg_path:
        print("No ffmpeg available. PNG frames saved — convert manually:")
        print(f"  ffmpeg -framerate 24 -i {frames_dir}/frame_%04d.png -c:v libx264 -pix_fmt yuv420p {renders_dir}/physics_crash.mp4")
except Exception as e:
    print(f"Error: {e}")

print("\nDone!")
