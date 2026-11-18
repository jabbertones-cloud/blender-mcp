"""Read-only, human-reviewed lessons from Blender Replay recording exports.

This is intentionally NOT a replay engine. The recorder is a separate GPL-3.0
Blender extension; this module reads its portable JSON as untrusted evidence.
Only approved concise summaries can be found by the five-tool guided MCP.
No operator identifier or JSON property is ever executed by this module.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path

MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_LESSON_BYTES = 256 * 1024
MAX_EVENTS = 10000
MAX_STEPS = 400
MAX_LOADED = 100
_SLUG = re.compile(r"^[a-z][a-z0-9-]{1,62}$")
_CREATE_OPERATORS = {
    "MESH_OT_primitive_cube_add": "cube",
    "MESH_OT_primitive_uv_sphere_add": "sphere",
    "MESH_OT_primitive_cylinder_add": "cylinder",
    "MESH_OT_primitive_plane_add": "plane",
}
_TRANSFORM_OPERATORS = {
    "TRANSFORM_OT_translate",
    "TRANSFORM_OT_rotate",
    "TRANSFORM_OT_resize",
}
_FIELDS = ("location", "rotation_euler", "scale")
_INPUT_KEYS = ("location", "rotation", "scale")


def _clean(value, limit=120):
    """Operator names and goals are untrusted labels, never instructions."""
    if not isinstance(value, str):
        return ""
    cleaned = " ".join("".join(c for c in value if c.isprintable()).split())[:limit]
    lower = cleaned.lower()
    if ("://" in lower or "/users/" in lower or "\\users\\" in lower or
        any(marker in lower for marker in ("password=", "secret=", "api_key=", "bearer ", "authorization:"))):
        return "[redacted]"
    return cleaned


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _vector(value, size=3):
    if not isinstance(value, list) or len(value) != size:
        return None
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in value):
        return None
    return [round(float(v), 6) for v in value]


def _changed(a, b):
    return a is None or b is None or any(abs(x-y) > 1e-5 for x, y in zip(a, b))


def _lesson_path(root, slug):
    if not _SLUG.fullmatch(slug):
        raise ValueError("Lesson ID must be a lowercase safe slug (2-63 characters)")
    root = Path(root).expanduser().resolve()
    return root / (slug + ".lesson.json")


def _atomic_store(path, lesson, *, replace=False):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.exists() and not replace:
        raise ValueError("Lesson exists; use a different ID")
    if path.is_symlink():
        raise ValueError("Refusing symbolic link lesson")
    encoded = (json.dumps(lesson, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    if len(encoded) > MAX_LESSON_BYTES:
        raise ValueError("Lesson draft too large")
    temp = path.with_name("." + path.stem + ".tmp." + str(os.getpid()))
    with temp.open("xb") as file:
        os.chmod(temp, 0o600)
        file.write(encoded)
        file.flush()
        os.fsync(file.fileno())
    os.replace(temp, path)


def _load_lesson(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_LESSON_BYTES:
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return None
    if (not isinstance(doc, dict) or doc.get("schema_version") != 1
        or doc.get("key") != "lesson." + path.name.removesuffix(".lesson.json")
        or not isinstance(doc.get("steps"), list)
        or len(doc["steps"]) > MAX_STEPS):
        return None
    return doc


def compile_recording(recording, *, identifier, goal, source_hash):
    """Summarize observed facts and evidence indices; never emit executable code."""
    if not isinstance(recording, dict) or recording.get("schema_version") != 1:
        raise ValueError("Unsupported Blender Replay schema")
    events = recording.get("events")
    if not isinstance(events, list) or len(events) > MAX_EVENTS:
        raise ValueError("Invalid or excessively large recording event list")
    if not all(isinstance(e, dict) and e.get("type") in ("operator", "checkpoint", "context", "segment") for e in events):
        raise ValueError("Invalid recording event")
    steps = []
    known_objects = {}
    known_meshes = {}
    last_operator = None
    last_context = {}
    counts = {"operators": 0, "mapped_changes": 0, "review_required": 0,
              "unsupported": 0, "state_checkpoints": 0, "geometry_changes": 0}
    truncated = False

    def emit(kind, event_index, summary, *, capability=None, arguments=None, quality="observed", context=None):
        nonlocal truncated
        if len(steps) >= MAX_STEPS:
            truncated = True
            return
        row = {"kind": kind, "evidence_event": event_index,
               "summary": _clean(summary, 180), "confidence": quality}
        if capability is not None:
            row["candidate_capability"] = capability
            row["candidate_arguments"] = arguments or {}
        if context:
            row["precondition"] = {"active_object": _clean(context.get("active_object")),
                                   "mode": _clean(context.get("mode"), 32)}
        steps.append(row)

    for i, event in enumerate(events):
        event_type = event["type"]
        if event_type == "context":
            c = event.get("context")
            if isinstance(c, dict):
                last_context = c
            continue
        if event_type == "operator":
            counts["operators"] += 1
            identifier_ = event.get("idname")
            if not isinstance(identifier_, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{2,100}", identifier_):
                identifier_ = "UNKNOWN_OPERATOR"
            last_operator = identifier_
            if identifier_ in _TRANSFORM_OPERATORS:
                # A matching checkpoint supplies the actual named-object state.
                emit("operator", i, "Blender completed " + identifier_ + "; verify ensuing object-state checkpoint",
                     quality="operator_recorded", context=last_context)
            elif identifier_ in _CREATE_OPERATORS:
                emit("operator", i, "Blender added a " + _CREATE_OPERATORS[identifier_] +
                     "; match the created object in the ensuing checkpoint",
                     quality="operator_recorded", context=last_context)
            else:
                counts["unsupported"] += 1
                emit("unsupported_operator", i, "Recorded operator " + identifier_ +
                     " has no reviewed canonical mapping", quality="unmapped", context=last_context)
            continue
        if event_type != "checkpoint":
            continue
        counts["state_checkpoints"] += 1
        baseline = bool(event.get("baseline") or event.get("segment_baseline"))
        objects = event.get("objects", [])
        if not isinstance(objects, list):
            raise ValueError("Checkpoint objects must be an array")
        for obj in objects:
            if not isinstance(obj, dict) or not isinstance(obj.get("name"), str):
                continue
            name = _clean(obj["name"], 120)
            transform = obj.get("transform")
            transform = transform if isinstance(transform, dict) else {}
            previous = known_objects.get(name)
            if previous is None and not baseline:
                primitive = _CREATE_OPERATORS.get(last_operator)
                if primitive and len(objects) == 1:
                    loc = _vector(transform.get("location"))
                    args = {"type": primitive, "name": name}
                    if loc is not None:
                        args["location"] = loc
                    emit("object_added", i, "Observed new object " + name + " after " + last_operator,
                         capability="scene.create_object", arguments=args,
                         quality="candidate_requires_replay", context=last_context)
                    counts["mapped_changes"] += 1
                else:
                    counts["review_required"] += 1
                    emit("object_added", i, "Object " + name + " appeared; creation method not proven",
                         quality="needs_review", context=last_context)
            if previous is not None and not baseline:
                args = {"name": name}
                updated = []
                for field, input_field in zip(_FIELDS, _INPUT_KEYS):
                    a = _vector(previous.get(field))
                    b = _vector(transform.get(field))
                    if b is None or not _changed(a, b):
                        continue
                    args[input_field] = [round(math.degrees(v), 5) for v in b] if field == "rotation_euler" else b
                    updated.append(input_field)
                if updated:
                    supporting_op = last_operator in _TRANSFORM_OPERATORS
                    quality = "candidate_requires_replay" if supporting_op else "state_only_needs_review"
                    emit("transform_change", i, "Observed " + name + " " + ", ".join(updated),
                         capability="scene.modify_object", arguments=args,
                         quality=quality, context=last_context)
                    if supporting_op:
                        counts["mapped_changes"] += 1
                    else:
                        counts["review_required"] += 1
                if previous.get("material_slots") != obj.get("material_slots"):
                    counts["review_required"] += 1
                    emit("material_change", i, "Material slots of " + name + " changed",
                         quality="material_requires_authoring", context=last_context)
                if previous.get("modifiers") != obj.get("modifiers"):
                    counts["review_required"] += 1
                    emit("modifier_change", i, "Modifier stack of " + name + " changed",
                         quality="modifier_requires_authoring", context=last_context)
            known_objects[name] = {
                **{f: transform.get(f) for f in _FIELDS},
                "material_slots": obj.get("material_slots", []),
                "modifiers": obj.get("modifiers", []),
            }
        for name in event.get("deleted_objects", []):
            if not isinstance(name, str):
                continue
            known_objects.pop(_clean(name), None)
            if not baseline:
                counts["review_required"] += 1
                emit("object_deleted", i, "Observed deletion of " + _clean(name),
                     quality="deletion_requires_review")
        meshes = event.get("meshes", [])
        if isinstance(meshes, list):
            for mesh in meshes:
                if not isinstance(mesh, dict) or not isinstance(mesh.get("object"), str):
                    continue
                name = _clean(mesh["object"])
                digest = mesh.get("digest")
                prior = known_meshes.get(name)
                if prior and digest and digest != prior and not baseline:
                    counts["geometry_changes"] += 1
                    counts["review_required"] += 1
                    emit("geometry_change", i, "Mesh topology or coordinates changed for " + name +
                         "; requires separate geometry verification", quality="mesh_checkpoint_only")
                if isinstance(digest, str):
                    known_meshes[name] = digest
        if not baseline and (objects or event.get("deleted_objects")):
            last_operator = None

    return {
        "schema_version": 1,
        "key": "lesson." + identifier,
        "name": _clean(recording.get("name"), 120) or identifier,
        "goal": _clean(goal, 180),
        "provenance": {
            "recorder": "sabetAI/blender-replay",
            "source_sha256": source_hash,
            "blender_version": _clean(recording.get("blender_version"), 30),
            "recorder_version": _clean(recording.get("recorder_version"), 30),
            "event_count": len(events),
            "warnings_count": len(recording.get("warnings", [])) if isinstance(recording.get("warnings", []), list) else -1,
        },
        "coverage": {**counts, "truncated": truncated},
        "steps": steps,
        "review": {"status": "draft", "note": "Operator and checkpoint summaries are evidence, not executable instructions."},
    }


def import_recording(source, *, directory, identifier, goal):
    path = Path(source).expanduser().resolve(strict=True)
    if not path.name.endswith(".chronicle.json") or not path.is_file() or path.stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError("Source must be a bounded .chronicle.json file")
    data = path.read_bytes()
    recording = json.loads(data)
    destination = _lesson_path(directory, identifier)
    lesson = compile_recording(recording, identifier=identifier, goal=goal, source_hash=_digest(data))
    _atomic_store(destination, lesson)
    return lesson


def approve_lesson(identifier, *, directory, source_hash, reviewer, accept_incomplete=False):
    path = _lesson_path(directory, identifier)
    lesson = _load_lesson(path)
    if not lesson:
        raise ValueError("Lesson missing or invalid")
    if lesson.get("provenance", {}).get("source_sha256") != source_hash:
        raise ValueError("Source digest mismatch: re-review exact recording")
    if lesson.get("coverage", {}).get("truncated") and not accept_incomplete:
        raise ValueError("Truncated lesson cannot be approved without explicit acknowledgement")
    if not _clean(reviewer):
        raise ValueError("Reviewer name required")
    lesson["review"] = {"status": "approved", "reviewer": _clean(reviewer, 80),
                        "approved_at": datetime.now(timezone.utc).isoformat(),
                        "note": "Approved as guidance only. Each capability must be separately validated before use."}
    _atomic_store(path, lesson, replace=True)
    return lesson


def _directory(root=None):
    value = root or os.environ.get("BLENDER_LESSONS_DIR")
    return Path(value).expanduser().resolve() if value else None


def get_approved(identifier, root=None):
    directory = _directory(root)
    if directory is None:
        return None
    if not identifier.startswith("lesson."):
        return None
    slug = identifier.removeprefix("lesson.")
    try:
        doc = _load_lesson(_lesson_path(directory, slug))
    except ValueError:
        return None
    if doc and doc.get("review", {}).get("status") == "approved":
        return doc
    return None


def find_approved(query, root=None, limit=4):
    directory = _directory(root)
    if directory is None or not directory.is_dir():
        return []
    tokens = set(re.findall(r"[a-z0-9]{3,}", (query or "").lower()))
    rows = []
    for index, path in enumerate(sorted(directory.glob("*.lesson.json"))):
        if index >= MAX_LOADED:
            break
        doc = _load_lesson(path)
        if not doc or doc.get("review", {}).get("status") != "approved":
            continue
        summary = str(doc.get("goal", "")) + " " + str(doc.get("name", ""))
        matches = tokens.intersection(set(re.findall(r"[a-z0-9]{3,}", summary.lower())))
        if tokens and not matches:
            continue
        rows.append({"key": doc["key"], "family": "lesson",
                     "description": "Reviewed demonstration: " + _clean(summary, 170),
                     "score": len(matches) * 10,
                     "reason": ["source-pinned approved human recording", "guidance only; never directly executable"]})
    return sorted(rows, key=lambda r: (-r["score"], r["key"]))[:max(0, min(limit, 12))]


def main():
    parser = argparse.ArgumentParser(description="Import and review Blender Replay lessons without executing code")
    parser.add_argument("--dir", default=os.environ.get("BLENDER_LESSONS_DIR", "./.blender-lessons"))
    command = parser.add_subparsers(dest="command", required=True)
    importer = command.add_parser("import")
    importer.add_argument("recording")
    importer.add_argument("--id", required=True)
    importer.add_argument("--goal", required=True)
    approver = command.add_parser("approve")
    approver.add_argument("id")
    approver.add_argument("--source-sha256", required=True)
    approver.add_argument("--reviewer", required=True)
    approver.add_argument("--accept-incomplete", action="store_true")
    reader = command.add_parser("inspect")
    reader.add_argument("id")
    args = parser.parse_args()
    if args.command == "import":
        doc = import_recording(args.recording, directory=args.dir, identifier=args.id, goal=args.goal)
    elif args.command == "approve":
        doc = approve_lesson(args.id, directory=args.dir, source_hash=args.source_sha256,
                             reviewer=args.reviewer, accept_incomplete=args.accept_incomplete)
    else:
        doc = _load_lesson(_lesson_path(args.dir, args.id))
        if doc is None:
            parser.error("Lesson not found")
    print(json.dumps(doc, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
