"""Default DomainTaxonomy catalog matching FE technical-domain card IDs.

Admin can still edit competency_areas later; these are bootstrap defaults so
sharpen_current works without manual Django admin seeding.
"""

from __future__ import annotations

DEFAULT_DOMAIN_TAXONOMIES: list[dict] = [
    {
        "slug": "ai-augmented",
        "domain_name": "AI-Augmented Engineering",
        "competency_areas": [
            "prompt_engineering",
            "llm_api_integration",
            "rag_basics",
            "ai_tooling_workflow",
            "eval_and_guardrails",
        ],
    },
    {
        "slug": "system-design",
        "domain_name": "System Design & Architecture",
        "competency_areas": [
            "service_boundaries",
            "scalability_patterns",
            "data_modeling",
            "caching_and_consistency",
            "api_contract_design",
        ],
    },
    {
        "slug": "reliability",
        "domain_name": "Reliability & Performance",
        "competency_areas": [
            "observability",
            "latency_debugging",
            "failure_modes",
            "capacity_and_load",
            "incident_response",
        ],
    },
    {
        "slug": "communication",
        "domain_name": "Technical Communication",
        "competency_areas": [
            "design_reviews",
            "rfc_writing",
            "stakeholder_explanation",
            "tradeoff_defense",
            "mentoring_and_feedback",
        ],
    },
]

DEFAULT_DOMAIN_BY_SLUG = {row["slug"]: row for row in DEFAULT_DOMAIN_TAXONOMIES}


def ensure_default_domain_taxonomies(*, model=None) -> int:
    """Idempotently create missing default DomainTaxonomy rows. Returns created count."""
    if model is None:
        from apps.diagnostics.models import DomainTaxonomy as model

    created = 0
    for row in DEFAULT_DOMAIN_TAXONOMIES:
        obj, was_created = model.objects.get_or_create(
            slug=row["slug"],
            defaults={
                "domain_name": row["domain_name"],
                "competency_areas": list(row["competency_areas"]),
            },
        )
        if was_created:
            created += 1
        elif not obj.clean_competency_areas():
            obj.competency_areas = list(row["competency_areas"])
            obj.domain_name = obj.domain_name or row["domain_name"]
            obj.save(update_fields=["competency_areas", "domain_name", "updated_at"])
    return created
