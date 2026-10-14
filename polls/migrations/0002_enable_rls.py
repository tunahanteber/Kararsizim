from django.db import migrations

from config.rls import enable_rls


class Migration(migrations.Migration):
    dependencies = [("polls", "0001_initial")]

    operations = [migrations.RunPython(enable_rls, migrations.RunPython.noop)]
