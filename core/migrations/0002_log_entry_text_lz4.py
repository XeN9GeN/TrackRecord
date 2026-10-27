from django.db import migrations


class Migration(migrations.Migration):
    """Compress long log entry texts with lz4 instead of the default pglz (ADR-0008)."""

    dependencies = [("core", "0001_initial")]

    operations = [
        migrations.RunSQL(
            "ALTER TABLE core_logentry ALTER COLUMN text SET COMPRESSION lz4",
            "ALTER TABLE core_logentry ALTER COLUMN text SET COMPRESSION DEFAULT",
        ),
    ]
