from fastapi import APIRouter
from app.api.v1.endpoints import auth, files, letters, calendar

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
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication & Profile"])
api_router.include_router(files.router, prefix="/files", tags=["File & Drive Management"])
api_router.include_router(letters.router, prefix="/letters", tags=["Official Letter Registry (የደብዳቤ መዝገብ)"])
api_router.include_router(calendar.router, prefix="/calendar", tags=["Ethiopian Calendar (ባሕረ ሐሳብ)"])
