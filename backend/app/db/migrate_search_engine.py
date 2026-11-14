import sys
from app.core.database import engine
from sqlalchemy import text

migration_sql = """
-- 1. Enable pg_trgm extension for trigram fuzzy matching
CREATE EXTENSION IF NOT EXISTS pg_trgm;

DO $$
BEGIN
    -- 2. Add columns to file_search_index
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='file_search_index' AND column_name='organization_id') THEN
        ALTER TABLE file_search_index ADD COLUMN organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='file_search_index' AND column_name='file_name') THEN
        ALTER TABLE file_search_index ADD COLUMN file_name VARCHAR(255) NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='file_search_index' AND column_name='normalized_text') THEN
        ALTER TABLE file_search_index ADD COLUMN normalized_text TEXT NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='file_search_index' AND column_name='content_hash') THEN
        ALTER TABLE file_search_index ADD COLUMN content_hash VARCHAR(64) NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='file_search_index' AND column_name='status') THEN
        ALTER TABLE file_search_index ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'INDEXED';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='file_search_index' AND column_name='error_message') THEN
        ALTER TABLE file_search_index ADD COLUMN error_message TEXT NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='file_search_index' AND column_name='character_count') THEN
        ALTER TABLE file_search_index ADD COLUMN character_count INTEGER DEFAULT 0;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='file_search_index' AND column_name='word_count') THEN
        ALTER TABLE file_search_index ADD COLUMN word_count INTEGER DEFAULT 0;
    END IF;

    -- 3. Backfill organization_id and file_name if any rows exist
    UPDATE file_search_index s 
    SET organization_id = f.organization_id, file_name = f.name 
    FROM file_items f 
    WHERE s.file_id = f.id AND s.organization_id IS NULL;

    -- 4. Create performance indexes
    CREATE INDEX IF NOT EXISTS ix_file_search_index_org_status ON file_search_index (organization_id, status);
    CREATE INDEX IF NOT EXISTS ix_file_search_vector ON file_search_index USING gin (search_vector);
    CREATE INDEX IF NOT EXISTS ix_file_search_name_trgm ON file_search_index USING gin (file_name gin_trgm_ops);

END $$;
"""

def run_migration():
    with engine.begin() as conn:
        conn.execute(text(migration_sql))
    print("SUCCESS: Module 10 (Search Engine) database schema and pg_trgm applied to PostgreSQL!")

if __name__ == "__main__":
    run_migration()
