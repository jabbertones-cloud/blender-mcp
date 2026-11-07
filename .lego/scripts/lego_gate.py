#!/usr/bin/env python3
"""Lego Builder policy gate: require donor provenance for changed production code.

This script checks assertions in a manifest; it does not establish whether code was
actually copied/adapted from the donor, whether a license is compatible, or whether
measurements are scientifically valid. Those require independent review.
"""

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

from jsonschema import Draft202012Validator

SOURCE_SUFFIXES = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".swift", ".m", ".mm", ".go",
    ".rs", ".java", ".kt", ".kts", ".rb", ".php", ".cs", ".c", ".cc",
    ".cpp", ".h", ".hpp", ".sh", ".sql", ".vue", ".svelte", ".dart",
    ".ex", ".exs", ".css", ".scss", ".html", ".htm",
}
SKIP_DIRS = {
    ".git", ".github", ".lego", "docs", "doc", "tests", "test", "__tests__",
    "examples", "fixtures", "vendor", "node_modules", "dist", "build", "coverage",
    ".next", ".build", "generated", "gen",
}
EXCLUDED_NAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "cargo.lock", "go.sum",
}
SHA_RE = re.compile(r"[a-fA-F0-9]{40}\Z")
REPO_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
HASH_RE = re.compile(r"[a-f0-9]{64}\Z")
SMAT_STUDY = re.compile(r"https://github\.com/jabbertones-cloud/smat-research/blob/[0-9a-fA-F]{40}/.+")
EXPERT_SOURCE = re.compile(r"https://github\.com/jabbertones-cloud/smat-expert-mcps/blob/[0-9a-fA-F]{40}/.+")


def git(repo, *args):
    p = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if p.returncode:
        raise ValueError(f"git {' '.join(args)} failed: {p.stderr.strip()}")
    return p.stdout


def changed_files(repo, base, head):
    output = git(repo, "diff", "--name-only", "--diff-filter=ACMR", "-z", f"{base}...{head}")
    return [path for path in output.split("\0") if path]


def is_source(path):
    p = PurePosixPath(path)
    parts = p.parts
    if not parts or any(part in SKIP_DIRS for part in parts[:-1]):
        return False
    name = p.name
    if name in EXCLUDED_NAMES or name.startswith("test_") or name.endswith(("_test.py", "_spec.rb")):
        return False
    if ".test." in name or ".spec." in name or name.endswith("Tests.swift"):
        return False
    return p.suffix.lower() in SOURCE_SUFFIXES


def non_placeholder(value, min_length=1):
    if not isinstance(value, str) or len(value.strip()) < min_length:
        return False
    upper = value.upper()
    return not any(w in upper for w in ("REPLACE", "TODO", "TBD", "UNKNOWN", "EXAMPLE"))


def command_list(value):
    # Inline one-liners can trivially fabricate green tests and benchmark numbers.
    # Require checked-in, inspectable test runners rather than shell evaluation.
    if not isinstance(value, list) or not value:
        return False
    banned = {"echo", "printf", "true", ":", "eval"}
    for cmd in value:
        if not isinstance(cmd, list) or not cmd or not all(
            isinstance(arg, str) and arg and "\x00" not in arg for arg in cmd
        ):
            return False
        if Path(cmd[0]).name in banned:
            return False
        if Path(cmd[0]).name in {"python", "python3", "node", "bash", "sh", "zsh"}:
            if any(arg in ("-c", "-e", "--eval", "--command") for arg in cmd[1:]):
                return False
    return True


