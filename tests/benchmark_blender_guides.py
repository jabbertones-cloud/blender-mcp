"""Compare the same task-specific guide lookup against exact main and candidate."""
import asyncio
import ast
import json
import os
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server import blender_mcp_guided as candidate
from server.blender_mcp_guided import GoalInput as CandidateInput, router_set_goal as candidate_goal

BASE = os.getenv('BLENDER_BENCH_BASE', '8ab74c6926ba0ee1d3f94fef81864e86495e195a')
source = subprocess.check_output(['git', 'show', f'{BASE}:server/blender_mcp_guided.py'], text=True)
tree = ast.parse(source)
fn = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == 'router_set_goal')
fn.decorator_list = []
fn.lineno = fn.lineno  # execute the unmodified baseline function body
module = ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[]))
namespace = {
    '__name__': 'server._baseline_guided_benchmark',
    'GoalInput': CandidateInput,
    '_workflow_match': candidate._workflow_match,
    'registry': candidate.registry,
    '_goal_state': {},
}
exec(compile(module, 'server/_baseline_guided_benchmark.py', 'exec'), namespace)
baseline_goal, baseline_input = namespace['router_set_goal'], CandidateInput
tasks = [
    ('model a vase', 'modeling'),
    ('make a product hero render', 'product-shot'),
    ('animate a walk cycle', 'animation'),
    ('inspect scene object topology', 'inspection'),
    ('attach a reference photograph', 'reconstruction'),
    ('save this blend file', 'file-io'),
    ('set a rigid body simulation', 'physics'),
    ('fix the camera lens', 'camera'),
    ('retopologize sculpt', 'retopology'),
    ('create procedural geometry nodes', 'nodes'),
]

async def measure(fn, model):
    found = 0
    for query, expected in tasks:
        answer = await fn(model(goal=query))
        guides = {g['key'] for g in answer.get('suggested_guides', [])}
        found += int(expected in guides)
    return found

baseline = asyncio.run(measure(baseline_goal, baseline_input))
candidate = asyncio.run(measure(candidate_goal, CandidateInput))
print(json.dumps({'metric':'appropriate_guides_suggested_for_10_blender_tasks',
                  'baseline':baseline,'candidate':candidate,'direction':'higher',
                  'source_base':BASE,'tasks':len(tasks)}))
