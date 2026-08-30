"""Build a course's seed data from a single PDF, split by the PDF's chapters/bookmarks.

Usage:
    python -m app.build_course <course.pdf> [options]

Each top-level bookmark in the PDF's outline becomes one topic: the bookmark title is
the topic title, the pages from that bookmark up to the next one are its source text,
and a one-line description is generated for retrieval. The result is written as seed data
(course.json, topics.json, topics/*.txt) which you review, then load with:

    python -m app.seed.seed_data          # applies it non-destructively
    # or delete storage/db.sqlite3 + storage/chroma and restart for a clean reseed

Options:
    --out DIR         Where to write seed data (default: app/seed/data).
    --title TITLE     Course title (default: PDF metadata title, else the file name).
    --description D   Course description (default: auto-generated from chapter titles).
    --min-chars N     Skip chapters with less than N characters of text (default: 200).
    --no-llm          Don't call Gemini; use a truncated first paragraph as each
                      description instead (no API key / quota needed).
    --dry-run         Print the detected chapter breakdown and write nothing.
"""

import argparse
import json
import re
import sys
from pathlib import Path

from pypdf import PdfReader

from app.rag.ingest import extract_pdf_pages

DEFAULT_OUT = Path(__file__).resolve().parent / "seed" / "data"


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "topic"


def _top_level_chapters(reader: PdfReader) -> list[tuple[str, int]]:
    """Returns [(title, start_page_index), ...] for each top-level bookmark, in order.

    pypdf's outline is a list where a nested list holds a bookmark's children; we keep
    only the top-level Destinations (chapters), skipping their sub-sections."""
    try:
        outline = reader.outline
    except Exception:  # noqa: BLE001 — some PDFs have malformed outlines
        return []

    chapters: list[tuple[str, int]] = []
    for item in outline:
        if isinstance(item, list):
            continue  # a nested list = children of the previous chapter; skip
        title = (getattr(item, "title", None) or "").strip()
        if not title:
            continue
        try:
            page_index = reader.get_destination_page_number(item)
        except Exception:  # noqa: BLE001
            continue
        if page_index is not None:
            chapters.append((title, page_index))
    return chapters


def _humanize(stem: str) -> str:
    return re.sub(r"[_\-]+", " ", stem).strip().title() or "Course"


def _llm_title(text: str) -> str:
    """Best-effort: ask Gemini for a short human title from the document's opening text.
    Returns '' on any failure so the caller can fall back."""
    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        from app.generation.script_gen import _get_llm

        messages = [
            SystemMessage(
                content=(
                    "You extract a short, human-readable title from a document. Reply with "
                    "ONLY the title text - no quotes, no 'Title:' prefix, at most ~12 words."
                )
            ),
            HumanMessage(content=text[:2000]),
        ]
        return _get_llm().invoke(messages).text.strip()
    except Exception:  # noqa: BLE001 — title is best-effort
        return ""


def _describe(title: str, text: str, use_llm: bool) -> str:
    fallback = " ".join(text.split())[:180].rsplit(" ", 1)[0]
    if not use_llm:
        return fallback
    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        from app.generation.script_gen import _get_llm

        messages = [
            SystemMessage(
                content=(
                    "You write one-sentence topic descriptions for a course catalog. "
                    "Given a topic title and an excerpt of its material, reply with a "
                    "single plain sentence (no quotes, no preamble) describing what the "
                    "topic covers, suitable for guiding search over the material."
                )
            ),
            HumanMessage(content=f"Title: {title}\n\nExcerpt:\n{text[:2000]}"),
        ]
        result = _get_llm().invoke(messages).text.strip()
        return result or fallback
    except Exception as exc:  # noqa: BLE001 — description is best-effort
        print(f"  ! description via LLM failed ({type(exc).__name__}); using fallback", file=sys.stderr)
        return fallback


