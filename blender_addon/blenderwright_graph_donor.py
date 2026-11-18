# SPDX-License-Identifier: MIT
# Third-party source assembly from HoldMyBeer-gg/blenderwright@bc2aaadceaf96d3436313ab1c05b2971f5f0718d
# Portions of src/blenderwright/validators.py, tools/geometry_nodes.py,
# addon/handlers/geometry_nodes.py. See blenderwright/LICENSE.md and provenance JSON.
# Source functions below are retained verbatim. Only the narrow validated entrypoint is local glue.
import bpy
import math
import os
import re
import unicodedata
from typing import Any

MAX_OBJECT_NAME_LENGTH = 255

_NODE_TYPE_PATTERN = re.compile(r"^(Geometry|Function|Shader)Node[A-Z][A-Za-z0-9]*$")

_SETTING_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

ALLOWED_INTERFACE_TYPES = {
    "GEOMETRY", "FLOAT", "INT", "BOOLEAN", "VECTOR", "COLOR", "ROTATION", "STRING",
    "OBJECT", "COLLECTION", "MATERIAL",
}

GROUP_NODES = {"Group Input", "Group Output"}

MAX_SPEC_NODES = 200

MAX_SPEC_LINKS = 500

MAX_SPEC_SOCKETS = 50

MAX_TEXT = 64

MAX_COORD = 100_000.0

ID_SOCKETS = {
    "NodeSocketObject": "objects",
    "NodeSocketCollection": "collections",
    "NodeSocketMaterial": "materials",
}

TEXT_SOCKETS = {"NodeSocketMenu", "NodeSocketString"} | set(ID_SOCKETS)

INTERFACE_SOCKETS = {
    "GEOMETRY": "NodeSocketGeometry", "FLOAT": "NodeSocketFloat", "INT": "NodeSocketInt",
    "BOOLEAN": "NodeSocketBool", "VECTOR": "NodeSocketVector", "COLOR": "NodeSocketColor",
    "ROTATION": "NodeSocketRotation", "STRING": "NodeSocketString",
    "OBJECT": "NodeSocketObject", "COLLECTION": "NodeSocketCollection",
    "MATERIAL": "NodeSocketMaterial",
}

NODE_SETTING_TYPES = {"BOOLEAN", "INT", "FLOAT", "ENUM", "STRING"}

NODE_PREFIXES = ("GeometryNode", "FunctionNode", "ShaderNode")

class ValidationError(Exception):
    """Raised when input validation fails."""
    pass

def validate_object_name(name: str) -> str:
    """Validate a Blender data-block name.

    Accepts anything Blender can store: printable text up to 255 UTF-8 bytes.
    Names are only ever sent as values, never built into code or paths, so
    'Material #25' and 'mixamorig:Hips' from imported files work as they are.
    """
    if not name or not isinstance(name, str):
        raise ValidationError("Object name must be a non-empty string")
    name = name.strip()
    if not name:
        raise ValidationError("Object name must be a non-empty string")
    if len(name.encode("utf-8")) > MAX_OBJECT_NAME_LENGTH:
        raise ValidationError(
            f"Names are at most {MAX_OBJECT_NAME_LENGTH} bytes, so nothing has this "
            f"name. Use the name returned when it was created."
        )
    if any(unicodedata.category(c) == "Cc" for c in name):
        raise ValidationError("Object name contains a control character")
    return name

def validate_new_name(name: str) -> str:
    """Validate the name for something about to be created.

    Same rules as validate_object_name, except that a name over Blender's
    limit is cut to fit rather than refused. A model that has just been told
    its shuttle lacks thermal tiles will name the next part in sixty-eight
    characters, and the refusal cost it seventeen rounds. Blender would cut
    it anyway; do it here and return what was used.
    """
    if not name or not isinstance(name, str):
        raise ValidationError("Object name must be a non-empty string")
    name = name.strip()
    encoded = name.encode("utf-8")
    if len(encoded) > MAX_OBJECT_NAME_LENGTH:
        name = encoded[:MAX_OBJECT_NAME_LENGTH].decode("utf-8", "ignore").rstrip("_-. ")
    return validate_object_name(name)

def validate_vector(vec: list | tuple, size: int = 3, name: str = "vector") -> tuple:
    """Validate a vector (e.g., location, rotation, scale)."""
    if not isinstance(vec, (list, tuple)):
        raise ValidationError(f"{name} must be a list or tuple")
    if len(vec) != size:
        raise ValidationError(f"{name} must have exactly {size} components")
    for i, v in enumerate(vec):
        if not isinstance(v, (int, float)):
            raise ValidationError(f"{name} component {i} must be a number")
    return tuple(vec)

