# OpenClaw Blender MCP — Auto-Learning System Guide

## Overview

The Auto-Learning Improvement System (`scripts/auto_learner.py`) is a comprehensive testing and analysis framework that:

1. **Runs all demo scripts** sequentially and captures pass/fail results
2. **Parses error messages** to identify patterns (e.g., context issues, missing objects, enum mismatches)
3. **Maintains a learning journal** tracking error history, patterns, and trends
4. **Generates fix suggestions** based on identified error categories
5. **Tracks improvement metrics** over time with historical data

## Quick Start

### Run all demos and capture results
```bash
python3 scripts/auto_learner.py --run
```

### Print formatted test report
```bash
python3 scripts/auto_learner.py --report
```

### Generate improvement suggestions
```bash
python3 scripts/auto_learner.py --suggest
```

### Full workflow (run + report + suggest)
```bash
python3 scripts/auto_learner.py --full
```

### Print cumulative learning journal summary
```bash
python3 scripts/auto_learner.py --journal
```

## Data Storage

All results are stored in the `data/` directory:

### `learning_journal.json`
Central record of all errors encountered, updated with each run.

```json
{
  "entries": [
    {
      "timestamp": "2026-03-24T12:34:56.789123",
      "command": "full_capability_showcase.py",
      "error_message": "socket error: Connection refused",
      "error_category": "BLENDER_UNREACHABLE",
      "auto_fixed": false
    }
  ],
  "error_patterns": {
    "CONTEXT_ISSUE": {
      "count": 3,
      "first_seen": "2026-03-24T10:00:00",
      "last_seen": "2026-03-24T12:30:00",
      "auto_fixes": 0
    },
    "MISSING_OBJECT": {
      "count": 1,
      "first_seen": "2026-03-24T11:15:00",
      "last_seen": "2026-03-24T11:15:00",
      "auto_fixes": 0
    }
  },
  "first_run": "2026-03-24T10:00:00",
  "last_run": "2026-03-24T12:34:56.789123",
  "total_tests": 16,
  "total_passed": 14,
  "total_failed": 2
}
```

### `metrics_history.json`
Historical trend data from each run, enabling progress tracking.

```json
[
  {
    "timestamp": "2026-03-24T10:00:00",
    "total_tests": 4,
    "passed": 4,
    "failed": 0,
    "pass_rate": 100.0,
    "error_analysis": {}
  },
  {
    "timestamp": "2026-03-24T12:34:56.789123",
    "total_tests": 4,
    "passed": 3,
    "failed": 1,
    "pass_rate": 75.0,
    "error_analysis": {
      "BLENDER_UNREACHABLE": [
        {
          "demo": "cityscape_sunset.py",
          "error": "socket error: Connection refused",
          "severity": "CRITICAL"
        }
      ]
    }
  }
]
```

### `improvement_suggestions.json`
Latest generated suggestions based on error patterns.

```json
{
  "generated_at": "2026-03-24T12:34:56.789123",
  "error_patterns": [
    {
      "error_category": "CONTEXT_ISSUE",
      "occurrences": 3,
      "severity": "HIGH",
      "fix_suggestion": "Add mode_set(mode='OBJECT') safety checks before operations",
      "auto_fix_attempts": 0
    }
  ],
  "critical_issues": [
    {
      "error_category": "BLENDER_UNREACHABLE",
      "occurrences": 1,
      "severity": "CRITICAL",
      "fix_suggestion": "Start Blender and ensure MCP server is running on port 9876"
    }
  ],
  "recommended_fixes": [
    {
      "priority": "CRITICAL",
      "action": "Address critical issues",
      "issues": [...]
    }
  ],
  "trend_analysis": {
    "status": "available",
    "entries_analyzed": 16,
    "improvement_by_category": {
      "CONTEXT_ISSUE": {
        "all_time": 3,
        "recent": 0,
        "trend": "improving"
      }
    }
  }
}
```

## Error Categories & Fix Suggestions

The system detects and categorizes errors based on regex patterns. Currently supported:

