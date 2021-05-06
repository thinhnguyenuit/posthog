# Generated by Django 3.1.8 on 2021-05-06 15:43

from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):

    dependencies = [
        ("posthog", "0149_fix_lifecycle_dashboard_items"),
    ]

    operations = [
        migrations.AddField(
            model_name="persondistinctid",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, default=timezone.now),
            preserve_default=False,
        )
    ]
