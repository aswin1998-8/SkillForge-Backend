from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.roles.models import Role
from apps.users.models import Profile, User


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)

    def validate_first_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("First name is required.")
        return value

    def validate_last_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Last name is required.")
        return value

    def validate(self, attrs):
        email = attrs["email"].lower().strip()
        password = attrs["password"]
        user = User(
            email=email,
            username=email,
            first_name=attrs["first_name"],
            last_name=attrs["last_name"],
        )
        try:
            validate_password(password, user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        attrs["email"] = email
        return attrs


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class GoogleAuthSerializer(serializers.Serializer):
    credential = serializers.CharField()


class VerifyEmailSerializer(serializers.Serializer):
    token = serializers.CharField()


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    token = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        password = attrs["password"]
        token = attrs["token"]
        from apps.users.models import PasswordResetToken

        token_obj = (
            PasswordResetToken.objects.select_related("user").filter(token=token).first()
        )
        user = token_obj.user if token_obj and token_obj.is_valid() else User()
        try:
            validate_password(password, user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        return attrs


class RoleBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ("id", "slug", "name")


class ProfileSerializer(serializers.ModelSerializer):
    target_role = RoleBriefSerializer(read_only=True)
    target_role_id = serializers.PrimaryKeyRelatedField(
        source="target_role",
        queryset=Role.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )
    known_skills = serializers.ListField(
        child=serializers.CharField(max_length=128),
        required=False,
        allow_empty=True,
    )
    target_learn_skills = serializers.ListField(
        child=serializers.CharField(max_length=128),
        required=False,
        allow_empty=True,
    )
    complete_onboarding = serializers.BooleanField(write_only=True, required=False)

    class Meta:
        model = Profile
        fields = (
            "current_role",
            "years_of_experience",
            "technical_goal",
            "target_role",
            "target_role_id",
            "target_role_label",
            "known_skills",
            "target_learn_skills",
            "onboarding_completed",
            "diagnostic_cycle",
            "diagnostic_difficulty_bump",
            "complete_onboarding",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "onboarding_completed",
            "diagnostic_cycle",
            "diagnostic_difficulty_bump",
            "created_at",
            "updated_at",
        )


class UserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "email_verified",
            "is_staff",
            "profile",
            "date_joined",
        )
        read_only_fields = ("email_verified", "is_staff")
