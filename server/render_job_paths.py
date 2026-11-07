"""File-system boundary for local, saved-scene render jobs."""
import os
from uuid import UUID
from pathlib import Path


def root():
    value = os.getenv('BLENDER_RENDER_ROOT') or os.getenv('BLENDER_QUALITY_ROOT')
    if not value:
        raise ValueError('BLENDER_RENDER_ROOT or BLENDER_QUALITY_ROOT is required')
    target = Path(value).expanduser().resolve(strict=True)
    if not target.is_dir():
        raise ValueError('Render root is not a directory')
    return target


def scene_path(value):
    if not isinstance(value, str) or not value:
        raise ValueError('A saved scene path is required')
    file = Path(value).expanduser().resolve(strict=True)
    if file.suffix.lower() != '.blend' or not file.is_file() or not file.is_relative_to(root()):
        raise ValueError('Scene must be a .blend file inside the authorized workspace')
    return file


def output_path(job_id):
    try:
        if not isinstance(job_id, str) or str(UUID(job_id)) != job_id:
            raise ValueError('Invalid render job ID')
    except (ValueError, AttributeError) as exc:
        raise ValueError('Invalid render job ID') from exc
    folder = root() / 'Blender MCP Renders'
    folder.mkdir(exist_ok=True)
    folder = folder.resolve(strict=True)
    if not folder.is_relative_to(root()):
        raise ValueError('Render output folder escapes the authorized workspace')
    target = folder / (job_id + '.png')
    if target.is_symlink():
        raise ValueError('Render output must not be a symlink')
    return target
