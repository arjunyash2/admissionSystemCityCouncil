# Generated by Django 4.2.14 on 2024-07-22 20:27

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0010_remove_application_preference_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="application",
            name="siblings",
        ),
    ]
