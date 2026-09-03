"""Numeric motion QA: foot skate and pops from evaluated bone samples."""
from __future__ import annotations

from typing import Iterable


def score_motion_qa(samples: Iterable[dict], *, skate_limit: float = 0.02, pop_limit: float = 0.25) -> dict:
    rows = list(samples or [])
    by_bone: dict[str, list[dict]] = {}
    for row in rows:
        bone = str(row.get("bone") or "root")
        by_bone.setdefault(bone, []).append(row)

    skate_max = 0.0
    pop_max = 0.0
    skate_hits = 0
    pop_hits = 0
    for bone_rows in by_bone.values():
        ordered = sorted(bone_rows, key=lambda r: int(r.get("frame") or 0))
        prev = None
        for row in ordered:
            loc = list(row.get("location") or [0, 0, 0])
            if prev is not None:
                dx = abs(loc[0] - prev[0])
                dy = abs(loc[1] - prev[1])
                dz = abs(loc[2] - prev[2])
                planar = (dx * dx + dy * dy) ** 0.5
                if bool(row.get("contact") or prev.get("contact")):
                    skate_max = max(skate_max, planar)
                    if planar > skate_limit:
                        skate_hits += 1
                pop_max = max(pop_max, dz)
                if dz > pop_limit:
                    pop_hits += 1
            prev = loc
    passed = skate_hits == 0 and pop_hits == 0
    return {
        "passed": passed,
        "foot_skate_max": round(skate_max, 6),
        "pop_max": round(pop_max, 6),
        "skate_hits": skate_hits,
        "pop_hits": pop_hits,
    }
