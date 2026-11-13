from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_user
from app.core.security import verify_password, create_access_token
from app.models.user import User
from app.models.audit import AuditLog, AuditAction
from app.schemas.auth import LoginRequest, Token, UserResponse, DepartmentSummary, OrganizationSummary

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


@router.post("/login", response_model=Token)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Authenticate employee and return signed JWT access token.
    """
    user = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is deactivated"
        )
    
    # Audit log login action
    audit = AuditLog(
        organization_id=user.organization_id,
        user_id=user.id,
        action=AuditAction.LOGIN,
        target_type="USER",
        target_id=user.id,
        target_name=user.full_name,
        details={"email": user.email}
    )
    db.add(audit)
    db.commit()

    access_token = create_access_token(
        subject=user.id,
        organization_id=user.organization_id,
        role=user.role.value if hasattr(user.role, "value") else str(user.role)
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=build_user_response(user)
    )


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    """
    Fetch profile of currently logged-in user including organization and departments.
    """
    return build_user_response(current_user)
