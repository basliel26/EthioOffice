import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_user, get_current_admin
from app.models.user import User, UserRole
from app.services.iam_service import (
    IAMService, 
    AuthenticationError, 
    TokenInvalidError, 
    PasswordValidationError,
    AccountLockedError,
    IPAccessRestrictedError,
)
from app.core.licensing import evaluate_license_lifecycle, LicenseStatus
from app.services.capability_service import SeatLimitExceededError, LicenseReadOnlyLockdownError
from app.schemas.iam import (
    LoginRequest, 
    DualTokenResponse, 
    RefreshTokenRequest, 
    PasswordChangeRequest, 
    SessionResponse,
    CreateUserRequest,
)
from app.schemas.auth import (
    UserResponse,
    DepartmentSummary,
    OrganizationSummary,
    ProfileUpdateRequest,
    ChangePasswordRequest,
    AdminResetPasswordRequest,
    UserLockRequest,
)

router = APIRouter()


def build_user_response(user: User) -> UserResponse:
    dept_summaries = [
        DepartmentSummary(
            id=ud.department.id,
            name=ud.department.name,
            code=ud.department.code,
            is_lead=ud.is_department_lead
        )
        for ud in user.departments
    ]

    org_dict = {
        "id": user.organization.id,
        "name": user.organization.name,
        "slug": user.organization.slug,
        "tin_number": user.organization.tin_number,
        "logo_url": user.organization.logo_url,
        "theme_color": user.organization.theme_color,
        "allowed_ip_ranges": user.organization.allowed_ip_ranges,
    }
    if user.organization.license:
        lic = user.organization.license
        lifecycle = evaluate_license_lifecycle(
            expires_at=lic.expires_at,
            grace_period_days=lic.grace_period_days or 14,
            is_active=lic.is_active
        )
        org_dict["license_tier"] = lic.tier.value if hasattr(lic.tier, "value") else str(lic.tier)
        org_dict["license_status"] = lifecycle["status"].value if hasattr(lifecycle["status"], "value") else str(lifecycle["status"])
        org_dict["days_remaining"] = lifecycle["days_remaining"]
        org_dict["is_grace_period"] = lifecycle["status"] == LicenseStatus.IN_GRACE_PERIOD
        org_dict["license_warning"] = lifecycle["warning"]

    org_summary = OrganizationSummary(**org_dict)
    
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        phone_number=user.phone_number,
        role=user.role.value if hasattr(user.role, "value") else str(user.role),
        is_active=user.is_active,
        is_locked=user.is_locked,
        avatar_url=user.avatar_url,
        organization=org_summary,
        departments=dept_summaries,
        created_at=user.created_at
    )


@router.post("/login", response_model=DualTokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Authenticate employee, issue short-lived JWT access token and secure rotated refresh token.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    try:
        user, access_token, refresh_token = IAMService.authenticate(
            db=db,
            email=payload.email,
            password=payload.password,
            client_ip=client_ip,
            user_agent=user_agent
        )
    except AccountLockedError as e:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail={"code": "ACCOUNT_LOCKED", "message": str(e)},
        )
    except IPAccessRestrictedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "IP_ACCESS_DENIED", "message": str(e)},
        )
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    return DualTokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=build_user_response(user)
    )


@router.post("/refresh")
def refresh_token(
    payload: RefreshTokenRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Rotate refresh token and issue a fresh access token.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    try:
        new_access_token, new_refresh_token = IAMService.rotate_refresh_token(
            db=db,
            refresh_token=payload.refresh_token,
            client_ip=client_ip,
            user_agent=user_agent
        )
        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer"
        }
    except TokenInvalidError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    """
    Fetch profile of currently logged-in user including organization and departments.
    """
    return build_user_response(current_user)


