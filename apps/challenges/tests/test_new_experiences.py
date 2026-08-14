"""Tests for new challenge experiences: AI audit, explain-diff, inherited, war room."""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.challenges.issue_match import grade_planted_issues
from apps.challenges.models import (
    Challenge,
    ChallengeAttempt,
    ChallengeModelAnswer,
    ChallengeRubricItem,
)
from apps.challenges.services import _grade_challenge_submission, submit_challenge
from apps.challenges.war_room import advance_war_room_beat
from apps.users.models import User

PLANTED = [
    {
        "id": "bug-1",
        "file": "checkout.py",
        "start_line": 8,
        "end_line": 9,
        "category": "bug",
        "severity": "high",
    },
    {
        "id": "sec-1",
        "file": "checkout.py",
        "start_line": 5,
        "end_line": 5,
        "category": "security",
        "severity": "high",
    },
]


def test_issue_match_requires_file_overlap_and_category() -> None:
    result = grade_planted_issues(
        planted=PLANTED,
        reported=[
            {
                "file": "checkout.py",
                "start_line": 8,
                "end_line": 10,
                "category": "bug",
                "severity": "high",
            },
            {
                "file": "checkout.py",
                "start_line": 5,
                "end_line": 5,
                "category": "security",
                "severity": "medium",
            },
        ],
    )
    assert result["matched"] == 2
    assert result["is_correct"] is True
    assert result["score"] >= 0.5


def test_issue_match_rejects_wrong_category() -> None:
    result = grade_planted_issues(
        planted=PLANTED,
        reported=[
            {
                "file": "checkout.py",
                "start_line": 8,
                "end_line": 9,
                "category": "style",
                "severity": "high",
            }
        ],
    )
    assert result["matched"] == 0
    assert result["is_correct"] is False


@pytest.mark.django_db
def test_audit_ai_pr_submit_grades_findings() -> None:
    user = User.objects.create_user(email="audit@example.com", password="x")
    challenge = Challenge.objects.create(
        title="Audit",
        slug="audit-ai-test",
        modality=Challenge.Modality.AUDIT_AI_PR,
        workspace_config={"planted_issues": PLANTED, "issue_count": 2},
    )
    ChallengeModelAnswer.objects.create(challenge=challenge, reference_text="find issues")
    attempt = submit_challenge(
        user=user,
        challenge_id=challenge.id,
        payload={
            "metadata": {
                "findings": [
                    {
                        "file": "checkout.py",
                        "start_line": 8,
                        "end_line": 9,
                        "category": "bug",
                        "severity": "high",
                    },
                    {
                        "file": "checkout.py",
                        "start_line": 5,
                        "end_line": 5,
                        "category": "security",
                        "severity": "high",
                    },
                ]
            }
        },
    )
    assert attempt.status == ChallengeAttempt.Status.COMPLETED
    grading = attempt.submission.metadata["grading"]
    assert grading["method"] == "issue_location_match"
    assert grading["matched"] == 2


@pytest.mark.django_db
def test_explain_ai_diff_uses_keyword_rubric() -> None:
    user = User.objects.create_user(email="diff@example.com", password="x")
    challenge = Challenge.objects.create(
        title="Explain diff",
        slug="explain-ai-diff-test",
        modality=Challenge.Modality.EXPLAIN_AI_DIFF,
        workspace_config={"before": "a", "after": "b"},
    )
    ChallengeModelAnswer.objects.create(
        challenge=challenge,
        reference_text="useMemo omitted query from the dependency array",
    )
    ChallengeRubricItem.objects.create(
        challenge=challenge,
        text="Calls out query missing from the dependency array",
        order=1,
        strength_fragment="caught stale query",
        gap_fragment="missed dep",
    )
    detail = _grade_challenge_submission(
        challenge=challenge,
        text_answer="useMemo omitted query from the dependency array so results go stale",
        code="",
        architecture_data={},
        research_data={},
    )
    assert detail["method"] in {"keyword_rubric", "keyword_reference_overlap"}
    assert detail["score"] > 0


