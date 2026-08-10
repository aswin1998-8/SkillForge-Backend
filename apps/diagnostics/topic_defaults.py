"""Seed data for fundamentals and framework topics."""

from __future__ import annotations

from apps.diagnostics.models import FrameworkTopic, FundamentalsTopic

JS_COMPETENCY_AREAS = [
    "closures",
    "async",
    "types",
    "modules",
    "error_handling",
    "testing",
]

PYTHON_COMPETENCY_AREAS = [
    "data_structures",
    "oop",
    "async",
    "typing",
    "testing",
    "packaging",
]

SQL_COMPETENCY_AREAS = [
    "indexing",
    "joins",
    "transactions",
    "query_plans",
    "normalization",
]

REACT_COMPETENCY_AREAS = [
    "hooks",
    "state_management",
    "rendering",
    "performance",
    "testing",
]

NEXTJS_COMPETENCY_AREAS = [
    "routing",
    "ssr_ssg",
    "data_fetching",
    "middleware",
    "deployment",
]

DJANGO_COMPETENCY_AREAS = [
    "models_orm",
    "views_api",
    "auth",
    "middleware",
    "testing",
]

FASTAPI_COMPETENCY_AREAS = [
    "routing",
    "dependencies",
    "validation",
    "async",
    "testing",
]

POSTGRES_COMPETENCY_AREAS = [
    "indexing",
    "joins",
    "transactions",
    "query_plans",
    "constraints",
]

FRAMEWORK_SEEDS = [
    (FrameworkTopic.FrameworkName.REACT, REACT_COMPETENCY_AREAS),
    (FrameworkTopic.FrameworkName.NEXTJS, NEXTJS_COMPETENCY_AREAS),
    (FrameworkTopic.FrameworkName.DJANGO, DJANGO_COMPETENCY_AREAS),
    (FrameworkTopic.FrameworkName.FASTAPI, FASTAPI_COMPETENCY_AREAS),
    (FrameworkTopic.FrameworkName.POSTGRESQL, POSTGRES_COMPETENCY_AREAS),
]

JS_FRAMEWORKS = {
    FrameworkTopic.FrameworkName.REACT,
    FrameworkTopic.FrameworkName.NEXTJS,
}

SQL_FRAMEWORKS = {
    FrameworkTopic.FrameworkName.POSTGRESQL,
}


def ensure_default_topics() -> None:
    js_topic, _ = FundamentalsTopic.objects.update_or_create(
        language_family=FundamentalsTopic.LanguageFamily.JAVASCRIPT,
        defaults={"competency_areas": JS_COMPETENCY_AREAS},
    )
    py_topic, _ = FundamentalsTopic.objects.update_or_create(
        language_family=FundamentalsTopic.LanguageFamily.PYTHON,
        defaults={"competency_areas": PYTHON_COMPETENCY_AREAS},
    )
    sql_topic, _ = FundamentalsTopic.objects.update_or_create(
        language_family=FundamentalsTopic.LanguageFamily.SQL,
        defaults={"competency_areas": SQL_COMPETENCY_AREAS},
    )

    for framework_name, areas in FRAMEWORK_SEEDS:
        if framework_name in JS_FRAMEWORKS:
            fundamentals = js_topic
        elif framework_name in SQL_FRAMEWORKS:
            fundamentals = sql_topic
        else:
            fundamentals = py_topic
        FrameworkTopic.objects.update_or_create(
            framework_name=framework_name,
            defaults={
                "fundamentals_topic": fundamentals,
                "competency_areas": areas,
            },
        )
