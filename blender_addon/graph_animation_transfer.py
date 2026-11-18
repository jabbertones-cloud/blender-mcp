"""Blender 5.3 Action F-Curve input identifier preservation."""
import re


def capture(obj, modifier_name):
    data = obj.animation_data
    if not data:
        return []
    target = f'modifiers["{modifier_name}"].properties.inputs.'
    if data.nla_tracks or any(target in f.data_path for f in data.drivers):
        raise ValueError("NLA or driver-based graph input animation needs separate verification")
    action = data.action
    if not action:
        return []
    if action.users > 1 or not data.action_slot:
        raise ValueError("Shared or slotless Action cannot be remapped safely")
    records = []
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                if bag.slot_handle != data.action_slot.handle:
                    continue
                records += [(fc, fc.data_path) for fc in bag.fcurves
                            if fc.data_path.startswith(target)]
    return records
def rebind(records, mapping):
    updates = []
    for curve, old_path in records:
        match = re.search(r'\.inputs\.(Socket_[0-9]+)\.', old_path)
        if not match or match.group(1) not in mapping:
            raise ValueError("Animated input cannot be mapped to the rebuilt graph")
        updates.append((curve, old_path.replace(
            f".inputs.{match.group(1)}.", f".inputs.{mapping[match.group(1)]}.")))
    for curve, new_path in updates:
        curve.data_path = new_path
    return len(updates)

def rollback(records):
    for curve, original in records:
        curve.data_path = original
