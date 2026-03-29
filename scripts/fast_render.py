"""
Fast Micro-Render — for rapid iteration.
Override render settings to get a preview in ~1-2 min on CPU.
Usage: blender -b file.blend -P fast_render.py -- --output /tmp/preview.png [--samples 64] [--pct 25]

This lets us test 10+ variations in the time one full render takes.
"""
import bpy
import sys

# Parse args after '--'
argv = sys.argv
args_start = argv.index("--") + 1 if "--" in argv else len(argv)
script_args = argv[args_start:]

# Defaults
output = "/tmp/fast_preview.png"
samples = 64
pct = 25  # resolution percentage

i = 0
while i < len(script_args):
    if script_args[i] == "--output" and i + 1 < len(script_args):
        output = script_args[i + 1]; i += 2
    elif script_args[i] == "--samples" and i + 1 < len(script_args):
        samples = int(script_args[i + 1]); i += 2
    elif script_args[i] == "--pct" and i + 1 < len(script_args):
        pct = int(script_args[i + 1]); i += 2
    else:
        i += 1

print(f"FAST RENDER: {samples} samples, {pct}% resolution, output={output}")

s = bpy.context.scene
s.cycles.samples = samples
s.cycles.use_adaptive_sampling = True
s.cycles.adaptive_threshold = 0.05  # Very aggressive adaptive sampling
s.cycles.use_denoising = True
s.render.resolution_percentage = pct
s.render.filepath = output
s.render.image_settings.file_format = "PNG"

# Force CPU (Metal hangs on this machine)
s.cycles.device = "CPU"

# Render
bpy.ops.render.render(write_still=True)
print(f"FAST RENDER COMPLETE: {output}")
