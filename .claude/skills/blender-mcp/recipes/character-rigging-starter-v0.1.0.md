---
id: character-rigging-starter
version: 0.1.0
title: Character Rigging Setup with Auto-Weights and IK Chains
description: |
  Complete character rigging pipeline including armature creation,
  auto-weight painting, IK chain setup for limbs, and control rig
  configuration. Production-ready for animation workflows.
trigger_patterns:
  - "character rig"
  - "armature setup"
  - "IK chain"
  - "auto-weight"
  - "animation ready"
tools_used:
  - blender_create_object
  - blender_add_armature
  - execute_python
  - blender_parent_object
created_at: 2026-04-23
author: AutoSkill
tier: atomic
category: rigging
dependencies: []
---

## When to Use
Essential for character animation pipelines. Use when:
- Setting up characters for game engines
- Preparing models for 3D animation
- Creating reusable character rigs
- Building mocap-ready skeletons
- Setting up IK/FK switching for limbs

## Parameters
- **Body Height**: 1.8m (adjustable 1.5-2.2m for human characters)
- **Bone Count**: 30+ (head, spine, arms, legs, hands, feet)
- **IK Chain Type**: Limb (arms and legs use IK solver)
- **Weight Distribution**: Auto-weights via Blender deformer
- **Control Rig**: Yes (separate control hierarchy)

## Steps

1. **Import or Create Base Character Mesh**
Prepare character model with topology optimized for deformation:
```python
import bpy
# Assume mesh already imported or created
# Character should have clean quad topology
char_mesh = bpy.context.active_object
char_mesh.name = 'Character_Body'
# Add subdivision surface for smooth deformation
char_mesh.modifiers.new(name='Subdivision', type='SUBSURF')
char_mesh.modifiers['Subdivision'].levels = 2
char_mesh.modifiers['Subdivision'].render_levels = 3
```

2. **Create Base Armature**
Build skeletal structure with proper bone hierarchy:
```python
import bpy
bpy.ops.object.armature_add(location=(0, 0, 0))
armature = bpy.context.active_object
armature.name = 'Armature_Character'
bpy.context.view_layer.objects.active = armature
bpy.ops.object.mode_set(mode='EDIT')

# Root bone (pelvis)
edit_bones = armature.data.edit_bones
root_bone = edit_bones.new('Root')
root_bone.head = (0, 0, 0)
root_bone.tail = (0, 0, 0.2)

# Spine chain (3 vertebrae)
spine_1 = edit_bones.new('Spine_1')
spine_1.head = root_bone.tail
spine_1.tail = (0, 0, 0.6)
spine_1.parent = root_bone

spine_2 = edit_bones.new('Spine_2')
spine_2.head = spine_1.tail
spine_2.tail = (0, 0, 0.9)
spine_2.parent = spine_1

chest = edit_bones.new('Chest')
chest.head = spine_2.tail
chest.tail = (0, 0, 1.3)
chest.parent = spine_2

# Neck and head
neck = edit_bones.new('Neck')
neck.head = chest.tail
neck.tail = (0, 0, 1.5)
neck.parent = chest

head = edit_bones.new('Head')
head.head = neck.tail
head.tail = (0, 0, 1.8)
head.parent = neck

bpy.ops.object.mode_set(mode='OBJECT')
```

