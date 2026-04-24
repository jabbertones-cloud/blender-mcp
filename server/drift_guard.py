"""
Behavioral Drift Detector - EMA-based Session Monitoring
=========================================================

Stateful per-session drift detector using Exponential Moving Average (EMA).
Per SAFi Spirit engine research: pure math, zero LLM cost.

Tracks object mesh complexity, modifier density, lighting, cameras, materials.
Computes cosine distance between current behavior vector and baseline.

References:
  - SAFi Spirit: https://arxiv.org/abs/2410.06475
  - EMA smoothing: β=0.9 (90% history, 10% current turn)
  - Cosine distance: standard L2-normalized dot product
  - Drift thresholds: warn at 0.3, alert at 0.5
"""

import math
from dataclasses import dataclass, field
from typing import Dict, Optional, Any


@dataclass
class BehaviorVector:
    """Normalized behavior profile from a Blender scene snapshot."""

    avg_vertices_per_object: float = 0.0
    """Average vertex count per mesh object."""

    modifier_density: float = 0.0
    """Ratio of objects with modifiers to total mesh objects."""

    light_count: int = 0
    """Number of light objects in scene."""

    camera_focal_avg: float = 50.0
    """Average focal length (default 50 for PERSP cameras)."""

    triangle_ratio: float = 0.0
    """Ratio of triangles to quads (tri_count / quad_count, capped at 2.0)."""

    material_count: int = 0
    """Total unique materials in scene."""

    def to_array(self) -> list[float]:
        """Convert to list for cosine distance computation."""
        return [
            self.avg_vertices_per_object,
            self.modifier_density,
            float(self.light_count),
            self.camera_focal_avg,
            self.triangle_ratio,
            float(self.material_count),
        ]


@dataclass
class DriftMonitor:
    """
    Tracks behavioral drift for a single MCP session.

    Uses EMA to smooth measurements and detect deviations from baseline.
    """

    beta: float = 0.9
    """EMA smoothing factor (0.9 = 90% history, 10% current)."""

    warn_threshold: float = 0.3
    """Cosine distance threshold for warning status."""

    alert_threshold: float = 0.5
    """Cosine distance threshold for alert status."""

    _baseline: Optional[BehaviorVector] = field(default=None, init=False)
    """First registered behavior vector (immutable baseline)."""

    _ema_vector: Optional[BehaviorVector] = field(default=None, init=False)
    """Current EMA-smoothed behavior vector."""

    _turn_count: int = field(default=0, init=False)
    """Number of turns registered."""

    def register_turn(self, vector: BehaviorVector) -> Dict[str, Any]:
        """
        Register a new behavioral snapshot.

        Args:
            vector: BehaviorVector from scene snapshot

        Returns:
            {
                "drift_score": float (0.0-1.0),
                "baseline_turn": int,
                "current_turn": int,
                "status": "ok" | "warn" | "alert",
                "recommendation": str,
            }
        """
        self._turn_count += 1

        # Initialize baseline on first turn
        if self._baseline is None:
            self._baseline = vector
            self._ema_vector = vector
            return {
                "drift_score": 0.0,
                "baseline_turn": self._turn_count,
                "current_turn": self._turn_count,
                "status": "ok",
                "recommendation": "Baseline established",
            }

        # Update EMA
        old_array = self._ema_vector.to_array()
        new_array = vector.to_array()
        ema_array = [
            self.beta * old_array[i] + (1 - self.beta) * new_array[i]
            for i in range(len(old_array))
        ]
        self._ema_vector = BehaviorVector(
            avg_vertices_per_object=ema_array[0],
            modifier_density=ema_array[1],
            light_count=int(ema_array[2]),
            camera_focal_avg=ema_array[3],
            triangle_ratio=ema_array[4],
            material_count=int(ema_array[5]),
        )

        # Compute drift
        drift_score = cosine_distance(self._baseline.to_array(), ema_array)
        drift_score = max(0.0, min(1.0, drift_score))  # Clamp to [0, 1]

        # Determine status and recommendation
        if drift_score >= self.alert_threshold:
            status = "alert"
            recommendation = (
                f"Scene has drifted significantly (score {drift_score:.2f}). "
                "Consider checkpointing or reducing tool scope."
            )
        elif drift_score >= self.warn_threshold:
            status = "warn"
            recommendation = (
                f"Scene showing drift (score {drift_score:.2f}). "
                "Monitor for unexpected changes."
            )
        else:
            status = "ok"
            recommendation = f"Scene behavior stable (score {drift_score:.2f})."

        return {
            "drift_score": drift_score,
            "baseline_turn": 1,
            "current_turn": self._turn_count,
            "status": status,
            "recommendation": recommendation,
        }

    def baseline(self) -> Optional[BehaviorVector]:
        """Get the baseline behavior vector (first registered turn)."""
        return self._baseline

    def reset(self) -> None:
        """Clear all state (useful for new sessions)."""
        self._baseline = None
        self._ema_vector = None
        self._turn_count = 0

    def stats(self) -> Dict[str, Any]:
        """Get running statistics."""
        return {
            "turn_count": self._turn_count,
            "has_baseline": self._baseline is not None,
            "baseline": self._baseline.to_array() if self._baseline else None,
            "current_ema": self._ema_vector.to_array() if self._ema_vector else None,
        }


