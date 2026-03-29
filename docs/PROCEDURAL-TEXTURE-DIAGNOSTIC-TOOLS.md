# Procedural Texture Diagnostic Tools & Advanced Python

> **Companion to PROCEDURAL-TEXTURE-TROUBLESHOOTING.md**
> 
> Production-ready Python utilities for diagnosing and fixing procedural texture issues in Blender cityscapes.

---

## Complete Diagnostic Suite

### Script: Full Health Check

Run this to get a complete report on all buildings' texture setups.

```python
import bpy
from mathutils import Vector

def full_texture_diagnostic_report(building_objects=None):
    """
    Complete health check for procedural textures on buildings.
    Returns structured report: issues, warnings, recommendations.
    """
    
    if building_objects is None:
        building_objects = [obj for obj in bpy.context.scene.objects 
                           if obj.type == 'MESH' and 'building' in obj.name.lower()]
    
    report = {
        'total_buildings': len(building_objects),
        'critical_issues': [],
        'warnings': [],
        'recommendations': [],
        'buildings': {}
    }
    
    for obj in building_objects:
        obj_report = {
            'name': obj.name,
            'scale': (obj.scale.x, obj.scale.y, obj.scale.z),
            'has_scale_applied': is_scale_applied(obj),
            'materials': {},
            'texture_nodes': {},
            'issues': []
        }
        
        # Check scale
        if not is_scale_applied(obj):
            report['critical_issues'].append(f"{obj.name}: Scale NOT applied. Will cause texture distortion.")
            obj_report['issues'].append('SCALE_NOT_APPLIED')
        
        # Check materials
        for mat in obj.data.materials:
            if not mat or not mat.use_nodes:
                report['warnings'].append(f"{obj.name}: Material not using nodes.")
                continue
            
            nodes = mat.node_tree.nodes
            
            # Find texture nodes
            brick_nodes = [n for n in nodes if n.type == 'TEX_BRICK']
            noise_nodes = [n for n in nodes if n.type == 'TEX_NOISE']
            tex_coord_nodes = [n for n in nodes if n.type == 'TEX_COORD']
            
            obj_report['texture_nodes'][mat.name] = {
                'brick': len(brick_nodes),
                'noise': len(noise_nodes),
                'tex_coord': len(tex_coord_nodes)
            }
            
            # Validate Brick Fac usage
            for brick in brick_nodes:
                fac_output = brick.outputs['Fac']
                fac_connections = fac_output.links
                
                if not fac_connections:
                    report['warnings'].append(f"{obj.name}: Brick Fac output NOT connected.")
                    obj_report['issues'].append('BRICK_FAC_UNUSED')
                else:
                    # Check if Fac is inverted
                    for link in fac_connections:
                        to_node = link.to_node
                        if to_node.type == 'MATH' and to_node.operation == 'SUBTRACT':
                            # Check if input 0 is 1.0 (correct inversion)
                            if abs(to_node.inputs[0].default_value - 1.0) < 0.001:
                                # Correctly inverted
                                pass
                            else:
                                report['warnings'].append(
                                    f"{obj.name}: Brick Fac inversion incorrect. "
                                    f"Should be (1.0 - Fac), got ({to_node.inputs[0].default_value} - Fac)"
                                )
                                obj_report['issues'].append('BRICK_FAC_INVERSION_WRONG')
                        else:
                            report['warnings'].append(
                                f"{obj.name}: Brick Fac may not be inverted. "
                                f"Connected to {to_node.type}, expected Math SUBTRACT."
                            )
                            obj_report['issues'].append('BRICK_FAC_NOT_INVERTED')
            
            # Check scale matching (Brick vs Noise)
            if brick_nodes and noise_nodes:
                brick = brick_nodes[0]
                noise = noise_nodes[0]
                brick_scale = brick.inputs['Scale'].default_value
                noise_scale = noise.inputs['Scale'].default_value
                
                if abs(brick_scale - noise_scale) > 0.01:
                    report['warnings'].append(
                        f"{obj.name}: Brick scale ({brick_scale}) ≠ Noise scale ({noise_scale}). "
                        f"Will cause blob patterns."
                    )
                    obj_report['issues'].append('SCALE_MISMATCH')
                else:
                    # Good
                    pass
            
            # Check ColorRamp interpolation
            for ramp_node in nodes:
                if ramp_node.type == 'VALTORGT':
                    if ramp_node.color_ramp.interpolation != 'LINEAR':
                        report['warnings'].append(
                            f"{obj.name}: ColorRamp using {ramp_node.color_ramp.interpolation} "
                            f"interpolation (should be LINEAR for smooth windows)."
                        )
                        obj_report['issues'].append('COLORRAMP_CONSTANT')
            
            # Check texture coordinates
            for tex_coord in tex_coord_nodes:
                # Determine which outputs are actually used
                generated_used = any(
                    link for link in tex_coord.outputs['Generated'].links
                ) if 'Generated' in tex_coord.outputs else False
                
                object_used = any(
                    link for link in tex_coord.outputs['Object'].links
                ) if 'Object' in tex_coord.outputs else False
                
                if generated_used and not is_scale_applied(obj):
                    report['warnings'].append(
                        f"{obj.name}: Using Generated coords on non-uniformly scaled object. "
                        f"Consider Object coords + Mapping, or apply scale first."
                    )
                    obj_report['issues'].append('GENERATED_COORDS_NO_SCALE')
        
        report['buildings'][obj.name] = obj_report
    
    # Generate recommendations
    num_scale_issues = len([b for b in report['buildings'].values() 
                           if 'SCALE_NOT_APPLIED' in b['issues']])
    if num_scale_issues > 0:
        report['recommendations'].append(
            f"CRITICAL: {num_scale_issues} building(s) need scale applied (Ctrl+A). "
            f"Run: apply_all_scales(building_objects)"
        )
    
    num_fac_issues = len([b for b in report['buildings'].values() 
                         if 'BRICK_FAC_NOT_INVERTED' in b['issues']])
    if num_fac_issues > 0:
        report['recommendations'].append(
            f"HIGH PRIORITY: {num_fac_issues} building(s) have incorrect Fac usage. "
            f"Brick Fac should be inverted (1.0 - Fac). Run: fix_brick_fac_all(building_objects)"
        )
    
    num_scale_mismatch = len([b for b in report['buildings'].values() 
                             if 'SCALE_MISMATCH' in b['issues']])
    if num_scale_mismatch > 0:
        report['recommendations'].append(
            f"HIGH PRIORITY: {num_scale_mismatch} building(s) have Brick ≠ Noise scale. "
            f"Run: match_texture_scales_all(building_objects)"
        )
    
    return report


def is_scale_applied(obj):
    """Check if object scale is identity (applied)."""
    scale = obj.scale
    return (abs(scale.x - 1.0) < 0.001 and 
            abs(scale.y - 1.0) < 0.001 and 
            abs(scale.z - 1.0) < 0.001)


def print_diagnostic_report(report):
    """Pretty-print diagnostic report."""
    print("\n" + "="*70)
    print("PROCEDURAL TEXTURE DIAGNOSTIC REPORT")
    print("="*70)
    
    print(f"\n📊 SUMMARY")
    print(f"Total buildings: {report['total_buildings']}")
    print(f"Critical issues: {len(report['critical_issues'])}")
    print(f"Warnings: {len(report['warnings'])}")
    
    if report['critical_issues']:
        print(f"\n🚨 CRITICAL ISSUES")
        for issue in report['critical_issues']:
            print(f"  • {issue}")
    
    if report['warnings']:
        print(f"\n⚠️  WARNINGS")
        for warning in report['warnings']:
            print(f"  • {warning}")
    
    if report['recommendations']:
        print(f"\n✅ RECOMMENDED FIXES")
        for rec in report['recommendations']:
            print(f"  • {rec}")
    
    print(f"\n📋 BUILDING DETAILS")
    for name, obj_data in report['buildings'].items():
        print(f"\n  {name}")
        print(f"    Scale: {obj_data['scale']}")
        print(f"    Scale applied: {'Yes' if obj_data['has_scale_applied'] else 'No'}")
        if obj_data['issues']:
            print(f"    Issues: {', '.join(obj_data['issues'])}")
    
    print("\n" + "="*70 + "\n")


# Usage:
# report = full_texture_diagnostic_report()
# print_diagnostic_report(report)
```

