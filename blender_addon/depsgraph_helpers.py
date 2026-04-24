"""
Depsgraph Helpers - Correct Evaluated Mesh Access for Blender Addon
====================================================================

Per CGWire article "Build Reliable Export Tools with Blender's Depsgraph":
querying obj.data gives pre-modifier data. This is silently wrong whenever
a Subsurf, Array, Bevel, or other modifier exists.

Always use the evaluated mesh via the depsgraph for:
  - Vertex/triangle counts
  - Bounding boxes
  - Mesh geometry queries
  - Scene snapshots

This module handles cleanup safely via context managers.

Ref: https://blender.stackexchange.com/questions/160718/get-mesh-with-modifiers
     https://docs.blender.org/api/current/bpy.types.Depsgraph.html
"""

from contextlib import contextmanager
from typing import Optional, Tuple

try:
    import bpy
    from bpy.types import Mesh, Object
    from mathutils import Vector
except ImportError:
    bpy = None


class DepsgraphError(RuntimeError):
    """Raised when depsgraph operations fail outside Blender."""

    pass


def get_evaluated_mesh(obj: "Object") -> Tuple["Mesh", callable]:
    """
    Get the evaluated mesh for an object (post-modifiers).

    Args:
        obj: Blender object

    Returns:
        (evaluated_mesh, cleanup_function)

    Note:
        CRITICAL: cleanup_function must be called in a finally block.
        Prefer evaluated_mesh context manager for automatic cleanup.
    """
    if bpy is None:
        raise DepsgraphError("depsgraph_helpers requires running inside Blender")

    try:
        dg = bpy.context.evaluated_depsgraph_get()
        obj_eval = obj.evaluated_get(dg)
        mesh = obj_eval.data

        def cleanup():
            # No explicit cleanup needed for Blender 3.6+
            # Depsgraph lifecycle is managed by Blender
            pass

        return mesh, cleanup

    except Exception as e:
        raise DepsgraphError(f"Failed to get evaluated mesh: {e}")


@contextmanager
def evaluated_mesh(obj: "Object"):
    """
    Context manager for safe evaluated mesh access.

    Usage:
        with evaluated_mesh(obj) as (mesh_eval, obj_eval):
            vertex_count = len(mesh_eval.vertices)

    Yields:
        (evaluated_mesh, evaluated_object)
    """
    if bpy is None:
        raise DepsgraphError("depsgraph_helpers requires running inside Blender")

    try:
        dg = bpy.context.evaluated_depsgraph_get()
        obj_eval = obj.evaluated_get(dg)
        mesh_eval = obj_eval.data
        yield mesh_eval, obj_eval
    except Exception as e:
        raise DepsgraphError(f"Failed to get evaluated mesh context: {e}")
    finally:
        # Cleanup handled by Blender's depsgraph lifecycle
        pass


def evaluated_bbox_world(obj: "Object") -> dict:
    """
    Get the world-space bounding box of an object (post-modifiers).

    Args:
        obj: Blender object

    Returns:
        {
            "min": [x, y, z],
            "max": [x, y, z],
            "center": [x, y, z],
            "dimensions": [width, depth, height]
        }
    """
    if bpy is None:
        raise DepsgraphError("depsgraph_helpers requires running inside Blender")

    try:
        dg = bpy.context.evaluated_depsgraph_get()
        obj_eval = obj.evaluated_get(dg)

        # Get all vertices in world space
        if hasattr(obj_eval.data, "vertices"):
            verts = [obj_eval.matrix_world @ Vector(v.co) for v in obj_eval.data.vertices]
        else:
            # Fallback for non-mesh objects
            return {
                "min": list(obj.location),
                "max": list(obj.location),
                "center": list(obj.location),
                "dimensions": [0, 0, 0],
            }

        if not verts:
            return {
                "min": list(obj.location),
                "max": list(obj.location),
                "center": list(obj.location),
                "dimensions": [0, 0, 0],
            }

        # Compute bounds
        xs = [v.x for v in verts]
        ys = [v.y for v in verts]
        zs = [v.z for v in verts]

        min_pt = [min(xs), min(ys), min(zs)]
        max_pt = [max(xs), max(ys), max(zs)]
        center = [(min_pt[i] + max_pt[i]) / 2 for i in range(3)]
        dims = [max_pt[i] - min_pt[i] for i in range(3)]

        return {
            "min": min_pt,
            "max": max_pt,
            "center": center,
            "dimensions": dims,
        }

    except Exception as e:
        raise DepsgraphError(f"Failed to compute bbox: {e}")


