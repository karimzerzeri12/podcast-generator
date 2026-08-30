"""CLI: python -m app.ingest [--dry-run]

Loads course material from SOURCE_ROOT (a local/network path or an S3-compatible
URI) per its manifest, and upserts it into the DB + vector store. This is the
non-destructive replacement for the old "delete db.sqlite3 and reseed" workflow:
it's idempotent (unchanged files are a no-op), it never touches students,
engagement records, or generated audio, and it never deletes a topic just
because it's absent from the manifest (it warns instead — you may be mid-rollout
of a partial manifest).
"""

import argparse
import sys

from sqlmodel import Session, select

from app.config import get_settings
from app.db import engine, init_db
from app.materials.manifest import load_manifest, resolve_manifest_path, validate_manifest
from app.materials.service import upsert_topic_material
from app.materials.storage import check_source_root, get_filesystem, join
from app.models import Course, Topic
from app.rag.ingest import extract_pdf_text


def _read_source_text(fs, path: str) -> str:
    if path.lower().endswith(".pdf"):
        with fs.open(path, "rb") as f:
            return extract_pdf_text(f.read())
    with fs.open(path, "r", encoding="utf-8") as f:
        return f.read()


def run(dry_run: bool = False) -> None:
    settings = get_settings()
    if not settings.source_root:
        print("SOURCE_ROOT is not configured — nothing to do.", file=sys.stderr)
        sys.exit(1)

    check_source_root()
    fs, root = get_filesystem()
    manifest_path = resolve_manifest_path(root)
    print(f"Manifest: {manifest_path}{' (dry run)' if dry_run else ''}")

    entries = load_manifest(fs, manifest_path)
    validate_manifest(fs, root, entries)

    init_db()
    with Session(engine) as db:
        course = db.exec(select(Course)).first()
        if course is None:
            print(
                "No course exists yet — run the seed script once first to create one, "
                "or create a Course row directly.",
                file=sys.stderr,
            )
            sys.exit(1)

        manifest_titles = {e.title for e in entries}
        existing_titles = {
            t.title for t in db.exec(select(Topic).where(Topic.course_id == course.id))
        }
        for stale_title in sorted(existing_titles - manifest_titles):
            print(f"WARNING: topic {stale_title!r} exists in the DB but is absent from the "
                  "manifest — leaving it untouched (not deleted).")

        for entry in entries:
            path = join(root, entry.filename)
            raw_text = _read_source_text(fs, path)

            topic, changed, action = upsert_topic_material(
                db,
                course_id=course.id,
                title=entry.title,
                description=entry.description,
                filename=entry.filename,
                raw_text=raw_text,
                dry_run=dry_run,
            )
            version_note = f", material_version={topic.material_version}" if topic and changed else ""
            print(f"  {entry.title}: {action}{version_note}")

    print("Dry run — no changes were made." if dry_run else "Done.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="Print the plan without changing anything"
    )
    args = parser.parse_args()
    run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
