from django.contrib import admin

from apps.core.models import InviteToken, WaitlistSignup


@admin.register(WaitlistSignup)
class WaitlistSignupAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "role_or_stack",
        "interest_preview",
        "utm_source",
        "invited",
        "created_at",
    )
    list_filter = ("invited", "utm_source", "utm_medium")
    search_fields = ("email", "role_or_stack", "interest_note")
    readonly_fields = ("created_at", "invited_at")

    @admin.display(description="Interest")
    def interest_preview(self, obj: WaitlistSignup) -> str:
        note = (obj.interest_note or "").strip()
        if len(note) <= 80:
            return note
        return f"{note[:80]}…"


@admin.register(InviteToken)
class InviteTokenAdmin(admin.ModelAdmin):
    list_display = ("email", "status", "expires_at", "used_at", "created_at")
    list_filter = ("used_at",)
    search_fields = ("email",)
    readonly_fields = (
        "waitlist_signup",
        "email",
        "token",
        "expires_at",
        "used_at",
        "created_at",
    )

    @admin.display(description="Status")
    def status(self, obj: InviteToken) -> str:
        if obj.used_at:
            return "used"
        if not obj.is_valid():
            return "expired"
        return "pending"
