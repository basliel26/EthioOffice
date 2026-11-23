#!/usr/bin/env python3
"""
Cleanup script to purge all mock and test-generated document files and folders.
Leaves user accounts, organization, departments, licenses, and letter registry intact.
Resets storage quota counters and storage directory.
"""

import os
import shutil
from pathlib import Path

# Add backend directory to path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.database import SessionLocal
from app.models.file import FileItem, FileVersion, DriveType
from app.models.lock import FileLock
from app.models.share import FileShare
from app.models.eurooffice import EuroOfficeSession
from app.models.audit import AuditLog
from app.models.organization import Organization
from app.models.department import Department
from app.models.user import User

def cleanup_mock_data():
    db = SessionLocal()
    try:
        print("[*] Starting cleanup of mock document files and folders...")

        # 1. Clear foreign-key child tables first
        num_sessions = db.query(EuroOfficeSession).delete()
        print(f"    - Deleted {num_sessions} EuroOffice session records.")

        num_locks = db.query(FileLock).delete()
        print(f"    - Deleted {num_locks} file lock records.")

        num_shares = db.query(FileShare).delete()
        print(f"    - Deleted {num_shares} file share records.")

        # Break circular FK between FileItem and FileVersion before deleting
        db.query(FileItem).update({FileItem.current_version_id: None})
        db.commit()

        num_versions = db.query(FileVersion).delete()
        print(f"    - Deleted {num_versions} file version records.")

        num_files = db.query(FileItem).delete()
        print(f"    - Deleted {num_files} document files and folders.")

        # 2. Reset storage used bytes on Organization and Departments
        db.query(Organization).update({Organization.used_storage_bytes: 0})
        db.query(Department).update({Department.used_storage_bytes: 0})

        # 3. Re-create the 3 clean default base folders
        admin_user = db.query(User).filter_by(email="admin@abyssinia.et").first() or db.query(User).first()
        staff_user = db.query(User).filter_by(email="abebe@abyssinia.et").first() or admin_user
        org = db.query(Organization).filter_by(slug="abyssinia").first() or db.query(Organization).filter_by(slug="wine-technologies").first() or db.query(Organization).first()
        dept_hr = db.query(Department).filter_by(code="HR").first()
        dept_fin = db.query(Department).filter_by(code="FIN").first()

        if org and admin_user:
            folder1 = FileItem(
                organization_id=org.id,
                name="የኩባንያ ደንቦችና መመሪያዎች (Policies & Guidelines)",
                is_folder=True,
                drive_type=DriveType.COMPANY,
                owner_id=admin_user.id,
                department_id=dept_hr.id if dept_hr else None,
            )
            folder2 = FileItem(
                organization_id=org.id,
                name="የ2019 የሒሳብ ዓመት ሪፖርቶች (Fiscal Year 2019 Reports)",
                is_folder=True,
                drive_type=DriveType.COMPANY,
                owner_id=admin_user.id,
                department_id=dept_fin.id if dept_fin else None,
            )
            personal_folder = FileItem(
                organization_id=org.id,
                name="የግል ማስታወሻዎች (My Notes)",
                is_folder=True,
                drive_type=DriveType.PERSONAL,
                owner_id=staff_user.id if staff_user else admin_user.id,
            )
            db.add_all([folder1, folder2, personal_folder])
            print("    [+] Re-created clean 3 root folders (Policies, Reports, Notes).")

        db.commit()

        # 4. Clear physical files in storage_data directory
        storage_dir = Path(__file__).resolve().parent / "storage_data"
        if storage_dir.exists():
            deleted_files = 0
            for item in storage_dir.iterdir():
                if item.is_file():
                    item.unlink()
                    deleted_files += 1
                elif item.is_dir():
                    shutil.rmtree(item)
                    deleted_files += 1
            print(f"    - Cleared {deleted_files} physical items from {storage_dir}")

        print("\n[SUCCESS] Mock documents cleanup complete! Drive is now clean and empty.")

    except Exception as e:
        db.rollback()
        print(f"[ERROR] Cleanup failed: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    cleanup_mock_data()
