import hashlib

from sqlmodel import Session, select

from app.models import SourceDocument, Topic
from app.rag.ingest import ingest_topic


def content_hash(raw_text: str) -> str:
    return hashlib.sha256(raw_text.encode("utf-8")).hexdigest()


def upsert_topic_material(
    db: Session,
    *,
    course_id: int,
    title: str,
    description: str,
    filename: str,
    raw_text: str,
    chapter: str = "",
    chapter_description: str = "",
    dry_run: bool = False,
) -> tuple[Topic | None, bool, str]:
    """Creates or updates a Topic + its SourceDocument from source material, and
    (re)ingests it into the vector store only when the content actually changed.

    This is the single upsert path shared by the admin PDF-upload endpoint and the
    `python -m app.ingest` CLI — both call this function so they can never drift
    out of sync with each other.

    Returns (topic, changed, action):
    - action is one of "unchanged" | "created" | "updated"
    - changed is False only for "unchanged"
    - in dry_run mode nothing is written to the DB or vector store; topic is the
      existing Topic if one matches by title, or None if this would create one.

    Matches an existing topic by (course_id, title) — the same rule used by the
    admin upload path — so re-ingesting the same title updates that topic's
    material in place rather than creating a duplicate. A content-hash comparison
    makes unchanged material a fast no-op: no re-embedding, no material_version
    bump, no cache invalidation for that topic.
    """
    topic = db.exec(select(Topic).where(Topic.course_id == course_id, Topic.title == title)).first()

    doc = None
    if topic is not None:
        doc = db.exec(
            select(SourceDocument).where(
                SourceDocument.topic_id == topic.id, SourceDocument.filename == filename
            )
        ).first()

    new_hash = content_hash(raw_text)
    if doc is not None and doc.content_hash == new_hash:
        return topic, False, "unchanged"

    action = "updated" if topic is not None else "created"
    if dry_run:
        return topic, True, action

    if topic is None:
        existing_orders = [
            t.order_index for t in db.exec(select(Topic).where(Topic.course_id == course_id))
        ]
        topic = Topic(
            course_id=course_id,
            title=title,
            description=description,
            chapter=chapter,
            chapter_description=chapter_description,
            order_index=max(existing_orders, default=0) + 1,
        )
        db.add(topic)
        db.commit()
        db.refresh(topic)
    elif (
        topic.description != description
        or topic.chapter != chapter
        or topic.chapter_description != chapter_description
    ):
        topic.description = description
        topic.chapter = chapter
        topic.chapter_description = chapter_description
        db.add(topic)
        db.commit()

    if doc is None:
        doc = SourceDocument(topic_id=topic.id, filename=filename, raw_text=raw_text, content_hash=new_hash)
    else:
        doc.raw_text = raw_text
        doc.content_hash = new_hash
    db.add(doc)
    db.commit()

    if action == "updated":
        # Only bump the version when replacing material on an already-ingested
        # topic — a brand-new topic starts at material_version=1 with nothing to
        # invalidate.
        topic.material_version += 1
        db.add(topic)
        db.commit()
        db.refresh(topic)

    ingest_topic(db, topic.id)
    return topic, True, action
