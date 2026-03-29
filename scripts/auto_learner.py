#!/usr/bin/env python3
"""
OpenClaw Blender MCP — Auto-Learning Improvement System
========================================================

Runs all demo scripts, captures results, analyzes errors, and generates
improvement suggestions based on identified patterns.

Usage:
    python3 scripts/auto_learner.py --run        # Run all demos, capture results
    python3 scripts/auto_learner.py --report     # Print learning report
    python3 scripts/auto_learner.py --suggest    # Generate fix suggestions
    python3 scripts/auto_learner.py --full       # Run + analyze + suggest

Features:
    - Runs all demo scripts sequentially
    - Parses error messages to identify patterns
    - Maintains learning journal with error history
    - Tracks success rate and trends over time
    - Generates fix suggestions based on error categories
    - Compares current run vs previous run
"""

import json
import os
import sys
import time
import argparse
import subprocess
import re
from datetime import datetime
from pathlib import Path
from collections import defaultdict, Counter
from typing import Dict, List, Any, Optional, Tuple


# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

DATA_DIR = Path(__file__).parent.parent / "data"
DEMOS_DIR = Path(__file__).parent.parent / "demos"
LEARNING_JOURNAL = DATA_DIR / "learning_journal.json"
METRICS_HISTORY = DATA_DIR / "metrics_history.json"
SUGGESTIONS_FILE = DATA_DIR / "improvement_suggestions.json"

# MCP socket-based demos (need Blender running with bridge on port 9876)
DEMO_SCRIPTS = [
    "full_capability_showcase.py",
    "vfx_showcase.py",
    "vfx_advanced_showoff.py",
    "cityscape_sunset.py",
]

# Standalone bpy demos (run via `blender -b -P script.py`, no bridge needed)
STANDALONE_DEMOS = [
    "cityscape_direct.py",
    "roblox_character.py",
    "math_windows3.py",
]

BLENDER_BIN = "/Applications/Blender.app/Contents/MacOS/Blender"
BLENDER_SOCKET = ("127.0.0.1", 9876)
BLENDER_TIMEOUT = 30


# ═══════════════════════════════════════════════════════════════
# ERROR PATTERN DETECTION
# ═══════════════════════════════════════════════════════════════

ERROR_PATTERNS = {
    "shade_smooth_error": {
        "regex": r"(shade_smooth|smooth_faces|operator.*context.*shade)",
        "category": "SHADE_SMOOTH_ISSUE",
        "fix_suggestion": "Use pattern: mode_set(mode='OBJECT'), deselect_all, then per-object shade_smooth with try/except",
        "severity": "HIGH",
    },
    "context_error": {
        "regex": r"(poll\(\)|context|mode_set|operator.*context)",
        "category": "CONTEXT_ISSUE",
        "fix_suggestion": "Add mode_set(mode='OBJECT') safety checks before operations",
        "severity": "HIGH",
    },
    "missing_object": {
        "regex": r"(not found|does not exist|KeyError.*object|AttributeError.*object)",
        "category": "MISSING_OBJECT",
        "fix_suggestion": "Verify object creation order and check object_name parameter spelling",
        "severity": "MEDIUM",
    },
    "enum_error": {
        "regex": r"(enum|invalid.*value|choice.*not found|AttributeError.*item)",
        "category": "ENUM_MISMATCH",
        "fix_suggestion": "Check API version compatibility; enum values may have changed",
        "severity": "HIGH",
    },
    "property_error": {
        "regex": r"(property|AttributeError|read-only|immutable)",
        "category": "PROPERTY_ISSUE",
        "fix_suggestion": "Verify property exists and is writable for current object type",
        "severity": "MEDIUM",
    },
    "type_error": {
        "regex": r"(TypeError|type mismatch|expected.*got)",
        "category": "TYPE_MISMATCH",
        "fix_suggestion": "Check parameter types (list/dict/str/float) match API expectations",
        "severity": "LOW",
    },
    "timeout_error": {
        "regex": r"(timeout|TIMEOUT|socket timeout|connection refused)",
        "category": "TIMEOUT",
        "fix_suggestion": "Increase timeout or simplify demo step; Blender may be unresponsive",
        "severity": "CRITICAL",
    },
    "file_error": {
        "regex": r"(FileNotFoundError|IOError|No such file|cannot find)",
        "category": "FILE_NOT_FOUND",
        "fix_suggestion": "Verify file paths are correct and files exist in expected location",
        "severity": "LOW",
    },
    "socket_error": {
        "regex": r"(Connection|refused|ECONNREFUSED|socket error)",
        "category": "BLENDER_UNREACHABLE",
        "fix_suggestion": "Start Blender and ensure MCP server is running on port 9876",
        "severity": "CRITICAL",
    },
}


