import uuid
from datetime import date, datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field
from app.models.file import DriveType


class SearchResultItem(BaseModel):
    file_id: uuid.UUID
    name: str
    is_folder: bool
    drive_type: str
    mime_type: Optional[str] = None
    size_bytes: int = 0
    owner_id: uuid.UUID
    owner_name: Optional[str] = None
    department_id: Optional[uuid.UUID] = None
    department_name: Optional[str] = None
    updated_at: datetime
    updated_at_ec: Optional[str] = None
    relevance_score: float = 0.0
    highlight_snippet: Optional[str] = None
    tags: List[str] = []

    model_config = ConfigDict(from_attributes=True)


class SearchResponse(BaseModel):
    query: Optional[str] = None
    total_hits: int
    items: List[SearchResultItem]
    limit: int
    offset: int
    facets: Dict[str, Any] = {}


class SearchSuggestionItem(BaseModel):
    text: str
    type: str = "keyword"  # 'file', 'tag', 'department', 'keyword'
    score: float = 1.0


class SearchSuggestionResponse(BaseModel):
    query: str
    suggestions: List[SearchSuggestionItem]


class ReindexResponse(BaseModel):
    status: str
    message: str
    indexed_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0


class SearchStatsResponse(BaseModel):
    total_files: int
    indexed_files: int
    pending_files: int
    failed_files: int
    total_characters_indexed: int
    total_words_indexed: int


class UnifiedSearchResult(BaseModel):
    query: Optional[str] = None
    total_hits: int
    documents: List[SearchResultItem]
    letters: List[Dict[str, Any]] = []
