import os
import io
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
import httpx
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.file import FileItem
from app.models.eurooffice import EuroOfficeSession
from app.models.user import User
from app.models.share import SharePermission
from app.models.audit import AuditLog, AuditAction
from app.services.capability_service import CapabilityService, LicenseReadOnlyLockdownError
from app.services.storage_service import (
    StorageService,
    DriveAccessDeniedError,
    FileItemNotFoundError,
)
from app.services.share_service import ShareService
from app.services.version_service import VersionService
from app.schemas.euro_office import (
    DocumentPermissions,
    DocumentUser,
    DocumentObject,
    EditorCustomization,
    EditorConfig,
    EuroOfficeConfigResponse,
    EuroOfficeCallbackPayload,
    EuroOfficeCallbackResponse,
    CoAuthorItem,
    ActiveCoAuthorsResponse,
)


# =====================================================================
# Domain Exceptions
# =====================================================================

class EuroOfficeDomainError(Exception):
    """Base exception for Euro-Office / ONLYOFFICE integration operations."""
    pass


class UnsupportedDocumentTypeError(EuroOfficeDomainError):
    """Raised when a requested file cannot be edited in Euro-Office."""
    pass


class InvalidCallbackSignatureError(EuroOfficeDomainError):
    """Raised when the document server callback JWT signature is invalid or tampered."""
    pass


class DocumentServerCallbackError(EuroOfficeDomainError):
    """Raised when document server callback payload is malformed or unprocessable."""
    pass


class SessionNotFoundError(EuroOfficeDomainError):
    """Raised when no active session matches the provided document key."""
    pass


# Supported File Extension Sets
WORD_EXTENSIONS = {".docx", ".doc", ".odt", ".rtf", ".txt", ".html", ".epub"}
CELL_EXTENSIONS = {".xlsx", ".xls", ".ods", ".csv"}
SLIDE_EXTENSIONS = {".pptx", ".ppt", ".odp"}


def get_document_type(filename: str) -> Optional[str]:
    """Determines ONLYOFFICE documentType from filename extension."""
    _, ext = os.path.splitext(filename.lower())
    if ext in WORD_EXTENSIONS:
        return "word"
    elif ext in CELL_EXTENSIONS:
        return "cell"
    elif ext in SLIDE_EXTENSIONS:
        return "slide"
    return None


def fetch_edited_document(url: str) -> bytes:
    """Downloads updated document binary payload from the Document Server callback URL."""
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.content
    except Exception as e:
        raise DocumentServerCallbackError(f"የተሻሻለውን ሰነድ ከDocument Server ማውረድ አልተቻለም (Failed to download document from Euro-Office): {str(e)}")


# =====================================================================
# Domain Service
# =====================================================================

