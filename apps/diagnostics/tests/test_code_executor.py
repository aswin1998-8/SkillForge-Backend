"""Tests for process-level code execution."""

from __future__ import annotations

import pytest

from apps.diagnostics.code_executor import CodeSecurityError, run_single_test, validate_source


def test_validate_python_blocks_os_import() -> None:
    with pytest.raises(CodeSecurityError):
        validate_source(code="import os\nprint(1)", language="python")


def test_validate_javascript_allows_function_keyword() -> None:
    validate_source(
        code="function solve(input) {\n  return input.map(item => item.name);\n}",
        language="javascript",
    )


def test_validate_javascript_blocks_Function_constructor() -> None:
    with pytest.raises(CodeSecurityError, match="Function"):
        validate_source(code='const f = new Function("return 1")', language="javascript")


def test_validate_javascript_blocks_eval() -> None:
    with pytest.raises(CodeSecurityError, match="eval"):
        validate_source(code='eval("1+1")', language="javascript")


def test_validate_javascript_blocks_require() -> None:
    with pytest.raises(CodeSecurityError, match="require"):
        validate_source(code='const fs = require("fs")', language="javascript")


def test_run_python_solve() -> None:
    code = "def solve(input):\n    return 'Hello, ' + input + '!'"
    result = run_single_test(
        code=code,
        language="python",
        stdin_data="World",
        expected_output="Hello, World!",
    )
    assert result["passed"] is True
