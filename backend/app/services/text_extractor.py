import os
import io
from typing import Tuple, Optional
import pypdf
import docx
import openpyxl


class TextExtractor:
    """
    Multi-format document text extractor supporting Word (.docx), PDF (.pdf),
    Excel spreadsheets (.xlsx), plain text, Markdown, and CSV files.
    """

    MAX_EXTRACT_CHARS = 500_000  # Cap extraction to 500KB of text per file

    @classmethod
    def extract_from_file(cls, file_path: str, mime_type: Optional[str] = None) -> Tuple[Optional[str], Optional[str], int, int]:
        """
        Extract text from file path.
        Returns: (extracted_text, error_message, character_count, word_count)
        """
        if not os.path.exists(file_path):
            return None, f"File not found: {file_path}", 0, 0

        ext = os.path.splitext(file_path)[1].lower()

        try:
            with open(file_path, "rb") as f:
                content_bytes = f.read()

            return cls.extract_from_bytes(content_bytes, ext, mime_type)
        except Exception as e:
            return None, f"Extraction failed: {str(e)}", 0, 0

    @classmethod
    def extract_from_bytes(cls, content_bytes: bytes, ext: str, mime_type: Optional[str] = None) -> Tuple[Optional[str], Optional[str], int, int]:
        """
        Extract text from raw byte buffer based on file extension or MIME type.
        """
        if not content_bytes:
            return "", None, 0, 0

        ext = ext.lower().strip()
        text_content = ""

        try:
            # 1. Word Documents (.docx)
            if ext == ".docx" or (mime_type and "wordprocessingml" in mime_type):
                text_content = cls._extract_docx(content_bytes)

            # 2. PDF Documents (.pdf)
            elif ext == ".pdf" or (mime_type and "pdf" in mime_type):
                text_content = cls._extract_pdf(content_bytes)

            # 3. Excel Spreadsheets (.xlsx)
            elif ext == ".xlsx" or (mime_type and "spreadsheetml" in mime_type):
                text_content = cls._extract_xlsx(content_bytes)

            # 4. Text, Markdown, CSV, JSON, Log, XML, HTML
            elif ext in [".txt", ".md", ".markdown", ".csv", ".json", ".log", ".xml", ".html", ".rst", ".yaml", ".yml", ".py"]:
                text_content = cls._extract_text(content_bytes)

            else:
                # Fallback: attempt utf-8 text decode if plausible
                try:
                    decoded = content_bytes.decode("utf-8")
                    # Check if text is printable
                    printable_ratio = sum(c.isprintable() or c.isspace() for c in decoded[:1000]) / min(len(decoded), 1000)
                    if printable_ratio > 0.85:
                        text_content = decoded
                    else:
                        return None, f"Unsupported binary format: {ext}", 0, 0
                except UnicodeDecodeError:
                    return None, f"Unsupported binary format: {ext}", 0, 0

            # Post-processing and truncation
            text_content = cls._clean_text(text_content)
            if len(text_content) > cls.MAX_EXTRACT_CHARS:
                text_content = text_content[:cls.MAX_EXTRACT_CHARS]

            char_count = len(text_content)
            word_count = len(text_content.split())
            return text_content, None, char_count, word_count

        except Exception as e:
            return None, f"Extraction error: {str(e)}", 0, 0

    @classmethod
    def _extract_docx(cls, content_bytes: bytes) -> str:
        doc = docx.Document(io.BytesIO(content_bytes))
        parts = []

        # Paragraphs
        for p in doc.paragraphs:
            if p.text and p.text.strip():
                parts.append(p.text.strip())

        # Tables
        for table in doc.tables:
            for row in table.rows:
                row_texts = [cell.text.strip() for cell in row.cells if cell.text and cell.text.strip()]
                if row_texts:
                    parts.append(" | ".join(row_texts))

        return "\n".join(parts)

    @classmethod
    def _extract_pdf(cls, content_bytes: bytes) -> str:
        reader = pypdf.PdfReader(io.BytesIO(content_bytes))
        parts = []
        for page in reader.pages:
            t = page.extract_text()
            if t and t.strip():
                parts.append(t.strip())
        return "\n".join(parts)

    @classmethod
    def _extract_xlsx(cls, content_bytes: bytes) -> str:
        wb = openpyxl.load_workbook(io.BytesIO(content_bytes), read_only=True, data_only=True)
        parts = []
        for sheet_name in wb.sheetnames:
            sheet = wb[sheet_name]
            parts.append(f"--- Sheet: {sheet_name} ---")
            for row in sheet.iter_rows(values_only=True):
                row_vals = [str(v).strip() for v in row if v is not None and str(v).strip()]
                if row_vals:
                    parts.append(" | ".join(row_vals))
        return "\n".join(parts)

    @classmethod
    def _extract_text(cls, content_bytes: bytes) -> str:
        # Try UTF-8 first, fallback to Latin-1
        try:
            return content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return content_bytes.decode("latin-1", errors="replace")

    @classmethod
    def _clean_text(cls, text: str) -> str:
        if not text:
            return ""
        # Normalize carriage returns and null bytes
        text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
        # Remove consecutive blank lines
        lines = [line.strip() for line in text.split("\n")]
        return "\n".join(line for line in lines if line)