def _clean_heading(full_text: str, m: "re.Match", regex: "re.Pattern") -> str:
    """A clean heading/title from a regex match: start at the heading keyword (dropping any
    running-header / page-number prefix on that line), stop before a repeated copy of the
    heading, before an author attribution ('By ...'), and on a word boundary."""
    line_end = full_text.find("\n", m.start())
    if line_end == -1:
        line_end = len(full_text)
    raw = " ".join(full_text[m.start() : line_end].split())
    inner = list(regex.finditer(raw))
    if len(inner) >= 2:  # cut at the 2nd occurrence — that's the duplicated running header
        raw = raw[: inner[1].start()].strip()
    by = re.search(r"\s+By\s", raw)  # course readers often append "By Prof. X"
    if by and by.start() <= 70:
        raw = raw[: by.start()].strip()
    if len(raw) > 60:  # truncate on a word boundary, never mid-word
        raw = raw[:60].rsplit(" ", 1)[0]
    return raw.strip()


def _heading_positions(full_text: str, regex: "re.Pattern") -> list[tuple[int, str]]:
    """Returns [(line_start, clean_title), ...] for each heading match, one per line."""
    out: list[tuple[int, str]] = []
    for m in regex.finditer(full_text):
        line_start = full_text.rfind("\n", 0, m.start()) + 1
        if out and out[-1][0] == line_start:
            continue
        out.append((line_start, _clean_heading(full_text, m, regex)))
    return out


def _chapter_for(pos: int, chapter_map: list[tuple[int, str]]) -> str:
    """The chapter title whose start is the last one at or before `pos`."""
    chapter = ""
    for start, title in chapter_map:
        if start <= pos:
            chapter = title
        else:
            break
    return chapter


def _topics_from_headings(
    full_text: str,
    pattern: str,
    min_chars: int,
    use_llm: bool,
    chapter_map: list[tuple[int, str]] | None = None,
) -> tuple[list[dict], list[tuple[str, str]]] | None:
    """Split text on lines matching `pattern` (a regex) — each match starts a new topic
    titled by that heading line. Used for PDFs whose 'chapters' are only text headings
    (e.g. 'Module 3', '3.1'), not real bookmarks. Consecutive segments with the same heading
    merge (running headers repeat the title on every page). If `chapter_map` is given, each
    topic is tagged with the chapter it falls under. Returns None on a bad regex, [] if the
    pattern matched nothing (caller falls back)."""
    try:
        regex = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
    except re.error as exc:
        print(f"ERROR: invalid --split-on regex: {exc}", file=sys.stderr)
        return None

    entries = _heading_positions(full_text, regex)
    if not entries:
        return []  # no matches — let the caller fall back
    seg_starts = [ls for ls, _ in entries] + [len(full_text)]

    merged: list[list] = []  # [title, text, start_pos]
    for i, (line_start, title) in enumerate(entries):
        seg = full_text[line_start : seg_starts[i + 1]].strip()
        if not seg:
            continue
        if merged and merged[-1][0] == title:  # running-header repeats merge into one topic
            merged[-1][1] += "\n\n" + seg
        else:
            merged.append([title, seg, line_start])

    topics: list[dict] = []
    topic_files: list[tuple[str, str]] = []
    order = 0
    for title, text, pos in merged:
        n_chars = len(text)
        status = "ok" if n_chars >= min_chars else f"SKIPPED (<{min_chars} chars)"
        chapter = _chapter_for(pos, chapter_map) if chapter_map else ""
        label = f"[{chapter}] " if chapter else ""
        print(f"  {label}{title}  ({n_chars} chars) {status}")
        if n_chars < min_chars:
            continue
        order += 1
        filename = f"{order:02d}-{_slug(title)}.txt"
        topics.append(
            {
                "order_index": order,
                "title": title,
                "description": _describe(title, text, use_llm),
                "filename": filename,
                "chapter": chapter,
            }
        )
        topic_files.append((filename, text))
    return topics, topic_files