def check_donor(donor, errors):
    if not isinstance(donor, dict):
        errors.append("Donor must be a JSON object")
        return
    name = donor.get("id")
    label = str(name) if name else "<unnamed donor>"
    repo, sha = donor.get("repository"), donor.get("commit")
    if not non_placeholder(name) or not REPO_RE.fullmatch(repo or ""):
        errors.append(f"{label}: require real donor id and owner/repo")
    if not isinstance(sha, str) or not SHA_RE.fullmatch(sha) or set(sha) == {"0"}:
        errors.append(f"{label}: require real pinned 40-character commit SHA")
    url = donor.get("url")
    try:
        parsed = urlparse(url if isinstance(url, str) else "")
        path = parsed.path.lstrip("/")
        expected = f"{repo}/" if isinstance(repo, str) else ""
        pinned = (f"blob/{sha}/" in path or f"tree/{sha}/" in path or path == f"{repo}/commit/{sha}")
        if parsed.scheme != "https" or parsed.netloc != "github.com" or not path.startswith(expected) or not pinned:
            raise ValueError("invalid pinned URL")
    except ValueError:
        errors.append(f"{label}: require GitHub source URL pinned to this exact SHA")
    for key in ("license", "fabric_project", "fabric_job_id", "fabric_claim", "rationale"):
        if not non_placeholder(donor.get(key), 12 if key in ("fabric_claim", "rationale") else 1):
            errors.append(f"{label}: missing verified {key}")
    if isinstance(donor.get("license"), str) and donor["license"].strip().lower() in ("none", "unlicensed", "proprietary"):
        errors.append(f"{label}: non-reusable license; no copying or porting")
    if donor.get("fabric_status") not in ("reported", "inferred", "measured"):
        errors.append(f"{label}: fabric_status must be reported, inferred, or measured")
    if donor.get("fabric_status") == "measured" and not non_placeholder(donor.get("fabric_verification_ref")):
        errors.append(f"{label}: measured claims need real fabric_verification_ref")


def check_component(component, donor_ids, errors):
    if not isinstance(component, dict):
        errors.append("Component must be a JSON object")
        return
    path = component.get("path")
    if not isinstance(path, str) or not path or path.startswith("/") or ".." in PurePosixPath(path).parts or "\\" in path:
        errors.append(f"Invalid component path: {path!r}")
        return
    if component.get("mode") not in ("assembly", "glue"):
        errors.append(f"{path}: mode must be assembly or glue")
    component_donors = component.get("donor_ids")
    if not isinstance(component_donors, list) or not component_donors:
        errors.append(f"{path}: must map to one or more donor_ids")
    else:
        for item in component_donors:
            if item not in donor_ids:
                errors.append(f"{path}: unknown donor id {item!r}")
    if not non_placeholder(component.get("purpose"), 12):
        errors.append(f"{path}: missing concrete donor assembly purpose")
    for key in ("tests", "benchmarks"):
        if not command_list(component.get(key)):
            errors.append(f"{path}: missing executable {key} argv commands")
    apple_refs = component.get("apple_refs", [])
    if not isinstance(apple_refs, list):
        errors.append(f"{path}: apple_refs must be a list")
    elif path.endswith((".swift", ".m", ".mm")):
        if not apple_refs or not all(
            isinstance(ref, str) and urlparse(ref).scheme == "https" and
            urlparse(ref).netloc in ("developer.apple.com", "docs.swift.org", "www.swift.org")
            for ref in apple_refs
        ):
            errors.append(f"{path}: Apple sources must include official WWDC/Apple URL(s)")


def glue_added(repo, base, head, path):
    output = git(repo, "diff", "--numstat", f"{base}...{head}", "--", path)
    if not output.strip():
        return 0
    first = output.splitlines()[0].split("\t")[0]
    if not first.isdigit():
        raise ValueError(f"binary diff for glue file {path}")
    return int(first)


def committed_bytes(repo, head, path):
    result = subprocess.run(
        ["git", "-C", str(repo), "show", f"{head}:{path}"], capture_output=True
    )
    if result.returncode:
        raise ValueError(f"{path}: missing from verified HEAD commit")
    return result.stdout


