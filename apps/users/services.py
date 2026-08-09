"""User authentication and profile services."""

from __future__ import annotations

import secrets
from datetime import timedelta

from django.contrib.auth import authenticate
from django.db import transaction
from django.utils import timezone
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from rest_framework.exceptions import AuthenticationFailed, ValidationError

from apps.users.models import EmailVerificationToken, PasswordResetToken, Profile, User, UserPreference
from apps.users.tasks import dispatch_password_reset_email, dispatch_verification_email


def ensure_user_side_effects(user: User) -> User:
    Profile.objects.get_or_create(user=user)
    UserPreference.objects.get_or_create(user=user)
    return user


def _create_verification_token(user: User) -> EmailVerificationToken:
    EmailVerificationToken.objects.filter(user=user, used_at__isnull=True).update(
        used_at=timezone.now()
    )
    return EmailVerificationToken.objects.create(
        user=user,
        token=secrets.token_urlsafe(32),
        expires_at=timezone.now() + timedelta(hours=24),
    )


def issue_verification_email(user: User) -> EmailVerificationToken:
    token_obj = _create_verification_token(user)
    dispatch_verification_email(user.id, token_obj.token)
    return token_obj


@transaction.atomic
def register_user(*, email: str, password: str, first_name: str = "", last_name: str = "") -> User:
    email = email.lower().strip()
    if User.objects.filter(email=email).exists():
        raise ValidationError({"email": "A user with this email already exists."})
    user = User.objects.create_user(
        email=email,
        password=password,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        email_verified=False,
    )
    user = ensure_user_side_effects(user)
    issue_verification_email(user)
    return user


def login_user(*, email: str, password: str) -> User:
    user = authenticate(username=email.lower().strip(), password=password)
    if user is None:
        raise AuthenticationFailed("Invalid email or password.")
    return ensure_user_side_effects(user)


@transaction.atomic
def login_or_register_google(*, credential: str, client_id: str) -> User:
    if not client_id:
        raise ValidationError({"google": "Google OAuth is not configured."})
    try:
        payload = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            client_id,
        )
    except ValueError as exc:
        raise AuthenticationFailed("Invalid Google credential.") from exc

    email = (payload.get("email") or "").lower().strip()
    sub = payload.get("sub") or ""
    if not email or not sub:
        raise ValidationError({"google": "Google account is missing required claims."})
    if not payload.get("email_verified"):
        raise ValidationError({"google": "Google email is not verified."})

    user = User.objects.filter(google_sub=sub).first()
    if user is None:
        user = User.objects.filter(email=email).first()
        if user is None:
            user = User.objects.create_user(
                email=email,
                password=None,
                first_name=payload.get("given_name") or "",
                last_name=payload.get("family_name") or "",
                google_sub=sub,
                email_verified=True,
            )
            user.set_unusable_password()
            user.save(update_fields=["password"])
        else:
            user.google_sub = sub
            user.email_verified = True
            user.save(update_fields=["google_sub", "email_verified"])
    else:
        if not user.email_verified:
            user.email_verified = True
            user.save(update_fields=["email_verified"])
    return ensure_user_side_effects(user)


@transaction.atomic
def verify_email_token(*, token: str) -> User:
    token_obj = (
        EmailVerificationToken.objects.select_related("user")
        .filter(token=token)
        .first()
    )
    if token_obj is None or not token_obj.is_valid():
        raise ValidationError({"token": "Invalid or expired verification token."})
    user = token_obj.user
    user.email_verified = True
    user.save(update_fields=["email_verified"])
    token_obj.used_at = timezone.now()
    token_obj.save(update_fields=["used_at"])
    EmailVerificationToken.objects.filter(user=user, used_at__isnull=True).exclude(
        pk=token_obj.pk
    ).update(used_at=timezone.now())
    return ensure_user_side_effects(user)


@transaction.atomic
def resend_verification_email(*, user: User) -> None:
    if user.email_verified:
        raise ValidationError({"email": "Email is already verified."})
    issue_verification_email(user)


@transaction.atomic
def request_password_reset(*, email: str) -> None:
    """Always succeed from the caller's perspective (no email enumeration)."""
    email = email.lower().strip()
    user = User.objects.filter(email=email).first()
    if user is None or not user.has_usable_password():
        return
    PasswordResetToken.objects.filter(user=user, used_at__isnull=True).update(
        used_at=timezone.now()
    )
    token_obj = PasswordResetToken.objects.create(
        user=user,
        token=secrets.token_urlsafe(32),
        expires_at=timezone.now() + timedelta(hours=1),
    )
    dispatch_password_reset_email(user.id, token_obj.token)


@transaction.atomic
def reset_password(*, token: str, password: str) -> User:
    token_obj = (
        PasswordResetToken.objects.select_related("user").filter(token=token).first()
    )
    if token_obj is None or not token_obj.is_valid():
        raise ValidationError({"token": "Invalid or expired reset token."})
    user = token_obj.user
    user.set_password(password)
    user.save(update_fields=["password"])
    token_obj.used_at = timezone.now()
    token_obj.save(update_fields=["used_at"])
    PasswordResetToken.objects.filter(user=user, used_at__isnull=True).exclude(
        pk=token_obj.pk
    ).update(used_at=timezone.now())
    return ensure_user_side_effects(user)


@transaction.atomic
def update_profile(user: User, data: dict) -> Profile:
    profile, _ = Profile.objects.get_or_create(user=user)
    for field in (
        "current_role",
        "years_of_experience",
        "technical_goal",
        "target_role",
        "target_role_label",
        "known_skills",
        "target_learn_skills",
    ):
        if field in data:
            setattr(profile, field, data[field])
    if data.get("complete_onboarding") is True:
        has_target = bool(profile.target_role_label) or profile.target_role_id is not None
        if not profile.current_role or not profile.technical_goal or not has_target:
            raise ValidationError(
                "Complete current role, goal, and target role before finishing onboarding."
            )
        profile.onboarding_completed = True
    profile.save()
    return profile
