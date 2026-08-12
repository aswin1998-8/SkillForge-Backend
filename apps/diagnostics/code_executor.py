"""Process-level code execution for coding diagnostic questions.

Security note: this is suitable for authenticated MVP users only.
Upgrade to Docker/Judge0 for untrusted public input.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import tempfile
import textwrap
import time
from pathlib import Path

from django.conf import settings

PYTHON_BLOCKED_MODULES = {
    "os",
    "subprocess",
    "socket",
    "shutil",
    "sys",
    "importlib",
    "builtins",
    "pty",
    "fcntl",
    "resource",
    "signal",
    "multiprocessing",
    "threading",
    "ctypes",
    "pickle",
    "code",
    "codeop",
    "compile",
}

JS_BLOCKED_IDENTIFIERS = {
    "require",
    "process",
    "child_process",
    "fs",
    "net",
    "http",
    "https",
    "vm",
    "cluster",
    "worker_threads",
    "eval",
    "Function",
}


class CodeSecurityError(ValueError):
    pass


def _validate_python_source(source: str) -> None:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise CodeSecurityError(f"Invalid Python syntax: {exc}") from exc

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in PYTHON_BLOCKED_MODULES:
                    raise CodeSecurityError(f"Blocked import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root = node.module.split(".")[0]
                if root in PYTHON_BLOCKED_MODULES:
                    raise CodeSecurityError(f"Blocked import: {node.module}")


def _validate_javascript_source(source: str) -> None:
    """Reject dangerous JS identifiers without flagging normal keywords.

    Uses case-sensitive whole-identifier matching so ``function solve()`` is
    allowed while ``new Function(...)`` / ``eval(...)`` stay blocked.
    """
    for blocked in JS_BLOCKED_IDENTIFIERS:
        pattern = rf"(?<![A-Za-z0-9_$]){re.escape(blocked)}(?![A-Za-z0-9_$])"
        if re.search(pattern, source):
            raise CodeSecurityError(f"Blocked identifier: {blocked}")


def validate_source(*, code: str, language: str) -> None:
    if language == "python":
        _validate_python_source(code)
    elif language == "javascript":
        _validate_javascript_source(code)
    else:
        raise CodeSecurityError(f"Unsupported language: {language}")


def _truncate_output(value: str, limit: int = 8000) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + "\n... [truncated]"


def _run_subprocess(
    *,
    command: list[str],
    cwd: Path,
    timeout_seconds: float,
) -> tuple[str, str, int, float]:
    start = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        runtime_ms = int((time.monotonic() - start) * 1000)
        stdout = _truncate_output(exc.stdout or "")
        stderr = _truncate_output((exc.stderr or "") + "\nExecution timed out.")
        return stdout, stderr, 124, runtime_ms

    runtime_ms = int((time.monotonic() - start) * 1000)
    return (
        _truncate_output(completed.stdout or ""),
        _truncate_output(completed.stderr or ""),
        completed.returncode,
        runtime_ms,
    )


def _python_harness(code: str, stdin_data: str) -> str:
    return textwrap.dedent(
        f"""
        _stdin_data = {json.dumps(stdin_data)}
        _ns = {{}}
        exec(compile({json.dumps(code)}, "<solution>", "exec"), _ns)
        if "solve" in _ns and callable(_ns["solve"]):
            _result = _ns["solve"](_stdin_data)
            if _result is not None:
                print(_result)
        """
    )


def _javascript_harness(code: str, stdin_data: str) -> str:
    escaped_stdin = json.dumps(stdin_data)
    return textwrap.dedent(
        f"""
        const inputData = {escaped_stdin};
        eval({json.dumps(code)});
        if (typeof solve === "function") {{
          const result = solve(inputData);
          if (result !== undefined && result !== null) {{
            console.log(String(result));
          }}
        }}
        """
    )


def run_single_test(
    *,
    code: str,
    language: str,
    stdin_data: str,
    expected_output: str,
    timeout_seconds: float | None = None,
) -> dict:
    if not getattr(settings, "CODE_EXECUTION_ENABLED", True):
        return {
            "passed": False,
            "stdout": "",
            "stderr": "Code execution is disabled.",
            "runtime_ms": 0,
        }

    timeout = timeout_seconds or getattr(settings, "CODE_EXECUTION_TIMEOUT_SECONDS", 5.0)
    validate_source(code=code, language=language)

    with tempfile.TemporaryDirectory(prefix="sf_exec_") as tmp:
        cwd = Path(tmp)
        if language == "python":
            harness = _python_harness(code, stdin_data)
            script_path = cwd / "solution.py"
            script_path.write_text(harness, encoding="utf-8")
            stdout, stderr, returncode, runtime_ms = _run_subprocess(
                command=["python3", str(script_path)],
                cwd=cwd,
                timeout_seconds=timeout,
            )
        elif language == "javascript":
            harness = _javascript_harness(code, stdin_data)
            script_path = cwd / "solution.js"
            script_path.write_text(harness, encoding="utf-8")
            stdout, stderr, returncode, runtime_ms = _run_subprocess(
                command=["node", str(script_path)],
                cwd=cwd,
                timeout_seconds=timeout,
            )
        else:
            return {
                "passed": False,
                "stdout": "",
                "stderr": f"Unsupported language: {language}",
                "runtime_ms": 0,
            }

    actual = stdout.strip()
    expected = expected_output.strip()
    passed = returncode == 0 and actual == expected
    return {
        "passed": passed,
        "stdout": stdout,
        "stderr": stderr,
        "runtime_ms": runtime_ms,
        "expected_output": expected_output,
        "actual_output": actual,
        "returncode": returncode,
    }


def run_test_cases(*, code: str, language: str, test_cases) -> list[dict]:
    results: list[dict] = []
    for case in test_cases:
        if case.is_hidden:
            visible_passed = all(r.get("passed") for r in results)
            if not visible_passed:
                results.append(
                    {
                        "case_id": case.id,
                        "passed": False,
                        "hidden": True,
                        "skipped": True,
                    }
                )
                continue

        outcome = run_single_test(
            code=code,
            language=language,
            stdin_data=case.input,
            expected_output=case.expected_output,
        )
        outcome["case_id"] = case.id
        outcome["hidden"] = case.is_hidden
        results.append(outcome)

    visible_passed = all(
        r.get("passed") for r in results if not r.get("hidden") and not r.get("skipped")
    )
    if visible_passed:
        for case in test_cases:
            if not case.is_hidden:
                continue
            if any(r.get("case_id") == case.id for r in results):
                continue
            outcome = run_single_test(
                code=code,
                language=language,
                stdin_data=case.input,
                expected_output=case.expected_output,
            )
            outcome["case_id"] = case.id
            outcome["hidden"] = True
            results.append(outcome)

    return results
