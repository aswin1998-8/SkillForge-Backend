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
