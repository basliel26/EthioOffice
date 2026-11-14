import uuid
import re
import os
from datetime import date, datetime, time, timezone
from typing import Optional, List, Dict, Any, Tuple, Set
from sqlalchemy.orm import Session
from sqlalchemy import text, or_, and_, func, desc, asc
from fastapi import HTTPException, status

from app.models.file import FileItem, DriveType
from app.models.search import FileSearchIndex, SearchIndexStatus
from app.models.tag import Tag, FileTag
from app.models.department import Department
from app.models.user import User
from app.models.letter import LetterRegistry
from app.services.text_extractor import TextExtractor
from app.services.localization_service import LocalizationService
from app.services.share_service import ShareService
from app.services.letter_service import LetterService
from app.services.storage_service import storage_provider
from app.schemas.search import (
    SearchResultItem,
    SearchResponse,
    SearchSuggestionItem,
    SearchSuggestionResponse,
    ReindexResponse,
    SearchStatsResponse,
    UnifiedSearchResult,
)


class SearchService:

    @classmethod
    def index_file(cls, db: Session, file_id: uuid.UUID, force: bool = False) -> Optional[FileSearchIndex]:
        """
        Extract text, normalize Amharic phonetics, generate weighted PostgreSQL TSVECTOR,
        and update the search index for a file item.
        """
        file_item = db.query(FileItem).filter(FileItem.id == file_id).first()
        if not file_item or file_item.is_folder or file_item.is_deleted:
            # If file was deleted or is a folder, purge any existing index
            existing = db.query(FileSearchIndex).filter(FileSearchIndex.file_id == file_id).first()
            if existing:
                db.delete(existing)
                db.commit()
            return None

        current_ver = file_item.current_version
        if not current_ver or not current_ver.storage_path:
            # No version payload available to index
            index_record = db.query(FileSearchIndex).filter(FileSearchIndex.file_id == file_id).first()
            if not index_record:
                index_record = FileSearchIndex(
                    file_id=file_item.id,
                    organization_id=file_item.organization_id,
                    file_name=file_item.name,
                    search_vector=func.to_tsvector('simple', file_item.name),
                    status=SearchIndexStatus.SKIPPED.value,
                    error_message="No version payload found",
                )
                db.add(index_record)
                db.commit()
            return index_record

        # Check fingerprint deduplication (prevent re-indexing unchanged documents)
        existing_idx = db.query(FileSearchIndex).filter(FileSearchIndex.file_id == file_id).first()
        if existing_idx and not force and existing_idx.content_hash == current_ver.checksum_sha256 and existing_idx.status == SearchIndexStatus.INDEXED.value:
            return existing_idx

        # Extract text using multi-format extractor
        resolved_path = current_ver.storage_path
        if not os.path.isabs(resolved_path):
            resolved_path = storage_provider.get_full_path(resolved_path)

        extracted_text, extract_err, char_count, word_count = TextExtractor.extract_from_file(
            file_path=resolved_path,
            mime_type=file_item.mime_type,
        )

        raw_text = extracted_text or ""
        norm_text = LocalizationService.normalize_amharic(raw_text) if raw_text else ""
        norm_name = LocalizationService.normalize_amharic(file_item.name)

        # Expand Amharic proclitics (የ, በ, ለ, ከ, እንደ, ስለ, ወደ)
        def expand_proclitics(txt: str) -> str:
            if not txt:
                return ""
            words = txt.split()
            expanded = []
            for w in words:
                expanded.append(w)
                if len(w) >= 3 and w[0] in ('የ', 'በ', 'ለ', 'ከ'):
                    expanded.append(w[1:])
                elif len(w) >= 4 and (w.startswith('ወደ') or w.startswith('ስለ')):
                    expanded.append(w[2:])
                elif len(w) >= 5 and w.startswith('እንደ'):
                    expanded.append(w[3:])
            return " ".join(expanded)

        expanded_name = expand_proclitics(norm_name)
        expanded_body = expand_proclitics(norm_text[:200_000]) if norm_text else ""

        dept = db.query(Department).filter(Department.id == file_item.department_id).first() if file_item.department_id else None
        dept_name = dept.name if dept else ""
        norm_dept = LocalizationService.normalize_amharic(dept_name) if dept_name else ""

        # Tags
        tags = db.query(Tag.name).join(FileTag, FileTag.tag_id == Tag.id).filter(FileTag.file_id == file_item.id).all()
        tags_str = " ".join(t[0] for t in tags)
        norm_tags = LocalizationService.normalize_amharic(tags_str) if tags_str else ""

        owner = db.query(User).filter(User.id == file_item.owner_id).first()
        owner_name = owner.full_name if owner else ""
        norm_owner = LocalizationService.normalize_amharic(owner_name) if owner_name else ""

        # Compute weighted TSVECTOR in PostgreSQL using 'simple' dictionary
        vector_sql = text("""
        SELECT setweight(to_tsvector('simple', COALESCE(:name, '')), 'A') ||
               setweight(to_tsvector('simple', COALESCE(:meta, '')), 'B') ||
               setweight(to_tsvector('simple', COALESCE(:body, '')), 'C')
        """)

        vector_res = db.execute(vector_sql, {
            "name": f"{expanded_name} {norm_name} {file_item.name}",
            "meta": f"{norm_dept} {norm_tags} {norm_owner}",
            "body": f"{expanded_body} {norm_text[:200_000]}" if norm_text else "",
        }).scalar()

        idx_status = SearchIndexStatus.INDEXED.value if not extract_err else SearchIndexStatus.FAILED.value

        if not existing_idx:
            existing_idx = FileSearchIndex(
                file_id=file_item.id,
                organization_id=file_item.organization_id,
                file_name=file_item.name,
                extracted_text=raw_text,
                normalized_text=norm_text,
                search_vector=vector_res,
                content_hash=current_ver.checksum_sha256,
                status=idx_status,
                error_message=extract_err,
                character_count=char_count,
                word_count=word_count,
                indexed_at=datetime.now(timezone.utc),
            )
            db.add(existing_idx)
        else:
            existing_idx.organization_id = file_item.organization_id
            existing_idx.file_name = file_item.name
            existing_idx.extracted_text = raw_text
            existing_idx.normalized_text = norm_text
            existing_idx.search_vector = vector_res
            existing_idx.content_hash = current_ver.checksum_sha256
            existing_idx.status = idx_status
            existing_idx.error_message = extract_err
            existing_idx.character_count = char_count
            existing_idx.word_count = word_count
            existing_idx.indexed_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(existing_idx)
        return existing_idx

    @classmethod
    def reindex_organization_files(cls, db: Session, organization_id: uuid.UUID, force: bool = False) -> ReindexResponse:
        """
        Bulk re-index all documents belonging to an organization.
        """
        files = db.query(FileItem).filter(
            FileItem.organization_id == organization_id,
            FileItem.is_folder == False,
            FileItem.is_deleted == False,
        ).all()

        indexed = 0
        failed = 0
        skipped = 0

        for f in files:
            try:
                res = cls.index_file(db=db, file_id=f.id, force=force)
                if not res or res.status == SearchIndexStatus.SKIPPED.value:
                    skipped += 1
                elif res.status == SearchIndexStatus.FAILED.value:
                    failed += 1
                else:
                    indexed += 1
            except Exception:
                failed += 1

        return ReindexResponse(
            status="SUCCESS",
            message=f"Reindexed {indexed} files, {skipped} skipped, {failed} failed.",
            indexed_count=indexed,
            failed_count=failed,
            skipped_count=skipped,
        )

    @classmethod
    def generate_snippet(cls, raw_text: Optional[str], query_terms: List[str], max_len: int = 220) -> Optional[str]:
        """
        Generate contextual highlight snippet with **bold** markers around matched terms.
        """
        if not raw_text or not raw_text.strip():
            return None

        clean_text = raw_text.replace("\n", " ").strip()
        if not query_terms:
            return clean_text[:max_len] + ("..." if len(clean_text) > max_len else "")

        # Find best match position
        best_pos = -1
        best_term = ""

        # Normalize terms for matching
        norm_terms = [LocalizationService.normalize_amharic(t) for t in query_terms if len(t) > 1]
        norm_full_text = LocalizationService.normalize_amharic(clean_text)

        for t in norm_terms:
            pos = norm_full_text.lower().find(t.lower())
            if pos != -1 and (best_pos == -1 or pos < best_pos):
                best_pos = pos
                best_term = t

        if best_pos == -1:
            # No term found in body text
            return clean_text[:max_len] + ("..." if len(clean_text) > max_len else "")

        start = max(0, best_pos - 80)
        end = min(len(clean_text), best_pos + len(best_term) + 120)

        snippet = clean_text[start:end].strip()
        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(clean_text) else ""

        # Highlight term matches
        for t in query_terms:
            if len(t) > 1:
                pattern = re.compile(re.escape(t), re.IGNORECASE)
                snippet = pattern.sub(f"**{t}**", snippet)

        return f"{prefix}{snippet}{suffix}"

    @classmethod
    def _classify_file_type(cls, file_item: FileItem) -> str:
        if file_item.is_folder:
            return "folder"
        name = file_item.name.lower()
        mime = (file_item.mime_type or "").lower()

        if name.endswith((".pdf",)) or "pdf" in mime:
            return "pdf"
        elif name.endswith((".docx", ".doc", ".odt")) or "word" in mime or "officedocument" in mime:
            return "document"
        elif name.endswith((".xlsx", ".xls", ".csv")) or "spreadsheet" in mime or "excel" in mime or "csv" in mime:
            return "spreadsheet"
        elif name.endswith((".pptx", ".ppt", ".odp")) or "presentation" in mime or "powerpoint" in mime:
            return "presentation"
        elif name.endswith((".txt", ".md", ".json", ".xml", ".log", ".yaml", ".yml")) or mime.startswith("text/"):
            return "text"
        else:
            return "other"

    @classmethod
    def search_files(
        cls,
        db: Session,
        user: User,
        query: Optional[str] = None,
        file_type: Optional[str] = None,
        mime_type: Optional[str] = None,
        department_id: Optional[uuid.UUID] = None,
        owner_id: Optional[uuid.UUID] = None,
        drive_type: Optional[DriveType] = None,
        tag: Optional[str] = None,
        date_from_gc: Optional[date] = None,
        date_to_gc: Optional[date] = None,
        ethiopian_year: Optional[int] = None,
        min_size_bytes: Optional[int] = None,
        max_size_bytes: Optional[int] = None,
        sort_by: str = "relevance",
        limit: int = 20,
        offset: int = 0,
    ) -> SearchResponse:
        """
        Execute high-performance bilingual full-text and metadata search with strict ACL fencing.
        """
        base_query = db.query(FileItem).outerjoin(
            FileSearchIndex, FileItem.id == FileSearchIndex.file_id
        ).filter(
            FileItem.organization_id == user.organization_id,
            FileItem.is_deleted == False,
        )

        query_terms: List[str] = []
        score_expr = None

        if query and query.strip():
            raw_q = query.strip()
            norm_q = LocalizationService.normalize_amharic(raw_q)
            # Tokenize words
            clean_q = re.sub(r'[^\w\s]', ' ', norm_q).strip()
            terms = [t for t in clean_q.split() if t]
            query_terms = terms if terms else [norm_q]

            tsquery_str = " & ".join(f"{t}:*" for t in terms) if terms else norm_q

            # Full-text vector match OR Trigram match on name OR Trigram match on text OR ILIKE
            ft_match = FileSearchIndex.search_vector.op("@@")(func.to_tsquery('simple', tsquery_str))
            name_ilike = FileItem.name.ilike(f"%{raw_q}%")
            norm_name_ilike = FileSearchIndex.file_name.ilike(f"%{norm_q}%")
            norm_text_ilike = FileSearchIndex.normalized_text.ilike(f"%{norm_q}%")

            # Term-level matches across filename and text
            term_matches = [
                or_(
                    FileItem.name.ilike(f"%{t}%"),
                    FileSearchIndex.normalized_text.ilike(f"%{t}%"),
                )
                for t in terms if len(t) > 1
            ]

            trgm_name = func.similarity(func.coalesce(FileSearchIndex.file_name, FileItem.name), norm_q) > 0.12
            trgm_text = func.similarity(func.coalesce(FileSearchIndex.normalized_text, ''), norm_q) > 0.08

            match_clauses = [ft_match, name_ilike, norm_name_ilike, norm_text_ilike, trgm_name, trgm_text]
            if term_matches:
                match_clauses.extend(term_matches)

            base_query = base_query.filter(or_(*match_clauses))

            # Relevance Score expression
            score_expr = (
                func.coalesce(func.ts_rank_cd(FileSearchIndex.search_vector, func.to_tsquery('simple', tsquery_str)), 0.0) * 3.0 +
                func.coalesce(func.similarity(func.coalesce(FileSearchIndex.file_name, FileItem.name), norm_q), 0.0) * 2.0
            )

        # Filters
        if file_type:
            ft = file_type.lower().strip()
            if ft == "folder":
                base_query = base_query.filter(FileItem.is_folder == True)
            elif ft == "document":
                base_query = base_query.filter(
                    FileItem.is_folder == False,
                    or_(
                        FileItem.name.ilike("%.docx"),
                        FileItem.name.ilike("%.doc"),
                        FileItem.name.ilike("%.odt"),
                        FileItem.mime_type.ilike("%word%"),
                    )
                )
            elif ft == "pdf":
                base_query = base_query.filter(
                    FileItem.is_folder == False,
                    or_(
                        FileItem.name.ilike("%.pdf"),
                        FileItem.mime_type.ilike("%pdf%"),
                    )
                )
            elif ft == "spreadsheet":
                base_query = base_query.filter(
                    FileItem.is_folder == False,
                    or_(
                        FileItem.name.ilike("%.xlsx"),
                        FileItem.name.ilike("%.xls"),
                        FileItem.name.ilike("%.csv"),
                        FileItem.mime_type.ilike("%excel%"),
                        FileItem.mime_type.ilike("%spreadsheet%"),
                        FileItem.mime_type.ilike("%csv%"),
                    )
                )
            elif ft == "text":
                base_query = base_query.filter(
                    FileItem.is_folder == False,
                    or_(
                        FileItem.name.ilike("%.txt"),
                        FileItem.name.ilike("%.md"),
                        FileItem.name.ilike("%.json"),
                        FileItem.mime_type.ilike("text/%"),
                    )
                )

        if mime_type:
            base_query = base_query.filter(FileItem.mime_type == mime_type)

        if department_id:
            base_query = base_query.filter(FileItem.department_id == department_id)

        if owner_id:
            base_query = base_query.filter(FileItem.owner_id == owner_id)

        if drive_type:
            base_query = base_query.filter(FileItem.drive_type == drive_type)

        if tag:
            norm_tag = LocalizationService.normalize_amharic(tag.strip())
            base_query = base_query.join(FileTag, FileTag.file_id == FileItem.id).join(
                Tag, Tag.id == FileTag.tag_id
            ).filter(
                or_(
                    Tag.name.ilike(f"%{tag.strip()}%"),
                    Tag.name.ilike(f"%{norm_tag}%"),
                )
            )

        if date_from_gc:
            dt_from = datetime.combine(date_from_gc, time.min).replace(tzinfo=timezone.utc)
            base_query = base_query.filter(FileItem.updated_at >= dt_from)

        if date_to_gc:
            dt_to = datetime.combine(date_to_gc, time.max).replace(tzinfo=timezone.utc)
            base_query = base_query.filter(FileItem.updated_at <= dt_to)

        if ethiopian_year:
            # Convert Ethiopian Fiscal Year to Gregorian bounds
            start_gc = LocalizationService.ethiopian_to_gregorian(ethiopian_year, 1, 1)
            is_leap = LocalizationService.is_ethiopian_leap_year(ethiopian_year)
            pagume = 6 if is_leap else 5
            end_gc = LocalizationService.ethiopian_to_gregorian(ethiopian_year, 13, pagume)
            base_query = base_query.filter(
                FileItem.updated_at >= datetime.combine(start_gc, time.min).replace(tzinfo=timezone.utc),
                FileItem.updated_at <= datetime.combine(end_gc, time.max).replace(tzinfo=timezone.utc),
            )

        if min_size_bytes is not None:
            base_query = base_query.filter(FileItem.size_bytes >= min_size_bytes)

        if max_size_bytes is not None:
            base_query = base_query.filter(FileItem.size_bytes <= max_size_bytes)

        # Sorting
        if sort_by == "date_desc":
            base_query = base_query.order_by(desc(FileItem.updated_at))
        elif sort_by == "date_asc":
            base_query = base_query.order_by(asc(FileItem.updated_at))
        elif sort_by == "name_asc":
            base_query = base_query.order_by(asc(FileItem.name))
        elif sort_by == "name_desc":
            base_query = base_query.order_by(desc(FileItem.name))
        elif sort_by == "size_desc":
            base_query = base_query.order_by(desc(FileItem.size_bytes))
        elif sort_by == "size_asc":
            base_query = base_query.order_by(asc(FileItem.size_bytes))
        else:
            # Default: relevance sort
            if score_expr is not None:
                base_query = base_query.order_by(desc(score_expr))
            else:
                base_query = base_query.order_by(desc(FileItem.updated_at))

        candidate_items = base_query.all()

        # ACL Filtering & Permission Resolution
        accessible_items = []
        dept_cache = {}
        user_cache = {}
        tag_cache = {}

        # Facet counters
        facet_types: Dict[str, int] = {}
        facet_drives: Dict[str, int] = {}
        facet_departments: Dict[str, int] = {}

        for item in candidate_items:
            # Verify permission
            perm = ShareService.resolve_effective_permission(db=db, file_item=item, user=user)
            if perm is None:
                continue  # Exclude unauthorized files

            # Collect facets
            cat = cls._classify_file_type(item)
            facet_types[cat] = facet_types.get(cat, 0) + 1
            facet_drives[item.drive_type.value] = facet_drives.get(item.drive_type.value, 0) + 1

            if item.department_id:
                if item.department_id not in dept_cache:
                    d = db.query(Department).filter(Department.id == item.department_id).first()
                    dept_cache[item.department_id] = d.name if d else "General"
                d_name = dept_cache[item.department_id]
                facet_departments[d_name] = facet_departments.get(d_name, 0) + 1

            accessible_items.append(item)

        total_hits = len(accessible_items)
        paged_items = accessible_items[offset : offset + limit]

        # Build response items
        results = []
        for item in paged_items:
            if item.department_id and item.department_id not in dept_cache:
                d = db.query(Department).filter(Department.id == item.department_id).first()
                dept_cache[item.department_id] = d.name if d else None

            if item.owner_id not in user_cache:
                u = db.query(User).filter(User.id == item.owner_id).first()
                user_cache[item.owner_id] = u.full_name if u else None

            if item.id not in tag_cache:
                t_names = [t[0] for t in db.query(Tag.name).join(FileTag, FileTag.tag_id == Tag.id).filter(FileTag.file_id == item.id).all()]
                tag_cache[item.id] = t_names

            # Snippet generation
            idx_rec = db.query(FileSearchIndex).filter(FileSearchIndex.file_id == item.id).first()
            raw_body = idx_rec.extracted_text if idx_rec else None
            snippet = cls.generate_snippet(raw_body, query_terms)

            # Ethiopian Date
            updated_date = item.updated_at.date()
            conv = LocalizationService.format_date_conversion(updated_date)
            updated_at_ec = conv.formatted_amharic

            results.append(
                SearchResultItem(
                    file_id=item.id,
                    name=item.name,
                    is_folder=item.is_folder,
                    drive_type=item.drive_type.value,
                    mime_type=item.mime_type,
                    size_bytes=item.size_bytes,
                    owner_id=item.owner_id,
                    owner_name=user_cache.get(item.owner_id),
                    department_id=item.department_id,
                    department_name=dept_cache.get(item.department_id),
                    updated_at=item.updated_at,
                    updated_at_ec=updated_at_ec,
                    relevance_score=1.0,
                    highlight_snippet=snippet,
                    tags=tag_cache.get(item.id, []),
                )
            )

        return SearchResponse(
            query=query,
            total_hits=total_hits,
            items=results,
            limit=limit,
            offset=offset,
            facets={
                "file_types": facet_types,
                "drive_types": facet_drives,
                "departments": facet_departments,
            },
        )

    @classmethod
    def get_suggestions(cls, db: Session, user: User, query: str, limit: int = 10) -> SearchSuggestionResponse:
        """
        Fast typeahead search suggestions for files and tags using trigram similarity.
        """
        clean_q = query.strip()
        if not clean_q:
            return SearchSuggestionResponse(query=query, suggestions=[])

        norm_q = LocalizationService.normalize_amharic(clean_q)
        term = f"%{norm_q}%"
        raw_term = f"%{clean_q}%"

        suggestions: List[SearchSuggestionItem] = []
        seen = set()

        # 1. Matching file names
        files = db.query(FileItem.name).filter(
            FileItem.organization_id == user.organization_id,
            FileItem.is_deleted == False,
            or_(
                FileItem.name.ilike(raw_term),
                FileItem.name.ilike(term),
                func.similarity(FileItem.name, norm_q) > 0.2,
            )
        ).limit(limit).all()

        for f in files:
            name = f[0]
            if name.lower() not in seen:
                seen.add(name.lower())
                suggestions.append(SearchSuggestionItem(text=name, type="file", score=1.0))

        # 2. Matching tags
        if len(suggestions) < limit:
            tags = db.query(Tag.name).filter(
                Tag.organization_id == user.organization_id,
                or_(
                    Tag.name.ilike(raw_term),
                    Tag.name.ilike(term),
                )
            ).limit(limit - len(suggestions)).all()

            for t in tags:
                tag_name = t[0]
                if tag_name.lower() not in seen:
                    seen.add(tag_name.lower())
                    suggestions.append(SearchSuggestionItem(text=tag_name, type="tag", score=0.9))

        return SearchSuggestionResponse(query=query, suggestions=suggestions)

    @classmethod
    def get_search_stats(cls, db: Session, user: User) -> SearchStatsResponse:
        """
        Produce indexing statistics for the organization.
        """
        total = db.query(func.count(FileItem.id)).filter(
            FileItem.organization_id == user.organization_id,
            FileItem.is_folder == False,
            FileItem.is_deleted == False,
        ).scalar() or 0

        indexed = db.query(func.count(FileSearchIndex.file_id)).filter(
            FileSearchIndex.organization_id == user.organization_id,
            FileSearchIndex.status == SearchIndexStatus.INDEXED.value,
        ).scalar() or 0

        failed = db.query(func.count(FileSearchIndex.file_id)).filter(
            FileSearchIndex.organization_id == user.organization_id,
            FileSearchIndex.status == SearchIndexStatus.FAILED.value,
        ).scalar() or 0

        pending = max(0, total - (indexed + failed))

        chars = db.query(func.coalesce(func.sum(FileSearchIndex.character_count), 0)).filter(
            FileSearchIndex.organization_id == user.organization_id,
        ).scalar() or 0

        words = db.query(func.coalesce(func.sum(FileSearchIndex.word_count), 0)).filter(
            FileSearchIndex.organization_id == user.organization_id,
        ).scalar() or 0

        return SearchStatsResponse(
            total_files=total,
            indexed_files=indexed,
            pending_files=pending,
            failed_files=failed,
            total_characters_indexed=int(chars),
            total_words_indexed=int(words),
        )

    @classmethod
    def unified_search(
        cls,
        db: Session,
        user: User,
        query: str,
        limit: int = 20,
    ) -> UnifiedSearchResult:
        """
        Unified search across Document Drive files AND Official Letter Registry.
        """
        # 1. Search Files
        files_resp = cls.search_files(
            db=db,
            user=user,
            query=query,
            limit=limit,
        )

        # 2. Search Letters
        letters_resp = LetterService.list_letters(
            db=db,
            user=user,
            search=query,
            limit=limit,
        )

        letters_data = [
            {
                "id": str(l.id),
                "reference_number": l.reference_number,
                "direction": l.direction.value,
                "status": l.status.value,
                "subject": l.subject,
                "sender_entity": l.sender_entity,
                "recipient_entity": l.recipient_entity,
                "date_ec": l.date_ec,
                "date_gc": l.date_gc.isoformat(),
            }
            for l in letters_resp
        ]

        total = files_resp.total_hits + len(letters_data)

        return UnifiedSearchResult(
            query=query,
            total_hits=total,
            documents=files_resp.items,
            letters=letters_data,
        )
