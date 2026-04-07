# Blender Skills Reference — for AI-Directed 3D Work

> Use this as a lookup when a user gives you Blender-native instructions.
> Every section maps natural-language Blender terms → MCP tool calls.
> **Tool count:** the live MCP server exposes **65** tools (59 core + 6 product animation). See the root `README.md` for the canonical grouped list.

> **⚠️ CRITICAL: MCP CALLING CONVENTION**
> When calling tools via the MCP socket, use the command name WITHOUT the `blender_` prefix.
> The registry uses `blender_execute_python` for namespacing, but the wire command is just `execute_python`.
> Similarly: `render` (not `blender_render`), `create_object` (not `blender_create_object`), etc.
> Using the prefix will cause silent failures or errors.
>
> **Operational source of truth:** `.claude/skills/blender-mcp/SKILL.md`
>
> This file is a terminology and tool-mapping reference only.
> For the full operational guide including Python quoting rules, scene management, lighting,
> camera framing, validation, health checks, and known failure modes, see:
> `.claude/skills/blender-mcp/SKILL.md`

---

## 1. MODELING (Edit Mode Mesh Operations)

### Selection
| User says | What it means |
|-----------|---------------|
| "Select edge loop" / "Alt+click" | Select continuous ring of edges |
| "Select edge ring" | Select edges perpendicular to flow |
| "Linked select" / "Select connected" | Select all geometry connected to current selection |
| "Grow/shrink selection" | Expand or contract selection outward |
| "Select by trait" / "Select similar" | Select vertices/edges/faces matching criteria |
| "Box/circle/lasso select" | Spatial selection methods |

→ Use `execute_python` with `bpy.ops.mesh.select_*` calls

### Core Mesh Tools
| User says | Blender operation | How to do it |
|-----------|-------------------|--------------|
| "Extrude" / "Extrude faces" | `bpy.ops.mesh.extrude_region_move()` | execute_python |
| "Extrude along normals" | `bpy.ops.mesh.extrude_faces_move()` | execute_python |
| "Inset faces" | `bpy.ops.mesh.inset()` | execute_python |
| "Bevel" / "Bevel edges" | `bpy.ops.mesh.bevel()` | execute_python or modifier |
| "Loop cut" / "Add loop cut" | `bpy.ops.mesh.loopcut_slide()` | execute_python |
| "Knife tool" / "Knife cut" | `bpy.ops.mesh.knife_tool()` | execute_python |
| "Bridge edge loops" | `bpy.ops.mesh.bridge_edge_loops()` | execute_python |
| "Fill" / "Grid fill" | `bpy.ops.mesh.fill()` / `grid_fill()` | execute_python |
| "Merge vertices" / "Merge at center" | `bpy.ops.mesh.merge(type='CENTER')` | execute_python |
| "Dissolve" / "Dissolve edges/faces" | `bpy.ops.mesh.dissolve_edges()` | execute_python |
| "Subdivide" | `bpy.ops.mesh.subdivide()` | execute_python |
| "Poke faces" | `bpy.ops.mesh.poke()` | execute_python |
| "Triangulate" | `bpy.ops.mesh.quads_convert_to_tris()` | execute_python |
| "Tris to quads" | `bpy.ops.mesh.tris_convert_to_quads()` | execute_python |
| "Separate" / "Separate by selection" | `bpy.ops.mesh.separate(type='SELECTED')` | execute_python |
| "Split" / "Rip" | `bpy.ops.mesh.split()` / `rip_move()` | execute_python |
| "Spin" / "Spin tool" | `bpy.ops.mesh.spin()` | execute_python |
| "Screw" | `bpy.ops.mesh.screw()` | execute_python |
| "Flip normals" / "Recalculate normals" | `bpy.ops.mesh.flip_normals()` / `normals_make_consistent()` | execute_python |
| "Mark sharp" / "Clear sharp" | `bpy.ops.mesh.mark_sharp()` | execute_python |
| "Mark seam" / "Clear seam" | `bpy.ops.mesh.mark_seam()` | execute_python |
| "Crease" / "Edge crease" | Set edge crease for subdivision | execute_python |

