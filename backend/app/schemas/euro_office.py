import uuid
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class DocumentPermissions(BaseModel):
    edit: bool = False
    download: bool = True
    print: bool = True
    review: bool = False
    comment: bool = False


class DocumentUser(BaseModel):
    id: str
    name: str


class DocumentObject(BaseModel):
    fileType: str
    key: str
    title: str
    url: str
    permissions: DocumentPermissions


class EditorCustomization(BaseModel):
    autosave: bool = True
    forcesave: bool = True
    chat: bool = True
    comments: bool = True
    customer: Optional[Dict[str, str]] = None


class EditorConfig(BaseModel):
    mode: str = "view"  # "view" | "edit"
    lang: str = "en"
    callbackUrl: str
    user: DocumentUser
    customization: EditorCustomization = Field(default_factory=EditorCustomization)


class EuroOfficeConfigResponse(BaseModel):
    documentType: str  # "word" | "cell" | "slide"
    document: DocumentObject
    editorConfig: EditorConfig
    token: str


class EuroOfficeCallbackPayload(BaseModel):
    actions: Optional[List[Dict[str, Any]]] = None
    key: str
    status: int  # 1: being edited, 2: save, 3: error, 4: closed, 6: force-save, 7: corrupted
    url: Optional[str] = None
    users: Optional[List[str]] = None
    history: Optional[Dict[str, Any]] = None
    token: Optional[str] = None


class EuroOfficeCallbackResponse(BaseModel):
    error: int = 0
    message: Optional[str] = None


class CoAuthorItem(BaseModel):
    user_id: uuid.UUID
    full_name: str
    email: str
    role: str
    is_current_user: bool = False


class ActiveCoAuthorsResponse(BaseModel):
    file_id: uuid.UUID
    document_key: str
    is_editing: bool
    coauthor_count: int
    coauthors: List[CoAuthorItem]