---

## Batch Fix Functions

### Fix All: Apply Scales

```python
def apply_all_scales(building_objects=None):
    """Apply scale on all buildings."""
    if building_objects is None:
        building_objects = [obj for obj in bpy.context.scene.objects 
                           if obj.type == 'MESH']
    
    count = 0
    for obj in building_objects:
        if not is_scale_applied(obj):
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.transform_apply(scale=True)
            count += 1
    
    print(f"✓ Applied scale to {count} objects")
    return count

# Usage:
# apply_all_scales()
```

### Fix All: Invert Brick Fac

```python
def fix_brick_fac_all(building_objects=None):
    """Ensure Brick Fac is inverted on all buildings."""
    if building_objects is None:
        building_objects = [obj for obj in bpy.context.scene.objects 
                           if obj.type == 'MESH']
    
    fixed_count = 0
    
    for obj in building_objects:
        for mat in obj.data.materials:
            if not mat or not mat.use_nodes:
                continue
            
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            
            # Find Brick texture
            brick_node = None
            for node in nodes:
                if node.type == 'TEX_BRICK':
                    brick_node = node
                    break
            
            if not brick_node:
                continue
            
            # Check if Fac is already inverted
            fac_output = brick_node.outputs['Fac']
            is_inverted = False
            
            for link in fac_output.links:
                to_node = link.to_node
                if (to_node.type == 'MATH' and 
                    to_node.operation == 'SUBTRACT' and
                    abs(to_node.inputs[0].default_value - 1.0) < 0.001):
                    is_inverted = True
                    break
            
            if not is_inverted:
                # Create invert node
                invert_node = nodes.new('ShaderNodeMath')
                invert_node.operation = 'SUBTRACT'
                invert_node.inputs[0].default_value = 1.0
                invert_node.name = 'Invert_Brick_Fac'
                
                # Disconnect Fac from any existing nodes
                for link in list(fac_output.links):
                    links.remove(link)
                
                # Connect: Fac -> input[1] of invert
                links.new(fac_output, invert_node.inputs[1])
                
                fixed_count += 1
    
    print(f"✓ Fixed Brick Fac inversion on {fixed_count} materials")
    return fixed_count

# Usage:
# fix_brick_fac_all()
```