### Modifiers (Use `apply_modifier`)
| User says | Modifier type |
|-----------|---------------|
| "Subdivide" / "Subsurf" / "Subdivision surface" | `SUBSURF` |
| "Mirror" / "Mirror across X" | `MIRROR` |
| "Array" / "Make copies in a line" | `ARRAY` |
| "Bevel modifier" | `BEVEL` |
| "Solidify" / "Give it thickness" | `SOLIDIFY` |
| "Boolean" / "Cut out" / "Union" | `BOOLEAN` |
| "Decimate" / "Reduce polycount" | `DECIMATE` |
| "Remesh" / "Voxel remesh" | `REMESH` |
| "Shrinkwrap" / "Snap to surface" | `SHRINKWRAP` |
| "Smooth" / "Smooth modifier" | `SMOOTH` |
| "Laplacian smooth" | `LAPLACIANSMOOTH` |
| "Simple deform" / "Twist/bend/taper" | `SIMPLE_DEFORM` |
| "Displace" / "Displacement" | `DISPLACE` |
| "Wireframe" | `WIREFRAME` |
| "Skin" / "Skin modifier" | `SKIN` |
| "Lattice deform" | `LATTICE` |
| "Curve deform" / "Follow curve" | `CURVE` |
| "Cast" / "Spherize" | `CAST` |
| "Wave deform" | `WAVE` |
| "Weld" / "Auto-merge" | `WELD` |
| "Weighted normal" | `WEIGHTED_NORMAL` |
| "Multires" / "Multiresolution" | `MULTIRES` |
| "Mesh deform" | `MESH_DEFORM` |
| "Surface deform" | `SURFACE_DEFORM` |
| "Data transfer" | `DATA_TRANSFER` |
| "Normal edit" | `NORMAL_EDIT` |
| "Triangulate modifier" | `TRIANGULATE` |
| "Edge split" | `EDGE_SPLIT` |
| "Screw modifier" | `SCREW` |
| "Build modifier" | `BUILD` |
| "Mask modifier" | `MASK` |
| "Ocean" / "Ocean modifier" | `OCEAN` |

---

## 2. SCULPTING

→ Use `execute_python` to enter sculpt mode and adjust brush settings

### Sculpt Brushes
| Brush | Use |
|-------|-----|
| Draw | General volume addition |
| Clay / Clay Strips | Add clay-like strips, good for building forms |
| Inflate / Blob | Expand surface outward |
| Smooth | Even out surface |
| Flatten / Planar | Make surface flat |
| Grab | Move geometry like clay |
| Snake Hook | Pull geometry in a long trail |
| Crease | Sharp crease lines |
| Pinch | Pinch geometry together |
| Scrape / Fill | Scrape peaks or fill valleys |
| Mask | Paint protection mask |
| Pose | Rotate/pose mesh regions |
| Cloth | Cloth-like sculpt dynamics |
| Multires Displacement | Sculpt on subdivision levels |
| Elastic Deform | Soft body-like deformation |
| Slide Relax | Slide vertices along surface |
| Boundary | Shape mesh boundaries |
| Draw Face Sets | Paint face set regions |
| Draw Sharp | Sharp detailed strokes |
| Thumb | Smudge-like drag |
| Layer | Add flat layer of volume |

### Sculpt Workflow Phrases
- "Enter sculpt mode" → `bpy.ops.object.mode_set(mode='SCULPT')`
- "Dyntopo" / "Dynamic topology" → Enable for adaptive detail
- "Remesh for sculpting" → Voxel remesh before sculpting
- "Mask and hide" → Paint mask then hide unmasked

---

## 3. SHADER NODES (Use `shader_nodes`)

