"""
EthioOffice Versioning & Concurrency Control Domain Service (Module 5)
Handles:
1. Document versioning lifecycle: sequential version incrementation, revision audit notes.
2. Content-Addressable Storage (CAS) zero-byte version rollback.
3. Exclusive document check-out / file locking state machine.
4. Concurrency protection against simultaneous conflicting edits (HTTP 423 Locked).
5. Administrative force-unlock with enterprise audit logging.
"""

import os
import uuid
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Tuple, BinaryIO
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.config import settings
from app.models.file import FileItem, FileVersion, DriveType
from app.models.lock import FileLock
from app.models.user import User, UserRole
from app.models.audit import AuditLog, AuditAction
from app.services.tenant_service import TenantService, StorageQuotaExceededError
from app.services.capability_service import CapabilityService, LicenseReadOnlyLockdownError
from app.services.storage_service import (
    StorageService,
    storage_provider,
    validate_file_security,
    StorageDomainError,
    FileItemNotFoundError,
    DriveAccessDeniedError,
    FilePayloadMissingError,
    FileLockedError,
)
from app.core.ethiopian_calendar import format_ethiopian_date
from app.schemas.file import (
    FileVersionSummary,
    FileLockInfo,
    FileItemResponse,
)


# =====================================================================
# Domain Exceptions
# =====================================================================

class VersionDomainError(Exception):
    """Base exception for file versioning and locking operations."""
    pass


class VersionNotFoundError(VersionDomainError):
    pass


class LockNotFoundError(VersionDomainError):
    pass


class LockPermissionDeniedError(VersionDomainError):
    pass


# =====================================================================
# Domain Service
# =====================================================================