### Fix All: Match Texture Scales

```python
def match_texture_scales_all(building_objects=None):
    """Match Noise scale to Brick scale on all buildings."""
    if building_objects is None:
        building_objects = [obj for obj in bpy.context.scene.objects 
                           if obj.type == 'MESH']
    
    fixed_count = 0
    
    for obj in building_objects:
        for mat in obj.data.materials:
            if not mat or not mat.use_nodes:
                continue
            
            nodes = mat.node_tree.nodes
            
            brick_nodes = [n for n in nodes if n.type == 'TEX_BRICK']
            noise_nodes = [n for n in nodes if n.type == 'TEX_NOISE']
            
            if brick_nodes and noise_nodes:
                brick_scale = brick_nodes[0].inputs['Scale'].default_value
                
                for noise in noise_nodes:
                    old_scale = noise.inputs['Scale'].default_value
                    if abs(old_scale - brick_scale) > 0.01:
                        noise.inputs['Scale'].default_value = brick_scale
                        fixed_count += 1
    
    print(f"✓ Matched texture scales on {fixed_count} noise nodes")
    return fixed_count

# Usage:
# match_texture_scales_all()
```

### Fix All: Set ColorRamp to LINEAR

```python
def fix_colorramp_interpolation_all(building_objects=None):
    """Set all ColorRamps to LINEAR interpolation."""
    if building_objects is None:
        building_objects = [obj for obj in bpy.context.scene.objects 
                           if obj.type == 'MESH']
    
    fixed_count = 0
    
    for obj in building_objects:
        for mat in obj.data.materials:
            if not mat or not mat.use_nodes:
                continue
            
            nodes = mat.node_tree.nodes
            
            for node in nodes:
                if node.type == 'VALTORGT':
                    if node.color_ramp.interpolation != 'LINEAR':
                        node.color_ramp.interpolation = 'LINEAR'
                        fixed_count += 1
    
    print(f"✓ Fixed ColorRamp interpolation on {fixed_count} nodes")
    return fixed_count

# Usage:
# fix_colorramp_interpolation_all()
```

