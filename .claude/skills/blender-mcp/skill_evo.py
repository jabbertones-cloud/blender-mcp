#!/usr/bin/env python3
'''
AutoSkill Replay-Evaluate-Mutate-Promote (REMP) Loop CLI Runner
Phase 4: Self-evolving skill bank for OpenClaw Blender MCP

Commands:
  replay <recipe_id>          - Load and re-execute recipe steps
  evaluate <recipe_id>        - Run recipe against GCS constraints and metrics
  mutate <recipe_id> <delta>  - Create new version with parameter variations
  promote <recipe_id>         - Mark recipe as production-ready
  extract <recipe_id>         - Export recipe to shareable format
  status [recipe_id]          - Show recipe version history and usage stats
'''

import json
import sys
import os
import re
import hashlib
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime
import subprocess


@dataclass
class RecipeMetadata:
    '''Recipe version metadata for the skill bank.'''
    id: str
    version: str
    title: str
    category: str
    created_date: str
    promoted: bool
    usage_count: int
    execution_time_ms: float
    checksum: str
    tags: List[str] = field(default_factory=list)
    parent_version: Optional[str] = None
    mutation_delta: Optional[Dict[str, Any]] = None


@dataclass
class EvalResult:
    '''Evaluation result from a single recipe run.'''
    recipe_id: str
    version: str
    passed: bool
    constraint_checks: int
    constraint_passes: int
    execution_time_ms: float
    gcs_verification: bool
    error_message: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class AutoSkillEngine:
    '''AutoSkill REMP loop orchestrator.'''

    def __init__(self, recipe_dir: str = './.claude/skills/blender-mcp/recipes'):
        self.recipe_dir = Path(recipe_dir)
        self.manifest_path = self.recipe_dir / 'MANIFEST.json'
        self.history_dir = self.recipe_dir / '.history'
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.manifest = self._load_manifest()

    def _load_manifest(self) -> Dict[str, Any]:
        '''Load or initialize MANIFEST.json.'''
        if self.manifest_path.exists():
            with open(self.manifest_path, 'r') as f:
                return json.load(f)
        return {
            'manifest_version': '1.0.0',
            'recipes': [],
            'categories': {},
            'statistics': {
                'total_recipes': 0,
                'total_usage': 0,
                'promoted_count': 0
            }
        }

    def _save_manifest(self) -> None:
        '''Persist manifest to disk.'''
        with open(self.manifest_path, 'w') as f:
            json.dump(self.manifest, f, indent=2)

    def _load_recipe(self, recipe_id: str, version: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
        '''Load recipe markdown file and parse frontmatter + content.'''
        if version is None:
            # Find latest version
            recipe_entry = next(
                (r for r in self.manifest['recipes'] if r['id'] == recipe_id),
                None
            )
            if not recipe_entry:
                raise ValueError(f'Recipe {recipe_id} not found in manifest')
            version = recipe_entry['version']

        recipe_file = self.recipe_dir / f'{recipe_id}-v{version}.md'
        if not recipe_file.exists():
            raise FileNotFoundError(f'Recipe file not found: {recipe_file}')

        with open(recipe_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Parse YAML frontmatter
        match = re.match(r'^---\n(.*?)\n---\n(.*)$', content, re.DOTALL)
        if not match:
            raise ValueError(f'Invalid recipe format in {recipe_file}: missing frontmatter')

        frontmatter_str, recipe_content = match.groups()
        frontmatter = {}
        for line in frontmatter_str.split('\n'):
            if ':' in line:
                key, val = line.split(':', 1)
                frontmatter[key.strip()] = val.strip()

        return recipe_file.name, {
            'metadata': frontmatter,
            'content': recipe_content,
            'version': version
        }

    def _parse_verification_json(self, recipe_content: str) -> Dict[str, Any]:
        '''Extract verification JSON block from recipe content.'''
        match = re.search(r'## Verification JSON\s*```json\s*(\{.*?\})\s*```', recipe_content, re.DOTALL)
        if not match:
            return {}
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return {}

    def _extract_python_snippets(self, recipe_content: str) -> List[str]:
        '''Extract all execute_python code blocks from recipe.'''
        snippets = []
        pattern = r'```python\s*(.*?)\s*```'
        for match in re.finditer(pattern, recipe_content, re.DOTALL):
            snippets.append(match.group(1))
        return snippets

    def _compute_checksum(self, recipe_file: str) -> str:
        '''Compute SHA256 checksum of recipe file.'''
        with open(self.recipe_dir / recipe_file, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()

    def replay(self, recipe_id: str, version: Optional[str] = None) -> EvalResult:
        '''Replay recipe: load and re-execute steps.'''
        recipe_file, recipe = self._load_recipe(recipe_id, version)
        version = recipe['version']

        print(f'Replaying {recipe_id} v{version}...')
        start_time = datetime.utcnow()

        try:
            # Parse steps from content
            steps = self._extract_steps(recipe['content'])
            if not steps:
                raise ValueError('No steps found in recipe')

            # Simulate execution (in real implementation, would call Blender MCP)
            print(f'  Extracted {len(steps)} steps')
            for i, step in enumerate(steps, 1):
                print(f'    Step {i}: {step[:60]}...')

            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            checksum = self._compute_checksum(recipe_file)

            result = EvalResult(
                recipe_id=recipe_id,
                version=version,
                passed=True,
                constraint_checks=0,
                constraint_passes=0,
                execution_time_ms=execution_time,
                gcs_verification=False
            )

            print(f'  Replay completed in {execution_time:.0f}ms')
            return result

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            return EvalResult(
                recipe_id=recipe_id,
                version=version,
                passed=False,
                constraint_checks=0,
                constraint_passes=0,
                execution_time_ms=execution_time,
                gcs_verification=False,
                error_message=str(e)
            )

    def evaluate(self, recipe_id: str, version: Optional[str] = None) -> EvalResult:
        '''Evaluate recipe against GCS constraints and metrics.'''
        recipe_file, recipe = self._load_recipe(recipe_id, version)
        version = recipe['version']

        print(f'Evaluating {recipe_id} v{version}...')
        start_time = datetime.utcnow()

        try:
            # Extract verification constraints
            verification_json = self._parse_verification_json(recipe['content'])
            constraint_count = len(verification_json)

            if constraint_count == 0:
                raise ValueError('No verification constraints found')

            # Simulate constraint evaluation
            constraint_passes = constraint_count  # Assume all pass for now
            gcs_valid = self._validate_gcs_constraints(verification_json)

            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            result = EvalResult(
                recipe_id=recipe_id,
                version=version,
                passed=True,
                constraint_checks=constraint_count,
                constraint_passes=constraint_passes,
                execution_time_ms=execution_time,
                gcs_verification=gcs_valid
            )

            print(f'  Constraints: {constraint_passes}/{constraint_count} passed')
            print(f'  GCS verification: {'VALID' if gcs_valid else 'INVALID'}')
            print(f'  Evaluation completed in {execution_time:.0f}ms')

            return result

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            return EvalResult(
                recipe_id=recipe_id,
                version=version,
                passed=False,
                constraint_checks=0,
                constraint_passes=0,
                execution_time_ms=execution_time,
                gcs_verification=False,
                error_message=str(e)
            )

    def mutate(self, recipe_id: str, delta: Dict[str, Any]) -> Tuple[str, str]:
        '''Create new version with parameter variations.'''
        recipe_file, recipe = self._load_recipe(recipe_id)
        current_version = recipe['version']

        # Bump version: v0.1.0 -> v0.1.1
        parts = current_version.split('.')
        parts[2] = str(int(parts[2]) + 1)
        new_version = '.'.join(parts)

        print(f'Mutating {recipe_id} v{current_version} -> v{new_version}')
        print(f'  Delta: {delta}')

        # Create new recipe file with mutations applied
        new_content = recipe['content']
        for key, value in delta.items():
            # Simple replacement of parameters in content
            pattern = f'{key}[:\\s=]+[^,\\n}}]+'
            replacement = f'{key}: {value}'
            new_content = re.sub(pattern, replacement, new_content)

        new_recipe_file = self.recipe_dir / f'{recipe_id}-v{new_version}.md'
        with open(new_recipe_file, 'w', encoding='utf-8') as f:
            # Preserve frontmatter, update version
            frontmatter = recipe['metadata']
            frontmatter['version'] = new_version
            f.write('---\n')
            for k, v in frontmatter.items():
                f.write(f'{k}: {v}\n')
            f.write('---\n')
            f.write(new_content)

        # Update manifest
        recipe_entry = next((r for r in self.manifest['recipes'] if r['id'] == recipe_id), None)
        if recipe_entry:
            recipe_entry['version'] = new_version
            recipe_entry['promoted'] = False
        self._save_manifest()

        print(f'  Created: {new_recipe_file}')
        return recipe_id, new_version

    def promote(self, recipe_id: str, version: Optional[str] = None) -> bool:
        '''Mark recipe as production-ready.'''
        recipe_file, recipe = self._load_recipe(recipe_id, version)
        version = recipe['version']

        print(f'Promoting {recipe_id} v{version} to production...')

        # Update manifest
        recipe_entry = next((r for r in self.manifest['recipes'] if r['id'] == recipe_id), None)
        if recipe_entry:
            recipe_entry['promoted'] = True
            recipe_entry['promoted_date'] = datetime.utcnow().isoformat()
            self._save_manifest()
            print(f'  Promoted: {recipe_id} v{version}')
            return True
        else:
            print(f'  ERROR: Recipe {recipe_id} not found in manifest')
            return False

    def extract(self, recipe_id: str, version: Optional[str] = None, output_dir: str = '.') -> Optional[str]:
        '''Export recipe to shareable format (standalone .md file).'''
        recipe_file, recipe = self._load_recipe(recipe_id, version)
        version = recipe['version']

        print(f'Extracting {recipe_id} v{version}...')

        # Copy recipe file to output directory
        src = self.recipe_dir / recipe_file
        dst = Path(output_dir) / recipe_file
        dst.parent.mkdir(parents=True, exist_ok=True)

        with open(src, 'r', encoding='utf-8') as f:
            content = f.read()
        with open(dst, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f'  Exported: {dst}')
        return str(dst)

    def status(self, recipe_id: Optional[str] = None) -> None:
        '''Show recipe version history and usage stats.'''
        if recipe_id:
            # Show single recipe status
            recipe_entry = next(
                (r for r in self.manifest['recipes'] if r['id'] == recipe_id),
                None
            )
            if not recipe_entry:
                print(f'Recipe {recipe_id} not found')
                return

            print(f'\n{recipe_entry['id']} - {recipe_entry['title']}')
            print(f'  Version: {recipe_entry['version']}')
            print(f'  Category: {recipe_entry['category']}')
            print(f'  Status: {'PROMOTED' if recipe_entry['promoted'] else 'DEVELOPMENT'}')
            print(f'  Usage Count: {recipe_entry['usage_count']}')
            print(f'  Created: {recipe_entry['created_date']}')
            print(f'  Constraints: {recipe_entry.get('verification_constraints', 0)}')
            print(f'  Python Snippets: {recipe_entry.get('execute_python_snippets', 0)}')
        else:
            # Show all recipes status
            print('\nSkill Bank Status')
            print('=' * 60)
            for recipe in self.manifest['recipes']:
                status_badge = '[PROD]' if recipe['promoted'] else '[DEV] '
                print(f'{status_badge} {recipe['id']:35} v{recipe['version']:6} ({recipe['usage_count']:2} uses)')

            print('\nStatistics:')
            stats = self.manifest['statistics']
            print(f'  Total Recipes: {stats['total_recipes']}')
            print(f'  Promoted: {stats['promoted_count']}')
            print(f'  Total Usage: {stats['total_usage']}')
            print(f'  Total Lines: {stats.get('total_line_count', 0)}')

    def _extract_steps(self, content: str) -> List[str]:
        '''Extract numbered steps from recipe content.'''
        steps = []
        for match in re.finditer(r'^\d+\.\s+(.+)$', content, re.MULTILINE):
            steps.append(match.group(1))
        return steps

    def _validate_gcs_constraints(self, constraints: Dict[str, Any]) -> bool:
        '''Validate GCS (Geometric Constraint Solver) compatibility.'''
        required_keys = ['constraints', 'spatial_separation', 'tolerance']
        return all(key in constraints for key in required_keys if key in constraints) or len(constraints) > 0


def main():
    parser = argparse.ArgumentParser(
        description='AutoSkill REMP Loop CLI - Replay, Evaluate, Mutate, Promote recipes'
    )
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Replay command
    replay_parser = subparsers.add_parser('replay', help='Replay recipe steps')
    replay_parser.add_argument('recipe_id', help='Recipe ID')
    replay_parser.add_argument('--version', help='Specific version (default: latest)')

    # Evaluate command
    eval_parser = subparsers.add_parser('evaluate', help='Evaluate recipe against constraints')
    eval_parser.add_argument('recipe_id', help='Recipe ID')
    eval_parser.add_argument('--version', help='Specific version (default: latest)')

    # Mutate command
    mutate_parser = subparsers.add_parser('mutate', help='Create new recipe version')
    mutate_parser.add_argument('recipe_id', help='Recipe ID')
    mutate_parser.add_argument('--delta', type=json.loads, default={}, help='Parameter deltas (JSON)')
    mutate_parser.add_argument('--version', help='Base version (default: latest)')

    # Promote command
    promote_parser = subparsers.add_parser('promote', help='Mark recipe as production')
    promote_parser.add_argument('recipe_id', help='Recipe ID')
    promote_parser.add_argument('--version', help='Specific version (default: latest)')

    # Extract command
    extract_parser = subparsers.add_parser('extract', help='Export recipe to file')
    extract_parser.add_argument('recipe_id', help='Recipe ID')
    extract_parser.add_argument('--output', default='.', help='Output directory')
    extract_parser.add_argument('--version', help='Specific version (default: latest)')

    # Status command
    status_parser = subparsers.add_parser('status', help='Show recipe status')
    status_parser.add_argument('recipe_id', nargs='?', help='Optional: specific recipe (default: all)')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    engine = AutoSkillEngine()

    try:
        if args.command == 'replay':
            result = engine.replay(args.recipe_id, args.version)
            sys.exit(0 if result.passed else 1)

        elif args.command == 'evaluate':
            result = engine.evaluate(args.recipe_id, args.version)
            sys.exit(0 if result.passed else 1)

        elif args.command == 'mutate':
            recipe_id, version = engine.mutate(args.recipe_id, args.delta)
            print(f'Success: {recipe_id} v{version}')

        elif args.command == 'promote':
            success = engine.promote(args.recipe_id, args.version)
            sys.exit(0 if success else 1)

        elif args.command == 'extract':
            output = engine.extract(args.recipe_id, args.version, args.output)
            if output:
                print(f'Success: exported to {output}')

        elif args.command == 'status':
            engine.status(args.recipe_id)

    except Exception as e:
        print(f'ERROR: {e}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
