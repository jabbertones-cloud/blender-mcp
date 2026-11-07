"""Trusted native bpy render script, never model-written Python."""
import os
from pathlib import Path
import bpy

output = Path(os.environ['BLENDER_MCP_RENDER_TEMP'])
scene = bpy.context.scene
scene.render.engine = 'BLENDER_WORKBENCH' if os.getenv('BLENDER_MCP_RENDER_PREVIEW') == '1' else scene.render.engine
if os.getenv('BLENDER_MCP_RENDER_PREVIEW') == '1':
    scene.render.resolution_percentage = min(scene.render.resolution_percentage, 25)
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = str(output)
if scene.camera is None:
    raise RuntimeError('A saved scene with an active camera is required for rendering')
bpy.ops.render.render(write_still=True)
if not output.is_file():
    raise RuntimeError('Blender did not produce the requested render')
print('BLENDER_MCP_RENDER_FINISHED', output.stat().st_size)
