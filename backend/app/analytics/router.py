from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.analytics.service import record_event
from app.deps import get_current_student, get_db
from app.models import Student, StudentEpisode
from app.schemas import ListeningEventIn

router = APIRouter(tags=["analytics"])


@router.post("/listening-events", status_code=status.HTTP_201_CREATED)
def post_listening_event(
    body: ListeningEventIn,
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
) -> dict:
    episode = db.get(StudentEpisode, body.student_episode_id)
    if episode is None or episode.student_id != student.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Episode not found")
    record_event(db, episode, body)
    return {"ok": True}