### Texture Nodes
| Node | Type string |
|------|-------------|
| Image Texture | `ShaderNodeTexImage` |
| Noise Texture | `ShaderNodeTexNoise` |
| Voronoi Texture | `ShaderNodeTexVoronoi` |
| Wave Texture | `ShaderNodeTexWave` |
| Gradient Texture | `ShaderNodeTexGradient` |
| Musgrave Texture | `ShaderNodeTexMusgrave` |
| Magic Texture | `ShaderNodeTexMagic` |
| Checker Texture | `ShaderNodeTexChecker` |
| Brick Texture | `ShaderNodeTexBrick` |
| Environment Texture | `ShaderNodeTexEnvironment` |
| Sky Texture | `ShaderNodeTexSky` |
| IES Texture | `ShaderNodeTexIES` |
| Point Density | `ShaderNodeTexPointDensity` |

### Shader Nodes
| Node | Type string |
|------|-------------|
| Principled BSDF | `ShaderNodeBsdfPrincipled` |
| Diffuse BSDF | `ShaderNodeBsdfDiffuse` |
| Glossy BSDF | `ShaderNodeBsdfGlossy` |
| Glass BSDF | `ShaderNodeBsdfGlass` |
| Emission | `ShaderNodeEmission` |
| Transparent BSDF | `ShaderNodeBsdfTransparent` |
| Translucent BSDF | `ShaderNodeBsdfTranslucent` |
| Refraction BSDF | `ShaderNodeBsdfRefraction` |
| Subsurface Scattering | `ShaderNodeSubsurfaceScattering` |
| Volume Absorption | `ShaderNodeVolumeAbsorption` |
| Volume Scatter | `ShaderNodeVolumeScatter` |
| Principled Volume | `ShaderNodeVolumePrincipled` |
| Mix Shader | `ShaderNodeMixShader` |
| Add Shader | `ShaderNodeAddShader` |
| Holdout | `ShaderNodeHoldout` |
| Shader to RGB | `ShaderNodeShaderToRGB` |

### Color Nodes
| Node | Type string |
|------|-------------|
| MixRGB / Mix Color | `ShaderNodeMix` |
| Color Ramp | `ShaderNodeValToRGB` |
| Invert | `ShaderNodeInvert` |
| Hue Saturation Value | `ShaderNodeHueSaturation` |
| Brightness Contrast | `ShaderNodeBrightContrast` |
| Gamma | `ShaderNodeGamma` |
| RGB Curves | `ShaderNodeRGBCurve` |

### Vector Nodes
| Node | Type string |
|------|-------------|
| Bump | `ShaderNodeBump` |
| Normal Map | `ShaderNodeNormalMap` |
| Displacement | `ShaderNodeDisplacement` |
| Vector Math | `ShaderNodeVectorMath` |
| Mapping | `ShaderNodeMapping` |
| Vector Rotate | `ShaderNodeVectorRotate` |

### Converter / Math Nodes
| Node | Type string |
|------|-------------|
| Math | `ShaderNodeMath` |
| Map Range | `ShaderNodeMapRange` |
| Clamp | `ShaderNodeClamp` |
| Color Ramp | `ShaderNodeValToRGB` |
| Separate XYZ | `ShaderNodeSeparateXYZ` |
| Combine XYZ | `ShaderNodeCombineXYZ` |
| Separate RGB | `ShaderNodeSeparateColor` |
| Combine RGB | `ShaderNodeCombineColor` |

### Input Nodes
| Node | Type string |
|------|-------------|
| Texture Coordinate | `ShaderNodeTexCoord` |
| Object Info | `ShaderNodeObjectInfo` |
| Geometry | `ShaderNodeNewGeometry` |
| Fresnel | `ShaderNodeFresnel` |
| Layer Weight | `ShaderNodeLayerWeight` |
| RGB | `ShaderNodeRGB` |
| Value | `ShaderNodeValue` |
| Ambient Occlusion | `ShaderNodeAmbientOcclusion` |
| Attribute | `ShaderNodeAttribute` |
| Tangent | `ShaderNodeTangent` |