---

## Automated Fix Pipeline

```python
def fix_all_texture_issues_automated(building_objects=None):
    """
    Run all fixes in sequence.
    1. Apply scales
    2. Fix Brick Fac inversion
    3. Match texture scales
    4. Set ColorRamp to LINEAR
    5. Report results
    """
    
    print("\n🔧 STARTING AUTOMATED TEXTURE FIX PIPELINE\n")
    
    if building_objects is None:
        building_objects = [obj for obj in bpy.context.scene.objects 
                           if obj.type == 'MESH']
    
    print(f"Processing {len(building_objects)} buildings...\n")
    
    # Step 1
    print("Step 1: Applying scales...")
    scales_fixed = apply_all_scales(building_objects)
    
    # Step 2
    print("\nStep 2: Fixing Brick Fac inversion...")
    fac_fixed = fix_brick_fac_all(building_objects)
    
    # Step 3
    print("\nStep 3: Matching texture scales...")
    scales_matched = match_texture_scales_all(building_objects)
    
    # Step 4
    print("\nStep 4: Fixing ColorRamp interpolation...")
    colorramps_fixed = fix_colorramp_interpolation_all(building_objects)
    
    # Step 5
    print("\n" + "="*70)
    print("✅ FIXES COMPLETED")
    print("="*70)
    print(f"Scales applied:           {scales_fixed}")
    print(f"Fac inversions fixed:     {fac_fixed}")
    print(f"Scales matched:           {scales_matched}")
    print(f"ColorRamps fixed:         {colorramps_fixed}")
    print(f"Total changes:            {scales_fixed + fac_fixed + scales_matched + colorramps_fixed}")
    print("="*70 + "\n")
    
    # Final diagnostic
    print("Running final diagnostic...\n")
    report = full_texture_diagnostic_report(building_objects)
    print_diagnostic_report(report)
    
    return report

# Usage:
# report = fix_all_texture_issues_automated()
```

---

## Node Inspection Tools

### Visualize Shader Node Graph

```python
def visualize_shader_graph(obj, mat_index=0):
    """Print a text representation of shader node connections."""
    
    mat = obj.data.materials[mat_index]
    if not mat or not mat.use_nodes:
        print(f"Material {mat_index} not using nodes")
        return
    
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    
    print(f"\n📐 SHADER GRAPH: {obj.name} → {mat.name}\n")
    
    # Group nodes by type
    node_groups = {}
    for node in nodes:
        node_type = node.type
        if node_type not in node_groups:
            node_groups[node_type] = []
        node_groups[node_type].append(node)
    
    # Print nodes
    for node_type, node_list in sorted(node_groups.items()):
        print(f"  [{node_type}]")
        for node in node_list:
            print(f"    • {node.name}")
            if hasattr(node, 'inputs'):
                for inp in node.inputs:
                    if inp.default_value and not isinstance(inp.default_value, object):
                        val = inp.default_value
                        if isinstance(val, (int, float)):
                            val = f"{val:.2f}"
                        print(f"      └ {inp.name}: {val}")
    
    # Print connections
    print(f"\n  [CONNECTIONS]")
    for link in links:
        from_node = link.from_node.name
        from_socket = link.from_socket.name
        to_node = link.to_node.name
        to_socket = link.to_socket.name
        print(f"    {from_node}.{from_socket} → {to_node}.{to_socket}")
    
    print()

# Usage:
# obj = bpy.data.objects['Building001']
# visualize_shader_graph(obj)
```

---

## Parameter Tuning Assistant

