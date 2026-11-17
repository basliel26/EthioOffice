"""
Database Migration: Completing Enterprise Features
Creates:
1. user_favorites (Starred / Bookmarked Files & Folders)
2. notifications (In-App Notification & Event Alert Engine)
3. letter_attachments (Linking Drive Documents to Official Letters)
"""

import sys
from sqlalchemy import text
from app.core.database import SessionLocal


def migrate():
    db = SessionLocal()
    try:
        print("Starting Completing Enterprise Features Migration...")

        # 1. user_favorites table
        db.execute(text("""
        CREATE TABLE IF NOT EXISTS user_favorites (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            file_id UUID NOT NULL REFERENCES file_items(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
            CONSTRAINT uq_user_file_favorite UNIQUE (user_id, file_id)
        );
        CREATE INDEX IF NOT EXISTS ix_user_favorites_user_id ON user_favorites (user_id);
        CREATE INDEX IF NOT EXISTS ix_user_favorites_file_id ON user_favorites (file_id);
        """))
        db.commit()
        print("Verified table: user_favorites")

        # 2. notifications table
        db.execute(text("""
        CREATE TABLE IF NOT EXISTS notifications (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            actor_id UUID REFERENCES users(id) ON DELETE SET NULL,
            event_type VARCHAR(50) NOT NULL,
            title VARCHAR(255) NOT NULL,
            title_amharic VARCHAR(255) NOT NULL,
            message TEXT NOT NULL,
            message_amharic TEXT NOT NULL,
            link VARCHAR(500),
            is_read BOOLEAN NOT NULL DEFAULT FALSE,
            read_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
        );
        CREATE INDEX IF NOT EXISTS ix_notifications_org_id ON notifications (organization_id);
        CREATE INDEX IF NOT EXISTS ix_notifications_user_id ON notifications (user_id);
        CREATE INDEX IF NOT EXISTS ix_notifications_is_read ON notifications (is_read);
        CREATE INDEX IF NOT EXISTS ix_notifications_created_at ON notifications (created_at DESC);
        """))
        db.commit()
        print("Verified table: notifications")

        # 3. letter_attachments table
        db.execute(text("""
        CREATE TABLE IF NOT EXISTS letter_attachments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            letter_id UUID NOT NULL REFERENCES letter_registry(id) ON DELETE CASCADE,
            file_id UUID NOT NULL REFERENCES file_items(id) ON DELETE CASCADE,
            attached_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
            attachment_type VARCHAR(50) NOT NULL DEFAULT 'SUPPORTING_DOCUMENT',
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
            CONSTRAINT uq_letter_file_attachment UNIQUE (letter_id, file_id)
        );
        CREATE INDEX IF NOT EXISTS ix_letter_attachments_letter_id ON letter_attachments (letter_id);
        CREATE INDEX IF NOT EXISTS ix_letter_attachments_file_id ON letter_attachments (file_id);
        CREATE INDEX IF NOT EXISTS ix_letter_attachments_org_id ON letter_attachments (organization_id);
        """))
        db.commit()
        print("Verified table: letter_attachments")

        print("Completing Enterprise Features Migration completed successfully!")

    except Exception as e:
        db.rollback()
        print(f"Migration error: {e}", file=sys.stderr)
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    migrate()
