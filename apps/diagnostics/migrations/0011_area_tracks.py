from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("diagnostics", "0010_diagnostic_cycle_difficulty_bump"),
    ]

    operations = [
        migrations.AddField(
            model_name="diagnosticsession",
            name="area_tracks",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
