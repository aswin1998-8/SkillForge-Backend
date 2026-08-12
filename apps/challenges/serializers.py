from __future__ import annotations

from rest_framework import serializers

from apps.challenges.models import (
    Challenge,
    ChallengeAttempt,
    ChallengeSkill,
    ConfidenceRating,
    DailyChallenge,
    Submission,
)
from apps.roles.serializers import SkillSerializer


class ChallengeSkillSerializer(serializers.ModelSerializer):
    skill = SkillSerializer(read_only=True)

    class Meta:
        model = ChallengeSkill
        fields = ("id", "skill")


class ChallengeSerializer(serializers.ModelSerializer):
    skills = ChallengeSkillSerializer(source="challenge_skills", many=True, read_only=True)

    class Meta:
        model = Challenge
        fields = (
            "id",
            "title",
            "slug",
            "description",
            "modality",
            "difficulty",
            "estimated_duration_minutes",
            "scenario",
            "requirements",
            "constraints",
            "workspace_config",
            "directions",
            "is_active",
            "skills",
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # LeetCode-style: visible examples include input + expected; hide secret cases.
        config = dict(data.get("workspace_config") or {})
        raw_cases = config.get("test_cases")
        if isinstance(raw_cases, list):
            public_cases = []
            hidden_count = 0
            for i, case in enumerate(raw_cases):
                if not isinstance(case, dict):
                    continue
                if bool(case.get("is_hidden", False)):
                    hidden_count += 1
                    continue
                public_cases.append(
                    {
                        "id": case.get("id", i),
                        "order": int(case.get("order", i)),
                        "is_hidden": False,
                        "input": str(case.get("input", "")),
                        "expected_output": str(case.get("expected_output", "")),
                    }
                )
            config["test_cases"] = public_cases
            config["hidden_test_count"] = hidden_count
            data["workspace_config"] = config
        return data


class DailyChallengeSerializer(serializers.ModelSerializer):
    challenge = ChallengeSerializer(read_only=True)

    class Meta:
        model = DailyChallenge
        fields = ("id", "date", "status", "challenge", "created_at", "updated_at")


class SubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Submission
        fields = (
            "text_answer",
            "code",
            "architecture_data",
            "research_data",
            "metadata",
            "created_at",
            "updated_at",
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        metadata = dict(data.get("metadata") or {})
        grading = dict(metadata.get("grading") or {})
        results = grading.get("test_results")
        if isinstance(results, list):
            public = []
            hidden_total = 0
            hidden_passed = 0
            for r in results:
                if not isinstance(r, dict):
                    continue
                if r.get("hidden"):
                    hidden_total += 1
                    if r.get("passed") and not r.get("skipped"):
                        hidden_passed += 1
                    continue
                public.append(
                    {
                        "case_id": r.get("case_id"),
                        "passed": bool(r.get("passed")),
                        "hidden": False,
                        "stdout": r.get("stdout") or "",
                        "stderr": r.get("stderr") or "",
                        "actual_output": r.get("actual_output") or "",
                        "expected_output": r.get("expected_output") or "",
                        "runtime_ms": r.get("runtime_ms") or 0,
                    }
                )
            grading["test_results"] = public
            if hidden_total:
                grading["hidden_summary"] = {
                    "total": hidden_total,
                    "passed": hidden_passed,
                }
            metadata["grading"] = grading
            data["metadata"] = metadata
        return data


class ConfidenceRatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfidenceRating
        fields = ("score", "note", "created_at")


class ChallengeAttemptSerializer(serializers.ModelSerializer):
    challenge = ChallengeSerializer(read_only=True)
    submission = SubmissionSerializer(read_only=True)
    confidence = ConfidenceRatingSerializer(read_only=True)
    debrief_id = serializers.SerializerMethodField()

    class Meta:
        model = ChallengeAttempt
        fields = (
            "id",
            "challenge",
            "daily_challenge_id",
            "status",
            "started_at",
            "completed_at",
            "submission",
            "confidence",
            "debrief_id",
        )

    def get_debrief_id(self, obj) -> int | None:
        debrief = getattr(obj, "debrief", None)
        return debrief.id if debrief else None


class ChallengeSubmitSerializer(serializers.Serializer):
    text_answer = serializers.CharField(required=False, allow_blank=True, default="")
    code = serializers.CharField(required=False, allow_blank=True, default="")
    architecture_data = serializers.JSONField(required=False, default=dict)
    research_data = serializers.JSONField(required=False, default=dict)
    metadata = serializers.JSONField(required=False, default=dict)


class ChallengeRunTestsSerializer(serializers.Serializer):
    code = serializers.CharField(required=True, allow_blank=False)


class ConfidenceCreateSerializer(serializers.Serializer):
    score = serializers.IntegerField(min_value=1, max_value=5)
    note = serializers.CharField(required=False, allow_blank=True, default="")


class DebriefChecklistSerializer(serializers.Serializer):
    checklist = serializers.DictField(child=serializers.BooleanField())


class DebriefFollowUpsSerializer(serializers.Serializer):
    follow_up_answers = serializers.DictField(child=serializers.CharField(allow_blank=True))


class AnalyticsEventSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=64)
    properties = serializers.DictField(required=False, default=dict)
