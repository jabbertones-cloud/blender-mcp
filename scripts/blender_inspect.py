#!/usr/bin/env python3
"""Batch scene inspector CLI — the repo's missing `inspect` command.

Takes .blend file paths and emits the same JSON scene dump used to teach
this MCP from the artist's real files: objects/types, evaluated-vs-base
geometry, modifier + constraint histograms, materials with Principled
inputs, lights, cameras, world, render settings, actions, node groups,
physics, and external (linked vs packed) file references.

Two modes:

  # Driver mode (plain python): spawns Blender headless per file.
  python3 scripts/blender_inspect.py FILE.blend [FILE2.blend ...] \
      [--blender /Applications/Blender.app/Contents/MacOS/Blender] \
      [--out DIR]            # default: ./inspect-out

  # Inside Blender (driver mode uses this automatically):
  blender --background FILE.blend --python scripts/blender_inspect.py \
      -- --out-one OUT.json

Read-only: files are opened, never saved. Exit code is non-zero if any
file fails to dump, and each failure is reported — no silent passes.

Format note: files are opened by Blender itself, never sniffed by magic
bytes. Blender 5.0+ writes a 17-byte header (BLENDER17-01v0502) and
zstd-compresses saves by default, so a naive first-7-bytes 'BLENDER'
check REJECTS current files — do not add one here.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import subprocess
import sys


# --------------------------------------------------------------------------
# Inside-Blender dump (imported/executed by Blender's python)
# --------------------------------------------------------------------------

def _dump_current_blend(src: str, outpath: str) -> dict:
    import bpy

    def safe(fn, default=None):
        try:
            return fn()
        except Exception:
            return default

    d = {"file": src, "basename": os.path.basename(src)}
    d["blender_version_runtime"] = bpy.app.version_string
    d["saved_version"] = safe(lambda: ".".join(str(x) for x in bpy.data.version))
    d["filepath"] = bpy.data.filepath

    objs = []
    typec = collections.Counter()
    modc = collections.Counter()
    consc = collections.Counter()
    dg = safe(lambda: bpy.context.evaluated_depsgraph_get())
    for o in bpy.data.objects:
        typec[o.type] += 1
        mods = []
        for m in o.modifiers:
            modc[m.type] += 1
            md = {"name": m.name, "type": m.type}
            for attr in ("levels", "subdivision_type", "width", "thickness", "count",
                         "offset", "strength", "segments", "angle", "use_mirror_merge"):
                if hasattr(m, attr):
                    v = getattr(m, attr)
                    if isinstance(v, (int, float, str, bool)) or v is None:
                        md[attr] = v
            if hasattr(m, "node_group") and m.node_group:
                md["node_group"] = m.node_group.name
            mods.append(md)
        cons = [{"name": c.name, "type": c.type} for c in o.constraints]
        for c in o.constraints:
            consc[c.type] += 1
        entry = {"name": o.name, "type": o.type, "modifiers": mods, "constraints": cons,
                 "parent": o.parent.name if o.parent else None,
                 "location": [round(x, 3) for x in o.location],
                 "scale": [round(x, 3) for x in o.scale],
                 "dimensions": [round(x, 3) for x in o.dimensions]}
        if o.type == "MESH" and o.data:
            entry["verts"] = len(o.data.vertices)
            entry["polys"] = len(o.data.polygons)
            if dg is not None:
                ev = safe(lambda o=o: o.evaluated_get(dg))
                if ev is not None:
                    em = safe(lambda ev=ev: ev.to_mesh())
                    if em is not None:
                        entry["evaluated_verts"] = len(em.vertices)
                        entry["evaluated_polys"] = len(em.polygons)
                        safe(lambda ev=ev: ev.to_mesh_clear())
                    entry["dimensions_evaluated"] = [round(x, 3) for x in ev.dimensions]
            entry["materials"] = [ms.material.name if ms.material else None for ms in o.material_slots]
            entry["vertex_groups"] = [g.name for g in o.vertex_groups]
        if o.type == "LIGHT" and o.data:
            ld = o.data
            entry["light"] = {"type": ld.type, "energy": safe(lambda: ld.energy),
                              "shape": safe(lambda: ld.shape), "size": safe(lambda: ld.size),
                              "size_y": safe(lambda: ld.size_y)}
        if o.type == "CAMERA" and o.data:
            cd = o.data
            entry["camera"] = {"lens_mm": cd.lens, "type": cd.type,
                               "dof_use": safe(lambda: cd.dof.use_dof),
                               "dof_aperture_fstop": safe(lambda: cd.dof.aperture_fstop)}
        if o.type == "ARMATURE" and o.data:
            entry["bones"] = [b.name for b in o.data.bones]
        if o.animation_data and o.animation_data.action:
            entry["action"] = o.animation_data.action.name
        objs.append(entry)
    d["object_count"] = len(objs)
    d["objects_by_type"] = dict(typec)
    d["objects"] = objs
    d["modifier_histogram_all"] = dict(modc)
    d["constraint_histogram_all"] = dict(consc)
    d["collections"] = [{"name": c.name, "objects": len(c.objects),
                         "children": [ch.name for ch in c.children]} for c in bpy.data.collections]

    mats = []
    for m in bpy.data.materials:
        md = {"name": m.name, "use_nodes": safe(lambda m=m: m.use_nodes)}
        if safe(lambda m=m: m.use_nodes) and m.node_tree:
            md["node_types"] = dict(collections.Counter(n.bl_idname for n in m.node_tree.nodes))
            md["links"] = len(m.node_tree.links)
            for n in m.node_tree.nodes:
                if n.bl_idname == "ShaderNodeBsdfPrincipled":
                    inp = {}
                    for k in ("Base Color", "Metallic", "Roughness", "IOR", "Alpha",
                              "Transmission Weight", "Coat Weight", "Specular IOR Level",
                              "Emission Color", "Emission Strength"):
                        if k in n.inputs:
                            s = n.inputs[k]
                            v = safe(lambda s=s: s.default_value)
                            if hasattr(v, "__len__") and not isinstance(v, str):
                                try:
                                    v = [round(float(x), 4) for x in v]
                                except Exception:
                                    v = str(v)
                            elif isinstance(v, float):
                                v = round(v, 4)
                            inp[k] = {"value": v, "linked": bool(s.links)}
                    md.setdefault("principled", []).append(inp)
                if n.bl_idname == "ShaderNodeTexImage" and n.image:
                    md.setdefault("image_textures", []).append(
                        {"image": n.image.name, "filepath": n.image.filepath,
                         "packed": bool(n.image.packed_file)})
        mats.append(md)
    d["materials"] = mats
    d["images"] = [{"name": im.name, "filepath": im.filepath, "packed": bool(im.packed_file),
                    "size": list(im.size), "source": im.source} for im in bpy.data.images]
    d["libraries_linked"] = [{"name": l.name, "filepath": l.filepath} for l in bpy.data.libraries]
    d["node_groups"] = [{"name": g.name,
                         "type": g.bl_idname if hasattr(g, "bl_idname") else type(g).__name__}
                        for g in bpy.data.node_groups]

    scenes = []
    for sc in bpy.data.scenes:
        r = sc.render
        sd = {"name": sc.name, "engine": r.engine,
              "resolution": [r.resolution_x, r.resolution_y, r.resolution_percentage],
              "film_transparent": r.film_transparent, "filepath": r.filepath,
              "file_format": safe(lambda: r.image_settings.file_format),
              "fps": sc.render.fps, "frame_start": sc.frame_start, "frame_end": sc.frame_end,
              "view_transform": safe(lambda: sc.view_settings.view_transform),
              "look": safe(lambda: sc.view_settings.look),
              "unit_system": safe(lambda: sc.unit_settings.system),
              "camera": sc.camera.name if sc.camera else None}
        cy = safe(lambda: sc.cycles)
        if cy:
            sd["cycles"] = {"samples": safe(lambda: cy.samples),
                            "use_denoising": safe(lambda: cy.use_denoising),
                            "device": safe(lambda: cy.device)}
        if sc.world and safe(lambda: sc.world.use_nodes) and sc.world.node_tree:
            sd["world_node_types"] = dict(collections.Counter(
                n.bl_idname for n in sc.world.node_tree.nodes))
        ct = safe(lambda: sc.node_tree) or safe(lambda: sc.compositing_node_group)
        if ct and safe(lambda: ct.nodes):
            sd["compositor_node_types"] = dict(collections.Counter(
                n.bl_idname for n in ct.nodes))
        scenes.append(sd)
    d["scenes"] = scenes

    acts = []
    try:
        from bpy_extras.anim_utils import action_get_channelbag_for_slot
    except Exception:
        action_get_channelbag_for_slot = None
    for a in bpy.data.actions:
        kf = 0
        if action_get_channelbag_for_slot is not None:
            try:
                slots = list(a.slots) if hasattr(a, "slots") and a.slots else [None]
                for slot in slots:
                    bag = action_get_channelbag_for_slot(a, slot)
                    if bag is not None:
                        kf += sum(len(f.keyframe_points) for f in bag.fcurves)
            except Exception:
                kf = 0
        acts.append({"name": a.name,
                     "frame_range": [round(float(x), 2) for x in a.frame_range],
                     "keyframes": kf,
                     "users": a.users})
    d["actions"] = acts
    d["armatures"] = [o.name for o in bpy.data.objects if o.type == "ARMATURE"]
    rb = []
    for o in bpy.data.objects:
        if safe(lambda o=o: o.rigid_body):
            rb.append({"obj": o.name, "rb_type": o.rigid_body.type})
        for m in o.modifiers:
            if m.type in ("CLOTH", "FLUID", "OCEAN", "DYNAMIC_PAINT", "SOFT_BODY"):
                rb.append({"obj": o.name, "sim_modifier": m.type, "name": m.name})
    d["physics_objects"] = rb

    # Fossil record: fake-user datablocks survive saving even with zero
    # users (unassigned actions = earlier takes; orphaned node groups and
    # materials = abandoned directions). Zero-user datablocks WITHOUT a
    # fake user are NOT saved, so everything listed here was deliberately
    # or incidentally preserved. (History-mining research, 2026-11-17.)
    fossil = {}
    for coll_name in ("actions", "materials", "images", "node_groups", "meshes",
                      "armatures", "cameras", "lights", "worlds", "texts"):
        coll = getattr(bpy.data, coll_name, None)
        if coll is None:
            continue
        rows = []
        for item in coll:
            rows.append({"name": item.name, "users": item.users,
                         "use_fake_user": bool(getattr(item, "use_fake_user", False))})
        kept = [r for r in rows if r["users"] == 0 and r["use_fake_user"]]
        if kept:
            fossil[coll_name] = kept
    d["fossil_fake_user_datablocks"] = fossil
    d["embedded_texts"] = [t.name for t in bpy.data.texts] if hasattr(bpy.data, "texts") else []

    os.makedirs(os.path.dirname(outpath) or ".", exist_ok=True)
    with open(outpath, "w") as f:
        json.dump(d, f, indent=1, default=str)
    print("INSPECT_OK", outpath, d["object_count"], dict(typec))
    return d


# --------------------------------------------------------------------------
# Driver mode
# --------------------------------------------------------------------------

def _inside_blender() -> bool:
    try:
        import bpy  # noqa: F401
        return True
    except ImportError:
        return False


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]

    if _inside_blender():
        ap = argparse.ArgumentParser(prog="blender_inspect (in-blender)")
        ap.add_argument("--out-one", required=True)
        ap.add_argument("--src", default="")
        args = ap.parse_args(argv)
        import bpy
        _dump_current_blend(args.src or bpy.data.filepath, args.out_one)
        return 0

    ap = argparse.ArgumentParser(prog="blender_inspect",
                                 description="Headless batch .blend inspector (read-only).")
    ap.add_argument("files", nargs="+", help=".blend files to inspect")
    ap.add_argument("--blender", default=os.environ.get(
        "BLENDER_BIN", "/Applications/Blender.app/Contents/MacOS/Blender"),
        help="Blender binary (default: $BLENDER_BIN or the macOS app path)")
    ap.add_argument("--out", default="inspect-out", help="output directory for JSON dumps")
    args = ap.parse_args(argv)

    if not os.path.isfile(args.blender):
        print(f"error: Blender binary not found: {args.blender}", file=sys.stderr)
        return 2
    os.makedirs(args.out, exist_ok=True)
    failures = 0
    for path in args.files:
        if not os.path.isfile(path):
            print(f"FAIL {path}: not a file", file=sys.stderr)
            failures += 1
            continue
        name = os.path.splitext(os.path.basename(path))[0]
        name = "".join(c if c.isalnum() or c in "_-" else "_" for c in name)
        out_json = os.path.join(args.out, name + ".json")
        cmd = [args.blender, "--background", "--factory-startup", os.path.abspath(path),
               "--python", os.path.abspath(__file__), "--",
               "--out-one", os.path.abspath(out_json), "--src", os.path.abspath(path)]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        ok = os.path.isfile(out_json) and "INSPECT_OK" in proc.stdout
        if ok:
            print(f"OK {path} -> {out_json}")
        else:
            failures += 1
            print(f"FAIL {path}", file=sys.stderr)
            tail = (proc.stdout + proc.stderr).strip().splitlines()[-5:]
            for line in tail:
                print(f"    {line}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
