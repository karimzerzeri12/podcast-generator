from sqlmodel import Session, select

from app.analytics.service import compute_engagement
from app.models import Student, StudentEpisode, Topic
from app.schemas import EngagementRow


def _current_episodes(db: Session) -> list[StudentEpisode]:
    """Latest StudentEpisode per (student_id, topic_id) — a student may have
    regenerated with a different format/voice, in which case only their most recent
    choice counts as their "current" assigned podcast."""
    all_episodes = list(db.exec(select(StudentEpisode)))
    latest: dict[tuple[int, int], StudentEpisode] = {}
    for ep in all_episodes:
        key = (ep.student_id, ep.topic_id)
        if key not in latest or ep.generated_at > latest[key].generated_at:
            latest[key] = ep
    return list(latest.values())


def get_engagement_rows(db: Session) -> list[EngagementRow]:
    rows: list[EngagementRow] = []
    for episode in _current_episodes(db):
        student = db.get(Student, episode.student_id)
        topic = db.get(Topic, episode.topic_id)
        if student is None or topic is None:
            continue

        total_listened_seconds, completion_pct, last_played_at = compute_engagement(db, episode)

        rows.append(
            EngagementRow(
                student_id=student.id,
                student_name=student.name,
                student_email=student.email,
                topic_id=topic.id,
                topic_title=topic.title,
                format=episode.format,
                voice_id=episode.voice_id,
                voice_id_2=episode.voice_id_2,
                generated_at=episode.generated_at,
                total_listened_seconds=total_listened_seconds,
                completion_pct=completion_pct,
                last_played_at=last_played_at,
            )
        )

    rows.sort(key=lambda r: (r.student_name, r.topic_title))
    return rows
