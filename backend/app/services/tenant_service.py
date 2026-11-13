import uuid
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.models.organization import Organization, OrganizationStatus, License, LicenseTier
from app.models.department import Department, UserDepartment
from app.models.user import User, UserRole
from app.models.file import FileItem, DriveType
from app.models.audit import AuditLog, AuditAction
from app.core.security import get_password_hash
from app.schemas.tenant import (
    OrganizationUpdate,
    DepartmentCreate,
    DepartmentUpdate,
    DepartmentResponse,
    DepartmentMemberResponse,
    StorageQuotaResponse,
    TenantBrandingPublicResponse,
    TenantProvisionRequest,
    TenantProvisionResponse,
)


class TenantNotFoundError(Exception):
    pass


class TenantSuspendedError(Exception):
    pass


class DepartmentConflictError(Exception):
    pass


class DepartmentNotFoundError(Exception):
    pass


class DepartmentHierarchyError(Exception):
    pass


class StorageQuotaExceededError(Exception):
    pass


class CrossTenantAccessError(Exception):
    pass


class TenantService:
    @classmethod
    def get_organization(cls, db: Session, org_id: uuid.UUID) -> Organization:
        org = db.query(Organization).filter(Organization.id == org_id).first()
        if not org:
            raise TenantNotFoundError("ድርጅቱ አልተገኘም (Organization not found)")
        return org

    @classmethod
    def get_branding_by_slug(cls, db: Session, slug: str) -> TenantBrandingPublicResponse:
        """
        Public pre-login branding resolution for custom subdomains or portal URLs.
        """
        org = db.query(Organization).filter(Organization.slug == slug.lower().strip()).first()
        if not org:
            raise TenantNotFoundError("ድርጅቱ አልተገኘም (Organization not found)")

        return TenantBrandingPublicResponse(
            name=org.name,
            slug=org.slug,
            logo_url=org.logo_url,
            theme_color=org.theme_color,
            is_active=org.is_active,
            status=org.status.value if hasattr(org.status, "value") else str(org.status)
        )

    @classmethod
    def update_organization(
        cls,
        db: Session,
        org_id: uuid.UUID,
        payload: OrganizationUpdate,
        actor: User
    ) -> Organization:
        org = cls.get_organization(db, org_id)

        changes = {}
        if payload.name is not None and payload.name.strip():
            changes["name"] = {"old": org.name, "new": payload.name.strip()}
            org.name = payload.name.strip()
        if payload.tin_number is not None:
            changes["tin_number"] = {"old": org.tin_number, "new": payload.tin_number}
            org.tin_number = payload.tin_number
        if payload.logo_url is not None:
            changes["logo_url"] = {"old": org.logo_url, "new": payload.logo_url}
            org.logo_url = payload.logo_url
        if payload.theme_color is not None:
            changes["theme_color"] = {"old": org.theme_color, "new": payload.theme_color}
            org.theme_color = payload.theme_color
        if payload.status is not None:
            changes["status"] = {"old": str(org.status), "new": payload.status}
            org.status = OrganizationStatus(payload.status)

        if changes:
            audit = AuditLog(
                organization_id=org.id,
                user_id=actor.id,
                action=AuditAction.LETTER_REGISTER,
                target_type="ORGANIZATION",
                target_id=org.id,
                target_name=org.name,
                details={"updated_fields": changes}
            )
            db.add(audit)
            db.commit()
            db.refresh(org)

        return org

    @classmethod
    def get_storage_quota(cls, db: Session, org_id: uuid.UUID) -> StorageQuotaResponse:
        org = cls.get_organization(db, org_id)
        limit = org.storage_limit_bytes
        used = org.used_storage_bytes

        percent = round((used / limit * 100), 2) if limit > 0 else 100.0
        used_gb = round(used / (1024 ** 3), 3)
        limit_gb = round(limit / (1024 ** 3), 2)

        return StorageQuotaResponse(
            used_bytes=used,
            limit_bytes=limit,
            used_gb=used_gb,
            limit_gb=limit_gb,
            percent_used=percent,
            is_warning=percent >= 80.0,
            is_exceeded=used >= limit,
        )

    @classmethod
    def check_storage_budget(cls, db: Session, org_id: uuid.UUID, incoming_bytes: int, dept_id: Optional[uuid.UUID] = None) -> None:
        org = cls.get_organization(db, org_id)
        
        # 1. Check organization-wide storage budget
        if org.used_storage_bytes + incoming_bytes > org.storage_limit_bytes:
            raise StorageQuotaExceededError(
                f"የድርጅቱ የማከማቻ ቦታ ሞልቷል (Organization storage quota exceeded: "
                f"Requires {incoming_bytes} bytes, limit is {org.storage_limit_bytes} bytes)"
            )

        # 2. Check department-specific quota if configured
        if dept_id:
            dept = db.query(Department).filter(Department.id == dept_id, Department.organization_id == org_id).first()
            if dept and dept.storage_quota_bytes is not None:
                if dept.used_storage_bytes + incoming_bytes > dept.storage_quota_bytes:
                    raise StorageQuotaExceededError(
                        f"የሥራ ክፍሉ የተመደበለት ማከማቻ ሞልቷል (Department '{dept.name}' storage quota exceeded: "
                        f"Requires {incoming_bytes} bytes, limit is {dept.storage_quota_bytes} bytes)"
                    )

    @classmethod
    def record_storage_change(cls, db: Session, org_id: uuid.UUID, byte_delta: int, dept_id: Optional[uuid.UUID] = None) -> int:
        org = cls.get_organization(db, org_id)
        org.used_storage_bytes = max(0, org.used_storage_bytes + byte_delta)
        
        if dept_id:
            dept = db.query(Department).filter(Department.id == dept_id, Department.organization_id == org_id).first()
            if dept:
                dept.used_storage_bytes = max(0, dept.used_storage_bytes + byte_delta)
                
        db.commit()
        return org.used_storage_bytes

    @classmethod
    def create_department(
        cls,
        db: Session,
        org_id: uuid.UUID,
        payload: DepartmentCreate,
        actor: User
    ) -> Department:
        # Check uniqueness within the organization
        existing = db.query(Department).filter(
            Department.organization_id == org_id,
            (Department.name == payload.name.strip()) | (Department.code == payload.code.strip())
        ).first()

        if existing:
            raise DepartmentConflictError(
                f"በዚህ ድርጅት ውስጥ በተመሳሳይ ስም ወይም ኮድ የተመዘገበ ክፍል አለ (Department with code '{payload.code}' or name '{payload.name}' already exists in this organization)"
            )

        # Validate parent department if provided (must belong to same org)
        if payload.parent_id:
            parent = db.query(Department).filter(
                Department.id == payload.parent_id,
                Department.organization_id == org_id
            ).first()
            if not parent:
                raise DepartmentNotFoundError("ዋናው የሥራ ክፍል አልተገኘም (Parent department not found)")

        quota_bytes = int(payload.storage_quota_gb * (1024 ** 3)) if payload.storage_quota_gb else None

        dept = Department(
            organization_id=org_id,
            parent_id=payload.parent_id,
            name=payload.name.strip(),
            code=payload.code.strip(),
            description=payload.description.strip() if payload.description else None,
            storage_quota_bytes=quota_bytes,
        )
        db.add(dept)
        db.flush()

        # Create root folder in Company Drive for this department automatically
        company_root = FileItem(
            organization_id=org_id,
            name=f"{dept.name} ({dept.code})",
            is_folder=True,
            drive_type=DriveType.COMPANY,
            department_id=dept.id,
            owner_id=actor.id,
        )
        db.add(company_root)

        audit = AuditLog(
            organization_id=org_id,
            user_id=actor.id,
            action=AuditAction.UPLOAD,
            target_type="DEPARTMENT",
            target_id=dept.id,
            target_name=dept.name,
            details={"code": dept.code, "parent_id": str(payload.parent_id) if payload.parent_id else None}
        )
        db.add(audit)
        db.commit()
        db.refresh(dept)
        return dept

    @classmethod
    def list_departments(cls, db: Session, org_id: uuid.UUID) -> List[DepartmentResponse]:
        departments = db.query(Department).filter(Department.organization_id == org_id).order_by(Department.name.asc()).all()
        
        result = []
        for d in departments:
            leads = [ud.user.full_name for ud in d.members if ud.is_department_lead and ud.user]
            subdept_count = db.query(Department).filter(Department.parent_id == d.id).count()
            
            quota_gb = round(d.storage_quota_bytes / (1024 ** 3), 2) if d.storage_quota_bytes else None
            used_gb = round(d.used_storage_bytes / (1024 ** 3), 3)
            percent = round((d.used_storage_bytes / d.storage_quota_bytes * 100), 1) if d.storage_quota_bytes else None

            result.append(
                DepartmentResponse(
                    id=d.id,
                    name=d.name,
                    code=d.code,
                    description=d.description,
                    parent_id=d.parent_id,
                    member_count=len(d.members),
                    subdepartment_count=subdept_count,
                    storage_quota_bytes=d.storage_quota_bytes,
                    used_storage_bytes=d.used_storage_bytes,
                    storage_quota_gb=quota_gb,
                    used_storage_gb=used_gb,
                    percent_used=percent,
                    leads=leads,
                    created_at=d.created_at
                )
            )
        return result

    @classmethod
    def assign_department_member(
        cls,
        db: Session,
        org_id: uuid.UUID,
        dept_id: uuid.UUID,
        user_id: uuid.UUID,
        is_lead: bool,
        actor: User
    ) -> UserDepartment:
        dept = db.query(Department).filter(Department.id == dept_id, Department.organization_id == org_id).first()
        if not dept:
            raise DepartmentNotFoundError("የሥራ ክፍሉ አልተገኘም (Department not found in this organization)")

        user = db.query(User).filter(User.id == user_id, User.organization_id == org_id).first()
        if not user:
            raise CrossTenantAccessError("ተጠቃሚው በዚህ ድርጅት ውስጥ አልተገኘም (User does not belong to this organization)")

        membership = db.query(UserDepartment).filter(
            UserDepartment.department_id == dept_id,
            UserDepartment.user_id == user_id
        ).first()

        if membership:
            membership.is_department_lead = is_lead
        else:
            membership = UserDepartment(
                department_id=dept_id,
                user_id=user_id,
                is_department_lead=is_lead
            )
            db.add(membership)

        audit = AuditLog(
            organization_id=org_id,
            user_id=actor.id,
            action=AuditAction.SHARE,
            target_type="DEPARTMENT_MEMBER",
            target_id=dept.id,
            target_name=f"{user.full_name} -> {dept.name}",
            details={"is_lead": is_lead}
        )
        db.add(audit)
        db.commit()
        db.refresh(membership)
        return membership

    @classmethod
    def list_department_members(cls, db: Session, org_id: uuid.UUID, dept_id: uuid.UUID) -> List[DepartmentMemberResponse]:
        dept = db.query(Department).filter(Department.id == dept_id, Department.organization_id == org_id).first()
        if not dept:
            raise DepartmentNotFoundError("የሥራ ክፍሉ አልተገኘም (Department not found)")

        return [
            DepartmentMemberResponse(
                user_id=ud.user.id,
                full_name=ud.user.full_name,
                email=ud.user.email,
                is_lead=ud.is_department_lead,
                joined_at=ud.joined_at
            )
            for ud in dept.members if ud.user
        ]

    @classmethod
    def remove_department_member(
        cls,
        db: Session,
        org_id: uuid.UUID,
        dept_id: uuid.UUID,
        user_id: uuid.UUID,
        actor: User
    ) -> bool:
        membership = db.query(UserDepartment).join(Department).filter(
            Department.organization_id == org_id,
            UserDepartment.department_id == dept_id,
            UserDepartment.user_id == user_id
        ).first()

        if not membership:
            return False

        db.delete(membership)
        audit = AuditLog(
            organization_id=org_id,
            user_id=actor.id,
            action=AuditAction.DELETE,
            target_type="DEPARTMENT_MEMBER",
            target_id=dept_id,
            target_name=f"User {user_id} removed from Dept {dept_id}"
        )
        db.add(audit)
        db.commit()
        return True

    @classmethod
    def provision_tenant(cls, db: Session, payload: TenantProvisionRequest) -> TenantProvisionResponse:
        """
        1-Click Enterprise Tenant Provisioning:
        - Checks slug uniqueness
        - Creates Organization
        - Binds Enterprise license
        - Creates Admin user with hashed password
        - Provisions standard Ethiopian departments (FIN, HR, OPS) and Company Drive folders
        - Logs audit event
        """
        existing_org = db.query(Organization).filter(Organization.slug == payload.slug).first()
        if existing_org:
            raise DepartmentConflictError(f"የተመረጠው የድርጅት መለያ ስም '{payload.slug}' አስቀድሞ ተይዟል (Slug already in use)")

        existing_user = db.query(User).filter(User.email == payload.admin_email.lower().strip()).first()
        if existing_user:
            raise DepartmentConflictError(f"የአስተዳዳሪው ኢሜይል '{payload.admin_email}' አስቀድሞ ተመዝግቧል (Admin email already exists)")

        storage_bytes = int(payload.storage_limit_gb * (1024 ** 3))

        # 1. Organization
        org = Organization(
            name=payload.organization_name.strip(),
            slug=payload.slug.strip().lower(),
            tin_number=payload.tin_number,
            max_users=payload.max_users,
            storage_limit_bytes=storage_bytes,
            status=OrganizationStatus.ACTIVE,
        )
        db.add(org)
        db.flush()

        # 2. Commercial License
        license_record = License(
            organization_id=org.id,
            license_key=f"EO-{org.slug.upper()}-{uuid.uuid4().hex[:12].upper()}",
            tier=LicenseTier.BUSINESS,
            max_users=payload.max_users,
            storage_limit_bytes=storage_bytes,
            expires_at=datetime.now(timezone.utc) + timedelta(days=365),
            is_active=True,
        )
        db.add(license_record)

        # 3. Admin User
        admin_user = User(
            organization_id=org.id,
            email=payload.admin_email.lower().strip(),
            full_name=payload.admin_full_name.strip(),
            hashed_password=get_password_hash(payload.admin_password),
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add(admin_user)
        db.flush()

        # 4. Standard Core Departments
        default_depts = [
            ("ፋይናንስና ሒሳብ (Finance & Accounting)", "FIN", 30.0),
            ("የሰው ኃይል ልማት (Human Resources)", "HR", 20.0),
            ("ኦፕሬሽንስና ሎጂስቲክስ (Operations & Logistics)", "OPS", 50.0),
        ]

        for dept_name, dept_code, quota_gb in default_depts:
            dept = Department(
                organization_id=org.id,
                name=dept_name,
                code=dept_code,
                storage_quota_bytes=int(quota_gb * (1024 ** 3)),
            )
            db.add(dept)
            db.flush()

            # Create default folder
            folder = FileItem(
                organization_id=org.id,
                name=f"{dept.name} ({dept.code})",
                is_folder=True,
                drive_type=DriveType.COMPANY,
                department_id=dept.id,
                owner_id=admin_user.id,
            )
            db.add(folder)

        audit = AuditLog(
            organization_id=org.id,
            user_id=admin_user.id,
            action=AuditAction.LOGIN,
            target_type="ORGANIZATION",
            target_id=org.id,
            target_name=org.name,
            details={"action": "TENANT_PROVISIONED", "slug": org.slug}
        )
        db.add(audit)
        db.commit()

        return TenantProvisionResponse(
            organization_id=org.id,
            name=org.name,
            slug=org.slug,
            admin_user_id=admin_user.id,
            admin_email=admin_user.email,
            status=org.status.value,
            created_at=org.created_at,
        )
