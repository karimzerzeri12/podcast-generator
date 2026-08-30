import csv
import io

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from app.admin.service import get_engagement_rows
from app.deps import get_db, require_admin
from app.podcast_settings import (
    MAX_GENERATIONS_CAP,
    MAX_LENGTH_MINUTES,
    MIN_LENGTH_MINUTES,
    get_episode_length_minutes,
    get_max_generations_per_student,
    set_episode_length_minutes,
    set_max_generations_per_student,
)
from app.schemas import EngagementRow, PodcastSettingsOut, PodcastSettingsUpdate

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def _settings_out(db: Session) -> PodcastSettingsOut:
    return PodcastSettingsOut(
        episode_length_minutes=get_episode_length_minutes(db),
        min_minutes=MIN_LENGTH_MINUTES,
        max_minutes=MAX_LENGTH_MINUTES,
        max_generations_per_student=get_max_generations_per_student(db),
        max_generations_cap=MAX_GENERATIONS_CAP,
    )


@router.get("/settings", response_model=PodcastSettingsOut)
def get_settings_route(db: Session = Depends(get_db)) -> PodcastSettingsOut:
    return _settings_out(db)


@router.put("/settings", response_model=PodcastSettingsOut)
def update_settings_route(
    body: PodcastSettingsUpdate, db: Session = Depends(get_db)
) -> PodcastSettingsOut:
    try:
        if body.episode_length_minutes is not None:
            set_episode_length_minutes(db, body.episode_length_minutes)
        if body.max_generations_per_student is not None:
            set_max_generations_per_student(db, body.max_generations_per_student)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return _settings_out(db)


@router.get("/engagement", response_model=list[EngagementRow])
def engagement(db: Session = Depends(get_db)) -> list[EngagementRow]:
    return get_engagement_rows(db)


@router.get("/engagement.csv")
def engagement_csv(db: Session = Depends(get_db)) -> StreamingResponse:
    rows = get_engagement_rows(db)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "student_id",
            "student_name",
            "student_email",
            "topic_id",
            "topic_title",
            "format",
            "voice_id",
            "voice_id_2",
            "generated_at",
            "total_listened_seconds",
            "completion_pct",
            "last_played_at",
        ]
    )
    for r in rows:
        writer.writerow(
            [
                r.student_id,
                r.student_name,
                r.student_email,
                r.topic_id,
                r.topic_title,
                r.format.value,
                r.voice_id,
                r.voice_id_2,
                r.generated_at.isoformat(),
                r.total_listened_seconds,
                r.completion_pct,
                r.last_played_at.isoformat() if r.last_played_at else "",
            ]
        )
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=engagement.csv"},
    )