def evaluated_vertex_count(obj: "Object") -> int:
    """
    Get vertex count of evaluated mesh.

    Args:
        obj: Blender object

    Returns:
        Vertex count (post-modifiers)
    """
    if bpy is None:
        raise DepsgraphError("depsgraph_helpers requires running inside Blender")

    try:
        dg = bpy.context.evaluated_depsgraph_get()
        obj_eval = obj.evaluated_get(dg)

        if hasattr(obj_eval.data, "vertices"):
            return len(obj_eval.data.vertices)
        return 0

    except Exception as e:
        raise DepsgraphError(f"Failed to get vertex count: {e}")


def evaluated_triangle_count(obj: "Object") -> int:
    """
    Get triangle count of evaluated mesh (post-modifiers).

    Args:
        obj: Blender object

    Returns:
        Triangle count
    """
    if bpy is None:
        raise DepsgraphError("depsgraph_helpers requires running inside Blender")

    try:
        dg = bpy.context.evaluated_depsgraph_get()
        obj_eval = obj.evaluated_get(dg)

        if hasattr(obj_eval.data, "polygons"):
            # Count polygons that are triangles or quad (split quads into 2 triangles)
            tri_count = 0
            for poly in obj_eval.data.polygons:
                if len(poly.vertices) == 3:
                    tri_count += 1
                elif len(poly.vertices) == 4:
                    tri_count += 2
                else:
                    # N-gon: split into n-2 triangles
                    tri_count += len(poly.vertices) - 2
            return tri_count
        return 0

    except Exception as e:
        raise DepsgraphError(f"Failed to get triangle count: {e}")


def scene_object_snapshot(scene: Optional["bpy.types.Scene"] = None) -> dict:
    """
    Get a scene snapshot for OpenTelemetry scene-diff attributes.

    Args:
        scene: Blender scene (defaults to context.scene)

    Returns:
        {
            "objects": [
                {
                    "name": str,
                    "type": str,
                    "bbox": {...},
                    "vertices": int,
                    "triangles": int,
                    "modifiers": int,
                    "visible": bool,
                }
            ],
            "total_vertices": int,
            "total_triangles": int,
            "timestamp": float,
        }
    """
    if bpy is None:
        raise DepsgraphError("depsgraph_helpers requires running inside Blender")

    import time

    if scene is None:
        scene = bpy.context.scene

    objects_info = []
    total_verts = 0
    total_tris = 0

    try:
        for obj in scene.objects:
            if obj.type == "MESH":
                vert_count = evaluated_vertex_count(obj)
                tri_count = evaluated_triangle_count(obj)
                total_verts += vert_count
                total_tris += tri_count

                objects_info.append(
                    {
                        "name": obj.name,
                        "type": obj.type,
                        "bbox": evaluated_bbox_world(obj),
                        "vertices": vert_count,
                        "triangles": tri_count,
                        "modifiers": len(obj.modifiers),
                        "visible": obj.visible_get(),
                    }
                )
            else:
                objects_info.append(
                    {
                        "name": obj.name,
                        "type": obj.type,
                        "vertices": 0,
                        "triangles": 0,
                        "modifiers": 0,
                        "visible": obj.visible_get(),
                    }
                )

        return {
            "objects": objects_info,
            "total_vertices": total_verts,
            "total_triangles": total_tris,
            "timestamp": time.time(),
        }

    except Exception as e:
        raise DepsgraphError(f"Failed to build scene snapshot: {e}")
