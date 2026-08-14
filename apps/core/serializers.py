from __future__ import annotations

from rest_framework import serializers

from apps.core.models import WaitlistSignup


class WaitlistSignupSerializer(serializers.ModelSerializer):
    class Meta:
        model = WaitlistSignup
        fields = (
            "email",
            "role_or_stack",
            "interest_note",
            "utm_source",
            "utm_medium",
            "utm_campaign",
        )

    def validate_email(self, value: str) -> str:
        return value.lower().strip()