class VersionService:
    @classmethod
    def to_version_summary(cls, version: FileVersion) -> FileVersionSummary:
        ec_date = format_ethiopian_date(version.created_at.date()) if version.created_at else None
        return FileVersionSummary(
            id=version.id,
            version_number=version.version_number,
            size_bytes=version.size_bytes,
            checksum_sha256=version.checksum_sha256,
            change_summary=version.change_summary,
            created_by_name=version.created_by.full_name if version.created_by else None,
            created_at=version.created_at,
            ec_created_at=ec_date,
        )

    # -----------------------------------------------------------------
    # Concurrency Control: Lock Verification & Management
    # -----------------------------------------------------------------

    @classmethod
    def verify_write_lock(cls, db: Session, file_item: FileItem, actor: User) -> None:
        """
        Verifies that the file is not currently locked by another colleague.
        If locked by another user and lock has not expired, raises FileLockedError (HTTP 423).
        """
        if file_item.is_folder:
            return

        lock = db.query(FileLock).filter(FileLock.file_id == file_item.id).first()
        if not lock:
            return

        now = datetime.now(timezone.utc)
        if lock.expires_at <= now:
            # Auto-expire stale lock
            db.delete(lock)
            db.commit()
            return

        if lock.locked_by_id != actor.id:
            holder_name = lock.locked_by.full_name if lock.locked_by else "ባልደረባ (Colleague)"
            raise FileLockedError(
                f"ይህ ፋይል በ{holder_name} ተቆልፏል። እባክዎን ይጠብቁ ወይም አስተዳዳሪን ያነጋግሩ (File is exclusively locked by {holder_name})",
                locked_by_name=holder_name,
                expires_at=lock.expires_at,
            )

    @classmethod
    def acquire_lock(
        cls,
        db: Session,
        org_id: uuid.UUID,
        file_id: uuid.UUID,
        actor: User,
        reason: Optional[str] = "Editing document",
        duration_minutes: int = 120,
    ) -> FileLockInfo:
        """
        Acquires exclusive checkout lock for the document.
        Enforces Module 3 write lockdown, file ownership/drive access, and prevents stealing.
        """
        CapabilityService.verify_organization_write_access(db, org_id)

        file_item = StorageService.get_item(db, org_id, file_id, actor)
        if file_item.is_folder:
            raise VersionDomainError("አቃፊዎችን መቆለፍ አይቻልም (Folders cannot be locked)")

        now = datetime.now(timezone.utc)
        capped_minutes = min(max(duration_minutes, 1), 1440)  # Max 24 hours
        expires_at = now + timedelta(minutes=capped_minutes)

        lock = db.query(FileLock).filter(FileLock.file_id == file_item.id).first()

        if lock:
            if lock.expires_at > now and lock.locked_by_id != actor.id:
                holder_name = lock.locked_by.full_name if lock.locked_by else "ባልደረባ"
                raise FileLockedError(
                    f"ይህ ፋይል ቀደም ሲል በ{holder_name} ተቆልፏል (File is already locked by {holder_name})",
                    locked_by_name=holder_name,
                    expires_at=lock.expires_at,
                )
            # Renew / re-acquire own lock or claim expired lock
            lock.locked_by_id = actor.id
            lock.reason = reason
            lock.locked_at = now
            lock.expires_at = expires_at
        else:
            lock = FileLock(
                file_id=file_item.id,
                locked_by_id=actor.id,
                reason=reason,
                locked_at=now,
                expires_at=expires_at,
            )
            db.add(lock)

        audit = AuditLog(
            organization_id=org_id,
            user_id=actor.id,
            action=AuditAction.UPLOAD,
            target_type="FILE",
            target_id=file_item.id,
            target_name=file_item.name,
            details={"action": "LOCK_ACQUIRED", "duration_minutes": capped_minutes, "reason": reason}
        )
        db.add(audit)
        db.commit()
        db.refresh(lock)

        return FileLockInfo(
            locked_by_name=actor.full_name,
            locked_by_id=actor.id,
            reason=lock.reason,
            expires_at=lock.expires_at,
        )

    @classmethod
    def release_lock(
        cls,
        db: Session,
        org_id: uuid.UUID,
        file_id: uuid.UUID,
        actor: User,
        force: bool = False,
    ) -> bool:
        """
        Releases checkout lock. Lock holders can release directly.
        Tenant Admins / Superadmins can force-unlock stale or abandoned locks.
        """
        CapabilityService.verify_organization_write_access(db, org_id)

        file_item = StorageService.get_item(db, org_id, file_id, actor)
        lock = db.query(FileLock).filter(FileLock.file_id == file_item.id).first()

        if not lock:
            return True  # Already unlocked

        if lock.locked_by_id != actor.id:
            if not force:
                raise LockPermissionDeniedError("ቁልፉን የመፍታት ፈቃድ የለዎትም (Only the lock holder or an Admin can unlock this file)")
            if not (actor.is_admin or actor.is_superuser):
                raise LockPermissionDeniedError("አስተዳዳሪ ብቻ ነው የሌላውን ሰው ቁልፍ በግድ መፍታት የሚችለው (Only Admins can force-unlock)")

        db.delete(lock)

        audit = AuditLog(
            organization_id=org_id,
            user_id=actor.id,
            action=AuditAction.UPLOAD,
            target_type="FILE",
            target_id=file_item.id,
            target_name=file_item.name,
            details={"action": "LOCK_RELEASED", "force": force}
        )
        db.add(audit)
        db.commit()
        return True

    @classmethod
    def get_lock_info(
        cls,
        db: Session,
        org_id: uuid.UUID,
        file_id: uuid.UUID,
        actor: User,
    ) -> Optional[FileLockInfo]:
        """Returns active lock status and holder details, or None if unlocked/expired."""
        file_item = StorageService.get_item(db, org_id, file_id, actor)
        lock = db.query(FileLock).filter(FileLock.file_id == file_item.id).first()

        if not lock:
            return None

        now = datetime.now(timezone.utc)
        if lock.expires_at <= now:
            db.delete(lock)
            db.commit()
            return None

        return FileLockInfo(
            locked_by_name=lock.locked_by.full_name if lock.locked_by else "Colleague",
            locked_by_id=lock.locked_by_id,
            reason=lock.reason,
            expires_at=lock.expires_at,
        )

    # -----------------------------------------------------------------
    # Document Versioning Lifecycle
    # -----------------------------------------------------------------

    @classmethod
    def upload_new_version(
        cls,
        db: Session,
        org_id: uuid.UUID,
        file_id: uuid.UUID,
        stream: BinaryIO,
        filename: str,
        actor: User,
        change_summary: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> FileItemResponse:
        """
        Uploads a new version (vN+1) using 64KB memory-capped chunked streaming,
        computes SHA-256 integrity hash, enforces lock concurrency and CAS deduplication.
        """
        CapabilityService.verify_organization_write_access(db, org_id)

        file_item = StorageService.get_item(db, org_id, file_id, actor)
        if file_item.is_folder:
            raise VersionDomainError("አቃፊዎችን ማሻሻል አይቻልም (Folders cannot have versions)")

        # Verify Lock Concurrency
        cls.verify_write_lock(db, file_item, actor)

        # Enterprise INSA Malware & Traversal Security check
        clean_filename = validate_file_security(filename)

        # 1. Stream payload to storage and calculate SHA-256
        rel_storage_path, sha256_checksum, size_bytes = storage_provider.save_stream(stream, org_id, clean_filename)

        # 2. Check maximum upload size
        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if size_bytes > max_bytes:
            storage_provider.delete_payload(rel_storage_path)
            raise StorageDomainError(f"የፋይሉ መጠን ከተፈቀደው {settings.MAX_UPLOAD_SIZE_MB}MB በላይ ነው")

        # 3. Check storage quota budget
        try:
            TenantService.check_storage_budget(db, org_id, size_bytes, dept_id=file_item.department_id)
        except StorageQuotaExceededError as e:
            storage_provider.delete_payload(rel_storage_path)
            raise e

        # 4. CAS Deduplication
        existing_version = db.query(FileVersion).join(FileItem).filter(
            FileItem.organization_id == org_id,
            FileVersion.checksum_sha256 == sha256_checksum,
            FileVersion.size_bytes == size_bytes,
        ).first()

        is_deduplicated = False
        if existing_version and storage_provider.exists(existing_version.storage_path):
            storage_provider.delete_payload(rel_storage_path)
            rel_storage_path = existing_version.storage_path
            is_deduplicated = True

        # 5. Determine next version number
        max_v = db.query(func.coalesce(func.max(FileVersion.version_number), 0)).filter(
            FileVersion.file_id == file_item.id
        ).scalar()
        next_v = max_v + 1

        summary = change_summary or f"Version {next_v}"
        if is_deduplicated:
            summary = f"{summary} (CAS Deduplicated)"

        version = FileVersion(
            file_id=file_item.id,
            version_number=next_v,
            storage_path=rel_storage_path,
            checksum_sha256=sha256_checksum,
            size_bytes=size_bytes,
            created_by_id=actor.id,
            change_summary=summary,
        )
        db.add(version)
        db.flush()

        # 6. Update current version pointer and size on FileItem
        file_item.current_version_id = version.id
        file_item.size_bytes = size_bytes
        if content_type:
            file_item.mime_type = content_type
        file_item.updated_at = datetime.now(timezone.utc)

        # 7. Record storage quota increment
        TenantService.record_storage_change(db, org_id, size_bytes, dept_id=file_item.department_id)

        # 8. Audit log
        audit = AuditLog(
            organization_id=org_id,
            user_id=actor.id,
            action=AuditAction.UPLOAD,
            target_type="FILE",
            target_id=file_item.id,
            target_name=file_item.name,
            details={
                "action": "NEW_VERSION",
                "version_number": next_v,
                "size_bytes": size_bytes,
                "sha256": sha256_checksum,
                "deduplicated": is_deduplicated,
            }
        )
        db.add(audit)
        db.commit()
        db.refresh(file_item)

        return StorageService.to_file_response(db, file_item)

    @classmethod
    def list_versions(
        cls,
        db: Session,
        org_id: uuid.UUID,
        file_id: uuid.UUID,
        actor: User,
    ) -> List[FileVersionSummary]:
        """Lists all revisions of the document ordered by newest first."""
        file_item = StorageService.get_item(db, org_id, file_id, actor)
        if file_item.is_folder:
            raise VersionDomainError("አቃፊዎች የትርጉም ታሪክ (Version history) የላቸውም")

        versions = db.query(FileVersion).filter(
            FileVersion.file_id == file_item.id
        ).order_by(FileVersion.version_number.desc()).all()

        return [cls.to_version_summary(v) for v in versions]

    @classmethod
    def get_version_file_info(
        cls,
        db: Session,
        org_id: uuid.UUID,
        file_id: uuid.UUID,
        version_number: int,
        actor: User,
    ) -> Tuple[FileItem, FileVersion, str]:
        """
        Retrieves historical version entity, parent file, and full on-disk path.
        Verifies drive permissions.
        """
        file_item = StorageService.get_item(db, org_id, file_id, actor)
        if file_item.is_folder:
            raise VersionDomainError("Folders cannot be downloaded")

        version = db.query(FileVersion).filter(
            FileVersion.file_id == file_item.id,
            FileVersion.version_number == version_number,
        ).first()

        if not version:
            raise VersionNotFoundError(f"የትርጉም ቁጥር {version_number} አልተገኘም (Version {version_number} not found)")

        full_path = storage_provider.get_full_path(version.storage_path)
        if not os.path.exists(full_path):
            raise FilePayloadMissingError("Historical payload missing on disk")

        return file_item, version, full_path

    @classmethod
    def revert_to_version(
        cls,
        db: Session,
        org_id: uuid.UUID,
        file_id: uuid.UUID,
        target_version_number: int,
        actor: User,
    ) -> FileItemResponse:
        """
        Reverts document to historical version target_version_number.
        Creates a new version N+1 reusing the exact payload of the target version (zero storage duplication).
        Enforces write lockdown and concurrency lock.
        """
        CapabilityService.verify_organization_write_access(db, org_id)

        file_item = StorageService.get_item(db, org_id, file_id, actor)
        if file_item.is_folder:
            raise VersionDomainError("Folders cannot be reverted")

        # Verify Lock Concurrency
        cls.verify_write_lock(db, file_item, actor)

        target_version = db.query(FileVersion).filter(
            FileVersion.file_id == file_item.id,
            FileVersion.version_number == target_version_number,
        ).first()

        if not target_version:
            raise VersionNotFoundError(f"የትርጉም ቁጥር {target_version_number} አልተገኘም")

        max_v = db.query(func.coalesce(func.max(FileVersion.version_number), 0)).filter(
            FileVersion.file_id == file_item.id
        ).scalar()
        next_v = max_v + 1

        new_version = FileVersion(
            file_id=file_item.id,
            version_number=next_v,
            storage_path=target_version.storage_path,
            checksum_sha256=target_version.checksum_sha256,
            size_bytes=target_version.size_bytes,
            created_by_id=actor.id,
            change_summary=f"Reverted to Version {target_version_number}",
        )
        db.add(new_version)
        db.flush()

        file_item.current_version_id = new_version.id
        file_item.size_bytes = target_version.size_bytes
        file_item.updated_at = datetime.now(timezone.utc)

        audit = AuditLog(
            organization_id=org_id,
            user_id=actor.id,
            action=AuditAction.UPLOAD,
            target_type="FILE",
            target_id=file_item.id,
            target_name=file_item.name,
            details={
                "action": "VERSION_REVERT",
                "reverted_to": target_version_number,
                "new_version": next_v,
            }
        )
        db.add(audit)
        db.commit()
        db.refresh(file_item)

        return StorageService.to_file_response(db, file_item)