# ═══════════════════════════════════════════════════════════════
# JOURNAL & METRICS MANAGEMENT
# ═══════════════════════════════════════════════════════════════

def load_journal() -> Dict[str, Any]:
    """Load existing learning journal."""
    if LEARNING_JOURNAL.exists():
        with open(LEARNING_JOURNAL, "r") as f:
            return json.load(f)
    return {
        "entries": [],
        "error_patterns": {},
        "first_run": None,
        "last_run": None,
        "total_tests": 0,
        "total_passed": 0,
        "total_failed": 0,
    }


def save_journal(journal: Dict[str, Any]) -> None:
    """Save learning journal to disk."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(LEARNING_JOURNAL, "w") as f:
        json.dump(journal, f, indent=2)


def load_metrics_history() -> List[Dict[str, Any]]:
    """Load historical metrics for trend analysis."""
    if METRICS_HISTORY.exists():
        with open(METRICS_HISTORY, "r") as f:
            return json.load(f)
    return []


def save_metrics_history(history: List[Dict[str, Any]]) -> None:
    """Save metrics history."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(METRICS_HISTORY, "w") as f:
        json.dump(history, f, indent=2)


def add_journal_entry(
    journal: Dict[str, Any],
    command: str,
    params: Dict,
    error_msg: str,
    error_category: str,
    auto_fixed: bool,
) -> None:
    """Add entry to learning journal."""
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "command": command,
        "params": params,
        "error_message": error_msg,
        "error_category": error_category,
        "auto_fixed": auto_fixed,
    }
    journal["entries"].append(entry)

    # Update pattern tracking
    if error_category not in journal["error_patterns"]:
        journal["error_patterns"][error_category] = {
            "count": 0,
            "first_seen": datetime.utcnow().isoformat(),
            "last_seen": None,
            "auto_fixes": 0,
        }

    journal["error_patterns"][error_category]["count"] += 1
    journal["error_patterns"][error_category]["last_seen"] = datetime.utcnow().isoformat()
    if auto_fixed:
        journal["error_patterns"][error_category]["auto_fixes"] += 1


# ═══════════════════════════════════════════════════════════════
# ERROR DETECTION & PATTERN MATCHING
# ═══════════════════════════════════════════════════════════════

def parse_error_from_output(output: str) -> Optional[Tuple[str, str]]:
    """Extract error message and category from command output."""
    # Look for common error patterns in output
    lines = output.split("\n")
    for line in lines:
        if "error" in line.lower() or "failed" in line.lower():
            # Try to match against error patterns
            for pattern_name, pattern_info in ERROR_PATTERNS.items():
                if re.search(pattern_info["regex"], line, re.IGNORECASE):
                    return line.strip(), pattern_info["category"]

    # Return None if no error detected
    return None


def detect_error_category(error_msg: str) -> str:
    """Categorize error based on message content."""
    for pattern_name, pattern_info in ERROR_PATTERNS.items():
        if re.search(pattern_info["regex"], error_msg, re.IGNORECASE):
            return pattern_info["category"]
    return "UNKNOWN"


def get_fix_suggestion(error_category: str) -> str:
    """Get fix suggestion for error category."""
    for pattern_info in ERROR_PATTERNS.values():
        if pattern_info["category"] == error_category:
            return pattern_info["fix_suggestion"]
    return "Unable to determine fix; check Blender logs for details."