---

## 4. GEOMETRY NODES

→ Use `execute_python` to add geometry node modifier and build node trees

### Key Node Categories
- **Mesh Primitives**: Cube, Cone, Cylinder, Grid, Ico Sphere, UV Sphere, Circle, Line
- **Curve Primitives**: Line, Circle, Quadrilateral, Star, Spiral, Arc
- **Instances**: Instance on Points, Realize Instances, Rotate Instances, Scale Instances
- **Mesh Operations**: Subdivide, Triangulate, Dual Mesh, Extrude Mesh, Flip Faces, Merge by Distance, Set Shade Smooth, Split Edges
- **Curve Operations**: Trim Curve, Resample Curve, Fill Curve, Fillet Curve, Curve to Mesh, Curve to Points
- **Point Operations**: Distribute Points on Faces, Points to Vertices
- **Fields/Math**: Math, Vector Math, Boolean Math, Compare, Map Range, Clamp, Random Value
- **Attributes**: Named Attribute, Store Named Attribute, Capture Attribute
- **Geometry**: Set Position, Set Material, Bounding Box, Convex Hull, Transform Geometry, Join Geometry, Delete Geometry
- **Input**: Position, Normal, Index, ID, Random Value, Scene Time, Object Info

### Common Geometry Node Phrases
- "Scatter objects" → Distribute Points on Faces + Instance on Points
- "Procedural terrain" → Subdivide + Set Position with Noise
- "Array along curve" → Curve to Points + Instance on Points
- "Random rotation" → Random Value + Rotate Instances

---

## 5. COMPOSITOR NODES (Use `execute_python` to set up compositor)

### Filter Nodes
- Blur, Dilate/Erode, Despeckle, Filter (Sharpen/Laplace/Sobel/Prewitt), Glare, Pixelate, Sun Beams, Denoise, Anti-Aliasing

### Color Nodes
- Mix, Alpha Over, Color Balance, Color Correction, Bright/Contrast, Hue Correct, Gamma, Tonemap, Exposure, Curves (RGB/Hue)

### Converter Nodes
- Color Ramp, Set Alpha, Math, Separate/Combine RGBA, Map Range, Map Value, Switch

### Distortion Nodes
- Lens Distortion, Movie Distortion, Translate, Rotate, Scale, Flip, Crop, Displace, Corner Pin, Plane Track Deform

### Matte Nodes
- Keying, Keying Screen, Channel Key, Chroma Key, Color Key, Difference Key, Distance Key, Luminance Key, Box/Ellipse Mask, Double Edge Mask, Cryptomatte

---

## 6. ANIMATION & RIGGING

### Animation Concepts (Use `set_keyframe`, `clear_keyframes`)
| User says | What to do |
|-----------|------------|
| "Keyframe the location" | `set_keyframe` with property="location" |
| "Animate rotation from frame 1 to 60" | Two keyframes at frame 1 and 60 |
| "Set ease in/out" | Change interpolation in graph editor via execute_python |
| "Constant interpolation" / "Stepped" | Set fcurve interpolation |
| "Follow path" | Add Follow Path constraint |
| "Shape keys" / "Morph targets" | Create shape keys on mesh |
| "Drivers" / "Drive value from..." | Create driver expressions |
| "NLA strips" / "Blend actions" | Non-Linear Animation editor |
| "Motion path" | `bpy.ops.object.paths_calculate()` |
| "Bake animation" | `bpy.ops.nla.bake()` |