def validate_enum(value: str, allowed: set[str], name: str = "value") -> str:
    """Validate a string is one of the allowed values."""
    if not isinstance(value, str):
        raise ValidationError(f"{name} must be a string")
    if value not in allowed:
        raise ValidationError(f"{name} must be one of {sorted(allowed)}, got '{value}'")
    return value

def _text(value: Any, what: str) -> str:
    if not isinstance(value, str) or not value or len(value) > MAX_TEXT \
            or not value.isprintable():
        raise ValidationError(f"{what} must be printable text, 1 to {MAX_TEXT} characters")
    return value

def _plain_value(value: Any, what: str) -> Any:
    """A socket or setting value: bool, finite number, short text, or 2 to 4 numbers."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if value != value or value in (float("inf"), float("-inf")):
            raise ValidationError(f"{what} must be a finite number")
        return value
    if isinstance(value, str):
        return _text(value, what)
    if isinstance(value, list) and 2 <= len(value) <= 4 and all(
            isinstance(v, (int, float)) and not isinstance(v, bool) and v == v
            and abs(v) != float("inf") for v in value):
        return value
    raise ValidationError(f"{what} must be a number, true/false, short text or 2-4 numbers")

def _socket_ref(ref: Any, what: str) -> str | int:
    if isinstance(ref, int) and not isinstance(ref, bool):
        if ref < 0:
            raise ValidationError(f"{what} index must be 0 or more")
        return ref
    return _text(ref, what)

def _interface_items(items: Any, what: str) -> list[dict[str, Any]]:
    if not isinstance(items, list) or len(items) > MAX_SPEC_SOCKETS:
        raise ValidationError(f"{what} must be a list of at most {MAX_SPEC_SOCKETS} sockets")
    clean = []
    for item in items:
        if not isinstance(item, dict) or not set(item) <= {"name", "type", "default",
                                                           "min", "max"}:
            raise ValidationError(f"Each of {what} is {{name, type, default?, min?, max?}}")
        entry = {"name": _text(item.get("name"), f"{what} name"),
                 "type": validate_enum(item.get("type"), ALLOWED_INTERFACE_TYPES,
                                       name=f"{what} type")}
        for key in ("default", "min", "max"):
            if key in item:
                value = _plain_value(item[key], f"{what} {key}")
                if key != "default" and not isinstance(value, (int, float)):
                    raise ValidationError(f"{what} {key} must be a number")
                if key == "default" and isinstance(value, str) and entry["type"] not in (
                        "STRING", "OBJECT", "COLLECTION", "MATERIAL"):
                    raise ValidationError(f"{what} default for {entry['type']} must not be text")
                entry[key] = value
        clean.append(entry)
    return clean

def _validate_spec(spec: Any) -> dict[str, Any]:
    if not isinstance(spec, dict) or not set(spec) <= {"inputs", "outputs", "nodes", "links"}:
        raise ValidationError("spec is an object with inputs, outputs, nodes and links")
    nodes = spec.get("nodes", [])
    links = spec.get("links", [])
    if not isinstance(nodes, list) or len(nodes) > MAX_SPEC_NODES:
        raise ValidationError(f"nodes must be a list of at most {MAX_SPEC_NODES}")
    if not isinstance(links, list) or len(links) > MAX_SPEC_LINKS:
        raise ValidationError(f"links must be a list of at most {MAX_SPEC_LINKS}")

    clean_nodes, names = [], set(GROUP_NODES)
    for node in nodes:
        if not isinstance(node, dict) or not set(node) <= {"name", "type", "location",
                                                           "settings", "inputs", "pair_with"}:
            raise ValidationError("Each node is {name, type, location?, settings?, inputs?, "
                                  "pair_with?}")
        name = validate_object_name(node.get("name"))
        if name in names:
            raise ValidationError(f"Node name {name!r} is used twice or is reserved")
        names.add(name)
        node_type = node.get("type")
        if not isinstance(node_type, str) or not _NODE_TYPE_PATTERN.match(node_type):
            raise ValidationError(f"Node type {node_type!r} is not a node identifier, "
                                  f"e.g. GeometryNodeMeshGrid or ShaderNodeMath")
        entry: dict[str, Any] = {"name": name, "type": node_type}
        if "pair_with" in node:
            entry["pair_with"] = node["pair_with"]
        if "location" in node:
            entry["location"] = [float(v) for v in validate_vector(node["location"], size=2,
                                                                   name="location")]
            if any(abs(v) > MAX_COORD for v in entry["location"]):
                raise ValidationError("location is out of range")
        settings = node.get("settings", {})
        if not isinstance(settings, dict):
            raise ValidationError("settings must be an object")
        for key, value in settings.items():
            if not isinstance(key, str) or not _SETTING_PATTERN.match(key):
                raise ValidationError(f"Setting {key!r} must be a lowercase name like operation")
            if not isinstance(value, (bool, int, float, str)):
                raise ValidationError(f"Setting {key!r} must be a single value")
            _plain_value(value, f"setting {key}")
        entry["settings"] = dict(settings)
        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            raise ValidationError("inputs must be an object of socket to value")
        entry["inputs"] = {}
        for key, value in inputs.items():
            ref = _socket_ref(int(key) if isinstance(key, str) and key.isdigit() else key,
                              "input socket")
            entry["inputs"][str(ref)] = _plain_value(value, f"input {key!r}")
        clean_nodes.append(entry)

    spec_names = {entry["name"] for entry in clean_nodes}
    for entry in clean_nodes:
        partner = entry.get("pair_with")
        if partner is not None and (not isinstance(partner, str) or partner == entry["name"]
                                    or partner not in spec_names):
            raise ValidationError(f"{entry['name']}: pair_with must name the zone's output "
                                  f"node in this spec")

    clean_links = []
    for link in links:
        if not isinstance(link, list) or len(link) != 4:
            raise ValidationError("Each link is [from_node, from_socket, to_node, to_socket]")
        from_node, from_socket, to_node, to_socket = link
        for node_name in (from_node, to_node):
            if node_name not in names:
                raise ValidationError(f"Link refers to unknown node {node_name!r}")
        clean_links.append([from_node, _socket_ref(from_socket, "from_socket"),
                            to_node, _socket_ref(to_socket, "to_socket")])
    return {"inputs": _interface_items(spec.get("inputs", []), "inputs"),
            "outputs": _interface_items(spec.get("outputs", []), "outputs"),
            "nodes": clean_nodes, "links": clean_links}

def _from_text(value, socket_type: str):
    """Convert a number or boolean sent as text to what the socket holds.

    Only the socket knows whether "5" is the number five or a label, so the
    conversion happens here and a String socket keeps its text.
    """
    if not isinstance(value, str):
        return value
    text = value.strip()
    try:
        if socket_type.startswith("NodeSocketFloat"):
            number = float(text)
            return number if math.isfinite(number) else value
        if socket_type.startswith("NodeSocketInt"):
            number = float(text)
            return int(number) if math.isfinite(number) else value
    except ValueError:
        return value
    if socket_type.startswith("NodeSocketBool") and text.lower() in ("true", "false"):
        return text.lower() == "true"
    return value

def _unknown_node_message(node_type, known):
    """Name the closest real node types: GeometryNodeCube -> GeometryNodeMeshCube."""
    import difflib

    prefix = next((p for p in NODE_PREFIXES if node_type.startswith(p)), "")
    tail = node_type[len(prefix):].lower()
    near = {n for n in known if tail and tail in n.lower()}
    near.update(difflib.get_close_matches(node_type, known, n=5, cutoff=0.75))
    ranked = sorted(near, key=lambda n: (len(n), n))[:5]
    hint = f" Did you mean: {', '.join(ranked)}?" if ranked else ""
    return f"Unknown node type '{node_type}'.{hint}"

def _known_node_types():
    """Node classes this Blender has, by name. 5.2 creates bpy.types classes
    lazily, so __subclasses__() is empty and refused every node."""
    base_names = NODE_PREFIXES
    bases = tuple(getattr(bpy.types, b) for b in base_names)
    known = set()
    for name in dir(bpy.types):
        if name.startswith(base_names) and name not in base_names:
            cls = getattr(bpy.types, name, None)
            if isinstance(cls, type) and issubclass(cls, bases):
                known.add(name)
    return known

def _base_node_props():
    """Properties every node has (name, location, label...): not node settings."""
    return set(bpy.types.Node.bl_rna.properties.keys())

def _data_block(socket_type, name, what):
    collection = getattr(bpy.data, ID_SOCKETS[socket_type])
    found = collection.get(name) if isinstance(name, str) else None
    if found is None:
        raise ValueError(f"{what} needs an existing {ID_SOCKETS[socket_type][:-1]}; "
                         f"'{name}' not found")
    return found

def _find_socket(node, sockets, ref, side):
    if isinstance(ref, str) and ref.isdigit():
        ref = int(ref)
    if isinstance(ref, int):
        if ref >= len(sockets):
            raise ValueError(f"'{node.name}' has {len(sockets)} {side}s; index {ref} is past them")
        return sockets[ref]
    for want_enabled in (True, False):
        for sock in sockets:
            if (sock.name == ref or sock.identifier == ref) and (sock.enabled or not want_enabled):
                return sock
    names = ", ".join(sock.name for sock in sockets if sock.enabled)
    raise ValueError(f"'{node.name}' has no {side} '{ref}'. {side.capitalize()}s: {names}")

def _apply_node_settings(node, settings):
    base = _base_node_props()
    props = node.bl_rna.properties
    for key, value in settings.items():
        rna = props.get(key)
        if rna is None or key in base or rna.is_readonly or rna.type not in NODE_SETTING_TYPES:
            own = sorted(k for k, p in props.items() if k not in base and not p.is_readonly
                         and p.type in NODE_SETTING_TYPES)
            raise ValueError(f"'{key}' is not a setting of {node.bl_idname}. "
                             f"Settings: {', '.join(own) or 'none'}")
        try:
            setattr(node, key, value)
        except (TypeError, ValueError) as e:
            raise ValueError(f"{node.name}: cannot set {key} to {value!r}: {e}") from None

def _set_socket_value(node, sock, value):
    if sock.bl_idname in ID_SOCKETS:
        value = _data_block(sock.bl_idname, value, f"'{node.name}' input '{sock.name}'")
    else:
        value = _from_text(value, sock.bl_idname)
    try:
        sock.default_value = value
    except (TypeError, ValueError, AttributeError) as e:
        raise ValueError(f"'{node.name}' input '{sock.name}' cannot take {value!r}: {e}") from None

def _add_interface(group, items, in_out):
    for item in items:
        socket_type = INTERFACE_SOCKETS[item["type"]]
        sock = group.interface.new_socket(name=item["name"], in_out=in_out,
                                          socket_type=socket_type)
        if "default" in item:
            value = item["default"]
            if socket_type in ID_SOCKETS:
                value = _data_block(socket_type, value, f"Group input '{item['name']}'")
            sock.default_value = value
        if "min" in item:
            sock.min_value = item["min"]
        if "max" in item:
            sock.max_value = item["max"]

def _fill_group(group, spec):
    _add_interface(group, [{"name": "Geometry", "type": "GEOMETRY"}] + spec["inputs"], "INPUT")
    _add_interface(group, [{"name": "Geometry", "type": "GEOMETRY"}] + spec["outputs"], "OUTPUT")
    group_in = group.nodes.new("NodeGroupInput")
    group_in.location = (-400, 0)
    group_out = group.nodes.new("NodeGroupOutput")
    group_out.location = (400, 0)
    nodes = {"Group Input": group_in, "Group Output": group_out}

    known = _known_node_types()
    for entry in spec["nodes"]:
        if entry["type"] not in known:
            raise ValueError(_unknown_node_message(entry["type"], known))
        node = group.nodes.new(type=entry["type"])
        node.name = entry["name"]
        node.location = tuple(entry.get("location", (0, 0)))
        _apply_node_settings(node, entry.get("settings", {}))  # may change which sockets exist
        nodes[entry["name"]] = node

    # Zones get their sockets from pairing, so pair before any value or link
    for entry in spec["nodes"]:
        if "pair_with" in entry:
            node = nodes[entry["name"]]
            if not hasattr(node, "pair_with_output"):
                raise ValueError(f"'{node.name}' is not a zone input node; only simulation, "
                                 f"repeat and for-each zone inputs pair")
            if not node.pair_with_output(nodes[entry["pair_with"]]):
                raise ValueError(f"'{node.name}' cannot pair with '{entry['pair_with']}': "
                                 f"use the matching zone output node")

    for entry in spec["nodes"]:
        node = nodes[entry["name"]]
        for ref, value in entry.get("inputs", {}).items():
            _set_socket_value(node, _find_socket(node, node.inputs, ref, "input"), value)

    links = spec["links"]
    if not any(link[2] == "Group Output" for link in links):
        links = [["Group Input", "Geometry", "Group Output", "Geometry"]] + links
    for from_name, from_ref, to_name, to_ref in links:
        source, target = nodes[from_name], nodes[to_name]
        group.links.new(_find_socket(source, source.outputs, from_ref, "output"),
                        _find_socket(target, target.inputs, to_ref, "input"))
    return len(nodes), len(links)

def handle_build_geometry_nodes(params):
    """Build into a fresh group; swap it onto the modifier only if every step worked."""
    obj = bpy.data.objects.get(params.get("object_name"))
    if obj is None:
        raise ValueError(f"Object '{params.get('object_name')}' not found")
    if not hasattr(obj, "modifiers"):
        raise ValueError(f"Object '{obj.name}' cannot take modifiers")
    name = params.get("modifier_name", "GeometryNodes")
    group = bpy.data.node_groups.new(name=name, type="GeometryNodeTree")
    try:
        node_count, link_count = _fill_group(group, params["spec"])
    except Exception:
        bpy.data.node_groups.remove(group)
        raise
    modifier = obj.modifiers.get(name)
    if modifier is None:
        modifier = obj.modifiers.new(name=name, type="NODES")
    elif modifier.type != "NODES":
        bpy.data.node_groups.remove(group)
        raise ValueError(f"Modifier '{name}' is not a geometry nodes modifier")
    modifier.node_group = group
    return {"object": obj.name, "modifier": modifier.name, "node_group": group.name,
            "nodes": node_count, "links": link_count}
