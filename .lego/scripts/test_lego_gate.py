#!/usr/bin/env python3
"""Black-box and adversarial acceptance tests for the version-2 Lego gate.

This suite exercises the exact CLI against temporary committed git repositories.
All synthetic research records are explicitly test fixtures, not real attestations.
"""
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

GATE = Path(__file__).with_name("lego_gate.py")
SHA = "1234567890abcdef1234567890abcdef12345678"  # fixture only
JOB = "fixture-job-123456789"
QUERY = "Validate donor provenance and build reusable components"


def git(repo, *args):
    p = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if p.returncode:
        raise AssertionError(p.stderr)
    return p.stdout.strip()


class GateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.name", "Fixture")
        git(self.repo, "config", "user.email", "fixture@example.test")
        (self.repo / "src").mkdir()
        (self.repo / "src/app.py").write_text("print('baseline')\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "baseline")
        self.base = git(self.repo, "rev-parse", "HEAD")

    def fixture_receipts(self):
        def receipt(lane, mode, refs):
            return {"lane": lane, "mode": mode, "query": QUERY,
                    "evidence": f"Synthetic {lane} fixture source evidence and test-only coverage map.",
                    "source_refs": refs,
                    "assessment": {"relevant": True, "sufficient": True,
                                   "gaps": [], "limitations": ["Only fixture evidence"]}}
        gh = receipt("github_research", "cli", [f"https://github.com/pallets/flask/blob/{SHA}/src/flask/app.py"])
        gh.update(taskmap_ref="fixture-taskmap", pattern_card_refs=["fixture-pattern-card"])
        smat = receipt("smat_research", "study", [
            f"https://github.com/jabbertones-cloud/smat-research/blob/{SHA}/studies/test/REPORT.md"])
        expert = receipt("expert_mcp", "repo_corpus", [
            f"https://github.com/jabbertones-cloud/smat-expert-mcps/blob/{SHA}/docs/PROGRAM.md"])
        fabric = receipt("fabric", "research_job", [f"https://github.com/pallets/flask/blob/{SHA}/src/flask/app.py"])
        fabric.update(job_id=JOB, project="test-project", result={
            "status": "succeeded", "sufficiency": {"sufficient": True, "relevantCandidates": 1}})
        return {"github_research": gh, "smat_research": smat,
                "expert_mcp": expert, "fabric": fabric}

    def fixture_lock(self):
        return {
            "schema_version": 2,
            "donors": [{"id": "flask-fixture", "repository": "pallets/flask",
                        "commit": SHA,
                        "url": f"https://github.com/pallets/flask/blob/{SHA}/src/flask/app.py",
                        "license": "BSD-3-Clause", "fabric_project": "test-project",
                        "fabric_job_id": JOB, "fabric_claim": "Fixture API supports demo application wiring",
                        "fabric_status": "reported", "rationale": "Fixture-only source with a pinned URL and expected API"}],
            "components": [{"path": "src/app.py", "mode": "assembly", "donor_ids": ["flask-fixture"],
                            "purpose": "Exercise minimal app integration in a versioned test fixture",
                            "tests": [["python3", "tests/test_app.py"]],
                            "benchmarks": [["python3", "tests/benchmark.py"]], "apple_refs": []}],
            "research_evidence": {}
        }

    def build(self, *, source_path="src/app.py", source="print('candidate')\n",
              lock_edit=None, receipt_edit=None, benchmark=None, test_fail=False):
        target = self.repo / source_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source)
        tests = self.repo / "tests"
        tests.mkdir(exist_ok=True)
        (tests / "test_app.py").write_text("raise SystemExit(1)\n" if test_fail else "assert 1 == 1\n")
        (tests / "benchmark.py").write_text(benchmark or (
            "import json\nprint(json.dumps({'metric':'failure_count',"
            "'baseline':3,'candidate':1,'direction':'lower'}))\n"))
        lock = self.fixture_lock()
        lock["components"][0]["path"] = source_path
        receipts = self.fixture_receipts()
        if receipt_edit:
            receipt_edit(receipts)
        for lane, document in receipts.items():
            name = f".lego/research/{lane}.json"
            fpath = self.repo / name
            fpath.parent.mkdir(parents=True, exist_ok=True)
            raw = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()
            fpath.write_bytes(raw)
            values = {"mode": document["mode"], "artifact_path": name,
                      "sha256": hashlib.sha256(raw).hexdigest()}
            if lane == "github_research":
                values.update(query=QUERY, taskmap_ref="fixture-taskmap",
                              pattern_card_refs=["fixture-pattern-card"])
            if lane == "smat_research":
                values.update(query=QUERY, finding="Fixture study provides applicable evidence",
                              study_refs=[f"https://github.com/jabbertones-cloud/smat-research/blob/{SHA}/studies/test/REPORT.md"])
            if lane == "expert_mcp":
                values.update(domain="reliability", finding="Fixture specialist verified relevant constraints",
                              source_refs=[f"https://github.com/jabbertones-cloud/smat-expert-mcps/blob/{SHA}/docs/PROGRAM.md"])
            if lane == "fabric":
                values.update(query=QUERY, job_id=JOB, project="test-project")
            lock["research_evidence"][lane] = values
        if lock_edit:
            lock_edit(lock)
        lockpath = self.repo / ".lego/lego-lock.json"
        lockpath.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "candidate")
        return git(self.repo, "rev-parse", "HEAD")

    def gate(self, head, *, verify=True, base=None):
        args = ["python3", str(GATE), "--repo", str(self.repo),
                "--manifest", ".lego/lego-lock.json", "--base", base or self.base,
                "--head", head]
        if verify:
            args.append("--verify")
        return subprocess.run(args, capture_output=True, text=True)

    def assert_blocked(self, response, phrase):
        self.assertNotEqual(response.returncode, 0, response.stdout + response.stderr)
        self.assertIn(phrase, response.stderr)

    def test_valid_committed_v2_fixture_passes_tests_and_benchmark(self):
        r = self.gate(self.build())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("PASS benchmarks", r.stdout)

    def test_blocks_unmapped_code(self):
        head = self.build(lock_edit=lambda d: d.update(components=[]))
        self.assert_blocked(self.gate(head), "no donor-backed")

    def test_blocks_fake_donor_or_missing_fabric(self):
        def edit(d):
            d["donors"][0]["fabric_job_id"] = "TODO"
            d["donors"][0]["commit"] = "0" * 40
        head = self.build(lock_edit=edit)
        self.assert_blocked(self.gate(head), "pinned 40-character")

    def test_glue_line_limit(self):
        code = "\n".join(f"x{i} = {i}" for i in range(48)) + "\n"
        head = self.build(source=code, lock_edit=lambda d: d["components"][0].update(mode="glue"))
        self.assert_blocked(self.gate(head), "limit 40")

    def test_apple_requires_official_sources(self):
        head = self.build(source_path="Sources/App.swift", source="import Foundation\n")
        self.assert_blocked(self.gate(head), "Apple sources")

    def test_apple_cannot_omit_expert(self):
        def edit(d):
            d["research_evidence"]["expert_mcp"].update(mode="not_applicable", reason="This artificial expert absence is part of a negative Apple test")
        head = self.build(source_path="Sources/App.swift", source="import Foundation\n",
                          lock_edit=edit)
        self.assert_blocked(self.gate(head), "Apple")

    def test_test_command_failure_blocks(self):
        head = self.build(test_fail=True)
        self.assert_blocked(self.gate(head), "tests")

    def test_unmeasured_benchmark_blocks(self):
        head = self.build(benchmark="print('unmeasured')\n")
        self.assert_blocked(self.gate(head), "benchmark last output line")

    def test_regressing_benchmark_blocks(self):
        head = self.build(benchmark="import json\nprint(json.dumps({'metric':'failures',"
                          "'baseline':1,'candidate':2,'direction':'lower'}))\n")
        self.assert_blocked(self.gate(head), "benchmark regression")

    def test_wrong_head_blocks(self):
        self.build()
        self.assert_blocked(self.gate(self.base), "checked out HEAD")

    def test_changed_receipt_hash_blocks(self):
        head = self.build()
        with (self.repo / ".lego/research/github_research.json").open("ab") as f:
            f.write(b" ")
        self.assert_blocked(self.gate(head), "SHA-256 mismatch")

    def test_research_unrelated_blocks(self):
        def edit(r):
            r["github_research"]["assessment"]["relevant"] = False
        head = self.build(receipt_edit=edit)
        self.assert_blocked(self.gate(head), "GAP-RELEVANCE")

    def test_fabric_success_but_no_relevant_donors_blocks(self):
        def edit(r):
            r["fabric"]["result"]["sufficiency"].update(sufficient=False, relevantCandidates=0)
        head = self.build(receipt_edit=edit)
        self.assert_blocked(self.gate(head), "GAP-DONOR-VERIFICATION")

    def test_missing_receipt_blocks(self):
        head = self.build()
        (self.repo / ".lego/research/expert_mcp.json").unlink()
        self.assert_blocked(self.gate(head), "receipt absent")

    def test_uncommitted_manifest_blocks(self):
        head = self.build()
        with (self.repo / ".lego/lego-lock.json").open("a") as f:
            f.write("\n")
        self.assert_blocked(self.gate(head), "Manifest must be committed")

    def test_unsafe_inline_commands_block(self):
        def edit(d):
            d["components"][0]["tests"] = [["python3", "-c", "print('fake green')"]]
        head = self.build(lock_edit=edit)
        self.assert_blocked(self.gate(head), "tests argv")

    def test_schema_v1_is_rejected(self):
        head = self.build(lock_edit=lambda d: d.update(schema_version=1))
        self.assert_blocked(self.gate(head), "2 was expected")


if __name__ == "__main__":
    unittest.main()
