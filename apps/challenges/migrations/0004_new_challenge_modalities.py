from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("challenges", "0003_v3_core_loop"),
    ]

    operations = [
        migrations.AlterField(
            model_name="challenge",
            name="modality",
            field=models.CharField(
                choices=[
                    ("THEORY", "Theory"),
                    ("CODING", "Coding"),
                    ("RESEARCH", "Research"),
                    ("DEFEND", "Defend"),
                    ("DIAGNOSE", "Diagnose"),
                    ("ARCHITECT", "Architect"),
                    ("EXPLAIN_CODE", "Explain code"),
                    ("USE_AI", "Use AI without skill atrophy"),
                    ("COMMUNICATE", "Communicate"),
                    ("AUDIT_AI_PR", "Audit the AI PR"),
                    ("EXPLAIN_AI_DIFF", "Explain AI diff"),
                    ("INHERITED_CODEBASE", "Inherited codebase"),
                    ("WAR_ROOM", "War room"),
                ],
                max_length=32,
            ),
        ),
    ]
