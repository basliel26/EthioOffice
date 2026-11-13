import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_user, get_current_admin
from app.models.user import User, UserRole
from app.services.iam_service import (
    IAMService, 
    AuthenticationError, 
    TokenInvalidError, 
    PasswordValidationError
)
from app.services.capability_service import SeatLimitExceededError
from app.schemas.iam import (
    LoginRequest, 
    DualTokenResponse, 
    RefreshTokenRequest, 
    PasswordChangeRequest, 
    SessionResponse,
    CreateUserRequest,
)
from app.schemas.auth import UserResponse, DepartmentSummary, OrganizationSummary

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
    org_summary = OrganizationSummary.model_validate(user.organization)
    
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value if hasattr(user.role, "value") else str(user.role),
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
    except SeatLimitExceededError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except AuthenticationError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except PasswordValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
