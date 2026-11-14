import sys
from app.core.database import engine
from sqlalchemy import text

migration_sql = """
-- 1. Add new enum values if needed
ALTER TYPE letter_direction_enum ADD VALUE IF NOT EXISTS 'INTERNAL_MEMO';
ALTER TYPE letter_status_enum ADD VALUE IF NOT EXISTS 'REJECTED';

DO $$
BEGIN
    -- audit actions
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'LETTER_APPROVE' AND enumtypid = 'audit_action_enum'::regtype) THEN
        ALTER TYPE audit_action_enum ADD VALUE 'LETTER_APPROVE';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'LETTER_REJECT' AND enumtypid = 'audit_action_enum'::regtype) THEN
        ALTER TYPE audit_action_enum ADD VALUE 'LETTER_REJECT';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'LETTER_ROUTE' AND enumtypid = 'audit_action_enum'::regtype) THEN
        ALTER TYPE audit_action_enum ADD VALUE 'LETTER_ROUTE';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'LETTER_ARCHIVE' AND enumtypid = 'audit_action_enum'::regtype) THEN
        ALTER TYPE audit_action_enum ADD VALUE 'LETTER_ARCHIVE';
    END IF;

    -- letter_confidentiality_enum
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'letter_confidentiality_enum') THEN
        CREATE TYPE letter_confidentiality_enum AS ENUM ('NORMAL', 'CONFIDENTIAL', 'STRICTLY_CONFIDENTIAL');
    END IF;

    -- letter_urgency_enum
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'letter_urgency_enum') THEN
        CREATE TYPE letter_urgency_enum AS ENUM ('NORMAL', 'URGENT', 'VERY_URGENT');
    END IF;

    -- letter_delivery_method_enum
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'letter_delivery_method_enum') THEN
        CREATE TYPE letter_delivery_method_enum AS ENUM ('HAND_DELIVERY', 'POSTAL', 'EMAIL', 'INTERNAL_DISPATCH', 'FAX');
    END IF;

    -- routing_action_enum
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'routing_action_enum') THEN
        CREATE TYPE routing_action_enum AS ENUM ('FOR_ACTION', 'FOR_INFORMATION', 'FOR_APPROVAL', 'FOR_COMMENT', 'FOR_ARCHIVE');
    END IF;

    -- routing_status_enum
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'routing_status_enum') THEN
        CREATE TYPE routing_status_enum AS ENUM ('PENDING', 'ACKNOWLEDGED', 'COMPLETED');
    END IF;

    -- 2. Add columns to letter_registry
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='letter_registry' AND column_name='department_id') THEN
        ALTER TABLE letter_registry ADD COLUMN department_id UUID REFERENCES departments(id) ON DELETE SET NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='letter_registry' AND column_name='external_reference_number') THEN
        ALTER TABLE letter_registry ADD COLUMN external_reference_number VARCHAR(100) NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='letter_registry' AND column_name='sender_contact') THEN
        ALTER TABLE letter_registry ADD COLUMN sender_contact VARCHAR(255) NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='letter_registry' AND column_name='recipient_contact') THEN
        ALTER TABLE letter_registry ADD COLUMN recipient_contact VARCHAR(255) NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='letter_registry' AND column_name='cc_entities') THEN
        ALTER TABLE letter_registry ADD COLUMN cc_entities JSONB NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='letter_registry' AND column_name='confidentiality') THEN
        ALTER TABLE letter_registry ADD COLUMN confidentiality letter_confidentiality_enum NOT NULL DEFAULT 'NORMAL';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='letter_registry' AND column_name='urgency') THEN
        ALTER TABLE letter_registry ADD COLUMN urgency letter_urgency_enum NOT NULL DEFAULT 'NORMAL';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='letter_registry' AND column_name='delivery_method') THEN
        ALTER TABLE letter_registry ADD COLUMN delivery_method letter_delivery_method_enum NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='letter_registry' AND column_name='ethiopian_year') THEN
        ALTER TABLE letter_registry ADD COLUMN ethiopian_year INTEGER NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='letter_registry' AND column_name='due_date_gc') THEN
        ALTER TABLE letter_registry ADD COLUMN due_date_gc DATE NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='letter_registry' AND column_name='due_date_ec') THEN
        ALTER TABLE letter_registry ADD COLUMN due_date_ec VARCHAR(30) NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='letter_registry' AND column_name='approved_at_gc') THEN
        ALTER TABLE letter_registry ADD COLUMN approved_at_gc TIMESTAMP WITH TIME ZONE NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='letter_registry' AND column_name='approved_by_id') THEN
        ALTER TABLE letter_registry ADD COLUMN approved_by_id UUID REFERENCES users(id) ON DELETE SET NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='letter_registry' AND column_name='rejected_at_gc') THEN
        ALTER TABLE letter_registry ADD COLUMN rejected_at_gc TIMESTAMP WITH TIME ZONE NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='letter_registry' AND column_name='rejected_by_id') THEN
        ALTER TABLE letter_registry ADD COLUMN rejected_by_id UUID REFERENCES users(id) ON DELETE SET NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='letter_registry' AND column_name='rejection_reason') THEN
        ALTER TABLE letter_registry ADD COLUMN rejection_reason TEXT NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='letter_registry' AND column_name='dispatched_at_gc') THEN
        ALTER TABLE letter_registry ADD COLUMN dispatched_at_gc TIMESTAMP WITH TIME ZONE NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='letter_registry' AND column_name='dispatched_at_ec') THEN
        ALTER TABLE letter_registry ADD COLUMN dispatched_at_ec VARCHAR(30) NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='letter_registry' AND column_name='dispatched_by_id') THEN
        ALTER TABLE letter_registry ADD COLUMN dispatched_by_id UUID REFERENCES users(id) ON DELETE SET NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='letter_registry' AND column_name='reply_to_letter_id') THEN
        ALTER TABLE letter_registry ADD COLUMN reply_to_letter_id UUID REFERENCES letter_registry(id) ON DELETE SET NULL;
    END IF;

    -- 3. Create letter_sequences table
    CREATE TABLE IF NOT EXISTS letter_sequences (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        department_id UUID NULL REFERENCES departments(id) ON DELETE CASCADE,
        fiscal_year INTEGER NOT NULL,
        counter_type VARCHAR(50) NOT NULL,
        current_number INTEGER NOT NULL DEFAULT 0,
        prefix VARCHAR(50) NOT NULL DEFAULT 'EO',
        format_pattern VARCHAR(100) NOT NULL DEFAULT '{ORG}/{DEPT}/{YEAR}/{SEQ:04d}',
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
    );

    CREATE UNIQUE INDEX IF NOT EXISTS uq_letter_seq_org_dept_year_type 
    ON letter_sequences (organization_id, COALESCE(department_id, '00000000-0000-0000-0000-000000000000'::uuid), fiscal_year, counter_type);

    -- 4. Create letter_routings table
    CREATE TABLE IF NOT EXISTS letter_routings (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        letter_id UUID NOT NULL REFERENCES letter_registry(id) ON DELETE CASCADE,
        organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        from_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        from_department_id UUID NULL REFERENCES departments(id) ON DELETE SET NULL,
        to_user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
        to_department_id UUID NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
        transferred_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        action_required routing_action_enum NOT NULL DEFAULT 'FOR_ACTION',
        priority letter_urgency_enum NOT NULL DEFAULT 'NORMAL',
        instructions TEXT NULL,
        status routing_status_enum NOT NULL DEFAULT 'PENDING',
        acknowledged_at TIMESTAMP WITH TIME ZONE NULL,
        completed_at TIMESTAMP WITH TIME ZONE NULL,
        response_notes TEXT NULL
    );

    CREATE INDEX IF NOT EXISTS ix_letter_routings_letter_id ON letter_routings(letter_id);
    CREATE INDEX IF NOT EXISTS ix_letter_routings_to_dept ON letter_routings(to_department_id);
    CREATE INDEX IF NOT EXISTS ix_letter_routings_to_user ON letter_routings(to_user_id);

END $$;
"""

def run_migration():
    with engine.begin() as conn:
        conn.execute(text(migration_sql))
    print("SUCCESS: Module 9 (Letter Registry) enterprise schema applied to PostgreSQL!")

if __name__ == "__main__":
    run_migration()
