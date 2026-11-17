"""
EthioOffice Sharing & Access Control Domain Service (Module 6)
Implements:
1. Internal User-to-User and Department-level document/folder sharing.
2. Recursive permission inheritance walking ancestor folder trees.
3. External CSPRNG tokenized public share links.
4. Password protection, download counters, TTL expiry, and Dropbox deposit portals.
5. "Shared With Me" unified directory queries and revocation lifecycles.
"""

import os
import uuid
import secrets
from datetime import datetime, timezone
from typing import Optional, List, Tuple, BinaryIO, Set
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.core.ethiopian_calendar import format_ethiopian_date
from app.models.file import FileItem, FileVersion, DriveType
from app.models.share import FileShare, SharePermission
from app.models.share_link import ShareLink, LinkAccessType
from app.models.user import User, UserRole
from app.models.department import Department
from app.models.audit import AuditLog, AuditAction
from app.services.capability_service import CapabilityService, LicenseReadOnlyLockdownError
from app.services.storage_service import (
    StorageService,
    storage_provider,
    validate_file_security,
    StorageDomainError,
    FileItemNotFoundError,
    DriveAccessDeniedError,
    FilePayloadMissingError,
)
from app.schemas.share import (
    ShareResponse,
    ShareLinkResponse,
    PublicLinkMetadataResponse,
)
from app.schemas.file import FileItemResponse


# =====================================================================
# Domain Exceptions
# =====================================================================

class ShareDomainError(Exception):
    """Base exception for sharing and access control operations."""
    pass


class ShareNotFoundError(ShareDomainError):
    pass


class ShareLinkNotFoundError(ShareDomainError):
    pass


class ShareLinkExpiredError(ShareDomainError):
    pass


class ShareLinkMaxDownloadsExceededError(ShareDomainError):
    pass


class InvalidLinkPasswordError(ShareDomainError):
    pass


class TargetUserNotFoundError(ShareDomainError):
    pass


class TargetDepartmentNotFoundError(ShareDomainError):
    pass


class CannotShareWithSelfError(ShareDomainError):
    pass


# =====================================================================
# Domain Service
# =====================================================================

