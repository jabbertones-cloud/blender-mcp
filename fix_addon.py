import re, shutil

path = '/Users/tatsheen/claw-architect/openclaw-blender-mcp/blender_addon/openclaw_blender_bridge.py'
with open(path, 'r') as f:
    lines = f.readlines()

# Fix 1: sculpt stroke return to OBJECT mode
fixed = False
new_lines = []
for i, line in enumerate(lines):
    if 'return {"stroked": True, "brush": brush_name, "points": len(stroke_points)}' in line and not fixed:
        indent = '            '
        new_lines.append(indent + 'bpy.ops.object.mode_set(mode="OBJECT")\n')
        new_lines.append(line)
        fixed = True
        print(f'Fix 1: Added OBJECT mode before stroked return at line {i+1}')
    else:
        new_lines.append(line)

if not fixed:
    print('Fix 1: stroked return not found')

lines = new_lines

# Fix 2 and 3: Add mode safety to create_object and force_field
safety = ('    if bpy.context.active_object and bpy.context.active_object.mode != "OBJECT":\n'
          '        try:\n'
          '            bpy.ops.object.mode_set(mode="OBJECT")\n'
          '        except:\n'
          '            pass\n')

targets = [
    ('handle_create_object', 'Ensure OBJECT mode before creating'),
    ('handle_force_field', 'Ensure OBJECT mode before force field'),
]

for func_name, comment in targets:
    content_check = ''.join(lines)
    if comment in content_check:
        print(f'Fix for {func_name}: already present')
        continue
    
    new_lines = []
    in_func = False
    docstring_count = 0
    inserted = False
    
    for i, line in enumerate(lines):
        new_lines.append(line)
        if not inserted:
            if f'def {func_name}(params):' in line:
                in_func = True
                docstring_count = 0
            elif in_func and '"""' in line:
                docstring_count += line.count('"""')
                if docstring_count >= 2:
                    new_lines.append(f'    # {comment}\n')
                    new_lines.append(safety)
                    inserted = True
                    print(f'Fix for {func_name}: inserted after line {i+1}')
    
    lines = new_lines

with open(path, 'w') as f:
    f.writelines(lines)

dst = '/Users/tatsheen/Library/Application Support/Blender/5.1/scripts/addons/openclaw_blender_bridge.py'
shutil.copy(path, dst)
print('Copied to Blender addons')
print('Done')