@router.get("/sessions", response_model=List[SessionResponse])
def get_active_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all active device sessions for the authenticated user.
    """
    sessions = IAMService.list_active_sessions(db, current_user.id)
    return [
        SessionResponse(
            id=s.id,
            client_ip=s.client_ip,
            user_agent=s.user_agent,
            last_active_at=s.last_active_at,
            created_at=s.created_at,
            is_current=False
        )
        for s in sessions
    ]


@router.post("/sessions/{session_id}/revoke")
def revoke_session(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Remotely revoke a specific device session.
    """
    success = IAMService.revoke_session(db, current_user.id, session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Session successfully revoked"}


@router.post("/logout-all")
def logout_all_devices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Revoke all device sessions across all browsers and apps for this user.
    """
    revoked_count = IAMService.revoke_all_sessions(db, current_user.id)
    return {"message": f"Successfully revoked {revoked_count} active sessions"}


@router.post("/change-password")
def change_password(
    payload: PasswordChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Change account password and automatically terminate all other sessions.
    """
    try:
        IAMService.change_password(
            db=db,
            user=current_user,
            current_password=payload.current_password,
            new_password=payload.new_password
        )
        return {"message": "የይለፍ ቃል በተሳካ ሁኔታ ተቀይሯል (Password successfully updated)"}
    except AuthenticationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PasswordValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_organization_user(
    payload: CreateUserRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """
    Provision a new employee under the organization.
    Requires ADMIN privileges. Enforces license seat limits.
    """
    role_enum = (
        UserRole[payload.role.upper()]
        if payload.role and payload.role.upper() in UserRole.__members__
        else UserRole.STAFF
    )

    try:
        user = IAMService.create_user(
            db=db,
            org_id=current_admin.organization_id,
            email=payload.email,
            password=payload.password,
            full_name=payload.full_name,
            role=role_enum,
            actor=current_admin,
        )
        return build_user_response(user)
    except LicenseReadOnlyLockdownError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "LICENSE_LOCKDOWN_READ_ONLY", "message": str(e)})
    except SeatLimitExceededError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except AuthenticationError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except PasswordValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.post("/users/{user_id}/unlock")
def unlock_user_account(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """
    Manually unfreeze an employee account after brute-force lockout.
    Requires ADMIN privileges.
    """
    try:
        IAMService.unlock_user_account(
            db=db,
            org_id=current_admin.organization_id,
            user_id=user_id,
            actor=current_admin,
        )
        return {"message": "አካውንቱ በተሳካ ሁኔታ ተከፍቷል (Account successfully unlocked)"}
    except AuthenticationError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/profile", response_model=UserResponse)
def update_profile(
    payload: ProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Self-service update of current user profile (full name, phone number, avatar URL).
    """
    try:
        updated_user = IAMService.update_profile(
            db=db,
            user=current_user,
            full_name=payload.full_name,
            phone_number=payload.phone_number,
            avatar_url=payload.avatar_url,
        )
        return build_user_response(updated_user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Self-service password change: validates old password, enforces complexity rules,
    and invalidates all existing sessions.
    """
    try:
        IAMService.change_password(
            db=db,
            user=current_user,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
        return {"message": "የይለፍ ቃል በተሳካ ሁኔታ ተቀይሯል (Password changed successfully)"}
    except AuthenticationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PasswordValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.post("/users/{user_id}/lock")
def lock_user_account(
    user_id: uuid.UUID,
    payload: Optional[UserLockRequest] = None,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """
    Administrative lock/suspension of employee account.
    Terminates active sessions and prevents further logins.
    """
    duration = payload.lock_duration_hours if payload else None
    reason = payload.reason if payload else None
    try:
        IAMService.lock_user_account(
            db=db,
            org_id=current_admin.organization_id,
            user_id=user_id,
            actor=current_admin,
            lock_duration_hours=duration,
            reason=reason,
        )
        return {"message": "ተጠቃሚው በተሳካ ሁኔታ ታግዷል (User account successfully locked)"}
    except AuthenticationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/users/{user_id}/reset-password")
def admin_reset_password(
    user_id: uuid.UUID,
    payload: AdminResetPasswordRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """
    Administrative password reset: forces new password, unfreezes account,
    and terminates existing active sessions.
    """
    try:
        IAMService.admin_reset_password(
            db=db,
            org_id=current_admin.organization_id,
            user_id=user_id,
            new_password=payload.new_password,
            actor=current_admin,
        )
        return {"message": "የይለፍ ቃል በአስተዳዳሪው በተሳካ ሁኔታ ተቀይሯል (Password successfully reset by admin)"}
    except AuthenticationError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PasswordValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
