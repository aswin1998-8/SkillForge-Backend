"""Wipe roadmap items, deactivate orphan AI challenges, rebuild from latest diagnostics."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.challenges.seed_challenges import deactivate_orphan_challenges
from apps.diagnostics.roadmap_rebuild import (
    wipe_and_rebuild_all_users,
    wipe_and_rebuild_user_roadmap,
)
from apps.users.models import User


class Command(BaseCommand):
    help = (
        "Deactivate leftover AI challenges (optional), wipe DiagnosticRoadmapItem rows, "
        "and rebuild from each user's latest completed diagnostic."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--deactivate-orphans",
            action="store_true",
            help="Deactivate challenges not in the current FE/BE allowlist.",
        )
        parser.add_argument(
            "--user-email",
            type=str,
            default="",
            help="Limit wipe+rebuild to a single user email.",
        )

    def handle(self, *args, **options) -> None:
        if options["deactivate_orphans"]:
            n = deactivate_orphan_challenges()
            self.stdout.write(self.style.WARNING(f"Deactivated {n} orphan challenge(s)."))

        email = (options.get("user_email") or "").strip()
        if email:
            try:
                user = User.objects.get(email__iexact=email)
            except User.DoesNotExist as exc:
                raise CommandError(f"No user with email {email}") from exc
            result = wipe_and_rebuild_user_roadmap(user=user)
            self.stdout.write(
                self.style.SUCCESS(
                    f"User {email}: deleted={result['deleted']} "
                    f"rebuilt={result['rebuilt']} session_id={result['session_id']}"
                )
            )
            return

        results = wipe_and_rebuild_all_users()
        rebuilt_users = sum(1 for r in results if r["rebuilt"] > 0)
        total_items = sum(r["rebuilt"] for r in results)
        self.stdout.write(
            self.style.SUCCESS(
                f"Processed {len(results)} user(s); "
                f"{rebuilt_users} rebuilt ({total_items} roadmap items)."
            )
        )