class EuroOfficeService:

    @classmethod
    def generate_document_key(cls, file_item: FileItem) -> str:
        """
        Generates a stable cache key for the current version of the document.
        Changes whenever a new version is created. Max 128 alphanumeric characters.
        """
        cur_v = file_item.current_version
        v_num = cur_v.version_number if cur_v else 1
        v_hash = cur_v.checksum_sha256[:12] if cur_v else "initial"
        raw_key = f"{file_item.id}_{v_num}_{v_hash}"
        # Sanitize for ONLYOFFICE key requirements
        clean_key = "".join(c for c in raw_key if c.isalnum() or c in "_-")
        return clean_key[:128]

    @classmethod
    def generate_config(
        cls,
        db: Session,
        org_id: uuid.UUID,
        file_id: uuid.UUID,
        actor: User,
        lang: str = "en",
    ) -> EuroOfficeConfigResponse:
        """
        Generates the ONLYOFFICE document configuration payload and HMAC-SHA256 JWT token.
        Enforces Module 6 ACL (VIEWER vs EDITOR) and Module 5 exclusive checkout lock.
        """
        file_item = StorageService.get_item(db, org_id, file_id, actor)
        if file_item.is_folder:
            raise UnsupportedDocumentTypeError("አቃፊዎችን በEuro-Office መክፈት አይቻልም (Folders cannot be opened in Euro-Office)")

        doc_type = get_document_type(file_item.name)
        if not doc_type:
            _, ext = os.path.splitext(file_item.name)
            raise UnsupportedDocumentTypeError(f"የፋይል ቅጥያው '{ext}' በEuro-Office አይደገፍም (Unsupported document type for Euro-Office co-authoring)")

        # 1. Resolve effective permission via Module 6 ACL
        effective = ShareService.resolve_effective_permission(db, file_item, actor)
        if not effective:
            raise DriveAccessDeniedError("ይህን ሰነድ የማየት ፈቃድ የለዎትም (Access denied: No permission to view this document)")

        # 2. Inspect Module 5 Lock status
        is_locked_by_other = False
        if file_item.lock:
            now = datetime.now(timezone.utc)
            if file_item.lock.expires_at > now:
                if file_item.lock.locked_by_id != actor.id and not (actor.is_admin or actor.is_superuser):
                    is_locked_by_other = True

        # Mode determination:
        # If user is VIEWER OR file is locked by another colleague -> View-only mode
        # If user is EDITOR AND file is unlocked (or locked by user) -> Edit mode
        if effective == SharePermission.EDITOR and not is_locked_by_other:
            mode = "edit"
            permissions = DocumentPermissions(
                edit=True,
                download=True,
                print=True,
                review=True,
                comment=True,
            )
        else:
            mode = "view"
            permissions = DocumentPermissions(
                edit=False,
                download=True,
                print=True,
                review=False,
                comment=False,
            )

        document_key = cls.generate_document_key(file_item)

        # Ensure EuroOfficeSession exists for this key
        session = db.query(EuroOfficeSession).filter(EuroOfficeSession.document_key == document_key).first()
        if not session:
            session = EuroOfficeSession(
                document_key=document_key,
                file_id=file_item.id,
                active_users=[],
                is_editing=False,
            )
            db.add(session)
            db.commit()
            db.refresh(session)

        # 3. Generate short-lived Document Server download token (HS256)
        dl_exp = datetime.now(timezone.utc) + timedelta(hours=4)
        dl_payload = {
            "sub": str(file_item.id),
            "org_id": str(org_id),
            "action": "document_download",
            "key": document_key,
            "exp": dl_exp,
        }
        download_token = jwt.encode(dl_payload, settings.EURO_OFFICE_JWT_SECRET, algorithm="HS256")

        base_url = settings.BACKEND_INTERNAL_URL.rstrip("/")
        download_url = f"{base_url}{settings.API_V1_STR}/euro-office/download/{file_item.id}?token={download_token}"
        callback_url = f"{base_url}{settings.API_V1_STR}/euro-office/callback"

        _, ext = os.path.splitext(file_item.name)
        clean_ext = ext.lstrip(".").lower()

        doc_obj = DocumentObject(
            fileType=clean_ext,
            key=document_key,
            title=file_item.name,
            url=download_url,
            permissions=permissions,
        )

        editor_cfg = EditorConfig(
            mode=mode,
            lang=lang,
            callbackUrl=callback_url,
            user=DocumentUser(
                id=str(actor.id),
                name=actor.full_name,
            ),
            customization=EditorCustomization(
                autosave=True,
                forcesave=True,
                chat=True,
                comments=True,
                customer={"name": "EthioOffice", "logo": "https://ethiooffice.et/logo.png"},
            ),
        )

        # 4. Generate Master ONLYOFFICE Configuration JWT
        full_payload = {
            "documentType": doc_type,
            "document": doc_obj.model_dump(),
            "editorConfig": editor_cfg.model_dump(),
        }
        signed_token = jwt.encode(full_payload, settings.EURO_OFFICE_JWT_SECRET, algorithm="HS256")

        return EuroOfficeConfigResponse(
            documentType=doc_type,
            document=doc_obj,
            editorConfig=editor_cfg,
            token=signed_token,
        )

    @classmethod
    def verify_download_token(cls, token: str, file_id: uuid.UUID) -> Dict[str, Any]:
        """Validates the short-lived download token presented by the Document Server."""
        try:
            payload = jwt.decode(token, settings.EURO_OFFICE_JWT_SECRET, algorithms=["HS256"])
            if payload.get("action") != "document_download":
                raise InvalidCallbackSignatureError("Invalid token action")
            if payload.get("sub") != str(file_id):
                raise InvalidCallbackSignatureError("Token does not match target document")
            return payload
        except JWTError as e:
            raise InvalidCallbackSignatureError(f"የማውረጃ ዲጂታል ፊርማ አልተረጋገጠም (Invalid download signature): {str(e)}")

    @classmethod
    def parse_callback_payload(
        cls,
        raw_body: bytes,
        authorization_header: Optional[str] = None
    ) -> EuroOfficeCallbackPayload:
        """
        Parses incoming Document Server callback, verifying HMAC-SHA256 signature
        from either the Authorization Bearer header or the embedded body token.
        """
        import json
        try:
            data = json.loads(raw_body.decode("utf-8"))
        except Exception as e:
            raise DocumentServerCallbackError(f"Invalid JSON in callback body: {str(e)}")

        token = None
        if authorization_header and authorization_header.startswith("Bearer "):
            token = authorization_header[7:].strip()
        elif "token" in data and data["token"]:
            token = data["token"]

        if token:
            try:
                decoded = jwt.decode(token, settings.EURO_OFFICE_JWT_SECRET, algorithms=["HS256"])
                # If decoded payload contains 'payload' key, unwrap it; otherwise use decoded dict
                if "payload" in decoded and isinstance(decoded["payload"], dict):
                    data = decoded["payload"]
                elif "status" in decoded:
                    data = decoded
            except JWTError as e:
                raise InvalidCallbackSignatureError(f"የEuro-Office ዲጂታል ፊርማ አልተረጋገጠም (Invalid Euro-Office JWT signature): {str(e)}")

        return EuroOfficeCallbackPayload(**data)

    @classmethod
    def handle_callback(
        cls,
        db: Session,
        payload: EuroOfficeCallbackPayload,
    ) -> EuroOfficeCallbackResponse:
        """
        Executes the Document Server Callback State Machine:
        - Status 1 (BEING_EDITED): Updates active co-author roster in EuroOfficeSession.
        - Status 2 (READY_FOR_SAVING): Downloads edited binary and commits Version N+1 with CAS.
        - Status 4 (CLOSED_NO_CHANGES): Resets session editing flag with no version bump.
        - Status 6 (FORCE_SAVE): Downloads intermediate binary and commits Version N+1 (Ctrl+S / AutoSave).
        - Status 3 / 7: Records audit errors.
        """
        document_key = payload.key
        session = db.query(EuroOfficeSession).filter(EuroOfficeSession.document_key == document_key).first()

        # Fallback: look up by file UUID if key matches file_id pattern
        file_item = None
        if session:
            file_item = session.file_item
        else:
            try:
                file_uuid_str = document_key.split("_")[0]
                potential_file_id = uuid.UUID(file_uuid_str)
                file_item = db.query(FileItem).filter(FileItem.id == potential_file_id).first()
            except Exception:
                pass

        if not file_item:
            return EuroOfficeCallbackResponse(error=1, message="Target document not found for callback key")

        now = datetime.now(timezone.utc)

        # Status 1: BEING_EDITED (User joined or session heartbeat)
        if payload.status == 1:
            if not session:
                session = EuroOfficeSession(
                    document_key=document_key,
                    file_id=file_item.id,
                    active_users=payload.users or [],
                    is_editing=True,
                )
                db.add(session)
            else:
                session.is_editing = True
                if payload.users:
                    session.active_users = payload.users
            db.commit()
            return EuroOfficeCallbackResponse(error=0, message="Status 1 processed")

        # Status 4: CLOSED_NO_CHANGES
        elif payload.status == 4:
            if session:
                session.is_editing = False
                session.active_users = []
                db.commit()
            return EuroOfficeCallbackResponse(error=0, message="Status 4 processed")

        # Status 2 (READY_FOR_SAVING) & Status 6 (FORCE_SAVE)
        elif payload.status in (2, 6):
            if not payload.url:
                raise DocumentServerCallbackError("Callback status indicates save, but download url is missing")

            # Module 3 Enterprise Write Lockdown check
            CapabilityService.verify_organization_write_access(db, file_item.organization_id)

            # 1. Download updated binary from Document Server
            edited_bytes = fetch_edited_document(payload.url)
            if not edited_bytes:
                raise DocumentServerCallbackError("Received empty payload from Document Server")

            # 2. Identify actor for version attribution
            saving_user = None
            if payload.users and len(payload.users) > 0:
                try:
                    user_uuid = uuid.UUID(str(payload.users[0]))
                    saving_user = db.query(User).filter(User.id == user_uuid).first()
                except Exception:
                    saving_user = None

            if not saving_user:
                saving_user = file_item.owner

            # 3. Commit new version via VersionService (CAS deduplication, quota, audit)
            change_summary = (
                "Euro-Office Collaborative Save" if payload.status == 2 else "Euro-Office AutoSave (Forcesave)"
            )
            stream = io.BytesIO(edited_bytes)

            VersionService.upload_new_version(
                db=db,
                org_id=file_item.organization_id,
                file_id=file_item.id,
                stream=stream,
                filename=file_item.name,
                actor=saving_user,
                change_summary=change_summary,
            )

            # 4. Update session
            if session:
                session.last_saved_at = now
                if payload.status == 2:
                    session.is_editing = False
                    session.active_users = []
                else:
                    session.is_editing = True
            db.commit()

            # 5. Audit Log
            audit = AuditLog(
                organization_id=file_item.organization_id,
                user_id=saving_user.id if saving_user else None,
                action=AuditAction.EDIT_EUROOFFICE,
                target_type="FILE",
                target_id=file_item.id,
                target_name=file_item.name,
                details={
                    "status": payload.status,
                    "document_key": document_key,
                    "coauthors": payload.users or [],
                    "save_type": "FINAL" if payload.status == 2 else "FORCESAVE",
                }
            )
            db.add(audit)
            db.commit()

            return EuroOfficeCallbackResponse(error=0, message="Document version successfully committed")

        # Status 3 (SAVING_ERROR) or Status 7 (CORRUPTED_ERROR)
        elif payload.status in (3, 7):
            audit = AuditLog(
                organization_id=file_item.organization_id,
                user_id=file_item.owner_id,
                action=AuditAction.EDIT_EUROOFFICE,
                target_type="FILE",
                target_id=file_item.id,
                target_name=file_item.name,
                details={"error_status": payload.status, "document_key": document_key}
            )
            db.add(audit)
            db.commit()
            return EuroOfficeCallbackResponse(error=0, message=f"Error status {payload.status} recorded")

        return EuroOfficeCallbackResponse(error=0, message="Unhandled status acknowledged")

    @classmethod
    def get_active_coauthors(
        cls,
        db: Session,
        org_id: uuid.UUID,
        file_id: uuid.UUID,
        current_user: User,
    ) -> ActiveCoAuthorsResponse:
        """Returns the list of active colleagues currently collaborating inside the document."""
        file_item = StorageService.get_item(db, org_id, file_id, current_user)
        key = cls.generate_document_key(file_item)

        session = db.query(EuroOfficeSession).filter(
            EuroOfficeSession.file_id == file_item.id,
            EuroOfficeSession.is_editing == True,
        ).order_by(EuroOfficeSession.created_at.desc()).first()

        coauthors: List[CoAuthorItem] = []
        if session and session.active_users:
            user_uuids = []
            for u in session.active_users:
                try:
                    user_uuids.append(uuid.UUID(str(u)))
                except Exception:
                    pass

            if user_uuids:
                users = db.query(User).filter(User.id.in_(user_uuids)).all()
                for u in users:
                    coauthors.append(
                        CoAuthorItem(
                            user_id=u.id,
                            full_name=u.full_name,
                            email=u.email,
                            role=u.role.value if hasattr(u.role, "value") else str(u.role),
                            is_current_user=(u.id == current_user.id),
                        )
                    )

        return ActiveCoAuthorsResponse(
            file_id=file_item.id,
            document_key=key,
            is_editing=bool(session and session.is_editing),
            coauthor_count=len(coauthors),
            coauthors=coauthors,
        )