class ShareService:
    @classmethod
    def to_share_response(cls, share: FileShare) -> ShareResponse:
        ec_date = format_ethiopian_date(share.created_at.date()) if share.created_at else None
        return ShareResponse(
            id=share.id,
            file_id=share.file_id,
            file_name=share.file_item.name if share.file_item else "Unknown",
            is_folder=share.file_item.is_folder if share.file_item else False,
            shared_by_id=share.shared_by_id,
            shared_by_name=share.shared_by.full_name if share.shared_by else "Colleague",
            target_user_id=share.target_user_id,
            target_user_name=share.target_user.full_name if share.target_user else None,
            target_department_id=share.target_department_id,
            target_department_name=share.target_department.name if share.target_department else None,
            permission=share.permission.value if hasattr(share.permission, "value") else str(share.permission),
            expires_at=share.expires_at,
            created_at=share.created_at,
            ec_created_at=ec_date,
        )

    @classmethod
    def to_link_response(cls, link: ShareLink) -> ShareLinkResponse:
        ec_date = format_ethiopian_date(link.created_at.date()) if link.created_at else None
        return ShareLinkResponse(
            id=link.id,
            file_id=link.file_id,
            file_name=link.file_item.name if link.file_item else "Unknown",
            is_folder=link.file_item.is_folder if link.file_item else False,
            token=link.token,
            access_type=link.access_type.value if hasattr(link.access_type, "value") else str(link.access_type),
            is_password_protected=bool(link.password_hash),
            expires_at=link.expires_at,
            max_downloads=link.max_downloads,
            download_count=link.download_count,
            is_active=link.is_active,
            created_at=link.created_at,
            ec_created_at=ec_date,
            public_url=f"/public/share/{link.token}",
        )

    # -----------------------------------------------------------------
    # Permission Resolution & Recursive Folder Tree Inheritance
    # -----------------------------------------------------------------

    @classmethod
    def resolve_effective_permission(
        cls,
        db: Session,
        file_item: FileItem,
        user: User
    ) -> Optional[SharePermission]:
        """
        Determines the user's highest effective permission on an item by evaluating:
        1. Superadmin / Tenant Admin privileges.
        2. Direct item ownership.
        3. Company Drive department membership.
        4. Direct internal file shares (User or Department).
        5. Recursive inherited shares from ancestor folders up the hierarchy.
        """
        # 1. Superadmin or Tenant Admin -> Full editor rights
        if user.is_superuser or user.is_admin:
            return SharePermission.EDITOR

        # 2. Document Owner -> Full editor rights
        if file_item.owner_id == user.id:
            return SharePermission.EDITOR

        # 3. Company Drive Root / Department access
        user_dept_ids = {ud.department_id for ud in user.departments}
        if file_item.drive_type == DriveType.COMPANY:
            if file_item.department_id is None:
                return SharePermission.EDITOR  # General company-wide collaborative drive
            if file_item.department_id in user_dept_ids:
                return SharePermission.EDITOR

        # 4 & 5. Direct and Recursive Ancestor Share Resolution
        now = datetime.now(timezone.utc)
        curr_id: Optional[uuid.UUID] = file_item.id
        visited: Set[uuid.UUID] = set()

        effective: Optional[SharePermission] = None

        while curr_id:
            if curr_id in visited:
                break
            visited.add(curr_id)

            shares = db.query(FileShare).filter(
                FileShare.file_id == curr_id,
                or_(FileShare.expires_at == None, FileShare.expires_at > now),
                or_(
                    FileShare.target_user_id == user.id,
                    FileShare.target_department_id.in_(user_dept_ids) if user_dept_ids else False
                )
            ).all()

            for s in shares:
                if s.permission == SharePermission.EDITOR:
                    return SharePermission.EDITOR  # Highest privilege takes precedence
                elif s.permission == SharePermission.VIEWER:
                    effective = SharePermission.VIEWER

            # Walk up to parent folder
            parent_item = db.query(FileItem.parent_id).filter(FileItem.id == curr_id).first()
            curr_id = parent_item[0] if parent_item and parent_item[0] else None

        return effective

    # -----------------------------------------------------------------
    # Internal User & Department Sharing
    # -----------------------------------------------------------------

    @classmethod
    def create_share(
        cls,
        db: Session,
        org_id: uuid.UUID,
        file_id: uuid.UUID,
        actor: User,
        target_user_id: Optional[uuid.UUID] = None,
        target_department_id: Optional[uuid.UUID] = None,
        permission: str = "VIEWER",
        expires_at: Optional[datetime] = None,
    ) -> ShareResponse:
        """
        Grants internal access to a specific user or department branch.
        Enforces Module 3 write lockdown and tenant isolation.
        """
        CapabilityService.verify_organization_write_access(db, org_id)

        file_item = StorageService.get_item(db, org_id, file_id, actor)

        # Ensure caller has permission to share (must be owner, admin, or editor)
        effective = cls.resolve_effective_permission(db, file_item, actor)
        if effective != SharePermission.EDITOR and not actor.is_superuser:
            raise DriveAccessDeniedError("ፋይሉን ለሌሎች የማጋራት ፈቃድ የለዎትም (You do not have permission to share this document)")

        # Validate target: exactly one target must be provided
        if not target_user_id and not target_department_id:
            raise ShareDomainError("የሚጋራበት ተጠቃሚ ወይም የስራ ክፍል መመረጥ አለበት (Must specify target user or department)")
        if target_user_id and target_department_id:
            raise ShareDomainError("በአንድ ጊዜ ለአንድ ተጠቃሚ ወይም ለአንድ ክፍል ብቻ ማጋራት ይቻላል (Specify either user or department, not both)")

        perm_enum = SharePermission.EDITOR if permission.upper() == "EDITOR" else SharePermission.VIEWER

        # Validate target user
        if target_user_id:
            if target_user_id == actor.id:
                raise CannotShareWithSelfError("ፋይሉን ለራስዎ ማጋራት አይችሉም (Cannot share a file with yourself)")
            target_user = db.query(User).filter(User.id == target_user_id, User.organization_id == org_id).first()
            if not target_user:
                raise TargetUserNotFoundError("የተመረጠው ባልደረባ አልተገኘም (Target user not found in this organization)")

        # Validate target department
        if target_department_id:
            target_dept = db.query(Department).filter(Department.id == target_department_id, Department.organization_id == org_id).first()
            if not target_dept:
                raise TargetDepartmentNotFoundError("የተመረጠው የስራ ክፍል አልተገኘም (Target department not found)")

        # Check existing share on this item for same target
        query = db.query(FileShare).filter(FileShare.file_id == file_item.id)
        if target_user_id:
            query = query.filter(FileShare.target_user_id == target_user_id)
        else:
            query = query.filter(FileShare.target_department_id == target_department_id)

        share = query.first()
        if share:
            # Update existing share
            share.permission = perm_enum
            share.expires_at = expires_at
        else:
            share = FileShare(
                file_id=file_item.id,
                shared_by_id=actor.id,
                target_user_id=target_user_id,
                target_department_id=target_department_id,
                permission=perm_enum,
                expires_at=expires_at,
            )
            db.add(share)

        audit = AuditLog(
            organization_id=org_id,
            user_id=actor.id,
            action=AuditAction.SHARE,
            target_type="FILE" if not file_item.is_folder else "FOLDER",
            target_id=file_item.id,
            target_name=file_item.name,
            details={
                "permission": perm_enum.value,
                "target_user_id": str(target_user_id) if target_user_id else None,
                "target_department_id": str(target_department_id) if target_department_id else None,
            }
        )
        db.add(audit)
        db.commit()
        db.refresh(share)

        # Dispatch real-time in-app notification
        try:
            from app.services.notification_service import NotificationService
            if target_user_id:
                NotificationService.create_notification(
                    db=db,
                    org_id=org_id,
                    user_id=target_user_id,
                    actor_id=actor.id,
                    event_type="FILE_SHARED",
                    title=f"File Shared: {file_item.name}",
                    title_amharic=f"ፋይል ተጋርቶልዎታል፦ {file_item.name}",
                    message=f"{actor.full_name} shared '{file_item.name}' with you.",
                    message_amharic=f"{actor.full_name} '{file_item.name}' የተባለውን ፋይል አጋርቶዎታል::",
                    link=f"/files/{file_item.id}",
                )
        except Exception:
            pass

        return cls.to_share_response(share)

    @classmethod
    def list_file_shares(
        cls,
        db: Session,
        org_id: uuid.UUID,
        file_id: uuid.UUID,
        actor: User
    ) -> List[ShareResponse]:
        """Lists all active internal shares for a specific document or folder."""
        file_item = StorageService.get_item(db, org_id, file_id, actor)
        shares = db.query(FileShare).filter(FileShare.file_id == file_item.id).all()
        return [cls.to_share_response(s) for s in shares]

    @classmethod
    def revoke_share(
        cls,
        db: Session,
        org_id: uuid.UUID,
        share_id: uuid.UUID,
        actor: User
    ) -> bool:
        """Revokes an internal document share immediately."""
        CapabilityService.verify_organization_write_access(db, org_id)

        share = db.query(FileShare).join(FileItem).filter(
            FileShare.id == share_id,
            FileItem.organization_id == org_id
        ).first()

        if not share:
            raise ShareNotFoundError("የማጋሪያ መዝገቡ አልተገኘም (Share record not found)")

        # Caller must be share creator, file owner, or admin
        if share.shared_by_id != actor.id and share.file_item.owner_id != actor.id and not (actor.is_admin or actor.is_superuser):
            raise DriveAccessDeniedError("ማጋራቱን የመሰረዝ ፈቃድ የለዎትም (Only the owner or Admin can revoke this share)")

        file_name = share.file_item.name
        db.delete(share)

        audit = AuditLog(
            organization_id=org_id,
            user_id=actor.id,
            action=AuditAction.DELETE,
            target_type="SHARE",
            target_id=share.id,
            target_name=file_name,
            details={"action": "REVOKE_SHARE"}
        )
        db.add(audit)
        db.commit()
        return True

    @classmethod
    def list_shared_with_me(
        cls,
        db: Session,
        org_id: uuid.UUID,
        user: User
    ) -> List[FileItemResponse]:
        """
        Lists all files and folders shared with the user directly or via their department branches.
        """
        now = datetime.now(timezone.utc)
        user_dept_ids = [ud.department_id for ud in user.departments]

        query = db.query(FileItem).join(FileShare).filter(
            FileItem.organization_id == org_id,
            FileItem.is_deleted == False,
            or_(FileShare.expires_at == None, FileShare.expires_at > now),
            or_(
                FileShare.target_user_id == user.id,
                FileShare.target_department_id.in_(user_dept_ids) if user_dept_ids else False
            )
        ).distinct()

        items = query.order_by(FileItem.is_folder.desc(), FileItem.name.asc()).all()
        return [StorageService.to_file_response(db, i) for i in items]

    # -----------------------------------------------------------------
    # External Public Share Links
    # -----------------------------------------------------------------

    @classmethod
    def create_share_link(
        cls,
        db: Session,
        org_id: uuid.UUID,
        file_id: uuid.UUID,
        actor: User,
        access_type: str = "ALLOW_DOWNLOAD",
        password: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        max_downloads: Optional[int] = None,
    ) -> ShareLinkResponse:
        """
        Generates a tokenized public access link with optional password and download controls.
        """
        CapabilityService.verify_organization_write_access(db, org_id)

        file_item = StorageService.get_item(db, org_id, file_id, actor)

        # If UPLOAD_DROPBOX, file must be a folder
        type_enum = LinkAccessType[access_type.upper()]
        if type_enum == LinkAccessType.UPLOAD_DROPBOX and not file_item.is_folder:
            raise ShareDomainError("የፋይል ማስረከቢያ ሊንክ (Upload Dropbox) ለአቃፊዎች ብቻ ነው የሚፈቀደው")

        token = secrets.token_urlsafe(32)
        pwd_hash = get_password_hash(password) if password else None

        link = ShareLink(
            file_id=file_item.id,
            created_by_id=actor.id,
            token=token,
            password_hash=pwd_hash,
            access_type=type_enum,
            expires_at=expires_at,
            max_downloads=max_downloads,
            download_count=0,
            is_active=True,
        )
        db.add(link)

        audit = AuditLog(
            organization_id=org_id,
            user_id=actor.id,
            action=AuditAction.SHARE,
            target_type="SHARE_LINK",
            target_id=link.id,
            target_name=file_item.name,
            details={"access_type": type_enum.value, "is_protected": bool(pwd_hash)}
        )
        db.add(audit)
        db.commit()
        db.refresh(link)

        return cls.to_link_response(link)

    @classmethod
    def list_file_links(
        cls,
        db: Session,
        org_id: uuid.UUID,
        file_id: uuid.UUID,
        actor: User
    ) -> List[ShareLinkResponse]:
        """Lists all active public links for a file or folder."""
        file_item = StorageService.get_item(db, org_id, file_id, actor)
        links = db.query(ShareLink).filter(ShareLink.file_id == file_item.id).all()
        return [cls.to_link_response(l) for l in links]

    @classmethod
    def revoke_share_link(
        cls,
        db: Session,
        org_id: uuid.UUID,
        link_id: uuid.UUID,
        actor: User
    ) -> bool:
        """Deactivates/deletes a public share link."""
        CapabilityService.verify_organization_write_access(db, org_id)

        link = db.query(ShareLink).join(FileItem).filter(
            ShareLink.id == link_id,
            FileItem.organization_id == org_id
        ).first()

        if not link:
            raise ShareLinkNotFoundError("የማጋሪያ ሊንኩ አልተገኘም (Share link not found)")

        if link.created_by_id != actor.id and not (actor.is_admin or actor.is_superuser):
            raise DriveAccessDeniedError("ሊንኩን የመሰረዝ ፈቃድ የለዎትም (Only creator or Admin can revoke link)")

        db.delete(link)

        audit = AuditLog(
            organization_id=org_id,
            user_id=actor.id,
            action=AuditAction.DELETE,
            target_type="SHARE_LINK",
            target_id=link.id,
            target_name=link.token,
            details={"action": "REVOKE_LINK"}
        )
        db.add(audit)
        db.commit()
        return True

    @classmethod
    def get_public_link_metadata(cls, db: Session, token: str) -> PublicLinkMetadataResponse:
        """
        Public unauthenticated endpoint to inspect share link metadata without exposing payload.
        """
        link = db.query(ShareLink).join(FileItem).filter(
            ShareLink.token == token,
            ShareLink.is_active == True,
            FileItem.is_deleted == False
        ).first()

        if not link:
            raise ShareLinkNotFoundError("የማጋሪያ ሊንኩ አልተገኘም ወይም ተሰርዟል (Link not found or deactivated)")

        now = datetime.now(timezone.utc)
        if link.expires_at and link.expires_at <= now:
            raise ShareLinkExpiredError("ይህ የማጋሪያ ሊንክ ጊዜው አልፎበታል (Share link has expired)")

        if link.max_downloads and link.download_count >= link.max_downloads:
            raise ShareLinkMaxDownloadsExceededError("ይህ ሊንክ ከተፈቀደው የዳውንሎድ ገደብ በላይ ሆኗል (Download limit exceeded)")

        ec_date = format_ethiopian_date(link.file_item.created_at.date()) if link.file_item.created_at else None

        return PublicLinkMetadataResponse(
            token=link.token,
            file_name=link.file_item.name,
            is_folder=link.file_item.is_folder,
            size_bytes=link.file_item.size_bytes,
            mime_type=link.file_item.mime_type,
            access_type=link.access_type.value if hasattr(link.access_type, "value") else str(link.access_type),
            is_password_protected=bool(link.password_hash),
            expires_at=link.expires_at,
            created_at=link.file_item.created_at,
            ec_created_at=ec_date,
        )

    @classmethod
    def verify_link_password(cls, db: Session, token: str, password: str) -> bool:
        """Verifies plaintext password against link's bcrypt hash."""
        link = db.query(ShareLink).filter(ShareLink.token == token, ShareLink.is_active == True).first()
        if not link:
            raise ShareLinkNotFoundError("Link not found")
        if not link.password_hash:
            return True
        if not verify_password(password, link.password_hash):
            raise InvalidLinkPasswordError("የተሳሳተ የይለፍ ቃል (Invalid password for share link)")
        return True

    @classmethod
    def download_public_file(
        cls,
        db: Session,
        token: str,
        password: Optional[str] = None
    ) -> Tuple[FileItem, FileVersion, str]:
        """
        Validates public download request, enforces password, increments download counter,
        and returns file entity, version, and physical disk path.
        """
        link = db.query(ShareLink).join(FileItem).filter(
            ShareLink.token == token,
            ShareLink.is_active == True,
            FileItem.is_deleted == False
        ).first()

        if not link:
            raise ShareLinkNotFoundError("Link not found or deactivated")

        now = datetime.now(timezone.utc)
        if link.expires_at and link.expires_at <= now:
            raise ShareLinkExpiredError("Link has expired")

        if link.max_downloads and link.download_count >= link.max_downloads:
            raise ShareLinkMaxDownloadsExceededError("Maximum download limit reached")

        if link.access_type == LinkAccessType.VIEW_ONLY:
            raise ShareDomainError("ይህ ፋይል ለማየት ብቻ የተፈቀደ ነው (This link allows viewing only, downloads are disabled)")

        if link.file_item.is_folder:
            raise ShareDomainError("Folders cannot be downloaded directly via single link")

        # Password verification
        if link.password_hash:
            if not password or not verify_password(password, link.password_hash):
                raise InvalidLinkPasswordError("የይለፍ ቃል ያስፈልጋል ወይም የተሳሳተ ነው (Password required or invalid)")

        # Fetch current version
        version = db.query(FileVersion).filter(FileVersion.id == link.file_item.current_version_id).first()
        if not version:
            raise FilePayloadMissingError("File version missing")

        full_path = storage_provider.get_full_path(version.storage_path)
        if not os.path.exists(full_path):
            raise FilePayloadMissingError("Physical file payload missing on disk")

        # Increment download counter atomically
        link.download_count += 1
        db.commit()

        return link.file_item, version, full_path

    @classmethod
    def upload_to_dropbox(
        cls,
        db: Session,
        token: str,
        stream: BinaryIO,
        filename: str,
        content_type: Optional[str] = None,
        password: Optional[str] = None,
    ) -> FileItemResponse:
        """
        Enables external counterparties to upload documents into an internal folder
        using a tokenized UPLOAD_DROPBOX public link.
        """
        link = db.query(ShareLink).join(FileItem).filter(
            ShareLink.token == token,
            ShareLink.is_active == True,
            FileItem.is_deleted == False
        ).first()

        if not link:
            raise ShareLinkNotFoundError("Dropbox link not found or inactive")

        if link.access_type != LinkAccessType.UPLOAD_DROPBOX:
            raise ShareDomainError("ይህ ሊንክ ፋይል ለመቀበል አልተፈቀደም (Link is not configured for dropbox uploads)")

        if not link.file_item.is_folder:
            raise ShareDomainError("Dropbox destination must be a folder")

        now = datetime.now(timezone.utc)
        if link.expires_at and link.expires_at <= now:
            raise ShareLinkExpiredError("Dropbox link has expired")

        # Password check
        if link.password_hash:
            if not password or not verify_password(password, link.password_hash):
                raise InvalidLinkPasswordError("Password required for dropbox upload")

        # Upload file directly into the folder owned by link creator
        return StorageService.upload_file_stream(
            db=db,
            org_id=link.file_item.organization_id,
            user=link.created_by,
            stream=stream,
            filename=filename,
            content_type=content_type,
            parent_id=link.file_id,
            drive_type=link.file_item.drive_type.value,
            department_id=link.file_item.department_id,
        )
