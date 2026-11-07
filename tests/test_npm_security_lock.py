"""CI fixture-based guard against reintroducing the vulnerable sharp dependency chain."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_lock_and_engine_contract():
    manifest = json.loads((ROOT/'package.json').read_text())
    lock = json.loads((ROOT/'package-lock.json').read_text())
    assert manifest['engines']['node'] == '>=20.9.0'
    assert 'sharp' not in manifest['dependencies']
    assert lock['lockfileVersion'] == 3
    assert lock['packages']['']['dependencies'] == manifest['dependencies']
    for name in ('core','extensions','functions'):
        assert lock['packages'][f'node_modules/@gltf-transform/{name}']['version'] == '4.5.1'
    assert lock['packages']['node_modules/ndarray-pixels']['version'] == '5.2.0'
    assert lock['packages']['node_modules/sharp']['version'] == '0.35.5'
    assert 'node_modules/ndarray-pixels/node_modules/sharp' not in lock['packages']


def test_frozen_security_negative_control_is_not_mislabelled():
    record = json.loads((ROOT/'tests/fixtures/npm_security_audit_observed.json').read_text())
    assert record['baseline']['high_vulnerable_package_nodes'] == 2
    assert record['baseline']['vulnerable_package_nodes'] == ['ndarray-pixels','sharp']
    assert record['candidate']['high_vulnerable_package_nodes'] == 0
    assert len(record['github_alerts_at_baseline']) == 3
    assert 'removal-only' in record['context']


def test_generated_node_modules_is_not_tracked_by_git():
    proc = subprocess.run(['git', 'ls-files', '--', 'node_modules'], cwd=ROOT, text=True, capture_output=True, check=True)
    assert not proc.stdout.strip(), 'Tracked node_modules defeats lockfile reproducibility and leaves stale vendor binaries'