| Category | Pattern | Severity | Fix Suggestion |
|----------|---------|----------|-----------------|
| **CONTEXT_ISSUE** | poll(), context, mode_set | HIGH | Add mode_set(mode='OBJECT') safety checks before operations |
| **MISSING_OBJECT** | not found, KeyError | MEDIUM | Verify object creation order and check object_name parameter spelling |
| **ENUM_MISMATCH** | enum, invalid value, AttributeError | HIGH | Check API version compatibility; enum values may have changed |
| **PROPERTY_ISSUE** | property, AttributeError, read-only | MEDIUM | Verify property exists and is writable for current object type |
| **TYPE_MISMATCH** | TypeError, type mismatch | LOW | Check parameter types (list/dict/str/float) match API expectations |
| **TIMEOUT** | timeout, TIMEOUT, socket timeout | CRITICAL | Increase timeout or simplify demo step; Blender may be unresponsive |
| **FILE_NOT_FOUND** | FileNotFoundError, IOError | LOW | Verify file paths are correct and files exist in expected location |
| **BLENDER_UNREACHABLE** | Connection, refused, ECONNREFUSED | CRITICAL | Start Blender and ensure MCP server is running on port 9876 |

## Demo Scripts Executed

The system runs these demos sequentially:

1. `full_capability_showcase.py` — Tests all major feature categories
2. `vfx_showcase.py` — Visual effects demonstrations
3. `vfx_advanced_showoff.py` — Advanced VFX features
4. `cityscape_sunset.py` — Complex scene with multiple elements

Each demo runs with a 5-minute timeout per script.

## Report Output Format

### Test Results Report
```
═══════════════════════════════════════════════════════════════════
  TEST RESULTS REPORT
═══════════════════════════════════════════════════════════════════

  Total Tests:  4
  Passed:       3 ✓
  Failed:       1 ✗
  Pass Rate:    75.0%

  DETAILED RESULTS:
  ──────────────────────────────────────────────────────────────────
    ✓ full_capability_showcase.py                        142.3s
    ✓ vfx_showcase.py                                     98.1s
    ✓ vfx_advanced_showoff.py                            176.5s
    ✗ cityscape_sunset.py                                 15.2s
      → socket error: Connection refused...

  ERROR ANALYSIS BY CATEGORY:
  ──────────────────────────────────────────────────────────────────
    BLENDER_UNREACHABLE       (1 occurrences)
      [CRITICAL] cityscape_sunset.py

═══════════════════════════════════════════════════════════════════
```

### Improvement Suggestions Report
```
═══════════════════════════════════════════════════════════════════
  IMPROVEMENT SUGGESTIONS
═══════════════════════════════════════════════════════════════════

  CRITICAL ISSUES (must fix):
  ──────────────────────────────────────────────────────────────────
    • BLENDER_UNREACHABLE (1x)
      → Start Blender and ensure MCP server is running on port 9876

  ERROR PATTERNS & FIXES:
  ──────────────────────────────────────────────────────────────────
     3x [HIGH    ] CONTEXT_ISSUE
        → Add mode_set(mode='OBJECT') safety checks before operations
     1x [CRITICAL] BLENDER_UNREACHABLE
        → Start Blender and ensure MCP server is running on port 9876

  RECOMMENDED ACTIONS:
  ──────────────────────────────────────────────────────────────────
    [CRITICAL] Address critical issues

  TREND ANALYSIS:
  ──────────────────────────────────────────────────────────────────
    ↓ CONTEXT_ISSUE           (all-time: 3, recent: 0)
    → MISSING_OBJECT          (all-time: 1, recent: 0)

═══════════════════════════════════════════════════════════════════
```

### Learning Journal Summary
```
═══════════════════════════════════════════════════════════════════
  LEARNING JOURNAL SUMMARY
═══════════════════════════════════════════════════════════════════

  Cumulative Statistics:
    Total Tests Run:  16
    Total Passed:     14 ✓
    Total Failed:     2 ✗
    Overall Pass Rate: 87.5%

  First Run:  2026-03-24T10:00:00
  Last Run:   2026-03-24T12:34:56.789123

  Error Patterns Tracked:
  ──────────────────────────────────────────────────────────────────
    CONTEXT_ISSUE             3x (fixed: 0x, first: 2026-03-2)
    MISSING_OBJECT            1x (fixed: 0x, first: 2026-03-2)
    BLENDER_UNREACHABLE       2x (fixed: 0x, first: 2026-03-2)

═══════════════════════════════════════════════════════════════════
```

