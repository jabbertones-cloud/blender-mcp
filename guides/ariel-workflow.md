# Ariel's Workflow — how this artist actually uses Blender

Taught from extraction of 20 of her real .blend files (831 inventoried in her
iCloud `Online Classes/` tree), Blender 5.3.0 headless, read-only copies.
Machine-readable twin: `config/ariel_workflow_profile.json`. Every preset here
is a pattern measured in her files, labelled with its learning status —
nothing below is Artist-approved or Production-proven yet.

## The box template (SKYN + Crave)

One template, many brands. The `Box` in SKYNpatches_Updated and CraveBox is
the identical object: 1.612 x 1.809 x 0.406, modifier stack
SOLIDIFY -> BEVEL -> SUBSURF, same backing planes, same two Area lights,
same Bezier-circle camera-orbit rig (Follow Path + Track To). She clones a
proven scene and swaps the label art. Never rebuild her product scenes from
scratch; start from the template shape.

## Lighting: named Area rigs, stored as ratios

- **TriLamp** (Bottle/Bottle3): Key/Fill/Back area lights at **2:1:1**,
  aimed with Track-To constraints.
- **SprayLight** (Bottle3): Key/Rim/Top at **1.8 : 2.7 : 1** — the rim is
  hotter than the key for spray shots.
- Finished-stills template (SKYN/Crave): a warm-tinted Area pair.
- Store presets as ratios plus product-bbox-relative sizes, never absolute
  wattages — her scenes mix a true-scale 28 mm bottle with ~1.6-unit boxes.
- A lone factory Point light at 1000 W marks an unlit work-in-progress file.
  It is a WIP marker, not a style.

## Render recipe (hers, measured)

- Finals engine: **Cycles, 400 samples + denoise** — 10/10 of her
  Cycles-chosen files. (Generic guidance says 64–128; her files win.)
- PNG always. 1920x1080 default; 1920x1920 square for patch/box stills;
  1080x1920 for vertical product (Pressed).
- film_transparent in 11/20 files — transparent-background cut-outs are a
  core deliverable (shadow catcher is Cycles-only).
- AgX in newer files, Filmic in older ones (a migration over time).
- Trap: Eevee files carry an unused 4096-sample Cycles default. Never read
  "samples" without checking the active engine.

## Cameras

- 50 mm everywhere; **70 mm for the bottle hero**; 32.17 mm only on the
  fSpy-matched camera.
- **Depth of field is OFF in 20/20 files.** Her product work is deep-focus.
  Do not enable DOF.
- Camera motion is constraint-driven: Follow Path around a Bezier circle +
  Track To (camera-orbit variant), or Track To empties.

## Materials

- Packaging = Principled + **linked** image-texture labels (relative `//`
  paths, almost never packed). Flavour variants are duplicated materials.
- Reused pair: "Matte Black" (Roughness 0.5) / "Shine Black" (0.0027,
  Roughness 0.1).
- Clear patch/film: Transmission Weight 1.0, Roughness 0; patch tint
  [0.80, 0.65, 0.57].
- Spray is water, physically: IOR 1.33, Transmission 1.0, Alpha 0.35;
  Droplets add Coat 0.7 / Roughness 0.01.

## The spray system

Shared across Bottle, Bottle3 and SMASH spray.blend: Geometry Nodes group
`SprayNodes_Final` + compositor group `SprayCompositorFinish`, animated on
frames 24–75. No authoritative web source exists for this workflow — her
files are the spec.

## Rigging

PTmascotRig: 29 bones with GENERIC names (`Bone`, `Bone.003.L` …
`Bone.015.R`), mirrored .L/.R pairs, no Rigify namespace. Work with the
names she has; never demand semantic renaming.

## Naming discipline

Heroes are semantic (`Bottle`, `Cap`, `Box`, `patch`); support geometry
keeps factory names (`Cube.157`, `Material.001`). Collections are mostly
plain, with functional exceptions that carry information: `boolean_cutters`,
`Reference`, `RigidBodyWorld`. **Inspect first, rename never by default** —
renaming destroys information she relies on.

## Version reality

Her corpus spans Blender 3.3 → 5.1 file formats; her machines run 5.3 (M3)
and 5.1 (M2). Version adapter rules live in the profile JSON: EEVEE engine
id flips (`BLENDER_EEVEE_NEXT` only 4.2–4.4), 5.0 removed `scene.node_tree`
(use `scene.compositing_node_group`), 4.0 renamed Principled inputs, and
5.0+ files use a 17-byte header + zstd (never sniff magic bytes — open
through Blender). Addon availability is per-version: her 5.2 config has no
addons migrated at all.

**Slotted Actions trap (proven):** Blender 5.3 removed `action.fcurves`; it
silently reads 0 keyframes. Use
`bpy_extras.anim_utils.action_get_channelbag_for_slot(action, slot)`.
Verified: Bottle = 158 keyframes / 7 actions; Bottle3 = 232 / 7. She
animates densely, per-object — lights get actions too.

## Fossil record: what her files can and cannot teach

A .blend file contains **no operator history, no undo, no click log** —
that state is session-only RAM and is gone when Blender closes. Never claim
a file records how it was made step by step.

What files DO hold is a fossil record: unapplied modifier stacks in order
(SKYN Box: SOLIDIFY -> BEVEL -> SUBSURF; Bag: MIRROR -> SUBSURF), node
trees, actions, custom properties — and fake-user datablocks, the only
unused data that survives a save. Her one protected fossil:
`SprayNodes_Final`, fake-user flagged in Bottle2. Across 15 of her files
there are zero embedded scripts, zero NLA, zero drivers, zero annotations,
and **no rejected-takes pattern**.

The real timeline is outside each file: the backup chain
(.blend1 -> .blend) and versioned series (Bottle -> Bottle2 -> Bottle3,
linked by an identical scene `uuid` custom property). Datablock-level
diffing of those snapshots reconstructs her process at save granularity —
spray sockets 7 -> 18, node tree 29 -> 74 nodes, EEVEE -> Cycles between
Bottle and Bottle2.

The recorder (`scene.human_activity`, consent-gated, OFF by default) is the
only source of true operator sequences, and it works **forward only**, from
live GUI sessions. Files = past, recorder = future.

## Hard guards

- Never auto-append missing linked assets — report them (`scene.health`).
  SKYNpatches_Updated genuinely has rotted texture links; that is a finding
  to surface, not to silently fix.
- Missing fluid cache = report, never auto-rebake.
- KeenTools being disabled by her startup.py is **policy**, not an error.
- Migration = read the saved version, work on a copy, preserve the original.
- Never modify her original .blend files. Open read-only; copy to scratch
  for any test that saves.

## Provenance

Three corpora, labelled, never merged blindly: **ariel-files** (this
profile), **artist-live** (recorder drains), **external** (licensed web
tutorial/demo files — generic good practice, never her style).
