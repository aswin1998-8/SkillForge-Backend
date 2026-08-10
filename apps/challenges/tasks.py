"""Challenge-related Celery tasks."""

from __future__ import annotations

from celery import shared_task


@shared_task(name="apps.challenges.tasks.ping_challenges")
def ping_challenges() -> str:
    return "challenges-ok"
