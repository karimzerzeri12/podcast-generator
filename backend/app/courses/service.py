from sqlmodel import Session, select

from app.models import Topic


def list_topics(db: Session, course_id: int) -> list[Topic]:
    return list(
        db.exec(
            select(Topic).where(Topic.course_id == course_id).order_by(Topic.order_index)
        ).all()
    )
