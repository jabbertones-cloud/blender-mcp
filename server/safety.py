"""
Code Safety Checker - AST-level guard for execute_python
===========================================================

Defense-in-depth layer for preventing RCE in the execute_python path.
See Issue #201 (ahujasid/blender-mcp): addon's handle_execute_python at line 885
uses exec(code, namespace) with 'os' in the namespace.

This module walks the AST of arbitrary Python code and rejects:
  1. All imports (and from-imports) of dangerous modules
  2. Calls to dangerous builtins (eval, exec, __import__, etc.) when strict=True
  3. Attempts to access __builtins__ or __class__ for privilege escalation

Primary control: remove 'os' from the exec namespace in the addon.
Secondary control: this AST checker.

Usage:
  from server.safety import check, is_allowed, CodeSafetyError

  try:
      check(code, strict=True)
      exec(code, safe_namespace)
  except CodeSafetyError as e:
      print(f"Blocked: {e.reason}")
"""

import ast
from typing import Optional, Set


class CodeSafetyError(Exception):
    """Raised when code violates safety policy."""

    def __init__(self, reason: str, blocked_node: str = ""):
        self.reason = reason
        self.blocked_node = blocked_node
        super().__init__(f"{reason} | Node: {blocked_node}")


# Default denylist of modules that should never be imported
DENY_IMPORTS = {
    "os",
    "subprocess",
    "socket",
    "shutil",
    "requests",
    "urllib",
    "http",
    "pathlib",
    "ctypes",
    "multiprocessing",
    "paramiko",
    "ftplib",
    "telnetlib",
    "smtplib",
}

# Dangerous builtins and names that should be blocked in strict mode
DENY_NAMES = {
    "eval",
    "exec",
    "__import__",
    "compile",
    "globals",
    "open",
}


def check(
    code: str,
    *,
    strict: bool = True,
    extra_deny: Optional[Set[str]] = None,
) -> None:
    """
    Parse and check code for dangerous patterns.

    Args:
        code: Python source code to check
        strict: If True, also block dangerous builtins (eval, exec, etc.)
        extra_deny: Additional module names to block

    Raises:
        CodeSafetyError: If code violates safety policy
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise CodeSafetyError(f"Syntax error: {e}", "parse")

    deny_imports = DENY_IMPORTS.copy()
    if extra_deny:
        deny_imports.update(extra_deny)

    _walk_ast(tree, deny_imports, strict)


def is_allowed(
    code: str,
    *,
    strict: bool = True,
    extra_deny: Optional[Set[str]] = None,
) -> tuple[bool, Optional[str]]:
    """
    Check if code is allowed without raising.

    Args:
        code: Python source code to check
        strict: If True, also block dangerous builtins
        extra_deny: Additional module names to block

    Returns:
        (is_safe, reason_if_blocked)
    """
    try:
        check(code, strict=strict, extra_deny=extra_deny)
        return (True, None)
    except CodeSafetyError as e:
        return (False, e.reason)


def _walk_ast(
    tree: ast.AST,
    deny_imports: Set[str],
    strict: bool,
) -> None:
    """
    Recursively walk AST nodes and check for violations.
    """
    for node in ast.walk(tree):
        # Check for dangerous imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_name = alias.name.split(".")[0]  # Get top-level module
                if module_name in deny_imports:
                    raise CodeSafetyError(
                        f"Import blocked: {module_name}",
                        f"Import({module_name})",
                    )

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                module_name = node.module.split(".")[0]
                if module_name in deny_imports:
                    raise CodeSafetyError(
                        f"Import blocked: {node.module}",
                        f"ImportFrom({node.module})",
                    )

        # Check for dangerous names in strict mode
        elif strict and isinstance(node, ast.Name):
            if node.id in DENY_NAMES:
                raise CodeSafetyError(
                    f"Name blocked: {node.id}",
                    f"Name({node.id})",
                )

        # Check for __builtins__ or __class__ access (privilege escalation)
        elif isinstance(node, ast.Attribute):
            if node.attr in ("__builtins__", "__class__", "__subclasses__", "__bases__"):
                raise CodeSafetyError(
                    f"Attribute access blocked: {node.attr}",
                    f"Attribute({node.attr})",
                )

        # Check for getattr calls that might access __class__
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "getattr":
                if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                    attr_name = node.args[1].value
                    if isinstance(attr_name, str) and attr_name.startswith("__"):
                        raise CodeSafetyError(
                            f"getattr access blocked: {attr_name}",
                            f"Call(getattr(..., {attr_name}))",
                        )


if __name__ == "__main__":
    # Test cases
    test_cases = [
        ("print('hello')", True, "plain print"),
        ("x = 1 + 2", True, "arithmetic"),
        ("import os", False, "os import blocked"),
        ("from subprocess import run", False, "subprocess import blocked"),
        ("eval('1+1')", False, "eval blocked in strict mode"),
        ("exec('x=1')", False, "exec blocked in strict mode"),
        ("obj.__class__", False, "__class__ access blocked"),
        ("getattr(x, '__bases__')", False, "getattr __bases__ blocked"),
        ("open('/etc/passwd')", False, "open blocked in strict mode"),
        ("def safe(): return 42", True, "function definition safe"),
    ]

    print("Running safety checks...")
    for code, should_pass, description in test_cases:
        ok, reason = is_allowed(code, strict=True)
        status = "PASS" if ok == should_pass else "FAIL"
        print(f"  [{status}] {description}: {code[:40]}")
        if reason:
            print(f"        Reason: {reason}")
    print("Done.")