def get_error_severity(error_category: str) -> str:
    """Get severity level for error category."""
    for pattern_info in ERROR_PATTERNS.values():
        if pattern_info["category"] == error_category:
            return pattern_info["severity"]
    return "UNKNOWN"


# ═══════════════════════════════════════════════════════════════
# DEMO EXECUTION
# ═══════════════════════════════════════════════════════════════

def run_demo(demo_name: str, standalone: bool = False) -> Dict[str, Any]:
    """Run a single demo script and capture results.

    standalone: if True, runs via `blender -b -P script.py` instead of plain Python.
    """
    demo_path = DEMOS_DIR / demo_name
    if not demo_path.exists():
        return {
            "demo": demo_name,
            "success": False,
            "error": f"Demo file not found: {demo_path}",
            "stdout": "",
            "stderr": "",
            "execution_time": 0,
        }

    mode = "standalone" if standalone else "MCP"
    print(f"\n  ▶ Running {demo_name} ({mode})...", flush=True)
    start_time = time.time()

    try:
        if standalone:
            # Run via Blender background mode
            if not Path(BLENDER_BIN).exists():
                return {
                    "demo": demo_name,
                    "success": False,
                    "error": f"Blender not found at {BLENDER_BIN}",
                    "stdout": "",
                    "stderr": "",
                    "execution_time": 0,
                }
            cmd = [BLENDER_BIN, "-b", "-P", str(demo_path)]
        else:
            cmd = [sys.executable, str(demo_path)]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes per demo
        )
        elapsed = time.time() - start_time

        # For standalone demos, check for render success markers
        if standalone:
            output = result.stdout + result.stderr
            has_saved = "Saved:" in output or "COMPLETE" in output
            # Filter out addon errors (not our fault)
            our_errors = [
                line for line in output.split("\n")
                if "File \"" + str(DEMOS_DIR) in line
                or ("Error" in line and "addon" not in line.lower()
                    and "unregister" not in line.lower()
                    and "register_class" not in line.lower())
            ]
            success = has_saved and len(our_errors) == 0
        else:
            success = result.returncode == 0

        return {
            "demo": demo_name,
            "success": success,
            "error": result.stderr if result.stderr else None,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "execution_time": elapsed,
            "returncode": result.returncode,
            "mode": mode,
        }

    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        return {
            "demo": demo_name,
            "success": False,
            "error": "Demo execution timeout (5 minutes)",
            "stdout": "",
            "stderr": "",
            "execution_time": elapsed,
        }
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            "demo": demo_name,
            "success": False,
            "error": str(e),
            "stdout": "",
            "stderr": "",
            "execution_time": elapsed,
        }


def run_all_demos() -> Tuple[List[Dict[str, Any]], float]:
    """Run all demo scripts sequentially."""
    print(
        "\n" + "═" * 70
        + "\n  OpenClaw Blender MCP — Auto-Learning System"
        + "\n  Running All Demos & Capturing Results"
        + "\n" + "═" * 70
    )

    results = []
    start_time = time.time()

    # Run standalone bpy demos first (most reliable, no bridge needed)
    print("\n  --- Standalone Demos (blender -b -P) ---")
    for demo in STANDALONE_DEMOS:
        result = run_demo(demo, standalone=True)
        results.append(result)
        status = "✓" if result["success"] else "✗"
        time_str = f"{result['execution_time']:.1f}s"
        print(f"    {status} {demo:45} {time_str}")

    # Run MCP socket-based demos (need bridge running)
    print("\n  --- MCP Socket Demos (need Blender bridge) ---")
    for demo in DEMO_SCRIPTS:
        result = run_demo(demo, standalone=False)
        results.append(result)
        status = "✓" if result["success"] else "✗"
        time_str = f"{result['execution_time']:.1f}s"
        print(f"    {status} {demo:45} {time_str}")

    elapsed = time.time() - start_time
    return results, elapsed


