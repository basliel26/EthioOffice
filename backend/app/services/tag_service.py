"""
EthioOffice Tag & Taxonomy Domain Service
Manages color-coded classification tags, file associations, and triggers search re-indexing.
"""

import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.tag import Tag, FileTag
from app.models.file import FileItem
from app.models.user import User
from app.models.audit import AuditAction
from app.services.storage_service import StorageService, StorageDomainError, FileItemNotFoundError, DriveAccessDeniedError
from app.services.share_service import ShareService
from app.models.share import SharePermission
from app.services.capability_service import CapabilityService
from app.services.audit_service import AuditService
from app.schemas.tag import TagResponse, FileTagResponse


class TagDomainError(StorageDomainError):
    pass


class TagNotFoundError(TagDomainError):
    pass


class TagConflictError(TagDomainError):
    pass


class TagService:

    @classmethod
    def create_tag(
        cls,
        db: Session,
        org_id: uuid.UUID,
        name: str,
        color: str,
        actor: User,
    ) -> TagResponse:
        """Creates a new color-coded tag for the organization."""
        CapabilityService.verify_organization_write_access(db, org_id)

        clean_name = name.strip()
        clean_color = color.strip()

        # Check for duplicates within organization
        existing = db.query(Tag).filter(
            Tag.organization_id == org_id,
            func.lower(Tag.name) == clean_name.lower(),
        ).first()

        if existing:
            raise TagConflictError(f"በዚህ ስም '{clean_name}' የተመዘገበ መለያ (Tag) ቀደም ሲል አለ")

        tag = Tag(
            organization_id=org_id,
            name=clean_name,
            color=clean_color,
        )
        db.add(tag)
        db.commit()
        db.refresh(tag)

        AuditService.record_event(
            db=db,
            org_id=org_id,
            user_id=actor.id,
            action=AuditAction.CONFIG_CHANGE,
            target_type="TAG",
            target_id=tag.id,
            target_name=tag.name,
            details={"color": tag.color},
        )

        return TagResponse(
            id=tag.id,
            organization_id=tag.organization_id,
            name=tag.name,
            color=tag.color,
            file_count=0,
            created_at=tag.created_at,
        )

    @classmethod
    def list_tags(cls, db: Session, org_id: uuid.UUID) -> List[TagResponse]:
        """Lists all tags for the organization with assigned document counts."""
        tags_with_counts = db.query(
            Tag, func.count(FileTag.file_id)
        ).outerjoin(
            FileTag, FileTag.tag_id == Tag.id
        ).filter(
            Tag.organization_id == org_id
        ).group_by(Tag.id).order_by(Tag.name.asc()).all()

        return [
            TagResponse(
                id=t.id,
                organization_id=t.organization_id,
                name=t.name,
                color=t.color,
                file_count=cnt,
                created_at=t.created_at,
            )
            for t, cnt in tags_with_counts
        ]

    @classmethod
    def delete_tag(cls, db: Session, org_id: uuid.UUID, tag_id: uuid.UUID, actor: User) -> bool:
        """Deletes a tag and removes all file associations."""
        CapabilityService.verify_organization_write_access(db, org_id)

        tag = db.query(Tag).filter(Tag.id == tag_id, Tag.organization_id == org_id).first()
        if not tag:
            raise TagNotFoundError("መለያው (Tag) አልተገኘም")

        # Affected files for re-indexing
        file_ids = [ft.file_id for ft in tag.file_associations]

        tag_name = tag.name
        db.delete(tag)
        db.commit()

        # Re-index affected files in search engine
        try:
            from app.services.search_service import SearchService
            for fid in file_ids:
                SearchService.index_file(db, fid, force=True)
        except Exception:
            pass

        AuditService.record_event(
            db=db,
            org_id=org_id,
            user_id=actor.id,
            action=AuditAction.CONFIG_CHANGE,
            target_type="TAG",
            target_id=tag_id,
            target_name=tag_name,
            details={"action": "DELETE_TAG"},
        )

        return True

    @classmethod
    def assign_tags_to_file(
        cls,
        db: Session,
        org_id: uuid.UUID,
        file_id: uuid.UUID,
        tag_ids: List[uuid.UUID],
        actor: User,
    ) -> FileTagResponse:
        """
        Assigns multiple tags to a document.
        Requires Editor permission on the document and triggers search re-indexing.
        """
        CapabilityService.verify_organization_write_access(db, org_id)

        file_item = StorageService.get_item(db, org_id, file_id, actor)
        if file_item.is_folder:
            raise TagDomainError("መለያዎችን (Tags) ለአቃፊዎች መስጠት አይቻልም")

        effective = ShareService.resolve_effective_permission(db, file_item, actor)
        if effective != SharePermission.EDITOR:
            raise DriveAccessDeniedError("የሰነዱን መለያዎች የመቀየር ፈቃድ የለዎትም (Editor permission required to tag documents)")

        # Verify all tags exist and belong to this organization
        tags = db.query(Tag).filter(Tag.id.in_(tag_ids), Tag.organization_id == org_id).all()
        if len(tags) != len(set(tag_ids)):
            raise TagNotFoundError("አንድ ወይም ከዚያ በላይ የተመረጡ መለያዎች አልተገኙም")

        # Assign new tags (idempotent)
        for t in tags:
            existing_assoc = db.query(FileTag).filter(
                FileTag.file_id == file_item.id,
                FileTag.tag_id == t.id,
            ).first()
            if not existing_assoc:
                assoc = FileTag(
                    file_id=file_item.id,
                    tag_id=t.id,
                    assigned_by_id=actor.id,
                )
                db.add(assoc)

        db.commit()

        # Trigger search re-indexing
        try:
            from app.services.search_service import SearchService
            SearchService.index_file(db, file_item.id, force=True)
        except Exception:
            pass

        # Return updated tags for this file
        current_tags = cls.get_file_tags(db, org_id, file_item.id, actor)
        return FileTagResponse(file_id=file_item.id, tags=current_tags)

    @classmethod
    def remove_tag_from_file(
        cls,
        db: Session,
        org_id: uuid.UUID,
        file_id: uuid.UUID,
        tag_id: uuid.UUID,
        actor: User,
    ) -> bool:
        """Removes a tag association from a document."""
        CapabilityService.verify_organization_write_access(db, org_id)

        file_item = StorageService.get_item(db, org_id, file_id, actor)
        effective = ShareService.resolve_effective_permission(db, file_item, actor)
        if effective != SharePermission.EDITOR:
            raise DriveAccessDeniedError("የሰነዱን መለያ የማስወገድ ፈቃድ የለዎትም")

        assoc = db.query(FileTag).filter(
            FileTag.file_id == file_item.id,
            FileTag.tag_id == tag_id,
        ).first()

        if not assoc:
            return True  # Idempotent

        db.delete(assoc)
        db.commit()

        # Trigger search re-indexing
        try:
            from app.services.search_service import SearchService
            SearchService.index_file(db, file_item.id, force=True)
        except Exception:
            pass

        return True

    @classmethod
    def get_file_tags(
        cls,
        db: Session,
        org_id: uuid.UUID,
        file_id: uuid.UUID,
        actor: User,
    ) -> List[TagResponse]:
        """Lists all tags assigned to a document."""
        file_item = StorageService.get_item(db, org_id, file_id, actor)

        tags = db.query(Tag).join(
            FileTag, FileTag.tag_id == Tag.id
        ).filter(
            FileTag.file_id == file_item.id,
            Tag.organization_id == org_id,
        ).all()

        return [
            TagResponse(
                id=t.id,
                organization_id=t.organization_id,
                name=t.name,
                color=t.color,
                file_count=0,
                created_at=t.created_at,
            )
            for t in tags
        ]
