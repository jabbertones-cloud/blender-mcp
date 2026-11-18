"""Blender 5.3 modifier-input transfer around a donor graph replacement."""
import copy
from blenderwright_graph_donor import INTERFACE_SOCKETS


def sockets(group):
    return [s for s in group.interface.items_tree if s.item_type == "SOCKET"
            and s.in_out == "INPUT" and s.socket_type != "NodeSocketGeometry"]


def capture(modifier):
    if not modifier or not modifier.node_group:
        return []
    return [(s.name, s.socket_type, s.identifier,
             copy.copy(getattr(modifier.properties.inputs, s.identifier).value),
             getattr(modifier.properties.inputs, s.identifier).type,
             getattr(modifier.properties.inputs, s.identifier).attribute_name)
            for s in sockets(modifier.node_group)]


def preflight(saved, spec):
    if saved and [(s[0], s[1]) for s in saved] != [
            (item["name"], INTERFACE_SOCKETS[item["type"]])
            for item in spec.get("inputs", [])]:
        raise ValueError("Existing modifier input names/types differ; refuse destructive graph replacement")


def restore(modifier, saved):
    dest = sockets(modifier.node_group)
    if len(saved) != len(dest) or [(s[0], s[1]) for s in saved] != [
            (s.name, s.socket_type) for s in dest]:
        raise ValueError("Generated modifier interface differs from source")
    mapping = {}
    for (name, kind, old_id, value, mode, attribute), target in zip(saved, dest):
        entry = getattr(modifier.properties.inputs, target.identifier)
        entry.type = mode
        if mode == "VALUE": entry.value = value
        else: entry.attribute_name = attribute
        mapping[old_id] = target.identifier
    return mapping
