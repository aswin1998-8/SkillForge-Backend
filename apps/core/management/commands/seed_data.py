"""Seed catalog data: roles, skills, frameworks, and sample questions."""

from __future__ import annotations

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.challenges.seed_challenges import (
    deactivate_orphan_challenges,
    seed_sample_challenges,
)
from apps.diagnostics.quick_score import ensure_default_quick_score_content
from apps.diagnostics.roadmap_rebuild import wipe_and_rebuild_all_users
from apps.diagnostics.synthesis_engine import ensure_default_report_content
from apps.diagnostics.topic_defaults import ensure_default_topics
from apps.roles.models import Role, RoleSkill, Skill


SOFTWARE_SKILLS = [
    ("React", "react", "Component architecture and React patterns."),
    ("Next.js", "nextjs", "App Router, SSR, and deployment."),
    ("Django", "django", "ORM, views, and API design."),
    ("FastAPI", "fastapi", "Async APIs, validation, and dependencies."),
    ("TypeScript", "typescript", "Strong typing for frontend applications."),
    ("Python", "python", "Core Python for backend engineering."),
    ("PostgreSQL", "postgresql", "SQL, indexing, and query performance."),
]


class Command(BaseCommand):
    help = "Seed SkillForge roles, skills, frameworks, and sample diagnostic questions."

    @transaction.atomic
    def handle(self, *args, **options) -> None:
        frontend = self._upsert_role(
            name="Frontend Developer",
            slug="frontend-developer",
            description="Builds polished product UIs with React and Next.js.",
        )
        backend = self._upsert_role(
            name="Backend Developer",
            slug="backend-developer",
            description="Builds reliable APIs with Django and FastAPI.",
        )

        skill_objs: dict[str, Skill] = {}
        for name, slug, description in SOFTWARE_SKILLS:
            skill = self._upsert_skill(name=name, slug=slug, description=description)
            skill_objs[slug] = skill

        for slug in ("react", "nextjs", "typescript"):
            RoleSkill.objects.update_or_create(
                role=frontend,
                skill=skill_objs[slug],
                defaults={"importance": 5},
            )
        for slug in ("django", "fastapi", "python", "postgresql"):
            RoleSkill.objects.update_or_create(
                role=backend,
                skill=skill_objs[slug],
                defaults={"importance": 5},
            )

        ensure_default_topics()
        ensure_default_quick_score_content(force=True)
        ensure_default_report_content()
        call_command("import_questions", file="content/sample_questions.json")

        count = seed_sample_challenges(skill_objs=skill_objs)
        orphans = deactivate_orphan_challenges()
        rebuild_results = wipe_and_rebuild_all_users()
        rebuilt = sum(r["rebuilt"] for r in rebuild_results)
        self.stdout.write(
            self.style.SUCCESS(
                f"Seed data loaded ({count} challenges; "
                f"{orphans} orphans deactivated; "
                f"{rebuilt} roadmap items rebuilt)."
            )
        )
    def _upsert_role(self, *, name: str, slug: str, description: str) -> Role:
        role, _ = Role.objects.update_or_create(
            slug=slug,
            defaults={"name": name, "description": description},
        )
        return role

    def _upsert_skill(self, *, name: str, slug: str, description: str) -> Skill:
        skill, _ = Skill.objects.update_or_create(
            slug=slug,
            defaults={"name": name, "description": description},
        )
        return skill
