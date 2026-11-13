"""
EthioOffice Storage & Hierarchy Domain Service
Implements the Storage Repository Pattern, streamed chunk I/O, SHA-256 CAS deduplication,
hierarchical breadcrumb path resolution, cycle-safe directory moves, and cascading trash lifecycles.
"""

import os
import abc
import uuid
import hashlib
from datetime import datetime, timezone
from typing import Optional, List, Tuple, BinaryIO, Set
from collections import deque
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.config import settings
from app.models.file import FileItem, FileVersion, DriveType
from app.models.user import User, UserRole
from app.models.department import Department
from app.models.audit import AuditLog, AuditAction
from app.services.tenant_service import TenantService, StorageQuotaExceededError
from app.services.capability_service import CapabilityService, LicenseReadOnlyLockdownError
from app.core.ethiopian_calendar import format_ethiopian_date
from app.schemas.file import (
    FileItemResponse,
    BreadcrumbItem,
    FileLockInfo,
)


# =====================================================================
# Domain Exceptions
# =====================================================================

class StorageDomainError(Exception):
    """Base exception for file storage operations."""
    pass


class FileItemNotFoundError(StorageDomainError):
    pass


class FolderCycleError(StorageDomainError):
    """Raised when moving a folder into itself or its own subfolder."""
    pass


class FileItemConflictError(StorageDomainError):
    """Raised when an item with the same name already exists in the folder."""
    pass


class DriveAccessDeniedError(StorageDomainError):
    pass


class FilePayloadMissingError(StorageDomainError):
    pass


# =====================================================================
# Storage Provider Abstraction
# =====================================================================

class StorageProvider(abc.ABC):
    @abc.abstractmethod
    def save_stream(self, stream: BinaryIO, org_id: uuid.UUID, filename: str) -> Tuple[str, str, int]:
        """
        Consumes stream, writes to storage, returns (rel_storage_path, sha256_checksum, size_bytes).
        """
        pass

    @abc.abstractmethod
    def open_stream(self, rel_storage_path: str) -> BinaryIO:
        pass

    @abc.abstractmethod
    def exists(self, rel_storage_path: str) -> bool:
        pass

    @abc.abstractmethod
    def delete_payload(self, rel_storage_path: str) -> bool:
        pass

    @abc.abstractmethod
    def get_full_path(self, rel_storage_path: str) -> str:
        pass


class LocalStorageProvider(StorageProvider):
    def __init__(self, root_dir: str):
        self.root_dir = os.path.abspath(root_dir)
        os.makedirs(self.root_dir, exist_ok=True)

    def save_stream(self, stream: BinaryIO, org_id: uuid.UUID, filename: str) -> Tuple[str, str, int]:
        org_dir = os.path.join(self.root_dir, str(org_id))
        os.makedirs(org_dir, exist_ok=True)

        temp_filename = f"temp_{uuid.uuid4().hex}.tmp"
        temp_path = os.path.join(org_dir, temp_filename)

        sha256 = hashlib.sha256()
        bytes_written = 0

        # Memory-capped 64KB streaming buffer
        with open(temp_path, "wb") as f_out:
            while True:
                chunk = stream.read(64 * 1024)
                if not chunk:
                    break
                sha256.update(chunk)
                f_out.write(chunk)
                bytes_written += len(chunk)

        checksum = sha256.hexdigest()
        ext = os.path.splitext(filename)[1].lower()
        final_filename = f"{uuid.uuid4().hex}{ext}"
        final_path = os.path.join(org_dir, final_filename)

        os.replace(temp_path, final_path)
        rel_path = os.path.relpath(final_path, self.root_dir)
        return rel_path, checksum, bytes_written

    def open_stream(self, rel_storage_path: str) -> BinaryIO:
        full_path = self.get_full_path(rel_storage_path)
        if not os.path.exists(full_path):
            raise FilePayloadMissingError("Physical file missing on server disk")
        return open(full_path, "rb")

    def exists(self, rel_storage_path: str) -> bool:
        return os.path.exists(self.get_full_path(rel_storage_path))

    def delete_payload(self, rel_storage_path: str) -> bool:
        full_path = self.get_full_path(rel_storage_path)
        if os.path.exists(full_path):
            os.remove(full_path)
            return True
        return False

    def get_full_path(self, rel_storage_path: str) -> str:
        return os.path.join(self.root_dir, rel_storage_path)