def build_course(
    pdf_path: Path,
    out_dir: Path,
    *,
    title: str | None,
    description: str | None,
    min_chars: int,
    use_llm: bool,
    dry_run: bool,
    split_on: str | None = None,
    chapter_on: str | None = None,
) -> int:
    data = pdf_path.read_bytes()
    reader = PdfReader(pdf_path)
    pages = extract_pdf_pages(data)  # cleaned text, one string per page

    chapters = _top_level_chapters(reader)
    topics: list[dict] = []
    topic_files: list[tuple[str, str]] = []  # (filename, text)

    # --split-on takes precedence: split by a text-heading regex (for PDFs whose chapters
    # are only visual headings, not bookmarks). --chapter-on additionally groups the
    # resulting sub-topics under their parent chapter (two-level: chapter -> sub-chapter).
    heading_result = None
    if split_on:
        full_text = "\n\n".join(p for p in pages if p).strip()
        course_title = (
            title or (getattr(reader.metadata, "title", None) or "").strip() or _humanize(pdf_path.stem)
        )
        print(f"Course: {course_title}")
        chapter_map: list[tuple[int, str]] | None = None
        if chapter_on:
            try:
                chapter_regex = re.compile(chapter_on, re.IGNORECASE | re.MULTILINE)
            except re.error as exc:
                print(f"ERROR: invalid --chapter-on regex: {exc}", file=sys.stderr)
                return 2
            chapter_map = _heading_positions(full_text, chapter_regex)
            print(f"Chapters (/{chapter_on}/): {', '.join(t for _p, t in chapter_map) or 'none found'}")
        print(f"Splitting '{pdf_path.name}' on pattern /{split_on}/ :\n")
        heading_result = _topics_from_headings(full_text, split_on, min_chars, use_llm, chapter_map)
        if heading_result is None:
            return 2  # bad regex
        if not heading_result[0]:
            print(
                f"WARNING: --split-on /{split_on}/ matched nothing usable; "
                "falling back to bookmarks / single topic.",
                file=sys.stderr,
            )
            heading_result = None
        else:
            topics, topic_files = heading_result

    if heading_result is not None:
        pass  # topics already built from headings
    elif chapters:
        course_title = (
            title or (getattr(reader.metadata, "title", None) or "").strip() or _humanize(pdf_path.stem)
        )
        print(f"Course: {course_title}")
        print(f"Found {len(chapters)} top-level chapter(s) in '{pdf_path.name}':\n")

        n_pages = len(pages)
        bounds = [start for _t, start in chapters] + [n_pages]  # [start, end) per chapter
        order = 0
        for i, (chap_title, start) in enumerate(chapters):
            end = bounds[i + 1]
            text = "\n\n".join(p for p in pages[start:end] if p).strip()
            n_chars = len(text)
            status = "ok" if n_chars >= min_chars else f"SKIPPED (<{min_chars} chars)"
            print(f"  {i + 1:2d}. {chap_title}  (pages {start + 1}-{end}, {n_chars} chars) {status}")
            if n_chars < min_chars:
                continue
            order += 1
            filename = f"{order:02d}-{_slug(chap_title)}.txt"
            topics.append(
                {
                    "order_index": order,
                    "title": chap_title,
                    "description": _describe(chap_title, text, use_llm),
                    "filename": filename,
                }
            )
            topic_files.append((filename, text))

        if not topics:
            print("ERROR: no chapters had enough extractable text.", file=sys.stderr)
            return 2
    else:
        # No bookmarks/outline -> the whole PDF becomes one topic and RAG retrieves across
        # it. This is the "else one topic" fallback (e.g. a journal article or a plain PDF).
        full_text = "\n\n".join(p for p in pages if p).strip()
        print(
            f"No bookmarks/outline in '{pdf_path.name}' - treating the whole document as a "
            f"single topic ({len(full_text)} chars extracted)."
        )
        if len(full_text) < min_chars:
            print(
                "ERROR: not enough extractable text (is it a scanned/image-only PDF?).",
                file=sys.stderr,
            )
            return 2
        topic_title = (
            title
            or (getattr(reader.metadata, "title", None) or "").strip()
            or (_llm_title(full_text) if use_llm else "")
            or _humanize(pdf_path.stem)
        )
        course_title = topic_title
        filename = f"01-{_slug(topic_title)}.txt"
        # In single-topic mode the course and the one topic are the same thing, so an
        # explicit --description applies to both; otherwise auto-generate the topic's.
        topic_description = description or _describe(topic_title, full_text, use_llm)
        topics.append(
            {
                "order_index": 1,
                "title": topic_title,
                "description": topic_description,
                "filename": filename,
            }
        )
        topic_files.append((filename, full_text))
        print(f"Course / topic title: {topic_title}")
        print("  (override with --title if you'd like a different name)")

    course_description = description or (
        "Auto-generated from "
        + pdf_path.name
        + ". Covers: "
        + ", ".join(t["title"] for t in topics[:6])
        + ("." if len(topics) <= 6 else ", and more.")
    )

    if dry_run:
        print(f"\n[dry-run] would write {len(topics)} topic(s) to {out_dir} - nothing written.")
        return 0

    topics_dir = out_dir / "topics"
    topics_dir.mkdir(parents=True, exist_ok=True)
    # Clear existing per-topic text files so a rebuild fully replaces the old course
    # rather than leaving orphaned files behind.
    for old in topics_dir.glob("*.txt"):
        old.unlink()
    for old in topics_dir.glob("*.pdf"):
        old.unlink()

    (out_dir / "course.json").write_text(
        json.dumps({"title": course_title, "description": course_description}, indent=2) + "\n",
        encoding="utf-8",
    )
    (out_dir / "topics.json").write_text(
        json.dumps(topics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    for filename, text in topic_files:
        (topics_dir / filename).write_text(text, encoding="utf-8")

    print(f"\nWrote seed data to {out_dir}:")
    print(f"  course.json, topics.json, and {len(topic_files)} file(s) under topics/")
    print("\nNext: review the generated titles/descriptions, then load them with:")
    print("  python -m app.seed.seed_data")
    print("(or delete storage/db.sqlite3 + storage/chroma and restart for a clean reseed)")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m app.build_course",
        description="Build course seed data from a PDF, split by its chapters/bookmarks.",
    )
    parser.add_argument("pdf", type=Path, help="Path to the course PDF")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output seed-data dir")
    parser.add_argument("--title", default=None, help="Course title override")
    parser.add_argument("--description", default=None, help="Course description override")
    parser.add_argument("--min-chars", type=int, default=200, help="Min chars to keep a chapter")
    parser.add_argument("--no-llm", action="store_true", help="Skip Gemini for descriptions")
    parser.add_argument("--dry-run", action="store_true", help="Preview only; write nothing")
    parser.add_argument(
        "--split-on",
        default=None,
        metavar="REGEX",
        help=(
            "Split by a text-heading pattern instead of bookmarks, for PDFs whose chapters "
            'are only visual headings. Example: --split-on "Module \\d+" or '
            '--split-on "Chapter \\d+".'
        ),
    )
    parser.add_argument(
        "--chapter-on",
        default=None,
        metavar="REGEX",
        help=(
            "Used with --split-on to group the sub-topics under a parent chapter (two-level "
            'chapter -> sub-chapter). Example: --split-on "[34]\\.[0-9]+ [A-Z]" '
            '--chapter-on "Module \\d+".'
        ),
    )
    args = parser.parse_args()

    if not args.pdf.is_file():
        parser.error(f"PDF not found: {args.pdf}")
    if args.pdf.suffix.lower() != ".pdf":
        parser.error("Input must be a .pdf file")

    exit_code = build_course(
        args.pdf,
        args.out,
        title=args.title,
        description=args.description,
        min_chars=args.min_chars,
        use_llm=not args.no_llm,
        dry_run=args.dry_run,
        split_on=args.split_on,
        chapter_on=args.chapter_on,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