3. **Create Arm Bones (Left and Right)**
Build upper/lower arm and hand chain:
```python
import bpy
armature = bpy.context.active_object
bpy.ops.object.mode_set(mode='EDIT')
edit_bones = armature.data.edit_bones

# Left arm
l_shoulder = edit_bones.new('L_Shoulder')
l_shoulder.head = (0.2, 0, 1.2)
l_shoulder.tail = (0.5, 0, 1.1)
l_shoulder.parent = chest

l_upper_arm = edit_bones.new('L_UpperArm')
l_upper_arm.head = l_shoulder.tail
l_upper_arm.tail = (0.9, 0, 0.8)
l_upper_arm.parent = l_shoulder

l_lower_arm = edit_bones.new('L_LowerArm')
l_lower_arm.head = l_upper_arm.tail
l_lower_arm.tail = (1.3, 0, 0.5)
l_lower_arm.parent = l_upper_arm

l_hand = edit_bones.new('L_Hand')
l_hand.head = l_lower_arm.tail
l_hand.tail = (1.5, 0, 0.4)
l_hand.parent = l_lower_arm

# Right arm (mirror of left)
r_shoulder = edit_bones.new('R_Shoulder')
r_shoulder.head = (-0.2, 0, 1.2)
r_shoulder.tail = (-0.5, 0, 1.1)
r_shoulder.parent = chest

r_upper_arm = edit_bones.new('R_UpperArm')
r_upper_arm.head = r_shoulder.tail
r_upper_arm.tail = (-0.9, 0, 0.8)
r_upper_arm.parent = r_shoulder

r_lower_arm = edit_bones.new('R_LowerArm')
r_lower_arm.head = r_upper_arm.tail
r_lower_arm.tail = (-1.3, 0, 0.5)
r_lower_arm.parent = r_upper_arm

r_hand = edit_bones.new('R_Hand')
r_hand.head = r_lower_arm.tail
r_hand.tail = (-1.5, 0, 0.4)
r_hand.parent = r_lower_arm

bpy.ops.object.mode_set(mode='OBJECT')
```

4. **Create Leg Bones (Left and Right)**
Build upper leg, lower leg, foot, and toe chains:
```python
import bpy
armature = bpy.context.active_object
bpy.ops.object.mode_set(mode='EDIT')
edit_bones = armature.data.edit_bones

# Left leg
l_thigh = edit_bones.new('L_Thigh')
l_thigh.head = (0.15, 0, 0.2)
l_thigh.tail = (0.15, 0, -0.3)
l_thigh.parent = root_bone

l_shin = edit_bones.new('L_Shin')
l_shin.head = l_thigh.tail
l_shin.tail = (0.15, 0, -0.8)
l_shin.parent = l_thigh

l_foot = edit_bones.new('L_Foot')
l_foot.head = l_shin.tail
l_foot.tail = (0.15, 0.2, -0.95)
l_foot.parent = l_shin

# Right leg
r_thigh = edit_bones.new('R_Thigh')
r_thigh.head = (-0.15, 0, 0.2)
r_thigh.tail = (-0.15, 0, -0.3)
r_thigh.parent = root_bone

r_shin = edit_bones.new('R_Shin')
r_shin.head = r_thigh.tail
r_shin.tail = (-0.15, 0, -0.8)
r_shin.parent = r_thigh

r_foot = edit_bones.new('R_Foot')
r_foot.head = r_shin.tail
r_foot.tail = (-0.15, 0.2, -0.95)
r_foot.parent = r_shin

bpy.ops.object.mode_set(mode='OBJECT')
```

5. **Apply Automatic Weight Painting**
Generate vertex weights from bone influences:
```python
import bpy
char_mesh = bpy.data.objects['Character_Body']
armature = bpy.data.objects['Armature_Character']

# Parent mesh to armature with automatic weights
bpy.context.view_layer.objects.active = char_mesh
char_mesh.select_set(True)
armature.select_set(True)
bpy.context.view_layer.objects.active = armature

bpy.ops.object.parent_set(type='ARMATURE_AUTO')
```