### Rigging (Use `armature_operations`, `constraint_operations`)
| User says | What to do |
|-----------|------------|
| "Add armature" | armature action="create" |
| "Add bone" / "Extrude bone" | armature action="add_bone" |
| "IK chain" / "Inverse kinematics" | Add INVERSE_KINEMATICS constraint |
| "Copy rotation" | Add COPY_ROTATION constraint |
| "Damped track" / "Aim at" | Add DAMPED_TRACK constraint |
| "Track to" / "Point at" | Add TRACK_TO constraint |
| "Stretch to" | Add STRETCH_TO constraint |
| "Limit rotation" | Add LIMIT_ROTATION constraint |
| "Child of" | Add CHILD_OF constraint |
| "Floor constraint" | Add FLOOR constraint |
| "Clamp to" / "Follow curve" | Add CLAMP_TO constraint |
| "Weight paint" | Enter weight paint mode |
| "Automatic weights" | Parent with automatic weights |
| "Bone layers" | Organize bones into layers |

### All Constraint Types
`COPY_LOCATION`, `COPY_ROTATION`, `COPY_SCALE`, `COPY_TRANSFORMS`, `LIMIT_DISTANCE`, `LIMIT_LOCATION`, `LIMIT_ROTATION`, `LIMIT_SCALE`, `MAINTAIN_VOLUME`, `TRANSFORM`, `TRANSFORM_CACHE`, `CLAMP_TO`, `DAMPED_TRACK`, `INVERSE_KINEMATICS`, `LOCKED_TRACK`, `SPLINE_IK`, `STRETCH_TO`, `TRACK_TO`, `ACTION`, `ARMATURE`, `CHILD_OF`, `FLOOR`, `FOLLOW_PATH`, `PIVOT`, `SHRINKWRAP`

---

## 7. RENDERING (Use `set_render_settings`, `render`)

> **Important:** `set_render_settings` accepts **lowercase** engine names: `'eevee'`, `'cycles'`, `'workbench'`.
> The `render` command uses `output_path` (not `filepath`) for the output file.
> For the full studio lighting and camera framing guide, see `.claude/skills/blender-mcp/SKILL.md`.

### Cycles Settings
| User says | Property |
|-----------|----------|
| "Use GPU" | `bpy.context.preferences.addons['cycles'].preferences.compute_device_type = 'METAL'` |
| "Set samples to 128" | `scene.cycles.samples = 128` |
| "Denoise" / "Use denoiser" | `scene.cycles.use_denoising = True` |
| "Adaptive sampling" | `scene.cycles.use_adaptive_sampling = True` |
| "Transparent background" | `scene.render.film_transparent = True` |
| "Motion blur" | `scene.render.use_motion_blur = True` |
| "Depth of field" / "DOF" | Camera DOF settings |
| "Volumetrics" / "Volume fog" | Add Volume Scatter to world |
| "Ambient occlusion" | `scene.world.light_settings.use_ambient_occlusion` |
| "Light bounces" | `scene.cycles.max_bounces` |

### EEVEE Settings
| User says | Property |
|-----------|----------|
| "Screen space reflections" / "SSR" | `scene.eevee.use_ssr` |
| "Ambient occlusion" / "SSAO" | `scene.eevee.use_gtao` |
| "Bloom" / "Glow" | `scene.eevee.use_bloom` |
| "Volumetric lighting" | `scene.eevee.use_volumetric_lights` |
| "Shadow quality" | `scene.eevee.shadow_cube_size` / `shadow_cascade_size` |

### Light Types (Use `create_object`)
| User says | Object type |
|-----------|-------------|
| "Point light" / "Omni light" | `light_point` |
| "Sun light" / "Directional light" | `light_sun` |
| "Spot light" | `light_spot` |
| "Area light" / "Rect light" / "Soft light" | `light_area` |

---

## 8. UV/TEXTURING (Use `uv_operations`)

### UV Methods
| User says | Action |
|-----------|--------|
| "Smart UV project" | `smart_project` |
| "Unwrap" / "Standard unwrap" | `unwrap` |
| "Cube projection" | `cube_project` |
| "Cylinder projection" | `cylinder_project` |
| "Sphere projection" | `sphere_project` |
| "Reset UV" | `reset` |

