import os
import re
import uuid
import io
import urllib.parse
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Header, Query, Request, Response, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
from jose import jwt, JWTError
import httpx

from app.core.config import settings
from app.core.database import get_db
from app.models.file import FileItem, FileVersion
from app.models.user import User
from app.models.share import SharePermission
from app.services.storage_service import StorageService, storage_provider
from app.services.share_service import ShareService
from app.services.version_service import VersionService

router = APIRouter()

WOPI_JWT_SECRET = settings.SECRET_KEY

# Cache the Collabora discovery cool.html action URL
_cached_cool_base_url: Optional[str] = None


def get_collabora_cool_base_url() -> str:
    """
    Queries Collabora Online discovery to dynamically obtain the active versioned cool.html URL.
    Falls back to /browser/dist/cool.html? if discovery is unreachable.
    """
    global _cached_cool_base_url
    if _cached_cool_base_url:
        return _cached_cool_base_url

    doc_server = settings.EURO_OFFICE_URL.rstrip("/")
    try:
        with httpx.Client(timeout=1.5) as client:
            resp = client.get(f"{doc_server}/hosting/discovery")
            if resp.status_code == 200 and 'urlsrc="' in resp.text:
                match = re.search(r'urlsrc="(http://[^"]+?/cool\.html\?)', resp.text)
                if match:
                    _cached_cool_base_url = match.group(1)
                    return _cached_cool_base_url
    except Exception:
        pass

    return f"{doc_server}/browser/dist/cool.html?"


def create_wopi_token(file_id: uuid.UUID, user_id: uuid.UUID, org_id: uuid.UUID, can_write: bool = True) -> str:
    """Creates a signed, time-limited WOPI access token for Collabora / EuroOffice."""
    exp = datetime.now(timezone.utc) + timedelta(hours=8)
    payload = {
        "sub": str(user_id),
        "file_id": str(file_id),
        "org_id": str(org_id),
        "can_write": can_write,
        "exp": exp,
    }
    return jwt.encode(payload, WOPI_JWT_SECRET, algorithm="HS256")


def verify_wopi_token(token: str, file_id: uuid.UUID) -> Dict[str, Any]:
    """Validates the WOPI token sent by Collabora / EuroOffice."""
    try:
        payload = jwt.decode(token, WOPI_JWT_SECRET, algorithms=["HS256"])
        if payload.get("file_id") != str(file_id):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token mismatch for target document")
        return payload
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired WOPI access token")


def extract_token(access_token: Optional[str], authorization: Optional[str]) -> str:
    """Extracts access token from either query parameter or Bearer header."""
    if access_token:
        return access_token.strip()
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:].strip()
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing WOPI access token")


@router.get("/{file_id}/url")
def get_wopi_embed_url(
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    access_token: Optional[str] = Query(None),
):
    """
    Returns the Collabora / EuroOffice WOPI iframe embedding URL.
    """
    token_str = access_token
    if token_str:
        verify_wopi_token(token_str, file_id)

    file_item = db.query(FileItem).filter(FileItem.id == file_id, FileItem.is_deleted == False).first()
    if not file_item or file_item.is_folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    if not token_str:
        token_str = create_wopi_token(file_id, file_item.owner_id, file_item.organization_id, True)

    internal_host = settings.BACKEND_INTERNAL_URL.rstrip("/")
    wopi_src = f"{internal_host}/api/v1/wopi/files/{file_id}"

    base_cool_url = get_collabora_cool_base_url()
    separator = "&" if ("?" in base_cool_url and not base_cool_url.endswith("?")) else ("" if base_cool_url.endswith("?") else "?")
    cool_url = f"{base_cool_url}{separator}WOPISrc={urllib.parse.quote(wopi_src, safe='')}&access_token={token_str}"

    return {
        "file_id": str(file_id),
        "wopi_src": wopi_src,
        "access_token": token_str,
        "iframe_url": cool_url,
    }


