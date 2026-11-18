# Verified procedural recipe execution for Ariel (Blender 5.3)

This change extends the **existing model.geometry_nodes canonical capability**. It does not add a sixth guided MCP tool or allow Blender Python source execution.

## Usage

1. In an authorized Blender 5.3 scene, inspect the target object, modifier, procedural graph, animation Action, and relevant shader dependencies. Work on a copy.
2. Use search_capabilities to find model.geometry_nodes; use get_capability_schema for the exact structured arguments.
3. Call execute_capability with key model.geometry_nodes and arguments containing action: build_graph, object_name, modifier_name, and spec. Provide a validated blenderwright-style graph specification, not Python code or a file path.
4. The Blender-side adapter validates the graph first. For existing modifiers, the adapter requires matching input socket names/types, restores values, and rebinds F-Curves. Shared Actions, NLA and driver-based modifier input animation, and incompatible interfaces are rejected.
5. Compare geometry at nonempty frames, independent coordinate hashes, renders and working-copy output before saving.

## Real M3 tests, November 17, 2026

Machine: smat-m3max; Blender 5.3.0. Private source scene files were never committed. Test cases opened with auto-execution disabled.

| Scene | Target graph | Measured outcome |
| --- | --- | --- |
| Ariel spray | 74 nodes, 113 links, 18 inputs, 2 animated channels | 7/7 frame hashes, 4 active |
| Ariel bottle spray | same graph, 3 animated channels | 10/10 frame hashes, 4 active |

Tests compare vertices, faces and SHA-256 vertex-coordinate hashes. Invalid node types and mismatched modifier interface requests were rejected without replacing the existing graph. An actual MCP stdio client -> TCP bridge -> Blender native build -> save -> fresh reopen preserved all seven spray geometry hashes.

Controlled Eevee render (400x225, temporary identical camera and lights, AgX normalized and dither off): 11 pixels differed among 90,000 by at most 1 RGB level. This does not establish the complete original-scene lighting and camera result.

Same-file baseline comparison at prior main cdace700ab0bb69673af7d7fca4e6caa001ee8c3: 0/7 qualifying frame matches (no build_graph support) versus 7/7 in the candidate.

## Source and licensing

21 verified AST-equivalent functions from [MIT-licensed blenderwright](https://github.com/HoldMyBeer-gg/blenderwright/tree/bc2aaadceaf96d3436313ab1c05b2971f5f0718d). Attribution and exact source mapping live in blender_addon/BLENDERWRIGHT_MIT_LICENSE.md and blender_addon/blenderwright_graph_donor.provenance.json.

Separate research evaluated GPL Blender Replay and NodeToPython, but no GPL source or generated code is in this runtime path.

## Limitations and release gate

A finished .blend cannot prove its original human edit chronology. Lesson promotion still requires Ariel's review; the existing reviewed-lesson importer is unchanged. This does not certify nested node groups, materials in this builder, rigs, fluid simulations, caches, all Blender versions, or full product render equivalence.

Research Fabric independently found the actual pinned donor alive, but its donor-check parser also extracted nonexistent gg/blenderwright and blocked sufficiency. The provenance gate is therefore not yet green; do not treat a passing local integration run as merged or deployed. GitHub Actions remain disabled.