### UV Workflow Phrases
- "Mark seam" → `bpy.ops.mesh.mark_seam()` in edit mode
- "Clear seam" → `bpy.ops.mesh.mark_seam(clear=True)`
- "Pack islands" → `bpy.ops.uv.pack_islands()`
- "Average island scale" → `bpy.ops.uv.average_islands_scale()`
- "Bake normal map" → Set up bake in Cycles
- "Bake AO" → Bake ambient occlusion
- "Texture paint" → `bpy.ops.object.mode_set(mode='TEXTURE_PAINT')`

---

## 9. PHYSICS (Use `execute_python` for physics setup)

### Physics Types
| User says | Physics type |
|-----------|-------------|
| "Rigid body" / "Make it fall" | `rigid_body` + ACTIVE |
| "Passive rigid body" / "Make it a floor" | `rigid_body` + PASSIVE |
| "Cloth simulation" | `cloth` |
| "Fluid simulation" / "Water" | `fluid` |
| "Soft body" / "Jelly" | `soft_body` |
| "Collision" / "Make it collidable" | `collision` |

### Force Fields (via execute_python)
Wind, Vortex, Turbulence, Drag, Magnetic, Harmonic, Charge, Lennard-Jones, Force, Boid

### Particle Phrases
- "Hair particles" → particle_type="HAIR"
- "Particle emitter" → particle_type="EMITTER"
- "Emit from faces" → emit_from="FACE"
- "Emit from volume" → emit_from="VOLUME"
- "Render as object" → render_type="OBJECT"
- "Particle instance" → render_type="COLLECTION"

---

## 10. COMMON WORKFLOW PHRASES → MCP TOOL MAPPING

> **Remember:** Strip the `blender_` prefix when calling via MCP socket.
> The names below are the MCP wire commands (no prefix).

| What user says | MCP command(s) |
|----------------|----------------|
| "Start fresh" / "New scene" | `save_file` action=new, use_empty=true, then Python cleanup (see SKILL.md §3) |
| "Add a cube at origin" | `create_object` type=cube |
| "Subdivide and smooth" | `execute_python` (add SUBSURF modifier + per-object shade_smooth loop) |
| "Apply all transforms" | `execute_python` with `bpy.ops.object.transform_apply()` |
| "Shade smooth" | `execute_python` — loop each mesh, set active, `bpy.ops.object.shade_smooth()` (NOT `cleanup` action) |
| "Bridge edge loops" | `execute_python` with bridge_edge_loops |
| "Make it metallic gold" | `set_material` color=[1,0.8,0.3] metallic=1.0 roughness=0.2 |
| "Glass material" | `shader_nodes` — Principled with transmission=1.0 |
| "Add an HDRI" | `set_world` hdri_path=... |
| "Find/download Sketchfab asset" | `sketchfab` action=search/download/import |
| "Generate model with Hunyuan3D" | `hunyuan3d` action=generate/status/import |
| "Run cinema render QA" | `render_quality_audit` profile=cinema |
| "Render at 4K" | `set_render_settings` resolution_x=3840 resolution_y=2160 |
| "Export as GLB" | `export_file` action=export_gltf filepath=.../model.glb |
| "Export as STL" | `execute_python` with `bpy.ops.wm.stl_export(filepath=...)` (NO STL action in export_file) |
| "Import FBX" | `import_file` filepath=.../.fbx |
| "Animate spinning" | Two rotation keyframes at frame 1 and end |
| "Add to collection" | `manage_collection` action=move_objects |
| "Parent the objects" | `parent_objects` |
| "Boolean subtract" | `boolean_operation` operation=DIFFERENCE |
| "Duplicate and offset" | `duplicate_object` with offset |
| "Delete everything" | `execute_python` — remove all objects (see SKILL.md §3 for full cleanup) |
| "What's in the scene?" | `get_scene_info` |
| "Tell me about this object" | `get_object_data` |
| "Run this script" | `execute_python` |
| "Render this" | `render` output_path=.../output.png (NOT filepath!) |
