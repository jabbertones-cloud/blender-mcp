"""Small app-specific transaction adapter around pinned MIT blenderwright."""
import bpy
from blenderwright_graph_donor import _validate_spec, validate_object_name, validate_new_name, handle_build_geometry_nodes
from graph_input_state import capture as capture_inputs, preflight, restore
from graph_animation_transfer import capture as capture_animation, rebind, rollback
def build_graph(params):
    if bpy.app.version < (5, 3, 0):
        raise ValueError("Validated graph replacement requires Blender 5.3+")
    name = validate_object_name(params["object_name"])
    modifier_name = validate_new_name(params.get("modifier_name") or "GeometryNodes")
    spec = _validate_spec(params["spec"])
    obj = bpy.data.objects.get(name)
    if not obj: raise ValueError("Target object not found")
    existing = obj.modifiers.get(modifier_name)
    if existing and existing.type != "NODES":
        raise ValueError("Existing modifier is not Geometry Nodes")
    old_group = existing.node_group if existing else None
    values = capture_inputs(existing)
    preflight(values, spec)
    curves = capture_animation(obj, modifier_name)
    created_group = None
    try:
        result = handle_build_geometry_nodes(
            {"object_name": name, "modifier_name": modifier_name, "spec": spec})
        mod = obj.modifiers[modifier_name]
        created_group = mod.node_group
        mapping = restore(mod, values) if old_group else {}
        result["preserved_inputs"] = len(mapping)
        result["rebound_curves"] = rebind(curves, mapping)
        return result
    except Exception:
        rollback(curves)
        current = obj.modifiers.get(modifier_name)
        if current and old_group:
            current.node_group = old_group
            restore(current, values)
        elif current and not existing: obj.modifiers.remove(current)
        if created_group and created_group != old_group:
            bpy.data.node_groups.remove(created_group)
        raise
