import os
import uuid
import urllib.parse
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.file import FileItem, FileVersion
from app.services.storage_service import (
    StorageService,
    storage_provider,
    FileItemNotFoundError,
    DriveAccessDeniedError,
)
from app.services.capability_service import LicenseReadOnlyLockdownError
from app.services.euro_office_service import (
    EuroOfficeService,
    UnsupportedDocumentTypeError,
    InvalidCallbackSignatureError,
    DocumentServerCallbackError,
    SessionNotFoundError,
)
from app.schemas.euro_office import (
    EuroOfficeConfigResponse,
    EuroOfficeCallbackPayload,
    EuroOfficeCallbackResponse,
    ActiveCoAuthorsResponse,
    EuroOfficeHealthResponse,
    EuroOfficeCommandRequest,
    EuroOfficeCommandResponse,
    EuroOfficeSessionHistoryResponse,
)

router = APIRouter()


@router.get("/health", response_model=EuroOfficeHealthResponse)
def get_euro_office_health():
    """
    Enterprise health check and readiness probe for Euro-Office / ONLYOFFICE Document Server.
    Reports operational state (UP, DEGRADED, DOWN), configuration, and font defaults.
    """
    return EuroOfficeService.check_health()


@router.get("/config/{file_id}", response_model=EuroOfficeConfigResponse)
def get_document_config(
    file_id: uuid.UUID,
    lang: str = Query("en", description="Editor UI language code ('en', 'am')"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generates the complete ONLYOFFICE / Euro-Office configuration JSON
    and signs it with HMAC-SHA256 JWT.
    Enforces Module 6 ACL (VIEWER vs EDITOR mode) and Module 5 Lock status.
    """
    try:
        return EuroOfficeService.generate_config(
            db=db,
            org_id=current_user.organization_id,
            file_id=file_id,
            actor=current_user,
            lang=lang,
        )
    except UnsupportedDocumentTypeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "UNSUPPORTED_DOCUMENT_TYPE", "message": str(e)}
        )
    except FileItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DriveAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.get("/download/{file_id}")
def download_document_for_euro_office(
    file_id: uuid.UUID,
    token: Optional[str] = Query(None, description="Short-lived download token"),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Internal streaming download endpoint called by Euro-Office Document Server.
    Authenticates using the short-lived download JWT token.
    Delivers raw payload with RFC 5987 Amharic encoding and ETag integrity header.
    """
    auth_token = token
    if not auth_token and authorization and authorization.startswith("Bearer "):
        auth_token = authorization[7:].strip()

    if not auth_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Download token required to stream document payload"
        )

    try:
        token_data = EuroOfficeService.verify_download_token(auth_token, file_id)
    except InvalidCallbackSignatureError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    org_id_str = token_data.get("org_id")
    try:
        org_id = uuid.UUID(org_id_str)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid organization context in token")

    file_item = db.query(FileItem).filter(
        FileItem.id == file_id,
        FileItem.organization_id == org_id,
        FileItem.is_deleted == False
    ).first()

    if not file_item or file_item.is_folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    version = db.query(FileVersion).filter(FileVersion.id == file_item.current_version_id).first()
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File version not found")

    full_path = storage_provider.get_full_path(version.storage_path)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Physical payload missing on disk")

    ascii_fallback = "".join(c for c in file_item.name if c.isascii() and (c.isalnum() or c in "._- ")).strip()
    if not ascii_fallback or ascii_fallback.startswith("."):
        ext = os.path.splitext(file_item.name)[1]
        ascii_fallback = f"document{ext}" if ext.isascii() else "document.bin"

    encoded_name = urllib.parse.quote(file_item.name, encoding="utf-8")
    content_disposition = f'attachment; filename="{ascii_fallback}"; filename*=UTF-8\'\'{encoded_name}'

    response_headers = {
        "ETag": f'"{version.checksum_sha256}"',
        "Content-Disposition": content_disposition,
        "Accept-Ranges": "bytes",
    }

    return FileResponse(
        path=full_path,
        media_type=file_item.mime_type or "application/octet-stream",
        headers=response_headers,
    )


@router.post("/callback", response_model=EuroOfficeCallbackResponse)
async def euro_office_callback(
    request: Request,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Webhook callback handler invoked by ONLYOFFICE / Euro-Office Document Server.
    Authenticates HMAC-SHA256 signature, processes Status 1 (editing),
    Status 2 (save version), Status 4 (close), and Status 6 (force-save).
    Protects against version storms via SHA-256 payload idempotency.
    Returns {"error": 0} on success.
    """
    body = await request.body()
    try:
        payload = EuroOfficeService.parse_callback_payload(body, authorization_header=authorization)
    except InvalidCallbackSignatureError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except DocumentServerCallbackError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    try:
        return EuroOfficeService.handle_callback(db=db, payload=payload)
    except LicenseReadOnlyLockdownError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "LICENSE_LOCKDOWN_READ_ONLY", "message": str(e)}
        )
    except DocumentServerCallbackError as e:
        return EuroOfficeCallbackResponse(error=1, message=str(e))


@router.get("/{file_id}/coauthors", response_model=ActiveCoAuthorsResponse)
def get_active_coauthors(
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns real-time roster of colleagues currently collaborating inside the document.
    """
    try:
        return EuroOfficeService.get_active_coauthors(
            db=db,
            org_id=current_user.organization_id,
            file_id=file_id,
            current_user=current_user,
        )
    except FileItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DriveAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.post("/command", response_model=EuroOfficeCommandResponse)
def dispatch_document_command(
    payload: EuroOfficeCommandRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Enterprise Command Service dispatcher:
    Dispatches programmatic administrative commands ('forcesave', 'drop', 'info')
    to the Euro-Office Document Server with HMAC-SHA256 authorization.
    """
    try:
        return EuroOfficeService.dispatch_command(
            db=db,
            org_id=current_user.organization_id,
            file_id=payload.file_id,
            command=payload.command,
            actor=current_user,
            userdata=payload.userdata,
        )
    except FileItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DriveAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.get("/{file_id}/sessions", response_model=EuroOfficeSessionHistoryResponse)
def get_document_session_history(
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Enterprise audit trail of historical collaborative editing sessions
    with Ethiopian calendar timestamps (ዓ.ም).
    """
    try:
        return EuroOfficeService.get_session_history(
            db=db,
            org_id=current_user.organization_id,
            file_id=file_id,
            actor=current_user,
        )
    except FileItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DriveAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
