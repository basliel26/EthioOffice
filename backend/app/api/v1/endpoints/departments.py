import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_user, get_current_admin
from app.models.user import User
from app.services.tenant_service import (
    TenantService,
    DepartmentConflictError,
    DepartmentNotFoundError,
    CrossTenantAccessError,
)
from app.services.capability_service import FeatureNotLicensedError
from app.schemas.tenant import (
    DepartmentCreate,
    DepartmentResponse,
    DepartmentMemberResponse,
    DepartmentMemberAssignRequest,
)

router = APIRouter()


@router.get("", response_model=List[DepartmentResponse])
def list_departments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all departments in the user's organization.
    """
    return TenantService.list_departments(db, current_user.organization_id)


@router.post("", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
def create_department(
    payload: DepartmentCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """
    Create a new organizational department and auto-generate its Company Drive folder.
    Requires ADMIN privileges.
    """
    try:
        dept = TenantService.create_department(
            db=db,
            org_id=current_admin.organization_id,
            payload=payload,
            actor=current_admin
        )
        return DepartmentResponse(
            id=dept.id,
            name=dept.name,
            code=dept.code,
            description=dept.description,
            member_count=0,
            leads=[],
            created_at=dept.created_at
        )
    except FeatureNotLicensedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except DepartmentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DepartmentConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("/{dept_id}/members", response_model=List[DepartmentMemberResponse])
def list_department_members(
    dept_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all employees assigned to this department.
    """
    try:
        return TenantService.list_department_members(db, current_user.organization_id, dept_id)
    except DepartmentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{dept_id}/members", status_code=status.HTTP_200_OK)
def assign_department_member(
    dept_id: uuid.UUID,
    payload: DepartmentMemberAssignRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """
    Assign an employee to a department and optionally designate as Department Lead.
    Requires ADMIN privileges.
    """
    try:
        TenantService.assign_department_member(
            db=db,
            org_id=current_admin.organization_id,
            dept_id=dept_id,
            user_id=payload.user_id,
            is_lead=payload.is_lead,
            actor=current_admin
        )
        return {"message": "Department membership updated successfully"}
    except DepartmentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except CrossTenantAccessError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.delete("/{dept_id}/members/{user_id}", status_code=status.HTTP_200_OK)
def remove_department_member(
    dept_id: uuid.UUID,
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """
    Remove an employee from a department.
    Requires ADMIN privileges.
    """
    success = TenantService.remove_department_member(
        db=db,
        org_id=current_admin.organization_id,
        dept_id=dept_id,
        user_id=user_id,
        actor=current_admin
    )
    if not success:
        raise HTTPException(status_code=404, detail="Membership record not found")
    return {"message": "Employee removed from department"}