@pytest.mark.django_db
def test_inherited_codebase_runs_constraint_tests() -> None:
    user = User.objects.create_user(email="inherit@example.com", password="x")
    files = {
        "pricing.py": (
            "def line_total(cents, qty, exempt=False, discount_pct=0):\n"
            "    subtotal = int(cents) * int(qty)\n"
            "    discounted = int(subtotal * (100 - int(discount_pct)) / 100)\n"
            "    if exempt:\n"
            "        return discounted\n"
            "    return discounted + discounted // 10\n"
        ),
        "cart.py": (
            "import json\n"
            "def solve(raw):\n"
            "    data = json.loads(raw)\n"
            "    discount = int(data.get('discount_pct') or 0)\n"
            "    total = 0\n"
            "    for item in data.get('items') or []:\n"
            "        total += line_total(item.get('cents') or 0, item.get('qty') or 1, bool(item.get('exempt')), discount)\n"
            "    return total\n"
        ),
    }
    challenge = Challenge.objects.create(
        title="Inherited cart",
        slug="inherited-cart-test",
        modality=Challenge.Modality.INHERITED_CODEBASE,
        workspace_config={
            "language": "python",
            "files": files,
            "test_cases": [
                {
                    "id": 0,
                    "order": 0,
                    "is_hidden": False,
                    "input": '{"items":[{"cents":1000,"qty":1,"exempt":false}],"discount_pct":0}',
                    "expected_output": "1100",
                },
                {
                    "id": 1,
                    "order": 1,
                    "is_hidden": True,
                    "input": '{"items":[{"cents":1000,"qty":1,"exempt":true}],"discount_pct":10}',
                    "expected_output": "900",
                },
            ],
        },
    )
    ChallengeModelAnswer.objects.create(challenge=challenge, reference_text="discount before tax")
    attempt = submit_challenge(
        user=user,
        challenge_id=challenge.id,
        payload={"metadata": {"files": files}, "code": ""},
    )
    assert attempt.status == ChallengeAttempt.Status.COMPLETED


@pytest.mark.django_db
def test_war_room_cannot_skip_beats() -> None:
    user = User.objects.create_user(email="war@example.com", password="x")
    challenge = Challenge.objects.create(
        title="War room",
        slug="war-room-test",
        modality=Challenge.Modality.WAR_ROOM,
        workspace_config={
            "beats": [
                {"id": "logs", "type": "logs", "content": "stack", "prompt": "diagnose"},
                {"id": "slack", "type": "slack", "content": "eta?", "prompt": "reply"},
            ]
        },
    )
    ChallengeModelAnswer.objects.create(challenge=challenge, reference_text="None rate")
    ChallengeRubricItem.objects.create(
        challenge=challenge, text="Identifies None tax rate", order=1
    )
    api = APIClient()
    api.force_authenticate(user=user)
    skipped = api.post(
        f"/api/v1/challenges/{challenge.id}/beats/",
        {"beat_id": "slack", "text": "soon"},
        format="json",
    )
    assert skipped.status_code == 400
    first = advance_war_room_beat(
        user=user,
        challenge_id=challenge.id,
        beat_id="logs",
        text="VAT lookup returned None rate, not Redis",
    )
    assert first["complete"] is False
    assert first["current_index"] == 1
    second = advance_war_room_beat(
        user=user,
        challenge_id=challenge.id,
        beat_id="slack",
        text="ETA 20m, impact checkout 500s, next update in 10m",
    )
    assert second["complete"] is True
    attempt = submit_challenge(
        user=user,
        challenge_id=challenge.id,
        payload={
            "metadata": {
                "war_room": {
                    "complete": True,
                    "answers": second["answers"],
                }
            },
            "text_answer": "VAT lookup None rate. ETA 20m. Guard add_tax and add a test.",
        },
    )
    assert attempt.submission.metadata["grading"]["method"] in {
        "keyword_rubric",
        "keyword_reference_overlap",
    }


@pytest.mark.django_db
def test_challenge_serializer_hides_planted_issues() -> None:
    from apps.challenges.serializers import ChallengeSerializer

    challenge = Challenge.objects.create(
        title="Hidden issues",
        slug="hidden-issues-test",
        modality=Challenge.Modality.AUDIT_AI_PR,
        workspace_config={"planted_issues": PLANTED, "pr": {"title": "x"}},
    )
    data = ChallengeSerializer(challenge).data
    config = data["workspace_config"]
    assert "planted_issues" not in config
    assert config["issue_count"] == 2
