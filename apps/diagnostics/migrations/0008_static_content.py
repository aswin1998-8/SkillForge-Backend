# Generated manually for static content architecture

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def seed_topics(apps, schema_editor):
    FundamentalsTopic = apps.get_model("diagnostics", "FundamentalsTopic")
    FrameworkTopic = apps.get_model("diagnostics", "FrameworkTopic")

    js, _ = FundamentalsTopic.objects.update_or_create(
        language_family="javascript",
        defaults={
            "competency_areas": [
                "closures",
                "async",
                "types",
                "modules",
                "error_handling",
                "testing",
            ]
        },
    )
    py, _ = FundamentalsTopic.objects.update_or_create(
        language_family="python",
        defaults={
            "competency_areas": [
                "data_structures",
                "oop",
                "async",
                "typing",
                "testing",
                "packaging",
            ]
        },
    )
    seeds = [
        ("react", js, ["hooks", "state_management", "rendering", "performance", "testing"]),
        ("nextjs", js, ["routing", "ssr_ssg", "data_fetching", "middleware", "deployment"]),
        ("django", py, ["models_orm", "views_api", "auth", "middleware", "testing"]),
        ("fastapi", py, ["routing", "dependencies", "validation", "async", "testing"]),
    ]
    for name, fundamentals, areas in seeds:
        FrameworkTopic.objects.update_or_create(
            framework_name=name,
            defaults={
                "fundamentals_topic": fundamentals,
                "competency_areas": areas,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("diagnostics", "0007_seed_default_domain_taxonomies"),
        ("challenges", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="FundamentalsTopic",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("language_family", models.CharField(choices=[("javascript", "JavaScript / TypeScript"), ("python", "Python")], max_length=32, unique=True)),
                ("competency_areas", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["language_family"]},
        ),
        migrations.CreateModel(
            name="FrameworkTopic",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("framework_name", models.CharField(choices=[("react", "React"), ("nextjs", "Next.js"), ("django", "Django"), ("fastapi", "FastAPI")], max_length=32, unique=True)),
                ("competency_areas", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("fundamentals_topic", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="frameworks", to="diagnostics.fundamentalstopic")),
            ],
            options={"ordering": ["framework_name"]},
        ),
        migrations.CreateModel(
            name="Question",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("competency_area", models.CharField(max_length=255)),
                ("modality", models.CharField(choices=[("foundational", "Foundational"), ("coding", "Coding"), ("find_issues", "Find issues"), ("scenario", "Scenario"), ("defend", "Defend"), ("diagnose", "Diagnose"), ("architect", "Architect"), ("explain", "Explain"), ("communicate", "Communicate")], max_length=32)),
                ("question_text", models.TextField()),
                ("difficulty_tier", models.PositiveSmallIntegerField(default=1)),
                ("language", models.CharField(blank=True, choices=[("python", "Python"), ("javascript", "JavaScript")], default="", max_length=32)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("framework_topic", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="questions", to="diagnostics.frameworktopic")),
                ("fundamentals_topic", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="questions", to="diagnostics.fundamentalstopic")),
            ],
            options={"ordering": ["difficulty_tier", "id"]},
        ),
        migrations.CreateModel(
            name="CodingTestCase",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("input", models.TextField(blank=True, default="")),
                ("expected_output", models.TextField()),
                ("is_hidden", models.BooleanField(default=False)),
                ("order", models.PositiveSmallIntegerField(default=1)),
                ("question", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="test_cases", to="diagnostics.question")),
            ],
            options={"ordering": ["order", "id"]},
        ),
        migrations.CreateModel(
            name="QuestionChoice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("choice_text", models.TextField()),
                ("is_correct", models.BooleanField(default=False)),
                ("question", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="choices", to="diagnostics.question")),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.CreateModel(
            name="ReferenceAnswer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reference_text", models.TextField()),
                ("rubric_points", models.JSONField(blank=True, default=list)),
                ("question", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="reference_answer", to="diagnostics.question")),
            ],
        ),
        migrations.RemoveField(model_name="diagnosticsession", name="selected_domains"),
        migrations.RemoveField(model_name="diagnosticsession", name="target_taxonomy"),
        migrations.RemoveField(model_name="diagnosticsession", name="current_block"),
        migrations.AddField(
            model_name="diagnosticsession",
            name="selection_log",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="diagnosticsession",
            name="selected_frameworks",
            field=models.ManyToManyField(blank=True, related_name="sessions", to="diagnostics.frameworktopic"),
        ),
        migrations.AlterField(
            model_name="diagnosticsession",
            name="status",
            field=models.CharField(choices=[("AWAITING_ANSWERS", "Awaiting answers"), ("COMPLETED", "Completed"), ("FAILED", "Failed")], default="AWAITING_ANSWERS", max_length=32),
        ),
        migrations.DeleteModel(name="SessionAnswer"),
        migrations.DeleteModel(name="SessionQuestion"),
        migrations.CreateModel(
            name="SessionQuestion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("stage", models.CharField(choices=[("FOUNDATIONAL", "Foundational"), ("SCENARIO", "Scenario"), ("DEBUGGING", "Debugging"), ("CODING", "Coding"), ("FIND_ISSUES", "Find issues")], max_length=32)),
                ("order", models.PositiveIntegerField(default=1)),
                ("competency_area", models.CharField(blank=True, default="", max_length=255)),
                ("status", models.CharField(choices=[("PENDING", "Pending"), ("ASKED", "Asked"), ("ANSWERED", "Answered"), ("REVEALED", "Revealed"), ("SELF_RATED", "Self rated")], default="ASKED", max_length=32)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("content_question", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="session_instances", to="diagnostics.question")),
                ("session", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="questions", to="diagnostics.diagnosticsession")),
            ],
            options={"ordering": ["order", "id"], "unique_together": {("session", "stage", "order")}},
        ),
        migrations.CreateModel(
            name="SessionAnswer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("answer_text", models.TextField(blank=True, default="")),
                ("choice_id", models.PositiveIntegerField(blank=True, null=True)),
                ("is_correct", models.BooleanField(blank=True, null=True)),
                ("confidence_rating", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("self_rated_alignment", models.JSONField(blank=True, null=True)),
                ("grading_detail", models.JSONField(blank=True, default=dict)),
                ("submitted_at", models.DateTimeField(auto_now_add=True)),
                ("revealed_at", models.DateTimeField(blank=True, null=True)),
                ("self_rated_at", models.DateTimeField(blank=True, null=True)),
                ("question", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="answer", to="diagnostics.sessionquestion")),
            ],
        ),
        migrations.DeleteModel(name="DiagnosticAnswer"),
        migrations.DeleteModel(name="DiagnosticResult"),
        migrations.DeleteModel(name="SkillEvidence"),
        migrations.DeleteModel(name="DiagnosticTurn"),
        migrations.DeleteModel(name="DiagnosticAttempt"),
        migrations.DeleteModel(name="DiagnosticQuestion"),
        migrations.DeleteModel(name="Diagnostic"),
        migrations.DeleteModel(name="DomainTaxonomy"),
        migrations.DeleteModel(name="RoleTaxonomy"),
        migrations.RunPython(seed_topics, migrations.RunPython.noop),
    ]
