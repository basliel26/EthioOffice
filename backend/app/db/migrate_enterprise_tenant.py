import sys
from app.core.database import engine
from sqlalchemy import text

migration_sql = """
DO $$
BEGIN
    -- 1. Create org_status_enum if not exists
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'org_status_enum') THEN
        CREATE TYPE org_status_enum AS ENUM ('TRIAL', 'ACTIVE', 'SUSPENDED', 'ARCHIVED');
    END IF;

    -- 2. Add status column to organizations if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='organizations' AND column_name='status') THEN
        ALTER TABLE organizations ADD COLUMN status org_status_enum NOT NULL DEFAULT 'ACTIVE';
    END IF;

    -- 3. Add parent_id to departments if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='departments' AND column_name='parent_id') THEN
        ALTER TABLE departments ADD COLUMN parent_id UUID REFERENCES departments(id) ON DELETE CASCADE;
    END IF;

    -- 4. Add storage_quota_bytes to departments if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='departments' AND column_name='storage_quota_bytes') THEN
        ALTER TABLE departments ADD COLUMN storage_quota_bytes BIGINT NULL;
    END IF;

    -- 5. Add used_storage_bytes to departments if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='departments' AND column_name='used_storage_bytes') THEN
        ALTER TABLE departments ADD COLUMN used_storage_bytes BIGINT NOT NULL DEFAULT 0;
    END IF;
END $$;
"""

with engine.begin() as conn:
    conn.execute(text(migration_sql))
    print("SUCCESS: Enterprise Module 2 database columns applied to Supabase PostgreSQL.")