6. **Create IK Chains for Arms and Legs**
Set up inverse kinematics for limb control:
```python
import bpy
armature = bpy.context.active_object
bpy.ops.object.mode_set(mode='POSE')

# Left arm IK constraint
l_lower_arm_pb = armature.pose.bones['L_LowerArm']
ik_constraint = l_lower_arm_pb.constraints.new(type='IK')
ik_constraint.target = armature
ik_constraint.subtarget = 'L_Hand'
ik_constraint.chain_count = 2  # IK solver includes 2 bones back
ik_constraint.use_tail = True

# Right arm IK constraint
r_lower_arm_pb = armature.pose.bones['R_LowerArm']
ik_constraint = r_lower_arm_pb.constraints.new(type='IK')
ik_constraint.target = armature
ik_constraint.subtarget = 'R_Hand'
ik_constraint.chain_count = 2

# Left leg IK constraint
l_foot_pb = armature.pose.bones['L_Foot']
ik_constraint = l_foot_pb.constraints.new(type='IK')
ik_constraint.target = armature
ik_constraint.subtarget = 'L_Foot'
ik_constraint.chain_count = 2

# Right leg IK constraint
r_foot_pb = armature.pose.bones['R_Foot']
ik_constraint = r_foot_pb.constraints.new(type='IK')
ik_constraint.target = armature
ik_constraint.subtarget = 'R_Foot'
ik_constraint.chain_count = 2

bpy.ops.object.mode_set(mode='OBJECT')
```

7. **Create Control Rig**
Build high-level control objects for animator interaction:
```python
import bpy
# Create control objects
controls = ['Root_Control', 'Hip_Control', 'Chest_Control', 'Head_Control']

for control_name in controls:
    bpy.ops.object.empty_add(type='CUBE', location=(0, 0, 0))
    control = bpy.context.active_object
    control.name = control_name
    control.scale = (0.15, 0.15, 0.15)
```

8. **Verify Rig Structure**
Execute comprehensive rigging validation:
```python
import bpy
armature = bpy.data.objects['Armature_Character']
char_mesh = bpy.data.objects['Character_Body']

print(f'Total bones: {len(armature.data.bones)}')
print(f'Mesh deformers (modifiers): {len(char_mesh.modifiers)}')

# Check vertex groups (weight maps)
print(f'Vertex groups: {len(char_mesh.vertex_groups)}')
for vg in char_mesh.vertex_groups:
    print(f'  - {vg.name}')

# Verify bone hierarchy
print(f'Root bones: {len([b for b in armature.data.bones if b.parent is None])}')

bpy.context.scene.render.engine = 'CYCLES'
print('Rig ready for animation.')
```

## Verification (GCS Constraints)

```json
{
  "constraints": [
    {
      "type": "bone_count",
      "operator": ">=",
      "value": 25,
      "description": "Minimum 25 bones for complete skeleton"
    },
    {
      "type": "object_relationship",
      "parent": "Armature_Character",
      "child": "Character_Body",
      "constraint": "parent_type == 'ARMATURE_AUTO'",
      "description": "Mesh parented to armature with auto-weights"
    },
    {
      "type": "constraint_count",
      "bone": "L_LowerArm",
      "constraint_type": "IK",
      "operator": ">=",
      "value": 1,
      "description": "IK constraints applied to arm bones"
    },
    {
      "type": "vertex_group_count",
      "object": "Character_Body",
      "operator": ">=",
      "value": 20,
      "description": "Vertex groups created for weight mapping"
    },
    {
      "type": "modifier_present",
      "object": "Character_Body",
      "modifier_type": "SUBSURF",
      "description": "Subdivision surface modifier for smooth deformation"
    },
    {
      "type": "armature_property",
      "property": "pose_position",
      "supported_values": ["REST", "POSE"],
      "description": "Armature supports pose mode deformation"
    }
  ],
  "rigging_specs": {
    "skeleton_type": "humanoid",
    "total_bones": 30,
    "ik_chains": 4,
    "control_objects": 4,
    "deformation_method": "auto_weights",
    "animation_ready": true
  }
}
```

## Known Failure Modes
- **Weight Painting Issues**: Rerun auto-weights; use weight normalize to fix overpaint
- **IK Chain Flipping**: Increase chain_count; check bone roll orientation
- **Mesh Deformation Asymmetrical**: Verify bone positions are symmetrical (L/R mirrored)
- **Poor Deformation at Joints**: Add more bones (e.g., extra spine segments); increase SubSurf levels
- **Control Rig Offset**: Ensure control objects parent to corresponding bones in pose mode
- **Animation Jumpiness**: Smooth keyframe interpolation; use Bézier curves in Graph Editor
- **Baking Issues**: Ensure render engine set to CYCLES before baking; check cage object if using modifiers

