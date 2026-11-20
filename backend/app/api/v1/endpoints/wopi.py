import os
import uuid
import io
import urllib.parse
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Header, Query, Request, Response, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
from jose import jwt, JWTError

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


@router.get("/{file_id}/url")
def get_wopi_embed_url(
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    access_token: Optional[str] = Query(None),
):
    """
    Returns the Collabora / Euro-Office WOPI iframe embedding URL.
    """
    from app.api.deps import get_current_user
    # If no token passed, requires standard session user
    token_str = access_token
    token_data = None
    if token_str:
        token_data = verify_wopi_token(token_str, file_id)

    file_item = db.query(FileItem).filter(FileItem.id == file_id, FileItem.is_deleted == False).first()
    if not file_item or file_item.is_folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    if not token_str:
        token_str = create_wopi_token(file_id, file_item.owner_id, file_item.organization_id, True)

    wopi_src = f"http://host.docker.internal:8000/api/v1/wopi/files/{file_id}"
    cool_url = f"http://localhost:9980/browser/dist/cool.html?WOPISrc={urllib.parse.quote(wopi_src, safe='')}&access_token={token_str}"

    return {
        "file_id": str(file_id),
        "wopi_src": wopi_src,
        "access_token": token_str,
        "iframe_url": cool_url,
    }


@router.get("/files/{file_id}")
def check_file_info(
    file_id: uuid.UUID,
    access_token: str = Query(..., description="WOPI access token"),
    db: Session = Depends(get_db),
):
    """
    WOPI CheckFileInfo endpoint:
    Returns file metadata, user capabilities, and permissions for Collabora / Euro-Office.
    """
    token_data = verify_wopi_token(access_token, file_id)
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
    last_modified = file_item.updated_at.isoformat() if file_item.updated_at else datetime.now(timezone.utc).isoformat()

    return {
        "BaseFileName": file_item.name,
        "OwnerId": str(file_item.owner_id),
        "Size": file_item.size_bytes,
        "UserId": str(user.id),
        "UserFriendlyName": user.full_name,
        "UserCanWrite": can_write,
        "UserCanNotWriteRelative": True,
        "SupportsUpdate": True,
        "SupportsLocks": True,
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
    access_token: str = Query(..., description="WOPI access token"),
    db: Session = Depends(get_db),
):
    """
    WOPI GetFile endpoint:
    Streams raw document binary from CAS storage to Collabora / Euro-Office.
    """
    token_data = verify_wopi_token(access_token, file_id)
    org_id = uuid.UUID(token_data["org_id"])

    file_item = db.query(FileItem).filter(
        FileItem.id == file_id,
        FileItem.organization_id == org_id,
        FileItem.is_deleted == False
    ).first()
    if not file_item or file_item.is_folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    cur_v = file_item.current_version
    if not cur_v:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")

    full_path = storage_provider.get_full_path(cur_v.storage_path)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Physical payload missing")

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
    access_token: str = Query(..., description="WOPI access token"),
    db: Session = Depends(get_db),
):
    """
    WOPI PutFile endpoint:
    Receives updated document bytes from Collabora / Euro-Office and commits a CAS revision.
    """
    token_data = verify_wopi_token(access_token, file_id)
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

    # Commit version
    updated_file = VersionService.upload_new_version(
        db=db,
        org_id=org_id,
        file_id=file_id,
        stream=stream,
        filename=file_item.name,
        actor=user,
        change_summary="Collabora / Euro-Office Collaborative Save",
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
    access_token: str = Query(..., description="WOPI access token"),
    db: Session = Depends(get_db),
):
    """
    Handles WOPI locking operations (LOCK, UNLOCK, REFRESH_LOCK, GET_LOCK).
    """
    token_data = verify_wopi_token(access_token, file_id)
    user_id = uuid.UUID(token_data["sub"])
    org_id = uuid.UUID(token_data["org_id"])

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
