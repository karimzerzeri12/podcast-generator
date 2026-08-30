import io
import re

from pypdf import PdfReader
from sqlmodel import Session, select

from app.models import SourceDocument
from app.rag.vectorstore import get_vectorstore

TARGET_CHUNK_CHARS = 700

_PAGE_NUMBER_LINE = re.compile(r"^(page\s*)?\d+(\s*/\s*\d+)?$", re.IGNORECASE)


def extract_pdf_pages(data: bytes) -> list[str]:
    """Returns cleaned text for each page (same header/footer stripping and
    hyphenation stitching as extract_pdf_text), one string per page. Running
    headers are detected across the whole document, so this must see all pages —
    callers that want a page subset should slice the returned list, not the input."""
    reader = PdfReader(io.BytesIO(data))
    pages = [page.extract_text() or "" for page in reader.pages]
    line_pages = _strip_noise_lines(pages)
    return [_lines_to_paragraphs(lines) for lines in line_pages]


def extract_pdf_text(data: bytes) -> str:
    """Extracts plain text from a text-based (non-scanned) PDF, stripping
    per-page headers/footers/page numbers and stitching hyphenated line breaks
    so the result reads like the source documents' plain-text counterparts."""
    return "\n\n".join(p for p in extract_pdf_pages(data) if p)


def _strip_noise_lines(pages: list[str]) -> list[list[str]]:
    """Splits each page into lines (blank lines preserved as paragraph
    breaks), blanking out running headers/footers and standalone page
    numbers."""
    line_lists = [[line.strip() for line in page.split("\n")] for page in pages]

    if len(pages) >= 3:
        counts: dict[str, int] = {}
        for lines in line_lists:
            for line in set(filter(None, lines)):
                counts[line] = counts.get(line, 0) + 1
        threshold = max(3, len(pages) // 2)
        repeated = {line for line, count in counts.items() if count >= threshold}
    else:
        repeated = set()

    return [
        [
            "" if (not line or line in repeated or _PAGE_NUMBER_LINE.match(line)) else line
            for line in lines
        ]
        for lines in line_lists
    ]


def _lines_to_paragraphs(lines: list[str]) -> str:
    """Joins a page's lines into paragraphs: a blank line starts a new
    paragraph, a hyphenated line-break is stitched into one word, and other
    line breaks within a paragraph become spaces."""
    paragraphs: list[str] = []
    current = ""
    for line in lines:
        if not line:
            if current:
                paragraphs.append(current)
                current = ""
        elif current.endswith("-"):
            current = current[:-1] + line
        elif current:
            current = f"{current} {line}"
        else:
            current = line
    if current:
        paragraphs.append(current)
    return "\n\n".join(paragraphs)


def chunk_text(text: str, target_chars: int = TARGET_CHUNK_CHARS) -> list[str]:
    """Paragraph-aware chunking: merges paragraphs up to ~target_chars, never
    splitting a paragraph mid-sentence. Oversized single paragraphs are kept whole."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        candidate = f"{current}\n\n{para}".strip() if current else para
        if len(candidate) > target_chars and current:
            chunks.append(current)
            current = para
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def ingest_topic(db: Session, topic_id: int) -> int:
    """(Re)ingests all SourceDocuments for a topic into the vector store. Deletes any
    existing chunks for this topic first — a full replace, not a merge — so a document
    that shrinks or is restructured doesn't leave orphaned stale chunks behind."""
    store = get_vectorstore()
    docs = list(db.exec(select(SourceDocument).where(SourceDocument.topic_id == topic_id)))

    store.delete(where={"topic_id": topic_id})

    all_ids: list[str] = []
    all_texts: list[str] = []
    all_metadatas: list[dict] = []

    for doc in docs:
        chunks = chunk_text(doc.raw_text)
        for idx, chunk in enumerate(chunks):
            all_ids.append(f"doc{doc.id}-chunk{idx}")
            all_texts.append(chunk)
            all_metadatas.append({"topic_id": topic_id, "source_document_id": doc.id})

    if all_ids:
        store.add_texts(texts=all_texts, metadatas=all_metadatas, ids=all_ids)

    return len(all_ids)
