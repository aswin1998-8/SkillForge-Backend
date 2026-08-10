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

FRAMEWORK_SEEDS = [
    (FrameworkTopic.FrameworkName.REACT, REACT_COMPETENCY_AREAS),
    (FrameworkTopic.FrameworkName.NEXTJS, NEXTJS_COMPETENCY_AREAS),
    (FrameworkTopic.FrameworkName.DJANGO, DJANGO_COMPETENCY_AREAS),
    (FrameworkTopic.FrameworkName.FASTAPI, FASTAPI_COMPETENCY_AREAS),
]

JS_FRAMEWORKS = {
    FrameworkTopic.FrameworkName.REACT,
    FrameworkTopic.FrameworkName.NEXTJS,
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

    for framework_name, areas in FRAMEWORK_SEEDS:
        fundamentals = js_topic if framework_name in JS_FRAMEWORKS else py_topic
        FrameworkTopic.objects.update_or_create(
            framework_name=framework_name,
            defaults={
                "fundamentals_topic": fundamentals,
                "competency_areas": areas,
            },
        )
