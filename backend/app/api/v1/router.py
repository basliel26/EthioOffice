from fastapi import APIRouter

api_router = APIRouter()

@api_router.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint to verify backend service readiness."""
    return {
        "status": "healthy",
        "service": "EthioOffice Backend API",
        "version": "0.1.0"
    }

# Additional routers (auth, files, eurooffice, shares, audit) will be registered here.
