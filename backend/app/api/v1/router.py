from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth,
    files,
    letters,
    calendar,
    organizations,
    departments,
    licenses,
    shares,
    public,
    euro_office,
    localization,
)

api_router = APIRouter()

# Health check
@api_router.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint to verify backend service readiness."""
    return {
        "status": "healthy",
        "service": "EthioOffice Commercial API",
        "version": "0.1.0",
        "market": "Ethiopia B2B Enterprise",
    }

# Register feature routers
api_router.include_router(auth.router, prefix="/auth", tags=["Module 1: Authentication & IAM"])
api_router.include_router(organizations.router, prefix="/organizations", tags=["Module 2: Organization & Tenant"])
api_router.include_router(departments.router, prefix="/departments", tags=["Module 2: Departments & Hierarchies"])
api_router.include_router(licenses.router, prefix="/licenses", tags=["Module 3: Licensing & Capability Engine"])
api_router.include_router(files.router, prefix="/files", tags=["Module 4: File & Drive Management"])
api_router.include_router(shares.router, prefix="/shares", tags=["Module 6: Access Control & Sharing"])
api_router.include_router(public.router, prefix="/public", tags=["Module 6: Public Share Links"])
api_router.include_router(euro_office.router, prefix="/euro-office", tags=["Module 7: Euro-Office Co-Authoring Connector"])
api_router.include_router(localization.router, prefix="/localization", tags=["Module 8: Ethiopian Localization Engine (ባሕረ ሐሳብ)"])
api_router.include_router(calendar.router, prefix="/calendar", tags=["Module 8: Ethiopian Calendar (ባሕረ ሐሳብ)"])
api_router.include_router(letters.router, prefix="/letters", tags=["Module 9: Official Letter Registry (የደብዳቤ መዝገብ)"])
