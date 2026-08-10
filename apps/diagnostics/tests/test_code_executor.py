"""Tests for process-level code execution."""

from __future__ import annotations

import pytest

from apps.diagnostics.code_executor import CodeSecurityError, run_single_test, validate_source


def test_validate_python_blocks_os_import() -> None:
    with pytest.raises(CodeSecurityError):
        validate_source(code="import os\nprint(1)", language="python")


def test_run_python_solve() -> None:
    code = "def solve(input):\n    return 'Hello, ' + input + '!'"
    result = run_single_test(
        code=code,
        language="python",
        stdin_data="World",
        expected_output="Hello, World!",
    )
    assert result["passed"] is True
