#!/usr/bin/env python3
"""
Phase 6: Evaluation Harness Orchestrator

Main runner coordinating LEGO-Eval (130 instructions, 1,250 constraints)
and BlenderGym (245 scenes, Task Completion Rate) benchmarks against
skill bank recipes from Phase 4.

Usage:
    python eval/run.py --suite lego-eval [--filter category]
    python eval/run.py --suite blender-gym [--filter difficulty]
    python eval/run.py --suite all --compare
"""

import sys
import json
import argparse
import time
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime

# Imports from eval/common.py
sys.path.insert(0, str(Path(__file__).parent))
from common import (
    EvalResult, EvalMetrics, ConstraintResult, TestInstruction,
    MetricType, MCPClient, ReportGenerator, format_duration,
    compute_f1_score, compute_cohens_kappa
)


class EvaluationOrchestrator:
    """Orchestrates LEGO-Eval and BlenderGym adapter runs."""

    def __init__(self, blender_host: str = 'localhost', blender_port: int = 29500):
        self.blender_host = blender_host
        self.blender_port = blender_port
        self.mcp_client: Optional[MCPClient] = None
        self.logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        """Configure logging with timestamp and level."""
        logger = logging.getLogger('EvalOrchestrator')
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        return logger

    def _connect_blender(self) -> bool:
        """Establish connection to Blender MCP server."""
        self.mcp_client = MCPClient(host=self.blender_host, port=self.blender_port)
        if self.mcp_client.connect():
            self.logger.info(f"Connected to Blender MCP at {self.blender_host}:{self.blender_port}")
            return True
        else:
            self.logger.warning(f"Failed to connect to Blender MCP. Running offline evaluation.")
            return False

    def _disconnect_blender(self) -> None:
        """Close connection to Blender MCP server."""
        if self.mcp_client:
            self.mcp_client.disconnect()
            self.logger.info("Disconnected from Blender MCP")

    def run_lego_eval(self, filter_category: Optional[str] = None) -> EvalResult:
        """
        Run LEGO-Eval benchmark: 130 instructions across 10 categories.
        Categories: Basic Modeling, Lighting, Materials, Composition, Animation,
                    Rendering, Shading, Rigging, Geometry, Procedural.
        
        Args:
            filter_category: Optional category filter (e.g., 'Lighting')
        
        Returns:
            EvalResult with 130 test instructions, constraint pass rates, metrics
        """
        from lego_eval.adapter import LEGOEvalAdapter
        
        self.logger.info("Starting LEGO-Eval benchmark (130 instructions, 1,250 constraints)")
        
        start_time = time.time()
        adapter = LEGOEvalAdapter(mcp_client=self.mcp_client, logger=self.logger)
        
        result = adapter.run(filter_category=filter_category)
        
        duration = time.time() - start_time
        result.duration_seconds = duration
        
        self.logger.info(
            f"LEGO-Eval complete: {result.passed_count}/{result.test_count} passed "
            f"({result.pass_rate():.1%}) in {format_duration(duration)}"
        )
        
        return result

    def run_blender_gym(self, filter_difficulty: Optional[str] = None) -> EvalResult:
        """
        Run BlenderGym benchmark: 245 procedural scenes.
        Difficulties: Beginner (50), Intermediate (120), Advanced (75).
        Metric: Task Completion Rate (TCR).
        
        Args:
            filter_difficulty: Optional difficulty filter ('beginner'|'intermediate'|'advanced')
        
        Returns:
            EvalResult with 245 scene tasks, TCR metric
        """
        from blender_gym.adapter import BlenderGymAdapter
        
        self.logger.info("Starting BlenderGym benchmark (245 procedural scenes)")
        
        start_time = time.time()
        adapter = BlenderGymAdapter(mcp_client=self.mcp_client, logger=self.logger)
        
        result = adapter.run(filter_difficulty=filter_difficulty)
        
        duration = time.time() - start_time
        result.duration_seconds = duration
        
        self.logger.info(
            f"BlenderGym complete: {result.passed_count}/{result.test_count} scenes completed "
            f"({result.pass_rate():.1%}) in {format_duration(duration)}"
        )
        
        return result

    def compare_results(self, results: Dict[str, EvalResult]) -> Dict[str, Any]:
        """
        Compare evaluation results across suites (LEGO-Eval vs BlenderGym).
        
        Args:
            results: Dict with suite names as keys (e.g., {'lego-eval': ..., 'blender-gym': ...})
        
        Returns:
            Comparison dict with relative metrics and cross-suite analysis
        """
        comparison = {
            'timestamp': datetime.utcnow().isoformat(),
            'suites_compared': list(results.keys()),
            'suite_results': {},
            'cross_suite_analysis': {}
        }

        # Summarize each suite
        for suite_name, result in results.items():
            comparison['suite_results'][suite_name] = {
                'test_count': result.test_count,
                'passed_count': result.passed_count,
                'pass_rate': result.pass_rate(),
                'constraint_pass_rate': result.constraint_pass_rate(),
                'execution_time_ms': result.duration_seconds * 1000 if result.duration_seconds else 0,
                'metrics': {
                    'f1_score': result.metrics.f1_score if result.metrics else None,
                    'holistic_success_rate': result.metrics.holistic_success_rate if result.metrics else None,
                    'task_completion_rate': result.metrics.task_completion_rate if result.metrics else None
                }
            }

        # Cross-suite analysis
        if len(results) > 1:
            suite_list = list(results.values())
            avg_pass_rate = sum(r.pass_rate() for r in suite_list) / len(suite_list)
            comparison['cross_suite_analysis'] = {
                'avg_pass_rate': avg_pass_rate,
                'constraint_coverage': 'LEGO-Eval (1,250 constraints) + BlenderGym (245 scenes)',
                'recommendation': (
                    'Promote recipes' if avg_pass_rate >= 0.85
                    else 'Refine and re-evaluate' if avg_pass_rate >= 0.70
                    else 'Request mutations'
                )
            }

        return comparison

    def run(self, suite: str, filter_arg: Optional[str] = None, compare: bool = False) -> None:
        """
        Main entry point: run specified evaluation suite(s).
        
        Args:
            suite: 'lego-eval', 'blender-gym', or 'all'
            filter_arg: Optional category/difficulty filter
            compare: If True and suite='all', compare results
        """
        results: Dict[str, EvalResult] = {}

        try:
            if suite in ('lego-eval', 'all'):
                self._connect_blender()
                results['lego-eval'] = self.run_lego_eval(filter_category=filter_arg)

            if suite in ('blender-gym', 'all'):
                if not self.mcp_client:
                    self._connect_blender()
                results['blender-gym'] = self.run_blender_gym(filter_difficulty=filter_arg)

            # Generate reports
            for suite_name, result in results.items():
                report_path = Path(__file__).parent / f"results_{suite_name}_{int(time.time())}.md"
                ReportGenerator.generate_markdown(result, output_file=str(report_path))
                self.logger.info(f"Report written to {report_path}")

            # Comparison if requested
            if compare and len(results) > 1:
                comparison = self.compare_results(results)
                comparison_path = Path(__file__).parent / f"comparison_{int(time.time())}.json"
                with open(comparison_path, 'w') as f:
                    json.dump(comparison, f, indent=2)
                self.logger.info(f"Comparison written to {comparison_path}")
                print(f"\nCross-suite recommendation: {comparison['cross_suite_analysis']['recommendation']}")

        except Exception as e:
            self.logger.error(f"Evaluation failed: {e}", exc_info=True)
            sys.exit(1)
        finally:
            self._disconnect_blender()


def main():
    parser = argparse.ArgumentParser(
        description='Phase 6 Evaluation Harness: LEGO-Eval and BlenderGym benchmarks'
    )
    parser.add_argument(
        '--suite',
        choices=['lego-eval', 'blender-gym', 'all'],
        default='all',
        help='Evaluation suite to run (default: all)'
    )
    parser.add_argument(
        '--filter',
        type=str,
        help='Category (LEGO-Eval) or difficulty (BlenderGym) filter'
    )
    parser.add_argument(
        '--compare',
        action='store_true',
        help='Compare results across suites (requires --suite all)'
    )
    parser.add_argument(
        '--blender-host',
        default='localhost',
        help='Blender MCP server host (default: localhost)'
    )
    parser.add_argument(
        '--blender-port',
        type=int,
        default=29500,
        help='Blender MCP server port (default: 29500)'
    )

    args = parser.parse_args()

    orchestrator = EvaluationOrchestrator(
        blender_host=args.blender_host,
        blender_port=args.blender_port
    )
    orchestrator.run(
        suite=args.suite,
        filter_arg=args.filter,
        compare=args.compare
    )


if __name__ == '__main__':
    main()
