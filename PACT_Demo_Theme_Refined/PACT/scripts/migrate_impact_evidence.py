"""One-time migration for existing SQLite/PostgreSQL demo databases.

Run from the project root before starting the new version:
    python scripts/migrate_impact_evidence.py
Fresh databases do not need this script; SQLAlchemy creates the new columns.
"""
from sqlalchemy import inspect, text
from app.db import engine

COLUMNS = {
    "evidence_url": "VARCHAR(500) NOT NULL DEFAULT ''",
    "verification_status": "VARCHAR(20) NOT NULL DEFAULT 'self_reported'",
    "verification_note": "TEXT NOT NULL DEFAULT ''",
    "verified_by": "INTEGER NULL",
    "verified_at": "DATETIME NULL",
}

with engine.begin() as conn:
    inspector = inspect(conn)
    if "impact_metrics" not in inspector.get_table_names():
        print("impact_metrics table does not exist; start the app once to create the schema.")
    else:
        present = {c["name"] for c in inspector.get_columns("impact_metrics")}
        for name, sql_type in COLUMNS.items():
            if name not in present:
                conn.execute(text(f"ALTER TABLE impact_metrics ADD COLUMN {name} {sql_type}"))
                print(f"Added impact_metrics.{name}")
            else:
                print(f"impact_metrics.{name} already exists")
print("Migration check complete. Back up your database before running migrations in production.")