# Default provider instance
storage_provider = LocalStorageProvider(settings.STORAGE_ROOT)


# =====================================================================
# Domain Service
# =====================================================================

class StorageService:
    @classmethod
    def to_file_response(cls, db: Session, item: FileItem) -> FileItemResponse:
        """Converts ORM entity to API response model with calculated counts & lock status."""
        is_locked = False
        lock_info = None
        if item.lock and item.lock.expires_at > datetime.now(timezone.utc):
            is_locked = True
            lock_info = FileLockInfo(
                locked_by_name=item.lock.locked_by.full_name if item.lock.locked_by else "Colleague",
                locked_by_id=item.lock.locked_by_id,
                reason=item.lock.reason,
                expires_at=item.lock.expires_at,
            )

        subfolder_count = 0
        file_count = 0
        if item.is_folder:
            subfolder_count = db.query(FileItem).filter(
                FileItem.parent_id == item.id,
                FileItem.is_folder == True,
                FileItem.is_deleted == False
            ).count()
            file_count = db.query(FileItem).filter(
                FileItem.parent_id == item.id,
                FileItem.is_folder == False,
                FileItem.is_deleted == False
            ).count()

        ec_date = format_ethiopian_date(item.created_at.date()) if item.created_at else None

        return FileItemResponse(
            id=item.id,
            name=item.name,
            is_folder=item.is_folder,
            parent_id=item.parent_id,
            drive_type=item.drive_type.value if hasattr(item.drive_type, "value") else str(item.drive_type),
            mime_type=item.mime_type,
            size_bytes=item.size_bytes,
            owner_id=item.owner_id,
            owner_name=item.owner.full_name if item.owner else None,
            department_id=item.department_id,
            is_deleted=item.is_deleted,
            is_locked=is_locked,
            lock_info=lock_info,
            subfolder_count=subfolder_count,
            file_count=file_count,
            created_at=item.created_at,
            updated_at=item.updated_at,
            ec_created_at=ec_date,
        )

    @classmethod
    def get_item(
        cls,
        db: Session,
        org_id: uuid.UUID,
        item_id: uuid.UUID,
        user: User,
        include_deleted: bool = False,
    ) -> FileItem:
        """Retrieves an item with organization scoping and drive-level ownership checks."""
        query = db.query(FileItem).filter(
            FileItem.id == item_id,
            FileItem.organization_id == org_id,
        )
        if not include_deleted:
            query = query.filter(FileItem.is_deleted == False)

        item = query.first()
        if not item:
            raise FileItemNotFoundError("ፋይሉ ወይም ፎልደሩ አልተገኘም (File or folder not found)")

        # Personal Drive Access Verification
        if item.drive_type == DriveType.PERSONAL:
            if item.owner_id != user.id and not user.is_superuser:
                raise DriveAccessDeniedError("የግል ድራይቭ ፋይልን የማየት ፈቃድ የለዎትም (Access denied: Personal drive item belongs to another user)")

        return item

    @classmethod
    def list_items(
        cls,
        db: Session,
        org_id: uuid.UUID,
        user: User,
        drive_type: str = "PERSONAL",
        parent_id: Optional[uuid.UUID] = None,
        department_id: Optional[uuid.UUID] = None,
        search: Optional[str] = None,
    ) -> List[FileItemResponse]:
        """Lists directory items scoped by drive partition and user role."""
        query = db.query(FileItem).filter(FileItem.organization_id == org_id)

        if drive_type.upper() == "TRASH":
            query = query.filter(FileItem.is_deleted == True)
            if user.role == UserRole.STAFF and not user.is_superuser:
                query = query.filter(FileItem.deleted_by_id == user.id)
        else:
            query = query.filter(FileItem.is_deleted == False)
            if drive_type.upper() == "PERSONAL":
                query = query.filter(
                    FileItem.drive_type == DriveType.PERSONAL,
                    FileItem.owner_id == user.id
                )
            elif drive_type.upper() == "COMPANY":
                query = query.filter(FileItem.drive_type == DriveType.COMPANY)
                if department_id:
                    query = query.filter(FileItem.department_id == department_id)

            if search and search.strip():
                query = query.filter(FileItem.name.ilike(f"%{search.strip()}%"))
            else:
                if parent_id:
                    query = query.filter(FileItem.parent_id == parent_id)
                else:
                    query = query.filter(FileItem.parent_id == None)

        items = query.order_by(FileItem.is_folder.desc(), FileItem.name.asc()).all()
        return [cls.to_file_response(db, i) for i in items]

    @classmethod
    def create_folder(
        cls,
        db: Session,
        org_id: uuid.UUID,
        user: User,
        name: str,
        parent_id: Optional[uuid.UUID] = None,
        drive_type: str = "PERSONAL",
        department_id: Optional[uuid.UUID] = None,
    ) -> FileItemResponse:
        """Creates a directory with write lockdown enforcement, parent validation, and duplicate checks."""
        # Module 3 Enterprise Write Lockdown check
        CapabilityService.verify_organization_write_access(db, org_id)

        clean_name = name.strip()
        drive_enum = DriveType.COMPANY if drive_type.upper() == "COMPANY" else DriveType.PERSONAL

        # Validate parent folder if specified
        if parent_id:
            parent = cls.get_item(db, org_id, parent_id, user)
            if not parent.is_folder:
                raise StorageDomainError("የተመረጠው ወላጅ አቃፊ (Parent) ፎልደር አይደለም (Target parent is not a folder)")
            drive_enum = parent.drive_type
            department_id = parent.department_id

        # Check duplicate name within the parent
        existing = db.query(FileItem).filter(
            FileItem.organization_id == org_id,
            FileItem.parent_id == parent_id,
            FileItem.name == clean_name,
            FileItem.is_deleted == False,
        )
        if drive_enum == DriveType.PERSONAL:
            existing = existing.filter(FileItem.owner_id == user.id)
        if existing.first():
            raise FileItemConflictError(f"በዚህ አቃፊ ውስጥ '{clean_name}' የተባለ ፋይል ወይም ፎልደር አለ (An item named '{clean_name}' already exists in this folder)")

        folder = FileItem(
            organization_id=org_id,
            name=clean_name,
            is_folder=True,
            parent_id=parent_id,
            drive_type=drive_enum,
            owner_id=user.id,
            department_id=department_id,
        )
        db.add(folder)
        db.flush()

        audit = AuditLog(
            organization_id=org_id,
            user_id=user.id,
            action=AuditAction.UPLOAD,
            target_type="FOLDER",
            target_id=folder.id,
            target_name=folder.name,
            details={"drive_type": drive_enum.value, "parent_id": str(parent_id) if parent_id else None}
        )
        db.add(audit)
        db.commit()
        db.refresh(folder)

        return cls.to_file_response(db, folder)

    @classmethod
    def upload_file_stream(
        cls,
        db: Session,
        org_id: uuid.UUID,
        user: User,
        stream: BinaryIO,
        filename: str,
        content_type: Optional[str] = None,
        parent_id: Optional[uuid.UUID] = None,
        drive_type: str = "PERSONAL",
        department_id: Optional[uuid.UUID] = None,
    ) -> FileItemResponse:
        """
        Uploads document using 64KB memory-capped chunked streaming, computes SHA-256 on the fly,
        enforces CAS deduplication, and records quota usage atomically.
        """
        # Module 3 Enterprise Write Lockdown check
        CapabilityService.verify_organization_write_access(db, org_id)

        clean_filename = filename.strip()
        drive_enum = DriveType.COMPANY if drive_type.upper() == "COMPANY" else DriveType.PERSONAL

        if parent_id:
            parent = cls.get_item(db, org_id, parent_id, user)
            if not parent.is_folder:
                raise StorageDomainError("የተመረጠው ወላጅ አቃፊ (Parent) ፎልደር አይደለም")
            drive_enum = parent.drive_type
            department_id = parent.department_id

        # 1. Stream payload to storage and calculate SHA-256
        rel_storage_path, sha256_checksum, size_bytes = storage_provider.save_stream(stream, org_id, clean_filename)

        # 2. Check maximum upload size
        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if size_bytes > max_bytes:
            storage_provider.delete_payload(rel_storage_path)
            raise StorageDomainError(f"የፋይሉ መጠን ከተፈቀደው {settings.MAX_UPLOAD_SIZE_MB}MB በላይ ነው (File exceeds max limit)")

        # 3. Check storage quota budget
        try:
            TenantService.check_storage_budget(db, org_id, size_bytes, dept_id=department_id)
        except StorageQuotaExceededError as e:
            storage_provider.delete_payload(rel_storage_path)
            raise e

        # 4. Content-Addressable Storage (CAS) Deduplication
        # Check if identical payload already exists for this organization
        existing_version = db.query(FileVersion).join(FileItem).filter(
            FileItem.organization_id == org_id,
            FileVersion.checksum_sha256 == sha256_checksum,
            FileVersion.size_bytes == size_bytes,
        ).first()

        is_deduplicated = False
        if existing_version and storage_provider.exists(existing_version.storage_path):
            # Payload already exists: remove duplicate disk file and reuse existing storage path!
            storage_provider.delete_payload(rel_storage_path)
            rel_storage_path = existing_version.storage_path
            is_deduplicated = True

        # 5. Create or version FileItem
        file_item = FileItem(
            organization_id=org_id,
            name=clean_filename,
            is_folder=False,
            parent_id=parent_id,
            drive_type=drive_enum,
            owner_id=user.id,
            department_id=department_id,
            mime_type=content_type or "application/octet-stream",
            size_bytes=size_bytes,
        )
        db.add(file_item)
        db.flush()

        version = FileVersion(
            file_id=file_item.id,
            version_number=1,
            storage_path=rel_storage_path,
            checksum_sha256=sha256_checksum,
            size_bytes=size_bytes,
            created_by_id=user.id,
            change_summary="Initial upload (CAS Deduplicated)" if is_deduplicated else "Initial upload",
        )
        db.add(version)
        db.flush()

        file_item.current_version_id = version.id

        # 6. Record storage quota change
        TenantService.record_storage_change(db, org_id, size_bytes, dept_id=department_id)

        # 7. Audit log
        audit = AuditLog(
            organization_id=org_id,
            user_id=user.id,
            action=AuditAction.UPLOAD,
            target_type="FILE",
            target_id=file_item.id,
            target_name=file_item.name,
            details={
                "size_bytes": size_bytes,
                "sha256": sha256_checksum,
                "deduplicated": is_deduplicated,
                "drive_type": drive_enum.value
            }
        )
        db.add(audit)
        db.commit()
        db.refresh(file_item)

        return cls.to_file_response(db, file_item)

    @classmethod
    def get_breadcrumbs(cls, db: Session, org_id: uuid.UUID, item_id: uuid.UUID) -> List[BreadcrumbItem]:
        """Walks up ancestor pointers to compute the hierarchical breadcrumbs path."""
        breadcrumbs: List[BreadcrumbItem] = []
        current_id: Optional[uuid.UUID] = item_id

        visited: Set[uuid.UUID] = set()
        while current_id:
            if current_id in visited:
                break  # Protect against legacy corrupt cycles
            visited.add(current_id)

            item = db.query(FileItem).filter(FileItem.id == current_id, FileItem.organization_id == org_id).first()
            if not item:
                break

            breadcrumbs.append(BreadcrumbItem(id=item.id, name=item.name, is_folder=item.is_folder))
            current_id = item.parent_id

        breadcrumbs.reverse()
        return breadcrumbs

    @classmethod
    def move_item(
        cls,
        db: Session,
        org_id: uuid.UUID,
        item_id: uuid.UUID,
        new_parent_id: Optional[uuid.UUID],
        actor: User
    ) -> FileItemResponse:
        """
        Moves an item to another parent folder with strict Anti-Loop / Cycle detection.
        Prevents moving a folder into itself or any of its descendant children.
        """
        CapabilityService.verify_organization_write_access(db, org_id)

        item = cls.get_item(db, org_id, item_id, actor)

        if new_parent_id:
            if new_parent_id == item.id:
                raise FolderCycleError("አቃፊን ወደ ራሱ ማንቀሳቀስ አይቻልም (Cannot move a folder into itself)")

            new_parent = cls.get_item(db, org_id, new_parent_id, actor)
            if not new_parent.is_folder:
                raise StorageDomainError("የተመረጠው ወላጅ አቃፊ (Parent) ፎልደር አይደለም")

            # Cycle Detection: Walk up ancestors of target folder to ensure item is not in the ancestor path
            curr = new_parent
            while curr:
                if curr.id == item.id:
                    raise FolderCycleError("አቃፊን ወደ ራሱ ንዑስ ቅርንጫፍ ማንቀሳቀስ አይቻልም (Cycle detected: Cannot move a folder into its own descendant subfolder)")
                curr = curr.parent if curr.parent_id else None

            # Enforce drive type consistency
            item.drive_type = new_parent.drive_type
            item.department_id = new_parent.department_id

        item.parent_id = new_parent_id

        audit = AuditLog(
            organization_id=org_id,
            user_id=actor.id,
            action=AuditAction.UPLOAD,
            target_type="FOLDER" if item.is_folder else "FILE",
            target_id=item.id,
            target_name=item.name,
            details={"action": "MOVE", "new_parent_id": str(new_parent_id) if new_parent_id else None}
        )
        db.add(audit)
        db.commit()
        db.refresh(item)

        resp = cls.to_file_response(db, item)
        resp.breadcrumbs = cls.get_breadcrumbs(db, org_id, item.id)
        return resp

    @classmethod
    def rename_item(
        cls,
        db: Session,
        org_id: uuid.UUID,
        item_id: uuid.UUID,
        new_name: str,
        actor: User
    ) -> FileItemResponse:
        """Renames an item with duplicate checking within the parent."""
        CapabilityService.verify_organization_write_access(db, org_id)

        clean_name = new_name.strip()
        item = cls.get_item(db, org_id, item_id, actor)

        # Duplicate check under same parent
        existing = db.query(FileItem).filter(
            FileItem.organization_id == org_id,
            FileItem.parent_id == item.parent_id,
            FileItem.name == clean_name,
            FileItem.id != item.id,
            FileItem.is_deleted == False,
        ).first()

        if existing:
            raise FileItemConflictError(f"በዚህ አቃፊ ውስጥ በተመሳሳይ ስም '{clean_name}' የተመዘገበ ፋይል አለ")

        old_name = item.name
        item.name = clean_name

        audit = AuditLog(
            organization_id=org_id,
            user_id=actor.id,
            action=AuditAction.UPLOAD,
            target_type="FOLDER" if item.is_folder else "FILE",
            target_id=item.id,
            target_name=item.name,
            details={"action": "RENAME", "old_name": old_name, "new_name": clean_name}
        )
        db.add(audit)
        db.commit()
        db.refresh(item)

        return cls.to_file_response(db, item)

    @classmethod
    def _collect_descendant_ids(cls, db: Session, org_id: uuid.UUID, root_id: uuid.UUID) -> List[FileItem]:
        """BFS traversal to collect all items in a folder subtree."""
        collected: List[FileItem] = []
        queue = deque([root_id])

        while queue:
            current_parent = queue.popleft()
            children = db.query(FileItem).filter(
                FileItem.organization_id == org_id,
                FileItem.parent_id == current_parent
            ).all()

            for child in children:
                collected.append(child)
                if child.is_folder:
                    queue.append(child.id)

        return collected

    @classmethod
    def soft_delete_item(
        cls,
        db: Session,
        org_id: uuid.UUID,
        item_id: uuid.UUID,
        actor: User
    ) -> int:
        """
        Moves item to Recycle Bin with Cascading Soft-Delete:
        If target is a folder, all descendant files and subfolders are also marked deleted.
        """
        CapabilityService.verify_organization_write_access(db, org_id)

        root = cls.get_item(db, org_id, item_id, actor)
        now = datetime.now(timezone.utc)

        root.is_deleted = True
        root.deleted_at = now
        root.deleted_by_id = actor.id

        affected_count = 1
        if root.is_folder:
            descendants = cls._collect_descendant_ids(db, org_id, root.id)
            for d in descendants:
                d.is_deleted = True
                d.deleted_at = now
                d.deleted_by_id = actor.id
                affected_count += 1

        audit = AuditLog(
            organization_id=org_id,
            user_id=actor.id,
            action=AuditAction.DELETE,
            target_type="FOLDER" if root.is_folder else "FILE",
            target_id=root.id,
            target_name=root.name,
            details={"cascaded_count": affected_count}
        )
        db.add(audit)
        db.commit()
        return affected_count

    @classmethod
    def restore_item(
        cls,
        db: Session,
        org_id: uuid.UUID,
        item_id: uuid.UUID,
        actor: User
    ) -> int:
        """
        Restores an item from Recycle Bin with Cascading Restore:
        Restores root and all its descendant items.
        """
        CapabilityService.verify_organization_write_access(db, org_id)

        root = cls.get_item(db, org_id, item_id, actor, include_deleted=True)
        if not root.is_deleted:
            return 0

        root.is_deleted = False
        root.deleted_at = None
        root.deleted_by_id = None

        restored_count = 1
        if root.is_folder:
            descendants = cls._collect_descendant_ids(db, org_id, root.id)
            for d in descendants:
                d.is_deleted = False
                d.deleted_at = None
                d.deleted_by_id = None
                restored_count += 1

        audit = AuditLog(
            organization_id=org_id,
            user_id=actor.id,
            action=AuditAction.UPLOAD,
            target_type="FOLDER" if root.is_folder else "FILE",
            target_id=root.id,
            target_name=root.name,
            details={"action": "RESTORE_FROM_TRASH", "restored_count": restored_count}
        )
        db.add(audit)
        db.commit()
        return restored_count

    @classmethod
    def purge_item(
        cls,
        db: Session,
        org_id: uuid.UUID,
        item_id: uuid.UUID,
        actor: User
    ) -> int:
        """
        Permanently purges an item from the database and physically deletes file payload
        if no other record references the same storage payload. Reclaims tenant quota.
        """
        CapabilityService.verify_organization_write_access(db, org_id)

        root = cls.get_item(db, org_id, item_id, actor, include_deleted=True)

        items_to_delete = [root]
        if root.is_folder:
            items_to_delete.extend(cls._collect_descendant_ids(db, org_id, root.id))

        total_freed_bytes = 0

        # Purge leaves first, then folders
        for item in reversed(items_to_delete):
            if not item.is_folder:
                for version in item.versions:
                    # Check if any other FileVersion references the exact same physical storage path
                    other_refs = db.query(FileVersion).filter(
                        FileVersion.storage_path == version.storage_path,
                        FileVersion.id != version.id
                    ).count()

                    if other_refs == 0:
                        storage_provider.delete_payload(version.storage_path)

                total_freed_bytes += item.size_bytes

            db.delete(item)

        # Reclaim quota from organization and department
        if total_freed_bytes > 0:
            TenantService.record_storage_change(db, org_id, -total_freed_bytes, dept_id=root.department_id)

        audit = AuditLog(
            organization_id=org_id,
            user_id=actor.id,
            action=AuditAction.DELETE,
            target_type="FOLDER" if root.is_folder else "FILE",
            target_id=root.id,
            target_name=root.name,
            details={"action": "PERMANENT_PURGE", "freed_bytes": total_freed_bytes}
        )
        db.add(audit)
        db.commit()
        return total_freed_bytes
