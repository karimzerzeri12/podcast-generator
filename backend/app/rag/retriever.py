from sqlmodel import Session, select

from app.models import SourceDocument, Topic


def retrieve_topic_context(db: Session, topic: Topic) -> str:
    """Returns the topic's full source material — every SourceDocument for this
    topic, concatenated in ingestion order. A topic's material is a bounded,
    student-selected section (a few KB up to tens of KB), well within the LLM's
    context window, so the whole section is used rather than a similarity-searched
    subset of it."""
    docs = db.exec(
        select(SourceDocument)
        .where(SourceDocument.topic_id == topic.id)
        .order_by(SourceDocument.id)
    ).all()
    return "\n\n".join(doc.raw_text for doc in docs)
