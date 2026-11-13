import uuid
from datetime import datetime, date, timedelta, timezone
from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.core.ethiopian_calendar import format_ethiopian_date
from app.models import (
    Organization,
    License,
    LicenseTier,
    User,
    UserRole,
    Department,
    UserDepartment,
    FileItem,
    DriveType,
    LetterRegistry,
    LetterDirection,
    LetterStatus,
    Tag,
)


def seed_database():
    db = SessionLocal()
    try:
        # Check if already seeded
        existing_org = db.query(Organization).filter_by(slug="abyssinia").first()
        if existing_org:
            print("Database already contains demo organization 'abyssinia'. Skipping seed.")
            return

        print("Seeding EthioOffice commercial database with initial demo data...")

        # 1. Organization
        org = Organization(
            name="Abyssinia Commercial Enterprise",
            slug="abyssinia",
            tin_number="0078945612",
            theme_color="#059669",
            max_users=100,
            storage_limit_bytes=250 * 1024 * 1024 * 1024,  # 250 GB
        )
        db.add(org)
        db.flush()

        # 2. Commercial License
        license_record = License(
            organization_id=org.id,
            license_key="EO-COMMERCIAL-2026-ABYSSINIA-ENTERPRISE-KEY-9988",
            tier=LicenseTier.ENTERPRISE,
            max_users=100,
            storage_limit_bytes=250 * 1024 * 1024 * 1024,
            expires_at=datetime.now(timezone.utc) + timedelta(days=365),
            is_active=True,
        )
        db.add(license_record)

        # 3. Departments
        dept_finance = Department(
            organization_id=org.id,
            name="ፋይናንስና ሒሳብ (Finance & Accounting)",
            code="FIN",
            description="የድርጅቱ የፋይናንስና የግብር ጉዳዮች ክፍል",
        )
        dept_hr = Department(
            organization_id=org.id,
            name="የሰው ኃይል ልማት (Human Resources)",
            code="HR",
            description="የሠራተኞች ምልመላና አስተዳደር",
        )
        dept_ops = Department(
            organization_id=org.id,
            name="ኦፕሬሽንስና ሎጂስቲክስ (Operations & Logistics)",
            code="OPS",
            description="የዕለት ተዕለት የሥራ እንቅስቃሴና አቅርቦት",
        )
        db.add_all([dept_finance, dept_hr, dept_ops])
        db.flush()

        # 4. Users
        admin_user = User(
            organization_id=org.id,
            email="admin@abyssinia.et",
            full_name="ሙሉጌታ አስፋው (Mulugeta Asfaw)",
            hashed_password=get_password_hash("Admin123!"),
            role=UserRole.ADMIN,
            is_active=True,
        )
        staff_user = User(
            organization_id=org.id,
            email="abebe@abyssinia.et",
            full_name="አበበ በቀለ (Abebe Bekele)",
            hashed_password=get_password_hash("Staff123!"),
            role=UserRole.STAFF,
            is_active=True,
        )
        db.add_all([admin_user, staff_user])
        db.flush()

        # 5. Department Memberships
        user_dept_1 = UserDepartment(
            user_id=admin_user.id,
            department_id=dept_finance.id,
            is_department_lead=True,
        )
        user_dept_2 = UserDepartment(
            user_id=staff_user.id,
            department_id=dept_ops.id,
            is_department_lead=False,
        )
        db.add_all([user_dept_1, user_dept_2])

        # 6. Sample Company Drive Folders
        company_folder_1 = FileItem(
            organization_id=org.id,
            name="የኩባንያ ደንቦችና መመሪያዎች (Policies & Guidelines)",
            is_folder=True,
            drive_type=DriveType.COMPANY,
            owner_id=admin_user.id,
            department_id=dept_hr.id,
        )
        company_folder_2 = FileItem(
            organization_id=org.id,
            name="የ2019 የሒሳብ ዓመት ሪፖርቶች (Fiscal Year 2019 Reports)",
            is_folder=True,
            drive_type=DriveType.COMPANY,
            owner_id=admin_user.id,
            department_id=dept_finance.id,
        )
        personal_folder = FileItem(
            organization_id=org.id,
            name="የግል ማስታወሻዎች (My Notes)",
            is_folder=True,
            drive_type=DriveType.PERSONAL,
            owner_id=staff_user.id,
        )
        db.add_all([company_folder_1, company_folder_2, personal_folder])

        # 7. Sample Tags
        tag_confidential = Tag(
            organization_id=org.id,
            name="ምስጢራዊ (Confidential)",
            color="#ef4444",
        )
        tag_tax = Tag(
            organization_id=org.id,
            name="ግብር 2019 (Tax 2019)",
            color="#10b981",
        )
        db.add_all([tag_confidential, tag_tax])

        # 8. Sample Letter Registry (የደብዳቤ መዝገብ)
        today = date.today()
        ec_date_str = format_ethiopian_date(today)
        sample_letter = LetterRegistry(
            organization_id=org.id,
            reference_number="ABYSS/FIN/2019/001",
            direction=LetterDirection.INWARD,
            status=LetterStatus.RECEIVED,
            subject="የዓመታዊ ግብር ስሌት ማሳሰቢያ ከገቢዎች ሚኒስቴር",
            sender_entity="የገቢዎች ሚኒስቴር (Ministry of Revenues)",
            recipient_entity="አቢሲንያ ኮሜርሻል ኢንተርፕራይዝ - ፋይናንስ ክፍል",
            date_ec=ec_date_str,
            date_gc=today,
            created_by_id=admin_user.id,
            assigned_to_id=admin_user.id,
            notes="በወቅቱ ምላሽ ተዘጋጅቶ እንዲላክ የተሰጠ ትዕዛዝ።",
        )
        db.add(sample_letter)

        db.commit()
        print("SUCCESS! Seeded initial organization, admin/staff users, departments, folders, and letter registry.")
        print("Login credentials:")
        print("  Admin: admin@abyssinia.et / Admin123!")
        print("  Staff: abebe@abyssinia.et / Staff123!")

    except Exception as e:
        db.rollback()
        print("Error during database seed:", e)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
