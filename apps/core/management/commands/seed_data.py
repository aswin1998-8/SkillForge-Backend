"""Seed catalog data: roles, skills, frameworks, and sample questions."""

from __future__ import annotations

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.challenges.models import Challenge, ChallengeSkill
from apps.diagnostics.topic_defaults import ensure_default_topics
from apps.roles.models import Role, RoleSkill, Skill


SOFTWARE_SKILLS = [
    ("React", "react", "Component architecture and React patterns."),
    ("Next.js", "nextjs", "App Router, SSR, and deployment."),
    ("Django", "django", "ORM, views, and API design."),
    ("FastAPI", "fastapi", "Async APIs, validation, and dependencies."),
    ("TypeScript", "typescript", "Strong typing for frontend applications."),
    ("Python", "python", "Core Python for backend engineering."),
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
        for slug in ("django", "fastapi", "python"):
            RoleSkill.objects.update_or_create(
                role=backend,
                skill=skill_objs[slug],
                defaults={"importance": 5},
            )

        ensure_default_topics()
        call_command("import_questions", file="content/sample_questions.json")

        challenges_spec = [
            {
                "title": "Explain React Reconciliation",
                "slug": "explain-react-reconciliation",
                "modality": Challenge.Modality.THEORY,
                "difficulty": 1,
                "skill": "react",
                "scenario": "A junior asks why React needs keys in lists.",
                "requirements": ["Explain reconciliation", "Explain key purpose"],
            },
            {
                "title": "Implement Pagination Helper",
                "slug": "implement-pagination-helper",
                "modality": Challenge.Modality.CODING,
                "difficulty": 2,
                "skill": "django",
                "scenario": "Write a helper to paginate queryset results.",
                "requirements": ["Accept page + page_size", "Return slice metadata"],
            },
        ]
        for spec in challenges_spec:
            challenge, _ = Challenge.objects.update_or_create(
                slug=spec["slug"],
                defaults={
                    "title": spec["title"],
                    "description": spec["scenario"],
                    "modality": spec["modality"],
                    "difficulty": spec["difficulty"],
                    "scenario": spec["scenario"],
                    "requirements": spec["requirements"],
                    "is_active": True,
                },
            )
            ChallengeSkill.objects.update_or_create(
                challenge=challenge,
                skill=skill_objs[spec["skill"]],
            )

        self.stdout.write(self.style.SUCCESS("Seed data loaded."))

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
