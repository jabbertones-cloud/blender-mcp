'''
Phase 6: Evaluation Harness Common Utilities
Shared dataclasses, MCP client, and reporting helpers for LEGO-Eval and BlenderGym.
'''

import json
import socket
import struct
import time
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path
from enum import Enum


class MetricType(Enum):
    '''Evaluation metric types.'''
    F1_SCORE = 'f1'
    COHENS_KAPPA = 'cohens_kappa'
    HOLISTIC_SR = 'holistic_success_rate'
    PARTIAL_SR = 'partial_success_rate'
    TASK_COMPLETION_RATE = 'task_completion_rate'


@dataclass
class ConstraintResult:
    '''Single constraint verification result.'''
    constraint_id: str
    constraint_type: str
    passed: bool
    expected: Any
    actual: Any
    tolerance: Optional[float] = None
    error_message: Optional[str] = None


@dataclass
class TestInstruction:
    '''Single test instruction with constraints.'''
    id: str
    instruction_text: str
    category: str
    difficulty: str  # 'beginner', 'intermediate', 'advanced'
    constraints: List[Dict[str, Any]] = field(default_factory=list)
    setup_steps: List[str] = field(default_factory=list)
    expected_objects: List[str] = field(default_factory=list)


@dataclass
class EvalMetrics:
    '''Computed metrics from evaluation.'''
    f1_score: float
    cohens_kappa: float
    holistic_success_rate: float
    partial_success_rate: float
    constraint_pass_rate: float
    avg_execution_time_ms: float
    total_constraints_checked: int
    total_constraints_passed: int


@dataclass
class EvalResult:
    '''Complete evaluation result for a test suite.'''
    suite_id: str
    test_count: int
    passed_count: int
    failed_count: int
    skipped_count: int
    constraint_results: List[ConstraintResult] = field(default_factory=list)
    metrics: Optional[EvalMetrics] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    duration_seconds: float = 0.0
    execution_log: List[str] = field(default_factory=list)

    def to_json(self) -> str:
        '''Serialize result to JSON.'''
        return json.dumps(asdict(self), indent=2, default=str)

    def pass_rate(self) -> float:
        '''Calculate overall pass rate.'''
        total = self.test_count
        return (self.passed_count / total * 100) if total > 0 else 0.0

    def constraint_pass_rate(self) -> float:
        '''Calculate constraint pass rate.'''
        total = len(self.constraint_results)
        passed = sum(1 for r in self.constraint_results if r.passed)
        return (passed / total * 100) if total > 0 else 0.0


