"""Seed catalog data: roles, skills, diagnostic, and challenges."""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.challenges.models import Challenge, ChallengeSkill
from apps.diagnostics.models import Diagnostic, DiagnosticQuestion
from apps.roles.models import Role, RoleSkill, Skill


AI_SKILLS = [
    ("RAG", "rag", "Retrieval-augmented generation patterns and evaluation."),
    ("LLM APIs", "llm-apis", "Prompting, tool use, and production LLM API design."),
    ("Agent Architecture", "agent-architecture", "Multi-step agents, planners, and tool routers."),
    ("Evaluation", "evaluation", "Offline/online eval harnesses and quality metrics."),
    ("AI Security", "ai-security", "Prompt injection, data leakage, and safe tool use."),
    ("Observability", "observability", "Tracing, cost, latency, and quality monitoring for AI systems."),
]

FRONTEND_SKILLS = [
    ("React", "react", "Component architecture and React patterns."),
    ("TypeScript", "typescript", "Strong typing for frontend applications."),
    ("CSS Architecture", "css-architecture", "Responsive layout and design systems."),
]


class Command(BaseCommand):
    help = "Seed SkillForge roles, skills, diagnostic, and challenges."

    @transaction.atomic
    def handle(self, *args, **options) -> None:
        frontend = self._upsert_role(
            name="Frontend Developer",
            slug="frontend-developer",
            description="Builds polished product UIs with strong engineering fundamentals.",
        )
        ai_engineer = self._upsert_role(
            name="AI Engineer",
            slug="ai-engineer",
            description="Designs and ships reliable AI-powered systems.",
        )

        ai_skill_objs: dict[str, Skill] = {}
        for name, slug, description in AI_SKILLS:
            skill = self._upsert_skill(name=name, slug=slug, description=description)
            ai_skill_objs[slug] = skill
            RoleSkill.objects.update_or_create(
                role=ai_engineer,
                skill=skill,
                defaults={"importance": 5},
            )

        for idx, (name, slug, description) in enumerate(FRONTEND_SKILLS, start=1):
            skill = self._upsert_skill(name=name, slug=slug, description=description)
            RoleSkill.objects.update_or_create(
                role=frontend,
                skill=skill,
                defaults={"importance": idx},
            )

        diagnostic, _ = Diagnostic.objects.update_or_create(
            title="AI Engineer Baseline Diagnostic",
            defaults={
                "description": "Assesses foundational AI engineering skills across RAG, APIs, agents, eval, and security.",
                "is_active": True,
            },
        )
        questions = [
            (
                1,
                "Describe how you would design a RAG pipeline for an internal knowledge base. What failure modes worry you most?",
                "rag",
                2,
            ),
            (
                2,
                "How do you structure LLM API calls for reliability (retries, timeouts, tool calling, and cost control)?",
                "llm-apis",
                2,
            ),
            (
                3,
                "Sketch an agent architecture for a multi-step research task. Where do you put planning vs execution?",
                "agent-architecture",
                3,
            ),
            (
                4,
                "What evaluation suite would you build before shipping an AI feature to production?",
                "evaluation",
                2,
            ),
            (
                5,
                "List the top AI security risks for a tool-using chatbot and how you would mitigate them.",
                "ai-security",
                3,
            ),
        ]
        for ordering, text, skill_slug, difficulty in questions:
            DiagnosticQuestion.objects.update_or_create(
                diagnostic=diagnostic,
                ordering=ordering,
                defaults={
                    "text": text,
                    "question_type": DiagnosticQuestion.QuestionType.FREE_TEXT,
                    "skill": ai_skill_objs[skill_slug],
                    "difficulty": difficulty,
                },
            )

        challenges_spec = [
            {
                "title": "Explain RAG Chunking Trade-offs",
                "slug": "explain-rag-chunking-tradeoffs",
                "modality": Challenge.Modality.THEORY,
                "difficulty": 1,
                "skill": "rag",
                "scenario": "A teammate proposes fixed 512-token chunks with overlap for all documents.",
                "requirements": ["Explain trade-offs", "Propose a better default"],
            },
            {
                "title": "Implement Retry Wrapper for LLM Calls",
                "slug": "implement-llm-retry-wrapper",
                "modality": Challenge.Modality.CODING,
                "difficulty": 2,
                "skill": "llm-apis",
                "scenario": "Write a resilient wrapper around an LLM client.",
                "requirements": ["Exponential backoff", "Idempotency notes", "Error taxonomy"],
            },
            {
                "title": "Research Agent Memory Strategies",
                "slug": "research-agent-memory-strategies",
                "modality": Challenge.Modality.RESEARCH,
                "difficulty": 2,
                "skill": "agent-architecture",
                "scenario": "Compare short-term vs long-term memory approaches for agents.",
                "requirements": ["Summarize 3 approaches", "Recommend one for a support bot"],
            },
            {
                "title": "Defend Your Eval Harness",
                "slug": "defend-eval-harness",
                "modality": Challenge.Modality.DEFEND,
                "difficulty": 3,
                "skill": "evaluation",
                "scenario": "Stakeholders claim offline evals are unnecessary if users like the demo.",
                "requirements": ["Defend offline evals", "Propose a minimal launch bar"],
            },
            {
                "title": "Diagnose Prompt Injection Incident",
                "slug": "diagnose-prompt-injection-incident",
                "modality": Challenge.Modality.DIAGNOSE,
                "difficulty": 3,
                "skill": "ai-security",
                "scenario": "A tool-using assistant leaked internal notes after a crafted user prompt.",
                "requirements": ["Root-cause analysis", "Containment steps", "Hardening plan"],
            },
            {
                "title": "Architect Observability for AI Features",
                "slug": "architect-ai-observability",
                "modality": Challenge.Modality.ARCHITECT,
                "difficulty": 2,
                "skill": "observability",
                "scenario": "Design tracing and quality signals for an AI support assistant.",
                "requirements": ["Trace model", "Quality metrics", "Alerting thresholds"],
            },
            {
                "title": "Explain This Retrieval Function",
                "slug": "explain-retrieval-function",
                "modality": Challenge.Modality.EXPLAIN_CODE,
                "difficulty": 1,
                "skill": "rag",
                "scenario": "Explain a hybrid retrieval function combining BM25 and embeddings.",
                "requirements": ["Line-by-line intent", "Failure modes"],
            },
            {
                "title": "Use AI to Draft an Eval Rubric",
                "slug": "use-ai-draft-eval-rubric",
                "modality": Challenge.Modality.USE_AI,
                "difficulty": 2,
                "skill": "evaluation",
                "scenario": "Use an AI assistant to draft a rubric, then critique and improve it.",
                "requirements": ["Show prompt", "Critique AI output", "Final rubric"],
            },
            {
                "title": "Communicate an AI Risk to Leadership",
                "slug": "communicate-ai-risk-leadership",
                "modality": Challenge.Modality.COMMUNICATE,
                "difficulty": 2,
                "skill": "ai-security",
                "scenario": "Write a short memo explaining prompt-injection risk without jargon overload.",
                "requirements": ["Executive summary", "Business impact", "Ask"],
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
                    "estimated_duration_minutes": 25 + spec["difficulty"] * 5,
                    "scenario": spec["scenario"],
                    "requirements": spec["requirements"],
                    "constraints": ["No proprietary data", "Keep answer under 800 words unless coding"],
                    "workspace_config": {"editor": "monaco" if spec["modality"] == Challenge.Modality.CODING else "markdown"},
                    "is_active": True,
                },
            )
            ChallengeSkill.objects.update_or_create(
                challenge=challenge,
                skill=ai_skill_objs[spec["skill"]],
            )

        from apps.diagnostics.domain_defaults import ensure_default_domain_taxonomies

        created_domains = ensure_default_domain_taxonomies()
        if created_domains:
            self.stdout.write(f"Created {created_domains} default DomainTaxonomy row(s).")

        self.stdout.write(self.style.SUCCESS("Seed data created/updated successfully."))

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