def schema_errors(manifest, schema_name="lego-lock.schema.json"):
    schema = json.loads(Path(__file__).with_name(schema_name).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    return [
        f"manifest schema {'.'.join(map(str, error.absolute_path)) or '<root>'}: {error.message}"
        for error in sorted(validator.iter_errors(manifest), key=lambda error: tuple(map(str, error.absolute_path)))
    ]


def check_research(repo, manifest, changed, head, verify, errors):
    if not changed:
        return
    sources = manifest.get("research_evidence", {})
    if not isinstance(sources, dict):
        errors.append("research_evidence must include three independent research lanes")
        return
    apple_files = any(path.endswith((".swift", ".m", ".mm")) for path in changed)
    for lane in ("github_research", "smat_research", "expert_mcp", "fabric"):
        item = sources.get(lane)
        if not isinstance(item, dict):
            errors.append(f"missing {lane} research receipt")
            continue
        rel = item.get("artifact_path")
        sha = item.get("sha256")
        if not isinstance(rel, str) or not rel.startswith(".lego/research/") or (
            ".." in PurePosixPath(rel).parts or "\\" in rel or not rel.endswith(".json")
        ):
            errors.append(f"{lane}: invalid receipt path under .lego/research/")
            continue
        if not isinstance(sha, str) or not HASH_RE.fullmatch(sha):
            errors.append(f"{lane}: invalid SHA-256 digest")
            continue
        path = repo / rel
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024 * 1024:
            errors.append(f"{lane}: receipt absent, symlinked or larger than 1 MiB")
            continue
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != sha:
            errors.append(f"{lane}: receipt SHA-256 mismatch")
        if verify:
            try:
                if data != committed_bytes(repo, head, rel):
                    errors.append(f"{lane}: receipt does not match verified HEAD")
            except ValueError as exc:
                errors.append(str(exc))
        try:
            doc = json.loads(data.decode("utf-8"))
            if not isinstance(doc, dict):
                raise ValueError("receipt must be a JSON object")
        except (ValueError, UnicodeDecodeError) as exc:
            errors.append(f"{lane}: invalid JSON research receipt: {exc}")
            continue
        for field, expected in (("lane", lane), ("mode", item.get("mode"))):
            if doc.get(field) != expected:
                errors.append(f"{lane}: receipt {field} does not match manifest")
        for error in schema_errors(doc, "lego-receipt.schema.json"):
            errors.append(f"{lane}: {error}")
        assessment = doc.get("assessment", {})
        if not isinstance(assessment, dict):
            assessment = {}
        # A successfully completed research job does NOT mean its answer is relevant.
        if lane != "expert_mcp" or item.get("mode") != "not_applicable":
            if assessment.get("relevant") is not True:
                errors.append(f"{lane}: GAP-RELEVANCE research is unrelated or unassessed")
            if assessment.get("sufficient") is not True:
                gaps = assessment.get("gaps", [])
                errors.append(f"{lane}: GAP-SUFFICIENCY research cannot justify implementation; open gaps: {len(gaps) if isinstance(gaps, list) else 'unknown'}")
        refs = doc.get("source_refs", [])
        if (lane != "expert_mcp" or item.get("mode") != "not_applicable") and (not isinstance(refs, list) or not refs):
            errors.append(f"{lane}: GAP-SOURCES no cited source references")
        if doc.get("query") != item.get("query") and lane != "expert_mcp":
            errors.append(f"{lane}: receipt query does not match manifest")
        if not non_placeholder(doc.get("evidence"), 20):
            errors.append(f"{lane}: receipt needs substantive source evidence")
        if lane == "github_research":
            if not non_placeholder(item.get("taskmap_ref"), 3) or not all(
                non_placeholder(ref, 3) for ref in item.get("pattern_card_refs", [])
            ):
                errors.append("github_research: requires actual TaskMap and Pattern Card references")
            if item.get("mode") == "fabric_lane" and doc.get("fabric_job_id") != item.get("fabric_job_id"):
                errors.append("github_research: Fabric-lane job does not match source evidence")
            if doc.get("taskmap_ref") != item.get("taskmap_ref") or not all(
                ref in doc.get("pattern_card_refs", []) for ref in item.get("pattern_card_refs", [])
            ):
                errors.append("github_research: TaskMap / Pattern Cards not present in research receipt")
        if lane == "smat_research" and item.get("mode") == "study":
            if not all(SMAT_STUDY.fullmatch(ref) for ref in item.get("study_refs", [])):
                errors.append("smat_research: study refs must be pinned to full commit SHA")
        if lane == "expert_mcp":
            if apple_files and item.get("mode") == "not_applicable":
                errors.append("expert_mcp: Apple code cannot omit the applicable expert lane")
            if item.get("mode") == "repo_corpus" and not all(
                EXPERT_SOURCE.fullmatch(ref) for ref in item.get("source_refs", [])
            ):
                errors.append("expert_mcp: corpus-only source refs must pin exact commit")
            if item.get("mode") == "not_applicable" and not non_placeholder(doc.get("reason"), 12):
                errors.append("expert_mcp: not_applicable requires a reason in the receipt")
        if lane == "fabric":
            if doc.get("job_id") != item.get("job_id") or doc.get("project") != item.get("project"):
                errors.append("fabric: job ID / project does not match research receipt")
            result = doc.get("result", {})
            if not isinstance(result, dict):
                result = {}
            sufficiency = result.get("sufficiency", {})
            if not isinstance(sufficiency, dict):
                sufficiency = {}
            if result.get("status") != "succeeded":
                errors.append("fabric: GAP-INCOMPLETE research job has not succeeded")
            if sufficiency.get("sufficient") is not True or not isinstance(sufficiency.get("relevantCandidates"), int) or sufficiency.get("relevantCandidates", 0) < 1:
                errors.append("fabric: GAP-DONOR-VERIFICATION insufficient relevant donor candidates; job success alone is not evidence")


def validate(repo, base, head, manifest, verify=False):
    errors = schema_errors(manifest)
    if errors:
        return errors, []
    donors = manifest.get("donors")
    components = manifest.get("components")
    if not isinstance(donors, list) or not isinstance(components, list):
        return ["Manifest requires donors and components arrays"], []
    donor_ids = set()
    fabric_job = manifest.get("research_evidence", {}).get("fabric", {}).get("job_id")
    fabric_project = manifest.get("research_evidence", {}).get("fabric", {}).get("project")
    # Already-approved donors retain their original Fabric job when carried
    # forward unchanged from the exact base commit. New or edited donors must
    # use the active, sufficient job verified in this HEAD.
    try:
        base_lock = json.loads(git(repo, "show", f"{base}:.lego/lego-lock.json"))
    except (ValueError, json.JSONDecodeError):
        base_lock = {}
    inherited = {d.get("id"): d for d in base_lock.get("donors", []) if isinstance(d, dict)}
    prior_fabric = base_lock.get("research_evidence", {}).get("fabric", {})
    for donor in donors:
        check_donor(donor, errors)
        if isinstance(donor, dict):
            if donor.get("fabric_job_id") != fabric_job or donor.get("fabric_project") != fabric_project:
                original = inherited.get(donor.get("id"))
                unchanged_and_approved = (
                    original == donor and donor.get("fabric_job_id") == prior_fabric.get("job_id")
                    and donor.get("fabric_project") == prior_fabric.get("project")
                )
                if not unchanged_and_approved:
                    errors.append(f"{donor.get('id', '<donor>')}: Fabric evidence must match active job or unchanged base donor provenance")
            ident = donor.get("id")
            if ident in donor_ids:
                errors.append(f"Duplicate donor id: {ident}")
            if isinstance(ident, str):
                donor_ids.add(ident)
    comp_map = {}
    for component in components:
        check_component(component, donor_ids, errors)
        if isinstance(component, dict) and isinstance(component.get("path"), str):
            path = component["path"]
            if path in comp_map:
                errors.append(f"Duplicate component path: {path}")
            comp_map[path] = component
    changed = [path for path in changed_files(repo, base, head) if is_source(path)]
    for path in changed:
        if path not in comp_map:
            errors.append(f"{path}: changed production code has no donor-backed component entry")
        elif comp_map[path].get("mode") == "glue":
            added = glue_added(repo, base, head, path)
            if added > 40:
                errors.append(f"{path}: glue adds {added} lines (limit 40); review/replace with donor")
    check_research(repo, manifest, changed, head, verify, errors)
    return errors, changed


def benchmark_verdict(output):
    """Read one measured baseline-vs-candidate JSON object from final output line."""
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        return "benchmark did not emit a JSON result"
    try:
        result = json.loads(lines[-1])
    except json.JSONDecodeError:
        return "benchmark last output line must be JSON with metric, baseline, candidate, direction"
    if not isinstance(result, dict):
        return "benchmark result must be a JSON object"
    if not non_placeholder(result.get("metric")):
        return "benchmark result is missing metric name"
    direction = result.get("direction")
    if direction not in ("higher", "lower"):
        return "benchmark direction must be higher or lower"
    baseline, candidate = result.get("baseline"), result.get("candidate")
    if not all(isinstance(v, (float, int)) and not isinstance(v, bool) and math.isfinite(v)
               for v in (baseline, candidate)):
        return "benchmark baseline and candidate must be finite numbers"
    if (direction == "higher" and candidate < baseline) or (direction == "lower" and candidate > baseline):
        return f"benchmark regression: baseline={baseline}, candidate={candidate}, direction={direction}"
    return None


def run_checks(repo, components, changed, timeout):
    commands, seen = [], set()
    for component in components:
        if component.get("path") not in changed:
            continue
        for kind in ("tests", "benchmarks"):
            for command in component[kind]:
                key = tuple(command)
                if key not in seen:
                    commands.append((kind, command))
                    seen.add(key)
    failures = []
    for kind, command in commands:
        print(f"RUN {kind}: {json.dumps(command)}", flush=True)
        try:
            result = subprocess.run(command, cwd=repo, capture_output=True, text=True, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as exc:
            failures.append(f"{kind} {command[0]}: {exc}")
            continue
        if result.returncode != 0:
            failures.append(f"{kind} {command[0]} exited {result.returncode}: {(result.stderr or result.stdout)[-500:]}")
        elif kind == "benchmarks" and (verdict := benchmark_verdict(result.stdout)):
            failures.append(f"{kind} {command[0]}: {verdict}")
        else:
            print(f"PASS {kind}: {json.dumps(command)}")
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--repo", default=".", type=Path)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--verify", action="store_true", help="Run manifest's test and benchmark argv commands")
    parser.add_argument("--timeout", type=int, default=240, help="Per-command timeout in seconds")
    args = parser.parse_args()
    repo = args.repo.resolve()
    try:
        base = git(repo, "rev-parse", "--verify", f"{args.base}^{{commit}}").strip()
        head = git(repo, "rev-parse", "--verify", f"{args.head}^{{commit}}").strip()
        if args.verify and git(repo, "rev-parse", "HEAD").strip() != head:
            raise ValueError("--verify requires checked out HEAD to match --head; no wrong-commit proof")
        path = args.manifest if args.manifest.is_absolute() else repo / args.manifest
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if args.verify:
            relative = path.resolve().relative_to(repo).as_posix()
            if path.is_symlink() or path.read_bytes() != committed_bytes(repo, head, relative):
                raise ValueError("Manifest must be committed and match the exact verified HEAD")
        errors, changed = validate(repo, base, head, manifest, verify=args.verify)
        if not errors and args.verify:
            if args.timeout < 1 or args.timeout > 3600:
                raise ValueError("timeout must be between 1 and 3600 seconds")
            errors.extend(run_checks(repo, manifest["components"], changed, args.timeout))
    except (OSError, ValueError, json.JSONDecodeError, KeyError, ImportError) as exc:
        errors = [str(exc)]
        changed = []
    for error in errors:
        print(f"BLOCKED: {error}", file=sys.stderr)
    if errors:
        return 1
    print(f"PASS Lego Builder donor gate: {len(changed)} changed production-code file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
