"""
EthioOffice Public Unauthenticated Sharing Endpoints (Module 6)
Allows external counterparties to view link metadata, verify passwords,
stream download documents, and upload to Dropbox deposit folders without an account.
"""

import os
import urllib.parse
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Header, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.file import FileItemResponse
from app.schemas.share import (
    PublicLinkMetadataResponse,
    PublicLinkVerifyRequest,
    PublicLinkAccessSession,
)
from app.services.share_service import (
    ShareService,
    ShareDomainError,
    ShareLinkNotFoundError,
    ShareLinkExpiredError,
    ShareLinkMaxDownloadsExceededError,
    InvalidLinkPasswordError,
)
from app.services.storage_service import (
    FilePayloadMissingError,
    SecurityViolationError,
)

router = APIRouter()


@router.get("/links/{token}", response_model=PublicLinkMetadataResponse)
def get_public_link_metadata(
    token: str,
    db: Session = Depends(get_db),
):
    """
    Fetch public metadata for a shared link (filename, size, password requirement, access type).
    Unauthenticated.
    """
    try:
        return ShareService.get_public_link_metadata(db, token)
    except ShareLinkNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ShareLinkExpiredError as e:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(e))
    except ShareLinkMaxDownloadsExceededError as e:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(e))


@router.post("/links/{token}/verify", response_model=PublicLinkAccessSession)
def verify_public_link_password(
    token: str,
    payload: PublicLinkVerifyRequest,
    db: Session = Depends(get_db),
):
    """
    Verify password for a password-protected public share link.
    """
    try:
        ShareService.verify_link_password(db, token, payload.password)
        return PublicLinkAccessSession(
            token=token,
            access_granted=True,
            message="Password verified successfully"
        )
    except ShareLinkNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidLinkPasswordError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.get("/links/{token}/download")
def download_public_link_file(
    token: str,
    password: Optional[str] = Query(None),
    x_link_password: Optional[str] = Header(None, alias="X-Link-Password"),
    db: Session = Depends(get_db),
):
    """
    Stream download payload for an external public share link.
    Enforces password validation, link expiry, and max downloads counter.
    """
    pwd = password or x_link_password
    try:
        file_item, version, full_path = ShareService.download_public_file(db, token, password=pwd)

        # RFC 5987 Amharic/UTF-8 filename encoding and ETag integrity header
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
    except ShareLinkNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (ShareLinkExpiredError, ShareLinkMaxDownloadsExceededError) as e:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(e))
    except InvalidLinkPasswordError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except FilePayloadMissingError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ShareDomainError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/links/{token}/upload", response_model=FileItemResponse, status_code=status.HTTP_201_CREATED)
async def upload_to_dropbox(
    token: str,
    file: UploadFile = File(...),
    password: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Deposit a document into an internal folder via an external UPLOAD_DROPBOX link.
    """
    try:
        return ShareService.upload_to_dropbox(
            db=db,
            token=token,
            stream=file.file,
            filename=file.filename or "uploaded_deposit.bin",
            content_type=file.content_type,
            password=password,
        )
    except ShareLinkNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ShareLinkExpiredError as e:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(e))
    except InvalidLinkPasswordError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except SecurityViolationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "SECURITY_VIOLATION", "message": str(e)})
    except ShareDomainError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
