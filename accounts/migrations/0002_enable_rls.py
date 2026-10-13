from django.db import migrations

ENABLE_RLS_SQL = """
DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
    EXECUTE 'ALTER TABLE public.' || quote_ident(r.tablename) || ' ENABLE ROW LEVEL SECURITY';
  END LOOP;
END $$;
"""


def enable_rls(apps, schema_editor):
    # Supabase Data API (PostgREST) üzerinden anon/authenticated rollerinin
    # hiçbir şey görmemesi için. Django `postgres` rolüyle bağlandığından etkilenmez.
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(ENABLE_RLS_SQL)


class Migration(migrations.Migration):
    # Yeni tablo ekleyen her faz (ör. polls), bu işlemi tekrarlayan yeni bir migration eklemeli.
    dependencies = [
        ("accounts", "0001_initial"),
        ("admin", "0003_logentry_add_action_flag_choices"),
        ("sessions", "0001_initial"),
    ]

    operations = [migrations.RunPython(enable_rls, migrations.RunPython.noop)]
