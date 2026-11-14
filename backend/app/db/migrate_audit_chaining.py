"""
Database Migration: Audit Hash Chaining & Enterprise Compliance Columns
Adds: user_agent, severity, status, prev_hash, entry_hash to audit_logs table.
Expands audit_action_enum with enterprise lifecycle events.
Backfills cryptographic hash chain for existing records.
"""

import sys
import hashlib
import json
from sqlalchemy import text
from app.core.database import SessionLocal


def migrate():
    db = SessionLocal()
    try:
        print("Starting Module 11 Audit Chaining Migration...")

        # 1. Expand audit_action_enum values
        new_enum_values = [
            "LOGOUT",
            "PASSWORD_CHANGE",
            "USER_CREATE",
            "USER_UPDATE",
            "USER_LOCK",
            "PERMISSION_DENIED",
            "SECURITY_ALERT",
            "CONFIG_CHANGE",
            "EXPORT",
            "LICENSE_CHANGE",
        ]

        for val in new_enum_values:
            try:
                db.execute(text(f"ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS '{val}'"))
                db.commit()
            except Exception as e:
                db.rollback()
                print(f"Enum value '{val}' note: {e}")

        # 2. Add columns to audit_logs
        column_defs = [
            ("user_agent", "VARCHAR(255)"),
            ("severity", "VARCHAR(20) DEFAULT 'INFO' NOT NULL"),
            ("status", "VARCHAR(20) DEFAULT 'SUCCESS' NOT NULL"),
            ("prev_hash", "VARCHAR(64)"),
            ("entry_hash", "VARCHAR(64)"),
        ]

        for col_name, col_type in column_defs:
            sql = text(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'audit_logs' AND column_name = '{col_name}'
                ) THEN
                    ALTER TABLE audit_logs ADD COLUMN {col_name} {col_type};
                END IF;
            END $$;
            """)
            db.execute(sql)
            db.commit()
            print(f"Verified column: audit_logs.{col_name}")

        # 3. Create indexes
        indexes = [
            ("ix_audit_logs_org_created", "CREATE INDEX IF NOT EXISTS ix_audit_logs_org_created ON audit_logs (organization_id, created_at DESC)"),
            ("ix_audit_logs_severity", "CREATE INDEX IF NOT EXISTS ix_audit_logs_severity ON audit_logs (severity)"),
            ("ix_audit_logs_status", "CREATE INDEX IF NOT EXISTS ix_audit_logs_status ON audit_logs (status)"),
            ("ix_audit_logs_entry_hash", "CREATE INDEX IF NOT EXISTS ix_audit_logs_entry_hash ON audit_logs (entry_hash)"),
        ]

        for idx_name, idx_sql in indexes:
            db.execute(text(idx_sql))
            db.commit()
            print(f"Verified index: {idx_name}")

        # 4. Backfill cryptographic hash chain for existing records directly inside PostgreSQL
        print("Backfilling cryptographic hash chain in PostgreSQL engine...")
        fast_backfill_sql = text("""
        DO $$
        DECLARE
            r RECORD;
            curr_org UUID := NULL;
            p_hash VARCHAR(64) := 'GENESIS';
            e_hash VARCHAR(64);
        BEGIN
            FOR r IN (
                SELECT id, organization_id, action, target_type, target_id, target_name, created_at
                FROM audit_logs
                WHERE entry_hash IS NULL
                ORDER BY organization_id, id ASC
            ) LOOP
                IF curr_org IS NULL OR curr_org != r.organization_id THEN
                    curr_org := r.organization_id;
                    p_hash := 'GENESIS';
                END IF;

                e_hash := encode(sha256((p_hash || '|' || COALESCE(curr_org::text, '') || '|' || r.action::text || '|' || r.target_type || '|' || COALESCE(r.target_id::text, '') || '|' || r.created_at::text)::bytea), 'hex');

                UPDATE audit_logs
                SET prev_hash = p_hash,
                    entry_hash = e_hash,
                    severity = COALESCE(severity, 'INFO'),
                    status = COALESCE(status, 'SUCCESS')
                WHERE id = r.id;

                p_hash := e_hash;
            END LOOP;
        END $$;
        """)
        db.execute(fast_backfill_sql)
        db.commit()

        print("Module 11 Audit Chaining Migration successfully completed!")

    except Exception as e:
        db.rollback()
        print(f"Migration error: {e}", file=sys.stderr)
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    migrate()