def cosine_distance(a: list[float], b: list[float]) -> float:
    """
    Compute cosine distance between two vectors.

    cosine_distance = 1 - (dot(a, b) / (||a|| * ||b||))
    Returns 1.0 for orthogonal vectors, 0.0 for identical.

    Args:
        a: First vector
        b: Second vector

    Returns:
        Cosine distance (0.0 to 1.0, or higher if vectors are very different)
    """
    if len(a) != len(b):
        raise ValueError("Vectors must have same length")

    # Dot product
    dot_product = sum(a[i] * b[i] for i in range(len(a)))

    # Magnitudes
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))

    # Avoid division by zero
    if mag_a == 0 or mag_b == 0:
        return 0.0 if dot_product == 0 else 1.0

    # Cosine similarity
    cosine_sim = dot_product / (mag_a * mag_b)

    # Clamp to [-1, 1] due to floating point errors
    cosine_sim = max(-1.0, min(1.0, cosine_sim))

    # Distance = 1 - similarity
    return 1.0 - cosine_sim


def extract_behavior_vector(scene_snapshot: Dict[str, Any]) -> BehaviorVector:
    """
    Build a BehaviorVector from a scene snapshot (from depsgraph_helpers).

    Args:
        scene_snapshot: Output from depsgraph_helpers.scene_object_snapshot()

    Returns:
        BehaviorVector with normalized fields
    """
    objects = scene_snapshot.get("objects", [])
    total_verts = scene_snapshot.get("total_vertices", 0)
    total_tris = scene_snapshot.get("total_triangles", 0)

    # Mesh object count
    mesh_count = sum(1 for obj in objects if obj.get("type") == "MESH")
    avg_verts = total_verts / mesh_count if mesh_count > 0 else 0.0

    # Modifier density
    modifier_count = sum(obj.get("modifiers", 0) for obj in objects)
    modifier_density = modifier_count / mesh_count if mesh_count > 0 else 0.0

    # Light count
    light_count = sum(1 for obj in objects if obj.get("type") == "LIGHT")

    # Camera focal (average, default 50)
    cameras = [obj for obj in objects if obj.get("type") == "CAMERA"]
    if cameras and "camera" in cameras[0]:
        focal_avg = sum(
            cam.get("camera", {}).get("lens", 50) for cam in cameras
        ) / len(cameras)
    else:
        focal_avg = 50.0

    # Triangle ratio (tri_count / quad_count, capped)
    # Count polygons from evaluated mesh
    quads = sum(1 for obj in objects if obj.get("type") == "MESH")  # Approximate
    triangle_ratio = total_tris / quads if quads > 0 else 0.0
    triangle_ratio = min(2.0, triangle_ratio)  # Cap at 2.0

    # Material count
    material_count = 0
    for obj in objects:
        materials = obj.get("materials")
        if isinstance(materials, list):
            material_count += len([m for m in materials if m])

    return BehaviorVector(
        avg_vertices_per_object=avg_verts,
        modifier_density=modifier_density,
        light_count=light_count,
        camera_focal_avg=focal_avg,
        triangle_ratio=triangle_ratio,
        material_count=material_count,
    )


class SessionDriftRegistry:
    """Registry mapping session_id -> DriftMonitor."""

    def __init__(self):
        self._monitors: Dict[str, DriftMonitor] = {}

    def get_or_create(self, session_id: str) -> DriftMonitor:
        """Get or create a DriftMonitor for a session."""
        if session_id not in self._monitors:
            self._monitors[session_id] = DriftMonitor()
        return self._monitors[session_id]

    def all_sessions(self) -> Dict[str, DriftMonitor]:
        """Get all active sessions."""
        return self._monitors.copy()

    def reset_session(self, session_id: str) -> None:
        """Reset a session's monitor."""
        if session_id in self._monitors:
            self._monitors[session_id].reset()

    def remove_session(self, session_id: str) -> None:
        """Remove a session from the registry."""
        self._monitors.pop(session_id, None)


# Module-level default registry
_default_registry = SessionDriftRegistry()


def default_registry() -> SessionDriftRegistry:
    """Get the module-level drift registry."""
    return _default_registry
