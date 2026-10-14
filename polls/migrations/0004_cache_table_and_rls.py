from django.core.management import call_command
from django.db import migrations

from config.rls import enable_rls


def create_cache_table(apps, schema_editor):
    # DatabaseCache tablosu (rate limit). Zaten varsa createcachetable atlar.
    call_command("createcachetable", "django_cache", database=schema_editor.connection.alias, verbosity=0)


class Migration(migrations.Migration):
    dependencies = [("polls", "0003_poll_closed_report")]

    operations = [
        migrations.RunPython(create_cache_table, migrations.RunPython.noop),
        migrations.RunPython(enable_rls, migrations.RunPython.noop),  # Report + cache tablosu dahil
    ]
