from django.db import models
from django.utils import timezone


class WaitlistSignup(models.Model):
    email = models.EmailField()
    role_or_stack = models.CharField(max_length=255, blank=True)
    interest_note = models.TextField(blank=True)
    utm_source = models.CharField(max_length=100, blank=True)
    utm_medium = models.CharField(max_length=100, blank=True)
    utm_campaign = models.CharField(max_length=100, blank=True)
    invited = models.BooleanField(default=False)
    invited_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.email


class InviteToken(models.Model):
    waitlist_signup = models.ForeignKey(
        WaitlistSignup,
        on_delete=models.CASCADE,
        related_name="invite_tokens",
    )
    email = models.EmailField(db_index=True)
    token = models.CharField(max_length=64, unique=True, db_index=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def is_valid(self) -> bool:
        return self.used_at is None and self.expires_at > timezone.now()

    def __str__(self) -> str:
        return f"InviteToken<{self.email}>"
