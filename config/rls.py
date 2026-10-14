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
    """public şemasındaki tüm tablolarda RLS'i açar (policy yok → anon/authenticated hiçbir şey göremez).

    Django `postgres` rolüyle bağlandığı için etkilenmez. Yeni tablo ekleyen her
    migration'dan sonra tekrar çağrılmalı. SQLite'ta (lokal/test) hiçbir şey yapmaz.
    """
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(ENABLE_RLS_SQL)