## Advanced Usage

### Quiet Mode (save to files only, no console output)
```bash
python3 scripts/auto_learner.py --full --quiet
# Data written to data/ directory without printing
```

### Check specific metric trends
```bash
python3 scripts/auto_learner.py --journal
# View cumulative stats and error pattern history
```

### View latest suggestions without running
```bash
python3 scripts/auto_learner.py --suggest
# Analyzes existing data and prints recommendations
```

## Integration with Blender

The auto-learner communicates with Blender via TCP socket on port 9876 (same as demos).

**Before running:**
1. Start Blender with MCP server listening on port 9876
2. Ensure the server is accessible (no firewall blocking)
3. Blender should not be in a blocking operation

**If you get BLENDER_UNREACHABLE errors:**
```bash
# Check if Blender is running and listening
lsof -i :9876  # macOS/Linux
netstat -an | grep 9876  # Alternative

# Check if MCP server is initialized
ps aux | grep blender  # Verify Blender process

# Restart Blender with MCP server active
```

## Architecture Details

### Error Detection Pipeline
1. **Execution**: Run demo subprocess, capture stdout/stderr
2. **Parsing**: Extract error messages from output
3. **Categorization**: Match against ERROR_PATTERNS regex
4. **Recording**: Store in learning journal with metadata
5. **Analysis**: Aggregate patterns and generate insights

### Metrics Tracking
- Per-run: total_tests, passed, failed, pass_rate, error_analysis
- Per-error-pattern: count, first_seen, last_seen, auto_fixes
- Trends: Compare recent errors vs all-time patterns

### Suggestion Generation
1. Count occurrences by error_category
2. Retrieve fix suggestions from ERROR_PATTERNS
3. Identify CRITICAL severity issues
4. Calculate trends (improving/stable/regressing)
5. Generate prioritized recommendations

## Adding New Error Patterns

Edit the `ERROR_PATTERNS` dictionary in `auto_learner.py`:

```python
ERROR_PATTERNS = {
    "your_new_error": {
        "regex": r"(pattern|to|match)",
        "category": "YOUR_CATEGORY_NAME",
        "fix_suggestion": "What users should do to fix this",
        "severity": "LOW",  # LOW, MEDIUM, HIGH, CRITICAL
    },
    # ... existing patterns ...
}
```

Patterns are matched case-insensitively and first match wins.

## Performance Expectations

- **Per demo**: 15-180 seconds depending on complexity
- **Total run** (all 4 demos): 4-8 minutes
- **Analysis**: <1 second (processes JSON)
- **Report generation**: <1 second

## Troubleshooting

### "Demo file not found"
Verify demos exist in `demos/` directory:
```bash
ls -la demos/
```

### "Connection refused" errors
Blender MCP server not running. Start Blender and wait for server initialization.

### "TIMEOUT" errors  
Demo exceeded 5 minute limit. Demos may be too complex or Blender is unresponsive.

### Empty error_analysis
Demos passed! No errors to analyze. This is a good thing.

### Data directory issues
The script auto-creates `data/` directory. If permissions denied:
```bash
mkdir -p data/
chmod 755 data/
```

## File Paths

```
openclaw-blender-mcp/
├── scripts/
│   └── auto_learner.py           # Main script
├── data/                           # Auto-created
│   ├── learning_journal.json       # Error history
│   ├── metrics_history.json        # Trends over time
│   └── improvement_suggestions.json # Latest recommendations
├── demos/
│   ├── full_capability_showcase.py
│   ├── vfx_showcase.py
│   ├── vfx_advanced_showoff.py
│   └── cityscape_sunset.py
└── AUTO_LEARNER_GUIDE.md          # This file
```

## Next Steps

1. **Run baseline**: `python3 scripts/auto_learner.py --run`
2. **Review suggestions**: `python3 scripts/auto_learner.py --suggest`
3. **Implement fixes** based on recommendations
4. **Re-run** to measure improvement: `python3 scripts/auto_learner.py --run`
5. **Monitor trends** with `--journal` to see long-term progress

## Contact & Support

For issues or enhancements, check the learning journal error categories and generated suggestions for diagnostic insights.