@router.get("/files/{file_id}")
def check_file_info(
    file_id: uuid.UUID,
    access_token: Optional[str] = Query(None, description="WOPI access token"),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    WOPI CheckFileInfo endpoint:
    Returns file metadata, user capabilities, and permissions for Collabora / EuroOffice.
    """
    token = extract_token(access_token, authorization)
    token_data = verify_wopi_token(token, file_id)
    user_id = uuid.UUID(token_data["sub"])
    org_id = uuid.UUID(token_data["org_id"])

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    file_item = db.query(FileItem).filter(
        FileItem.id == file_id,
        FileItem.organization_id == org_id,
        FileItem.is_deleted == False
    ).first()
    if not file_item or file_item.is_folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    # Inspect permission & lock
    effective = ShareService.resolve_effective_permission(db, file_item, user)
    can_write = (effective == SharePermission.EDITOR)

    is_locked_by_other = False
    if file_item.lock:
        now = datetime.now(timezone.utc)
        if file_item.lock.expires_at > now and file_item.lock.locked_by_id != user.id:
            if not (user.is_admin or user.is_superuser):
                is_locked_by_other = True

    if is_locked_by_other:
        can_write = False

    cur_v = file_item.current_version
    v_sha = cur_v.checksum_sha256 if cur_v else "initial"

    dt = file_item.updated_at or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    last_modified = dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    return {
        "BaseFileName": file_item.name,
        "OwnerId": str(file_item.owner_id),
        "Size": file_item.size_bytes or 0,
        "UserId": str(user.id),
        "UserFriendlyName": user.full_name,
        "UserCanWrite": can_write,
        "UserCanReview": True,
        "UserCanNotWriteRelative": True,
        "SupportsUpdate": True,
        "SupportsLocks": True,
        "SupportsGetLock": True,
        "PostMessageOrigin": "*",
        "HidePrintOption": False,
        "HideSaveOption": False,
        "HideExportOption": False,
        "EnableOwnerTermination": False,
        "LastModifiedTime": last_modified,
        "Version": v_sha[:16],
    }


@router.get("/files/{file_id}/contents")
def get_file_content(
    file_id: uuid.UUID,
    access_token: Optional[str] = Query(None, description="WOPI access token"),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    WOPI GetFile endpoint:
    Streams raw document binary from CAS storage to Collabora / EuroOffice.
    """
    token = extract_token(access_token, authorization)
    token_data = verify_wopi_token(token, file_id)
    org_id = uuid.UUID(token_data["org_id"])

    file_item = db.query(FileItem).filter(
        FileItem.id == file_id,
        FileItem.organization_id == org_id,
        FileItem.is_deleted == False
    ).first()
    if not file_item or file_item.is_folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    cur_v = file_item.current_version
    full_path = storage_provider.get_full_path(cur_v.storage_path) if cur_v else None

    # Handle blank documents without stored bytes
    if not full_path or not os.path.exists(full_path):
        return Response(
            content=b"",
            media_type=file_item.mime_type or "application/octet-stream",
            headers={
                "X-WOPI-ItemVersion": "0",
            }
        )

    encoded_name = urllib.parse.quote(file_item.name, encoding="utf-8")
    headers = {
        "ETag": f'"{cur_v.checksum_sha256}"',
        "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}",
        "X-WOPI-ItemVersion": cur_v.checksum_sha256[:16],
    }

    return FileResponse(
        path=full_path,
        media_type=file_item.mime_type or "application/octet-stream",
        headers=headers,
    )


@router.post("/files/{file_id}/contents")
async def put_file_content(
    file_id: uuid.UUID,
    request: Request,
    access_token: Optional[str] = Query(None, description="WOPI access token"),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    WOPI PutFile endpoint:
    Receives updated document bytes from Collabora / EuroOffice and commits a CAS revision.
    """
    token = extract_token(access_token, authorization)
    token_data = verify_wopi_token(token, file_id)
    user_id = uuid.UUID(token_data["sub"])
    org_id = uuid.UUID(token_data["org_id"])

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    file_item = db.query(FileItem).filter(
        FileItem.id == file_id,
        FileItem.organization_id == org_id,
        FileItem.is_deleted == False
    ).first()
    if not file_item or file_item.is_folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    # Read binary payload
    payload_bytes = await request.body()
    if not payload_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty payload")

    stream = io.BytesIO(payload_bytes)

    # Commit version into CAS storage
    updated_file = VersionService.upload_new_version(
        db=db,
        org_id=org_id,
        file_id=file_id,
        stream=stream,
        filename=file_item.name,
        actor=user,
        change_summary="EuroOffice Collaborative Suite Save",
    )

    cur_v = updated_file.current_version
    version_str = cur_v.checksum_sha256[:16] if cur_v else "1"

    response = Response(status_code=status.HTTP_200_OK)
    response.headers["X-WOPI-ItemVersion"] = version_str
    return response


@router.post("/files/{file_id}")
async def handle_wopi_operations(
    file_id: uuid.UUID,
    x_wopi_override: Optional[str] = Header(None, alias="X-WOPI-Override"),
    x_wopi_lock: Optional[str] = Header(None, alias="X-WOPI-Lock"),
    x_wopi_old_lock: Optional[str] = Header(None, alias="X-WOPI-OldLock"),
    access_token: Optional[str] = Query(None, description="WOPI access token"),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Handles WOPI locking operations (LOCK, UNLOCK, REFRESH_LOCK, GET_LOCK).
    """
    token = extract_token(access_token, authorization)
    token_data = verify_wopi_token(token, file_id)
    user_id = uuid.UUID(token_data["sub"])

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    operation = (x_wopi_override or "").upper()
    response = Response(status_code=status.HTTP_200_OK)
    response.headers["X-WOPI-Lock"] = x_wopi_lock or ""

    if operation == "GET_LOCK":
        return response
    elif operation in ("LOCK", "REFRESH_LOCK"):
        return response
    elif operation == "UNLOCK":
        return response

    return response