class MCPClient:
    '''Blender MCP wire protocol client (JSON over TCP, brace-depth parsing).'''

    def __init__(self, host: str = 'localhost', port: int = 29500, timeout: int = 30):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.socket = None
        self.connected = False

    def connect(self) -> bool:
        '''Connect to Blender MCP server.'''
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.timeout)
            self.socket.connect((self.host, self.port))
            self.connected = True
            return True
        except Exception as e:
            print(f'MCP connection failed: {e}')
            self.connected = False
            return False

    def disconnect(self) -> None:
        '''Close MCP connection.'''
        if self.socket:
            self.socket.close()
            self.connected = False

    def send_command(self, command: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        '''Send command and receive response (brace-depth parsing).'''
        if not self.connected:
            return None

        try:
            # Send command as JSON
            cmd_json = json.dumps(command)
            self.socket.sendall(cmd_json.encode('utf-8'))

            # Receive response with brace-depth parsing
            response = self._receive_json()
            return response
        except Exception as e:
            print(f'MCP command failed: {e}')
            return None

    def _receive_json(self) -> Optional[Dict[str, Any]]:
        '''Receive JSON with brace-depth tracking.'''
        buffer = b''
        brace_depth = 0
        in_string = False
        escape_next = False

        while True:
            try:
                chunk = self.socket.recv(4096)
                if not chunk:
                    break

                for byte in chunk:
                    char = chr(byte)
                    buffer += bytes([byte])

                    # Handle string escape sequences
                    if escape_next:
                        escape_next = False
                        continue

                    if char == '\\':
                        escape_next = True
                        continue

                    # Track string boundaries
                    if char == '"' and not escape_next:
                        in_string = not in_string
                        continue

                    # Track brace depth (only outside strings)
                    if not in_string:
                        if char == '{':
                            brace_depth += 1
                        elif char == '}':
                            brace_depth -= 1

                    # Complete message when braces balance
                    if brace_depth == 0 and len(buffer) > 0:
                        try:
                            return json.loads(buffer.decode('utf-8'))
                        except json.JSONDecodeError:
                            continue

            except socket.timeout:
                break

        return None

    def execute_python(self, code: str) -> Optional[Dict[str, Any]]:
        '''Execute Python code in Blender.'''
        return self.send_command({
            'method': 'execute_python',
            'code': code,
            'single_quotes': True
        })

    def query_scene(self) -> Optional[Dict[str, Any]]:
        '''Query current scene structure.'''
        return self.send_command({
            'method': 'query',
            'target': 'scene'
        })

    def verify_constraint(self, constraint: Dict[str, Any]) -> bool:
        '''Verify a single GCS constraint.'''
        result = self.send_command({
            'method': 'verify_gcs_constraint',
            'constraint': constraint
        })
        return result.get('valid', False) if result else False


class ReportGenerator:
    '''Generate evaluation reports in multiple formats.'''

    @staticmethod
    def generate_markdown(result: EvalResult, output_file: Optional[str] = None) -> str:
        '''Generate markdown report.'''
        lines = [
            f'# Evaluation Report: {result.suite_id}',
            f'Generated: {result.timestamp}',
            f'Duration: {result.duration_seconds:.2f}s',
            '',
            '## Summary',
            f'- Tests: {result.test_count}',
            f'- Passed: {result.passed_count} ({result.pass_rate():.1f}%)',
            f'- Failed: {result.failed_count}',
            f'- Skipped: {result.skipped_count}',
            f'- Constraint Pass Rate: {result.constraint_pass_rate():.1f}%',
            '',
        ]

        if result.metrics:
            lines.extend([
                '## Metrics',
                f'- F1 Score: {result.metrics.f1_score:.3f}',
                f"- Cohen's Kappa: {result.metrics.cohens_kappa:.3f}",
                f'- Holistic SR: {result.metrics.holistic_success_rate:.1f}%',
                f'- Partial SR: {result.metrics.partial_success_rate:.1f}%',
                f'- Avg Exec Time: {result.metrics.avg_execution_time_ms:.0f}ms',
                '',
            ])

        if result.constraint_results:
            lines.extend([
                '## Constraint Results',
                '| ID | Type | Status | Expected | Actual |',
                '|---|---|---|---|---|',
            ])
            for cr in result.constraint_results[:20]:  # Limit to first 20
                status = 'PASS' if cr.passed else 'FAIL'
                lines.append(f'| {cr.constraint_id} | {cr.constraint_type} | {status} | {cr.expected} | {cr.actual} |')

        report = '\n'.join(lines)

        if output_file:
            Path(output_file).write_text(report)

        return report

    @staticmethod
    def generate_json(result: EvalResult, output_file: Optional[str] = None) -> str:
        '''Generate JSON report.'''
        report = result.to_json()

        if output_file:
            Path(output_file).write_text(report)

        return report

    @staticmethod
    def generate_summary_table(results: List[EvalResult]) -> str:
        '''Generate summary table for multiple results.'''
        lines = [
            '| Suite | Tests | Passed | Pass Rate | Exec Time |',
            '|---|---|---|---|---|',
        ]

        for result in results:
            lines.append(
                f'| {result.suite_id} | {result.test_count} | {result.passed_count} | '
                f'{result.pass_rate():.1f}% | {result.duration_seconds:.1f}s |'
            )

        return '\n'.join(lines)


def compute_f1_score(tp: int, fp: int, fn: int) -> float:
    '''Compute F1 score (precision-recall harmonic mean).'''
    if (tp + fp) == 0 or (tp + fn) == 0:
        return 0.0
    precision = tp / (tp + fp)
    recall = tp / (tp + fn)
    if precision + recall == 0:
        return 0.0
    return 2 * (precision * recall) / (precision + recall)


def compute_cohens_kappa(po: float, pe: float) -> float:
    '''Compute Cohen's kappa (inter-rater agreement).
    po: observed agreement proportion
    pe: expected agreement by chance
    '''
    if pe == 1.0:
        return 0.0
    return (po - pe) / (1 - pe)


def format_duration(seconds: float) -> str:
    '''Format duration as human-readable string.'''
    if seconds < 1:
        return f'{seconds * 1000:.0f}ms'
    elif seconds < 60:
        return f'{seconds:.1f}s'
    else:
        minutes = seconds / 60
        return f'{minutes:.1f}min'
