"""Reproduce donor-supplied material technical gate before/after authorized edit."""
import json
from pathlib import Path

from blender_quality import api

ROOT = Path(__file__).resolve().parent / 'fixtures/quality_lab'
original = api.score(ROOT / 'missing_material.json')
repaired = api.score(ROOT / 'assigned_material.json')
before = sum(v['passed'] for v in original['checks'])
after = sum(v['passed'] for v in repaired['checks'])
original_failed = [v['id'] for v in original['checks'] if not v['passed']]
repaired_failed = [v['id'] for v in repaired['checks'] if not v['passed']]
assert (before, after) == (9, 10), (original_failed, repaired_failed)
assert original_failed == ['materials'] and not repaired_failed
print(json.dumps({'metric':'technical_gates_passed_after_authorized_material_repair',
                  'baseline': before, 'candidate': after, 'direction': 'higher',
                  'gate_count':10, 'original_failed_gates':original_failed,
                  'repaired_failed_gates':repaired_failed,
                  'proof':'two real M2 Blender 5.2.3 inspection-v2 JSON fixtures; donor Quality Lab API v1'}))
