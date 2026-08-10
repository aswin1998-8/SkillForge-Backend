"""Bulk import static diagnostic questions from JSON."""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.diagnostics.models import (
    CodingTestCase,
    FrameworkTopic,
    FundamentalsTopic,
    Question,
    QuestionChoice,
    ReferenceAnswer,
)
from apps.diagnostics.topic_defaults import ensure_default_topics

OPEN_ENDED = {
    Question.Modality.SCENARIO,
    Question.Modality.DEFEND,
    Question.Modality.DIAGNOSE,
    Question.Modality.ARCHITECT,
    Question.Modality.EXPLAIN,
    Question.Modality.COMMUNICATE,
}


class Command(BaseCommand):
    help = "Import static diagnostic questions from a JSON file."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--file", required=True, help="Path to JSON import file")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate without writing to the database",
        )

    @transaction.atomic
    def handle(self, *args, **options) -> None:
        path = Path(options["file"])
        if not path.exists():
            raise CommandError(f"File not found: {path}")

        payload = json.loads(path.read_text(encoding="utf-8"))
        questions = payload.get("questions")
        if not isinstance(questions, list) or not questions:
            raise CommandError("JSON must contain a non-empty 'questions' array.")

        ensure_default_topics()
        created = 0
        updated = 0

        for idx, item in enumerate(questions, start=1):
            self._validate_item(item, idx)
            question, was_created = self._upsert_question(item)
            if was_created:
                created += 1
            else:
                updated += 1

        if options["dry_run"]:
            transaction.set_rollback(True)
            self.stdout.write(self.style.WARNING("Dry run — no changes committed."))

        self.stdout.write(
            self.style.SUCCESS(
                f"Import complete: {created} created, {updated} updated."
            )
        )

    def _validate_item(self, item: dict, index: int) -> None:
        required = {"modality", "competency_area", "difficulty_tier", "question_text"}
        missing = required - set(item.keys())
        if missing:
            raise CommandError(f"Question #{index} missing fields: {sorted(missing)}")

        has_framework = bool(item.get("framework"))
        has_fundamentals = bool(item.get("fundamentals"))
        if has_framework == has_fundamentals:
            raise CommandError(
                f"Question #{index} must specify exactly one of 'framework' or 'fundamentals'."
            )

        modality = item["modality"]
        if modality == Question.Modality.FOUNDATIONAL and not item.get("choices"):
            raise CommandError(f"Question #{index} foundational requires 'choices'.")
        if modality in {Question.Modality.CODING, Question.Modality.FIND_ISSUES}:
            if not item.get("test_cases"):
                raise CommandError(f"Question #{index} coding requires 'test_cases'.")
            if not item.get("language"):
                raise CommandError(f"Question #{index} coding requires 'language'.")
        if modality in OPEN_ENDED and not item.get("reference_answer"):
            raise CommandError(
                f"Question #{index} open-ended requires 'reference_answer'."
            )

    def _upsert_question(self, item: dict) -> tuple[Question, bool]:
        framework_topic = None
        fundamentals_topic = None

        if item.get("framework"):
            framework_topic = FrameworkTopic.objects.get(
                framework_name=str(item["framework"]).strip().lower()
            )
            topic_areas = framework_topic.clean_competency_areas()
        else:
            fundamentals_topic = FundamentalsTopic.objects.get(
                language_family=str(item["fundamentals"]).strip().lower()
            )
            topic_areas = fundamentals_topic.clean_competency_areas()

        area = str(item["competency_area"]).strip()
        if area not in topic_areas:
            raise CommandError(
                f"competency_area '{area}' not in topic areas: {topic_areas}"
            )

        lookup = {
            "modality": item["modality"],
            "competency_area": area,
            "framework_topic": framework_topic,
            "fundamentals_topic": fundamentals_topic,
        }

        existing = Question.objects.filter(**lookup, question_text=item["question_text"]).first()
        defaults = {
            "question_text": item["question_text"],
            "difficulty_tier": int(item["difficulty_tier"]),
            "language": item.get("language") or "",
            "is_active": item.get("is_active", True),
        }

        if existing:
            for key, value in defaults.items():
                setattr(existing, key, value)
            existing.save()
            question = existing
            was_created = False
            QuestionChoice.objects.filter(question=question).delete()
            CodingTestCase.objects.filter(question=question).delete()
            ReferenceAnswer.objects.filter(question=question).delete()
        else:
            question = Question.objects.create(**lookup, **defaults)
            was_created = True

        for choice in item.get("choices") or []:
            QuestionChoice.objects.create(
                question=question,
                choice_text=choice["text"],
                is_correct=bool(choice.get("is_correct")),
            )

        for order, case in enumerate(item.get("test_cases") or [], start=1):
            CodingTestCase.objects.create(
                question=question,
                input=case.get("input") or "",
                expected_output=case["expected_output"],
                is_hidden=bool(case.get("is_hidden")),
                order=case.get("order") or order,
            )

        ref = item.get("reference_answer")
        if ref:
            ReferenceAnswer.objects.create(
                question=question,
                reference_text=ref["text"],
                rubric_points=ref.get("rubric_points") or [],
            )

        return question, was_created
