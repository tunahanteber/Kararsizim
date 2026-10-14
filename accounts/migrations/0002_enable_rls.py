from django.db import migrations

from config.rls import enable_rls


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("admin", "0003_logentry_add_action_flag_choices"),
        ("sessions", "0001_initial"),
    ]

    operations = [migrations.RunPython(enable_rls, migrations.RunPython.noop)]
