from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.courses.service import list_topics
from app.deps import get_current_student, get_db
from app.models import Student
from app.schemas import TopicOut

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("/{course_id}/topics", response_model=list[TopicOut])
def get_topics(
    course_id: int,
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
) -> list[TopicOut]:
    if student.course_id != course_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not enrolled in this course")
    topics = list_topics(db, course_id)
    return [
        TopicOut(
            id=t.id,
            title=t.title,
            order_index=t.order_index,
            description=t.description,
            chapter=t.chapter,
            chapter_description=t.chapter_description,
        )
        for t in topics
    ]