```python
def tune_brick_parameters(obj, mat_index=0, 
                         brick_scale=5.0, mortar_size=0.25, 
                         noise_scale=None):
    """
    Tune brick and noise parameters on a single object.
    If noise_scale is None, sets it to match brick_scale.
    """
    
    mat = obj.data.materials[mat_index]
    if not mat or not mat.use_nodes:
        print(f"Material {mat_index} not using nodes")
        return
    
    nodes = mat.node_tree.nodes
    
    if noise_scale is None:
        noise_scale = brick_scale
    
    # Find and update Brick
    for node in nodes:
        if node.type == 'TEX_BRICK':
            node.inputs['Scale'].default_value = brick_scale
            node.inputs['Mortar Size'].default_value = mortar_size
            print(f"✓ Updated Brick: Scale={brick_scale}, Mortar={mortar_size}")
    
    # Find and update Noise
    for node in nodes:
        if node.type == 'TEX_NOISE':
            node.inputs['Scale'].default_value = noise_scale
            print(f"✓ Updated Noise: Scale={noise_scale}")
    
    # Update ColorRamp threshold (optional)
    for node in nodes:
        if node.type == 'VALTORGT':
            # Set threshold at 0.5 (50% lit, 50% dark)
            node.color_ramp.elements[0].position = 0.4
            node.color_ramp.elements[1].position = 0.6
            print(f"✓ Updated ColorRamp threshold")

# Usage:
# obj = bpy.data.objects['Building001']
# tune_brick_parameters(obj, brick_scale=5.0, mortar_size=0.2)
```

---

## Export/Import Texture Configuration

```python
import json

def export_texture_config(obj, filepath):
    """Export texture node parameters to JSON for reuse."""
    
    config = {
        'object_name': obj.name,
        'scale': tuple(obj.scale),
        'materials': {}
    }
    
    for mat in obj.data.materials:
        if not mat or not mat.use_nodes:
            continue
        
        mat_config = {
            'nodes': {},
            'use_nodes': True
        }
        
        for node in mat.node_tree.nodes:
            node_data = {
                'type': node.type,
                'inputs': {}
            }
            
            # Export input values
            for inp in node.inputs:
                if hasattr(inp, 'default_value'):
                    val = inp.default_value
                    if isinstance(val, (int, float, str)):
                        node_data['inputs'][inp.name] = val
                    elif isinstance(val, tuple):
                        node_data['inputs'][inp.name] = list(val)
            
            mat_config['nodes'][node.name] = node_data
        
        config['materials'][mat.name] = mat_config
    
    with open(filepath, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"✓ Exported texture config to {filepath}")


def import_texture_config(obj, filepath):
    """Import texture node parameters from JSON."""
    
    with open(filepath, 'r') as f:
        config = json.load(f)
    
    for mat_name, mat_config in config['materials'].items():
        mat = bpy.data.materials.get(mat_name)
        if not mat or not mat.use_nodes:
            print(f"⚠️  Material {mat_name} not found or not using nodes")
            continue
        
        for node_name, node_data in mat_config['nodes'].items():
            node = mat.node_tree.nodes.get(node_name)
            if not node:
                continue
            
            # Import input values
            for inp_name, inp_value in node_data['inputs'].items():
                if inp_name in node.inputs:
                    try:
                        node.inputs[inp_name].default_value = inp_value
                    except:
                        pass  # Skip if type mismatch
    
    print(f"✓ Imported texture config from {filepath}")

# Usage:
# export_texture_config(obj, "/tmp/texture_config.json")
# import_texture_config(obj, "/tmp/texture_config.json")
```

---

## Quick Reference

### One-Liner Fixes

```python
# Apply all scales
for obj in bpy.context.selected_objects:
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(scale=True)

# Match all Noise to Brick scale
for obj in bpy.context.selected_objects:
    for mat in obj.data.materials:
        if not mat.use_nodes: continue
        brick = next((n for n in mat.node_tree.nodes if n.type == 'TEX_BRICK'), None)
        noise = next((n for n in mat.node_tree.nodes if n.type == 'TEX_NOISE'), None)
        if brick and noise:
            noise.inputs['Scale'].default_value = brick.inputs['Scale'].default_value

# Set all ColorRamps to LINEAR
for obj in bpy.context.selected_objects:
    for mat in obj.data.materials:
        if not mat.use_nodes: continue
        for node in mat.node_tree.nodes:
            if node.type == 'VALTORGT':
                node.color_ramp.interpolation = 'LINEAR'
```

---

**Last Updated:** 2026-03-24 | Diagnostic Suite v1.0 | Ready for Integration
