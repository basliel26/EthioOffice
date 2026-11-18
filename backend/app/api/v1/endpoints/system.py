from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.organization import Organization

router = APIRouter()


class SystemContextResponse(BaseModel):
    deployment_mode: str  # "ON_PREMISE" | "CLOUD_SAAS"
    organization_name: Optional[str] = None
    organization_slug: Optional[str] = None
    allow_public_registration: bool
    system_name: str


@router.get("/context", response_model=SystemContextResponse)
def get_system_context(db: Session = Depends(get_db)):
    """
    Unauthenticated system deployment context probe.
    Provides frontend client with offline/intranet topology vs cloud multi-tenant mode
    allowing the login screen to brand itself dynamically without external internet.
    """
    is_on_premise = settings.DEPLOYMENT_MODE.upper() == "ON_PREMISE"

    org_name = None
    org_slug = None

    if is_on_premise:
        # On private intranet, look up the dedicated organization
        org = None
        if settings.ORGANIZATION_NAME:
            org = db.query(Organization).filter(Organization.name.ilike(f"%{settings.ORGANIZATION_NAME}%")).first()
        if not org:
            org = db.query(Organization).order_by(Organization.created_at.asc()).first()

        if org:
            org_name = org.name
            org_slug = org.slug
        else:
            org_name = settings.ORGANIZATION_NAME

    return SystemContextResponse(
        deployment_mode="ON_PREMISE" if is_on_premise else "CLOUD_SAAS",
        organization_name=org_name,
        organization_slug=org_slug,
        allow_public_registration=settings.ALLOW_PUBLIC_REGISTRATION,
        system_name=f"{org_name} — Private Workspace" if is_on_premise and org_name else "EthioOffice",
    )
