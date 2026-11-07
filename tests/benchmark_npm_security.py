"""Frozen M2 npm-audit graph comparison; real npm audit remains a separate live test."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
record = json.loads((root/'tests/fixtures/npm_security_audit_observed.json').read_text())
lock = json.loads((root/'package-lock.json').read_text())
assert record['baseline']['vulnerable_package_nodes'] == ['ndarray-pixels','sharp']
assert record['baseline']['high_vulnerable_package_nodes'] == 2
assert record['candidate']['high_vulnerable_package_nodes'] == 0
for package, version in {
    'node_modules/@gltf-transform/functions':'4.5.1',
    'node_modules/ndarray-pixels':'5.2.0',
    'node_modules/sharp':'0.35.5',
}.items():
    assert lock['packages'][package]['version'] == version
print(json.dumps({'metric':'high_severity_vulnerable_package_nodes_in_single_M2_resolved_npm_experiment',
                  'baseline':2,'candidate':0,'direction':'lower',
                  'proof':'one observed removal-only negative control vs one pinned upstream replacement; frozen npm-audit metadata, not a time-independent security claim'}))
