import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.organization import Organization
from app.models.department import Department, UserDepartment
from app.models.user import User
from app.models.file import FileItem, DriveType
from app.models.audit import AuditLog, AuditAction
from app.schemas.tenant import (
    OrganizationUpdate,
    DepartmentCreate,
    DepartmentUpdate,
    DepartmentResponse,
    DepartmentMemberResponse,
    StorageQuotaResponse,
)


class TenantNotFoundError(Exception):
    pass


class DepartmentConflictError(Exception):
    pass


class DepartmentNotFoundError(Exception):
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

        if changes:
            audit = AuditLog(
                organization_id=org.id,
                user_id=actor.id,
                action=AuditAction.LETTER_REGISTER,  # Used as general config audit action
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
    def check_storage_budget(cls, db: Session, org_id: uuid.UUID, incoming_bytes: int) -> None:
        org = cls.get_organization(db, org_id)
        if org.used_storage_bytes + incoming_bytes > org.storage_limit_bytes:
            raise StorageQuotaExceededError(
                f"የድርጅቱ የማከማቻ ቦታ ሞልቷል (Organization storage quota exceeded: "
                f"Requires {incoming_bytes} bytes, limit is {org.storage_limit_bytes} bytes)"
            )

    @classmethod
    def record_storage_change(cls, db: Session, org_id: uuid.UUID, byte_delta: int) -> int:
        org = cls.get_organization(db, org_id)
        new_val = max(0, org.used_storage_bytes + byte_delta)
        org.used_storage_bytes = new_val
        db.commit()
        return new_val

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

        dept = Department(
            organization_id=org_id,
            name=payload.name.strip(),
            code=payload.code.strip(),
            description=payload.description.strip() if payload.description else None,
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
            details={"code": dept.code}
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
            result.append(
                DepartmentResponse(
                    id=d.id,
                    name=d.name,
                    code=d.code,
                    description=d.description,
                    member_count=len(d.members),
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

        # Check existing membership
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
