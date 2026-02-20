"""Safety checks for generated Manim code before execution."""

from __future__ import annotations

import ast


class UnsafeCodeError(ValueError):
    """Raised when generated code contains blocked operations."""


_DANGEROUS_MODULES = {
    "os",
    "sys",
    "subprocess",
    "shutil",
    "pathlib",
    "socket",
    "requests",
    "urllib",
    "http",
    "ftplib",
    "ctypes",
    "multiprocessing",
    "threading",
    "asyncio",
    "importlib",
    "builtins",
}

_BLOCKED_CALL_NAMES = {
    "exec",
    "eval",
    "compile",
    "open",
    "__import__",
    "input",
    "breakpoint",
}

_BLOCKED_CALL_ROOTS = _DANGEROUS_MODULES | {"__builtins__"}


def _call_root_name(node: ast.AST) -> str | None:
    current = node
    while isinstance(current, ast.Attribute):
        current = current.value
    if isinstance(current, ast.Name):
        return current.id
    return None


def validate_generated_manim_code(code: str) -> None:
    """Validate generated Python code and raise UnsafeCodeError when unsafe."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        line = f" line {exc.lineno}" if exc.lineno else ""
        raise UnsafeCodeError(f"Generated code is not valid Python ({exc.msg}{line}).") from exc

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_name = alias.name.split(".")[0]
                if module_name in _DANGEROUS_MODULES:
                    raise UnsafeCodeError(f"Blocked import detected: '{module_name}'.")

        elif isinstance(node, ast.ImportFrom):
            module_name = (node.module or "").split(".")[0]
            if module_name in _DANGEROUS_MODULES:
                raise UnsafeCodeError(f"Blocked import detected: '{module_name}'.")

        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in _BLOCKED_CALL_NAMES:
                raise UnsafeCodeError(f"Blocked function call detected: '{node.func.id}()'.")

            root_name = _call_root_name(node.func)
            if root_name and root_name in _BLOCKED_CALL_ROOTS:
                raise UnsafeCodeError(f"Blocked call root detected: '{root_name}'.")
