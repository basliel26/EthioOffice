import uuid
from datetime import date, datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User, UserRole
from app.schemas.audit import (
    AuditLogQueryResponse,
    AuditIntegrityResponse,
    AuditDashboardSummary,
    SystemHealthResponse,
    AuditActionItem,
)
from app.services.audit_service import AuditService

router = APIRouter()


def require_admin(user: User) -> None:
    """Enforces that only Organization Administrators or Superadmins can inspect audit logs."""
    if user.role not in (UserRole.ADMIN, UserRole.SUPER_ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="የኦዲት እና የቁጥጥር መዝገቦችን ለማየት የአስተዳዳሪ ፈቃድ ያስፈልጋል (Administrator privileges required to access audit trails)",
        )


@router.get("/logs", response_model=AuditLogQueryResponse)
def query_audit_logs(
    action: Optional[str] = Query(None, description="Filter by action (e.g. UPLOAD, DOWNLOAD, LOGIN, LETTER_REGISTER)"),
    target_type: Optional[str] = Query(None, description="Filter by target type (FILE, FOLDER, SHARE, USER, LETTER)"),
    user_id: Optional[uuid.UUID] = Query(None, description="Filter by actor user ID"),
    target_id: Optional[uuid.UUID] = Query(None, description="Filter by specific entity ID"),
    severity: Optional[str] = Query(None, description="Filter by severity: INFO, WARNING, CRITICAL"),
    status: Optional[str] = Query(None, description="Filter by status: SUCCESS, FAILED, DENIED"),
    ip_address: Optional[str] = Query(None, description="Filter by client IP address"),
    date_from: Optional[date] = Query(None, description="Filter by start date (Gregorian)"),
    date_to: Optional[date] = Query(None, description="Filter by end date (Gregorian)"),
    ethiopian_year: Optional[int] = Query(None, description="Filter by Ethiopian fiscal year (e.g. 2018)"),
    search: Optional[str] = Query(None, description="Search by target name or IP"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Query enterprise audit trail logs with Ethiopian calendar timestamps and multi-attribute filters.
    Requires Organization Administrator privileges.
    """
    require_admin(current_user)

    return AuditService.query_logs(
        db=db,
        org_id=current_user.organization_id,
        action=action,
        target_type=target_type,
        user_id=user_id,
        target_id=target_id,
        severity=severity,
        status=status,
        ip_address=ip_address,
        date_from_gc=date_from,
        date_to_gc=date_to,
        ethiopian_year=ethiopian_year,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.get("/integrity/verify", response_model=AuditIntegrityResponse)
def verify_audit_ledger_integrity(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Cryptographic verification endpoint traversing the organization's hash chain from Genesis.
    Validates that no record has been deleted, inserted, or modified directly in PostgreSQL.
    """
    require_admin(current_user)

    return AuditService.verify_ledger_integrity(
        db=db,
        org_id=current_user.organization_id,
    )


@router.get("/export/excel")
def export_audit_excel(
    action: Optional[str] = Query(None),
    target_type: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    ethiopian_year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Export compliance audit logs to Microsoft Excel (.xlsx) formatted for OFAG / regulatory submission.
    """
    require_admin(current_user)

    excel_stream = AuditService.export_excel(
        db=db,
        org_id=current_user.organization_id,
        actor=current_user,
        action=action,
        target_type=target_type,
        date_from_gc=date_from,
        date_to_gc=date_to,
        ethiopian_year=ethiopian_year,
    )

    filename = f"audit_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        excel_stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/csv")
def export_audit_csv(
    action: Optional[str] = Query(None),
    target_type: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    ethiopian_year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Export compliance audit logs to UTF-8 with BOM CSV format for SIEM tool ingestion.
    """
    require_admin(current_user)

    csv_bytes = AuditService.export_csv(
        db=db,
        org_id=current_user.organization_id,
        actor=current_user,
        action=action,
        target_type=target_type,
        date_from_gc=date_from,
        date_to_gc=date_to,
        ethiopian_year=ethiopian_year,
    )

    filename = f"audit_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/dashboard/summary", response_model=AuditDashboardSummary)
def get_audit_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns enterprise security dashboard metrics, active user rankings, and anomaly intrusion alerts.
    """
    require_admin(current_user)

    return AuditService.get_dashboard_summary(
        db=db,
        org_id=current_user.organization_id,
    )


@router.get("/system/health", response_model=SystemHealthResponse)
def get_system_health(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Operational observability health probe inspecting database connection pools, disk space, and uptime.
    """
    require_admin(current_user)

    return AuditService.get_system_health(db=db)


@router.get("/actions", response_model=List[AuditActionItem])
def get_audit_action_catalog(
    current_user: User = Depends(get_current_user),
):
    """
    Returns full catalog of supported domain audit actions with formal Amharic translations.
    """
    return AuditService.get_audit_actions()