# ═══════════════════════════════════════════════════════════════
# ANALYSIS & REPORTING
# ═══════════════════════════════════════════════════════════════

def analyze_results(
    results: List[Dict[str, Any]], journal: Dict[str, Any]
) -> Dict[str, Any]:
    """Analyze demo results and update journal."""
    total_tests = len(results)
    passed = sum(1 for r in results if r["success"])
    failed = total_tests - passed

    # Update metrics
    journal["last_run"] = datetime.utcnow().isoformat()
    if not journal["first_run"]:
        journal["first_run"] = journal["last_run"]

    journal["total_tests"] += total_tests
    journal["total_passed"] += passed
    journal["total_failed"] += failed

    # Analyze errors
    error_analysis = defaultdict(list)
    for result in results:
        if not result["success"]:
            error_msg = result.get("error", "Unknown error")
            category = detect_error_category(error_msg)
            error_analysis[category].append(
                {
                    "demo": result["demo"],
                    "error": error_msg,
                    "severity": get_error_severity(category),
                }
            )
            add_journal_entry(
                journal,
                result["demo"],
                {},
                error_msg,
                category,
                auto_fixed=False,
            )

    return {
        "total_tests": total_tests,
        "passed": passed,
        "failed": failed,
        "pass_rate": (passed / total_tests * 100) if total_tests > 0 else 0,
        "error_analysis": dict(error_analysis),
        "timestamp": datetime.utcnow().isoformat(),
    }


