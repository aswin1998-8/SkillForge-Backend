"""Coding challenge test-execution grading and run-tests API."""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.challenges.models import Challenge, ChallengeAttempt, ChallengeModelAnswer
from apps.challenges.services import (
    _grade_challenge_submission,
    run_challenge_tests_preview,
    submit_challenge,
)
from apps.diagnostics.code_executor import run_single_test
from apps.users.models import User

PAGINATION_CASES = [
    {
        "id": 0,
        "order": 0,
        "is_hidden": False,
        "input": '{"items":[1,2,3,4,5],"page":1,"page_size":2}',
        "expected_output": '{"items":[1,2],"page":1,"page_size":2,"total":5,"pages":3}',
    },
    {
        "id": 1,
        "order": 1,
        "is_hidden": False,
        "input": '{"items":[1,2,3,4,5],"page":2,"page_size":2}',
        "expected_output": '{"items":[3,4],"page":2,"page_size":2,"total":5,"pages":3}',
    },
    {
        "id": 2,
        "order": 2,
        "is_hidden": True,
        "input": '{"items":[],"page":1,"page_size":10}',
        "expected_output": '{"items":[],"page":1,"page_size":10,"total":0,"pages":0}',
    },
]

CORRECT_PAGINATION = '''
import json
import math

def solve(input):
    data = json.loads(input)
    items = data.get("items") or []
    page = max(1, int(data.get("page") or 1))
    page_size = max(1, int(data.get("page_size") or 10))
    total = len(items)
    pages = math.ceil(total / page_size) if total else 0
    offset = (page - 1) * page_size
    sliced = items[offset:offset + page_size]
    return json.dumps({
        "items": sliced,
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": pages,
    }, separators=(",", ":"))
'''

WRONG_PAGINATION = '''
import json

def solve(input):
    return json.dumps({"items":[],"page":1,"page_size":10,"total":0,"pages":0}, separators=(",", ":"))
'''


@pytest.mark.django_db
def test_coding_grade_requires_test_cases() -> None:
    challenge = Challenge.objects.create(
        title="No cases",
        slug="coding-no-cases",
        modality=Challenge.Modality.CODING,
        difficulty=1,
        workspace_config={"language": "python"},
    )
    detail = _grade_challenge_submission(
        challenge=challenge,
        text_answer="",
        code=CORRECT_PAGINATION,
        architecture_data={},
        research_data={},
    )
    assert detail["method"] == "test_execution"
    assert detail["is_correct"] is False
    assert detail["error"] == "no_test_cases_configured"


@pytest.mark.django_db
def test_coding_grade_passes_when_all_tests_pass() -> None:
    challenge = Challenge.objects.create(
        title="Pagination",
        slug="coding-pagination-pass",
        modality=Challenge.Modality.CODING,
        difficulty=1,
        workspace_config={"language": "python", "test_cases": PAGINATION_CASES},
    )
    detail = _grade_challenge_submission(
        challenge=challenge,
        text_answer="",
        code=CORRECT_PAGINATION,
        architecture_data={},
        research_data={},
    )
    assert detail["method"] == "test_execution"
    assert detail["is_correct"] is True
    assert detail["score"] == 1.0


@pytest.mark.django_db
def test_coding_grade_fails_when_any_test_fails() -> None:
    challenge = Challenge.objects.create(
        title="Pagination fail",
        slug="coding-pagination-fail",
        modality=Challenge.Modality.CODING,
        difficulty=1,
        workspace_config={"language": "python", "test_cases": PAGINATION_CASES},
    )
    detail = _grade_challenge_submission(
        challenge=challenge,
        text_answer="",
        code=WRONG_PAGINATION,
        architecture_data={},
        research_data={},
    )
    assert detail["is_correct"] is False
    assert detail["score"] == 0.0


@pytest.mark.django_db
def test_run_tests_preview_visible_only() -> None:
    user = User.objects.create_user(email="runtests@example.com", password="x")
    challenge = Challenge.objects.create(
        title="Pagination run",
        slug="coding-pagination-run",
        modality=Challenge.Modality.CODING,
        difficulty=1,
        workspace_config={"language": "python", "test_cases": PAGINATION_CASES},
    )
    payload = run_challenge_tests_preview(
        user=user,
        challenge_id=challenge.id,
        code=CORRECT_PAGINATION,
    )
    assert payload["passed_visible"] is True
    assert len(payload["test_results"]) == 2
    assert all(not r["hidden"] for r in payload["test_results"])
    assert payload["test_results"][0]["input"]
    assert payload["test_results"][0]["expected_output"]


