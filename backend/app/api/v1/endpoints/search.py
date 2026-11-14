import uuid
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User, UserRole
from app.models.file import DriveType
from app.schemas.search import (
    SearchResponse,
    SearchSuggestionResponse,
    ReindexResponse,
    SearchStatsResponse,
    UnifiedSearchResult,
)
from app.services.search_service import SearchService

router = APIRouter()


@router.get("", response_model=SearchResponse)
def search_documents(
    q: Optional[str] = Query(None, description="Bilingual search query in Amharic or English"),
    file_type: Optional[str] = Query(None, description="Filter by file type: document, spreadsheet, presentation, pdf, text, folder"),
    mime_type: Optional[str] = Query(None, description="Filter by MIME type"),
    department_id: Optional[uuid.UUID] = Query(None, description="Filter by department ID"),
    owner_id: Optional[uuid.UUID] = Query(None, description="Filter by owner user ID"),
    drive_type: Optional[DriveType] = Query(None, description="Filter by drive type: PERSONAL or COMPANY"),
    tag: Optional[str] = Query(None, description="Filter by tag label"),
    date_from: Optional[date] = Query(None, description="Filter by updated date start (Gregorian)"),
    date_to: Optional[date] = Query(None, description="Filter by updated date end (Gregorian)"),
    ethiopian_year: Optional[int] = Query(None, description="Filter by Ethiopian fiscal year (e.g. 2018)"),
    min_size: Optional[int] = Query(None, ge=0, description="Minimum size in bytes"),
    max_size: Optional[int] = Query(None, ge=0, description="Maximum size in bytes"),
    sort_by: str = Query("relevance", description="Sort order: relevance, date_desc, date_asc, name_asc, name_desc, size_desc, size_asc"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Execute full-text and metadata search with Amharic phonetic folding, GIN indexing, and ACL fencing.
    """
    return SearchService.search_files(
        db=db,
        user=current_user,
        query=q,
        file_type=file_type,
        mime_type=mime_type,
        department_id=department_id,
        owner_id=owner_id,
        drive_type=drive_type,
        tag=tag,
        date_from_gc=date_from,
        date_to_gc=date_to,
        ethiopian_year=ethiopian_year,
        min_size_bytes=min_size,
        max_size_bytes=max_size,
        sort_by=sort_by,
        limit=limit,
        offset=offset,
    )


@router.get("/suggest", response_model=SearchSuggestionResponse)
def get_search_suggestions(
    q: str = Query(..., min_length=1, description="Partial search query"),
    limit: int = Query(10, ge=1, le=25),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Fast typeahead autocomplete search suggestions using trigram matching.
    """
    return SearchService.get_suggestions(
        db=db,
        user=current_user,
        query=q,
        limit=limit,
    )


@router.get("/stats", response_model=SearchStatsResponse)
def get_search_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve document search indexing metrics and character counts for the organization.
    """
    return SearchService.get_search_stats(db=db, user=current_user)


@router.get("/unified", response_model=UnifiedSearchResult)
def unified_search(
    q: str = Query(..., min_length=1, description="Query to search across Document Drive files AND Letter Registry"),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Cross-module enterprise search across Document Drive and Official Letter Registry.
    """
    return SearchService.unified_search(
        db=db,
        user=current_user,
        query=q,
        limit=limit,
    )


@router.post("/reindex/{file_id}")
def reindex_single_file(
    file_id: uuid.UUID,
    force: bool = Query(False, description="Force re-indexing even if content hash matches"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Trigger immediate extraction and re-indexing of a single file.
    """
    res = SearchService.index_file(db=db, file_id=file_id, force=force)
    if not res:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found or cannot be indexed")
    return {
        "status": res.status,
        "file_id": str(res.file_id),
        "word_count": res.word_count,
        "character_count": res.character_count,
    }


@router.post("/reindex", response_model=ReindexResponse)
def reindex_all_files(
    force: bool = Query(False, description="Force re-indexing of all organization files"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Trigger organization-wide bulk document re-indexing. Requires Organization Administrator privileges.
    """
    if current_user.role not in (UserRole.ADMIN, UserRole.SUPER_ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bulk re-indexing requires Organization Administrator privileges",
        )

    return SearchService.reindex_organization_files(
        db=db,
        organization_id=current_user.organization_id,
        force=force,
    )