def generate_suggestions(
    analysis: Dict[str, Any], journal: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate fix suggestions based on error patterns."""
    suggestions = {
        "generated_at": datetime.utcnow().isoformat(),
        "error_patterns": [],
        "recommended_fixes": [],
        "critical_issues": [],
    }

    # Group by error category
    category_counts = Counter()
    for pattern_info in journal.get("error_patterns", {}).items():
        category, info = pattern_info
        category_counts[category] = info["count"]

    # Sort by frequency
    for category, count in category_counts.most_common():
        pattern_info = None
        for p_info in ERROR_PATTERNS.values():
            if p_info["category"] == category:
                pattern_info = p_info
                break

        if pattern_info:
            entry = {
                "error_category": category,
                "occurrences": count,
                "severity": pattern_info.get("severity", "UNKNOWN"),
                "fix_suggestion": pattern_info.get("fix_suggestion", ""),
                "auto_fix_attempts": journal.get("error_patterns", {})
                .get(category, {})
                .get("auto_fixes", 0),
            }
            suggestions["error_patterns"].append(entry)

            if entry["severity"] == "CRITICAL":
                suggestions["critical_issues"].append(entry)

    # Generate recommendations
    if analysis.get("pass_rate", 0) < 50:
        suggestions["recommended_fixes"].append(
            {
                "priority": "URGENT",
                "action": "Pass rate below 50% - review critical errors in learning journal",
                "details": f"Current pass rate: {analysis.get('pass_rate', 0):.1f}%",
            }
        )

    if suggestions["critical_issues"]:
        suggestions["recommended_fixes"].append(
            {
                "priority": "CRITICAL",
                "action": "Address critical issues",
                "issues": suggestions["critical_issues"],
            }
        )

    # Add trend analysis
    suggestions["trend_analysis"] = analyze_trends(journal)

    return suggestions


def analyze_trends(journal: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze trends in error patterns over time."""
    entries = journal.get("entries", [])
    if len(entries) < 2:
        return {"status": "insufficient_data", "entries_available": len(entries)}

    # Count errors by category over time windows
    recent_errors = Counter()
    for entry in entries[-20:]:  # Last 20 entries
        recent_errors[entry.get("error_category", "UNKNOWN")] += 1

    overall_errors = Counter()
    for entry in entries:
        overall_errors[entry.get("error_category", "UNKNOWN")] += 1

    # Calculate improvement
    overall_counts = dict(overall_errors)
    recent_counts = dict(recent_errors)

    improvement = {}
    for category in overall_counts:
        overall = overall_counts.get(category, 0)
        recent = recent_counts.get(category, 0)
        if overall > 0:
            improvement[category] = {
                "all_time": overall,
                "recent": recent,
                "trend": "improving"
                if recent < overall * 0.5
                else "stable"
                if recent <= overall * 1.1
                else "regressing",
            }

    return {
        "status": "available",
        "entries_analyzed": len(entries),
        "improvement_by_category": improvement,
    }


# ═══════════════════════════════════════════════════════════════
# REPORTING & OUTPUT
# ═══════════════════════════════════════════════════════════════

def print_report(results: List[Dict[str, Any]], analysis: Dict[str, Any]) -> None:
    """Print formatted test report."""
    print(
        "\n" + "═" * 70
        + "\n  TEST RESULTS REPORT"
        + "\n" + "═" * 70
    )

    # Summary
    total = analysis["total_tests"]
    passed = analysis["passed"]
    failed = analysis["failed"]
    pass_rate = analysis["pass_rate"]

    print(
        f"\n  Total Tests:  {total}"
        f"\n  Passed:       {passed} ✓"
        f"\n  Failed:       {failed} ✗"
        f"\n  Pass Rate:    {pass_rate:.1f}%"
    )

    # Test details
    print("\n  DETAILED RESULTS:")
    print("  " + "─" * 66)
    for result in results:
        status = "✓" if result["success"] else "✗"
        time_str = f"{result['execution_time']:.1f}s"
        print(f"    {status} {result['demo']:40} {time_str:>8}")
        if result.get("error"):
            error_preview = result["error"][:60].replace("\n", " ")
            print(f"      → {error_preview}...")

    # Error analysis
    if analysis.get("error_analysis"):
        print("\n  ERROR ANALYSIS BY CATEGORY:")
        print("  " + "─" * 66)
        for category, errors in analysis["error_analysis"].items():
            print(f"    {category:25} ({len(errors)} occurrences)")
            for error in errors[:2]:  # Show first 2 of each type
                severity = error.get("severity", "?")
                demo = error.get("demo", "?")
                print(f"      [{severity}] {demo}")

    print("\n" + "═" * 70 + "\n")


def print_suggestions(suggestions: Dict[str, Any]) -> None:
    """Print improvement suggestions."""
    print(
        "\n" + "═" * 70
        + "\n  IMPROVEMENT SUGGESTIONS"
        + "\n" + "═" * 70
    )

    if suggestions.get("critical_issues"):
        print("\n  CRITICAL ISSUES (must fix):")
        print("  " + "─" * 66)
        for issue in suggestions["critical_issues"]:
            category = issue.get("error_category", "?")
            count = issue.get("occurrences", 0)
            fix = issue.get("fix_suggestion", "?")
            print(f"    • {category} ({count}x)")
            print(f"      → {fix}")

    if suggestions.get("error_patterns"):
        print("\n  ERROR PATTERNS & FIXES:")
        print("  " + "─" * 66)
        for pattern in suggestions["error_patterns"][:5]:  # Top 5
            category = pattern.get("error_category", "?")
            count = pattern.get("occurrences", 0)
            severity = pattern.get("severity", "?")
            fix = pattern.get("fix_suggestion", "?")
            print(f"    {count:2}x [{severity:8}] {category}")
            print(f"        → {fix}")

    if suggestions.get("recommended_fixes"):
        print("\n  RECOMMENDED ACTIONS:")
        print("  " + "─" * 66)
        for fix in suggestions["recommended_fixes"]:
            priority = fix.get("priority", "?")
            action = fix.get("action", "?")
            print(f"    [{priority:8}] {action}")
            if fix.get("details"):
                print(f"              {fix['details']}")

    # Trends
    trends = suggestions.get("trend_analysis", {})
    if trends.get("status") == "available":
        print("\n  TREND ANALYSIS:")
        print("  " + "─" * 66)
        improvements = trends.get("improvement_by_category", {})
        for category, trend_info in list(improvements.items())[:3]:
            all_time = trend_info.get("all_time", 0)
            recent = trend_info.get("recent", 0)
            trend_dir = trend_info.get("trend", "?")
            trend_emoji = "↓" if trend_dir == "improving" else "→" if trend_dir == "stable" else "↑"
            print(
                f"    {trend_emoji} {category:25} "
                f"(all-time: {all_time}, recent: {recent})"
            )

    print("\n" + "═" * 70 + "\n")


def print_learning_summary(journal: Dict[str, Any]) -> None:
    """Print learning journal summary."""
    print(
        "\n" + "═" * 70
        + "\n  LEARNING JOURNAL SUMMARY"
        + "\n" + "═" * 70
    )

    total_tests = journal.get("total_tests", 0)
    total_passed = journal.get("total_passed", 0)
    total_failed = journal.get("total_failed", 0)
    overall_rate = (
        (total_passed / total_tests * 100) if total_tests > 0 else 0
    )

    print(
        f"\n  Cumulative Statistics:"
        f"\n    Total Tests Run:  {total_tests}"
        f"\n    Total Passed:     {total_passed} ✓"
        f"\n    Total Failed:     {total_failed} ✗"
        f"\n    Overall Pass Rate: {overall_rate:.1f}%"
    )

    if journal.get("first_run"):
        print(f"\n  First Run:  {journal['first_run']}")
    if journal.get("last_run"):
        print(f"  Last Run:   {journal['last_run']}")

    print("\n  Error Patterns Tracked:")
    print("  " + "─" * 66)
    patterns = journal.get("error_patterns", {})
    for category, info in sorted(
        patterns.items(), key=lambda x: x[1].get("count", 0), reverse=True
    ):
        count = info.get("count", 0)
        fixed = info.get("auto_fixes", 0)
        first = info.get("first_seen", "?")[:10]
        print(f"    {category:25} {count:3}x (fixed: {fixed:2}x, first: {first})")

    print("\n" + "═" * 70 + "\n")


# ═══════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="OpenClaw Blender MCP — Auto-Learning System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/auto_learner.py --run       # Run all demos
  python3 scripts/auto_learner.py --report    # Print report from last run
  python3 scripts/auto_learner.py --suggest   # Print suggestions
  python3 scripts/auto_learner.py --full      # Run + report + suggest
        """,
    )

    parser.add_argument(
        "--run",
        action="store_true",
        help="Run all demo scripts and capture results",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Print test report from last run",
    )
    parser.add_argument(
        "--suggest",
        action="store_true",
        help="Print improvement suggestions",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run demos, print report, and suggest improvements",
    )
    parser.add_argument(
        "--journal",
        action="store_true",
        help="Print learning journal summary",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress output (save to files only)",
    )

    args = parser.parse_args()

    # If no args, show help
    if not any([args.run, args.report, args.suggest, args.full, args.journal]):
        parser.print_help()
        return 1

    # Load existing journal
    journal = load_journal()

    # Run demos if requested
    if args.run or args.full:
        results, total_time = run_all_demos()
        analysis = analyze_results(results, journal)
        save_journal(journal)

        # Save to metrics history
        history = load_metrics_history()
        history.append(analysis)
        save_metrics_history(history)

        if not args.quiet:
            print_report(results, analysis)

    # Generate suggestions
    if args.suggest or args.full:
        analysis = analyze_results([], journal)  # Use existing data
        suggestions = generate_suggestions(analysis, journal)

        # Save suggestions
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(SUGGESTIONS_FILE, "w") as f:
            json.dump(suggestions, f, indent=2)

        if not args.quiet:
            print_suggestions(suggestions)

    # Print report
    if args.report and not args.full and not args.quiet:
        # Try to load last analysis from history
        history = load_metrics_history()
        if history:
            latest_analysis = history[-1]
            results = [
                {"success": True, "demo": "cached", "execution_time": 0}
            ]
            print_report(results, latest_analysis)

    # Print journal
    if args.journal and not args.quiet:
        print_learning_summary(journal)

    return 0


if __name__ == "__main__":
    sys.exit(main())