@pytest.mark.django_db
def test_challenge_detail_exposes_visible_examples_only() -> None:
    user = User.objects.create_user(email="examples@example.com", password="x")
    api = APIClient()
    api.force_authenticate(user=user)
    challenge = Challenge.objects.create(
        title="Pagination examples",
        slug="coding-pagination-examples",
        modality=Challenge.Modality.CODING,
        difficulty=1,
        workspace_config={"language": "python", "test_cases": PAGINATION_CASES},
    )
    res = api.get(f"/api/v1/challenges/{challenge.id}/")
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    config = data["workspace_config"]
    cases = config["test_cases"]
    assert len(cases) == 2
    assert config["hidden_test_count"] == 1
    assert all(not c.get("is_hidden") for c in cases)
    assert cases[0]["input"]
    assert cases[0]["expected_output"]
    assert "items" in cases[0]["expected_output"]


@pytest.mark.django_db
def test_run_tests_api() -> None:
    user = User.objects.create_user(email="runapi@example.com", password="x")
    api = APIClient()
    api.force_authenticate(user=user)
    challenge = Challenge.objects.create(
        title="Pagination api",
        slug="coding-pagination-api",
        modality=Challenge.Modality.CODING,
        difficulty=1,
        workspace_config={"language": "python", "test_cases": PAGINATION_CASES},
    )
    res = api.post(
        f"/api/v1/challenges/{challenge.id}/run-tests/",
        {"code": CORRECT_PAGINATION},
        format="json",
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["passed_visible"] is True
    assert len(data["test_results"]) == 2


@pytest.mark.django_db
def test_submit_coding_challenge_completes_on_pass() -> None:
    user = User.objects.create_user(email="codepass@example.com", password="x")
    challenge = Challenge.objects.create(
        title="Pagination submit",
        slug="coding-pagination-submit",
        modality=Challenge.Modality.CODING,
        difficulty=1,
        workspace_config={"language": "python", "test_cases": PAGINATION_CASES},
    )
    ChallengeModelAnswer.objects.create(challenge=challenge, reference_text="paginate")
    attempt = submit_challenge(
        user=user,
        challenge_id=challenge.id,
        payload={"code": CORRECT_PAGINATION},
    )
    assert attempt.status == ChallengeAttempt.Status.COMPLETED
    grading = attempt.submission.metadata["grading"]
    assert grading["is_correct"] is True


def test_chunk_array_fixture_smoke() -> None:
    code = """
function solve(input) {
  const data = JSON.parse(input);
  const arr = data.array || [];
  const size = Number(data.size);
  const out = [];
  for (let i = 0; i < arr.length; i += size) {
    out.push(arr.slice(i, i + size));
  }
  return JSON.stringify(out);
}
"""
    result = run_single_test(
        code=code,
        language="javascript",
        stdin_data='{"array":[1,2,3,4,5],"size":2}',
        expected_output="[[1,2],[3,4],[5]]",
    )
    assert result["passed"] is True


def test_pagination_fixture_smoke() -> None:
    result = run_single_test(
        code=CORRECT_PAGINATION,
        language="python",
        stdin_data='{"items":[1,2,3,4,5],"page":1,"page_size":2}',
        expected_output='{"items":[1,2],"page":1,"page_size":2,"total":5,"pages":3}',
    )
    assert result["passed"] is True


def test_typescript_react_classnames_smoke() -> None:
    code = """
type Token = string | false | null | undefined;

function solve(input: string): string {
  const tokens = JSON.parse(input) as Token[];
  return tokens
    .filter((t) => typeof t === "string" && t.length > 0)
    .join(" ");
}
"""
    result = run_single_test(
        code=code,
        language="typescript",
        stdin_data='["btn","btn-primary",false,null,"active"]',
        expected_output="btn btn-primary active",
    )
    assert result["passed"] is True, result


def test_nextjs_search_params_smoke() -> None:
    code = """
type ParamValue = string | string[] | null;

function solve(input: string): string {
  const data = JSON.parse(input) as { params: Record<string, ParamValue> };
  const params = data.params || {};
  const parts: string[] = [];
  for (const key of Object.keys(params).sort()) {
    const value = params[key];
    if (value == null || value === "") continue;
    if (Array.isArray(value)) {
      for (const item of value) {
        if (item == null || item === "") continue;
        parts.push(key + "=" + item);
      }
    } else {
      parts.push(key + "=" + value);
    }
  }
  return parts.join("&");
}
"""
    result = run_single_test(
        code=code,
        language="typescript",
        stdin_data='{"params":{"tag":["a","b"],"q":"x"}}',
        expected_output="q=x&tag=a&tag=b",
    )
    assert result["passed"] is True, result


def test_django_query_filter_smoke() -> None:
    code = """
import json

def solve(input):
    data = json.loads(input)
    allowed = set(data.get("allowed_fields") or [])
    query = data.get("query") or {}
    out = {}
    for key, value in query.items():
        if key not in allowed:
            continue
        if value is None or value == "":
            continue
        if key == "search":
            out["name__icontains"] = value
        else:
            out[key] = value
    return json.dumps(out, separators=(",", ":"))
"""
    result = run_single_test(
        code=code,
        language="python",
        stdin_data='{"allowed_fields":["status","search"],"query":{"search":"hooks","status":""}}',
        expected_output='{"name__icontains":"hooks"}',
    )
    assert result["passed"] is True, result
