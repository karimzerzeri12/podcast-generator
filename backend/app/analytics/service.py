from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models import AudioCache, ListeningEvent, ListeningEventType, StudentEpisode
from app.schemas import ListeningEventIn

# Matches the frontend AudioPlayer's heartbeat interval — total listened time is
# approximated as heartbeat_count * this interval, which is simple, cheap to test,
# and accurate enough for engagement/usage monitoring (not billing-grade precision).
HEARTBEAT_INTERVAL_SECONDS = 15


def _to_naive_utc(dt: datetime) -> datetime:
    # SQLite drops tzinfo on round-trip — normalize to naive UTC at write time so
    # every datetime in the DB is comparable (see app/models.py's utcnow()).
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def record_event(db: Session, episode: StudentEpisode, body: ListeningEventIn) -> ListeningEvent:
    event = ListeningEvent(
        student_episode_id=episode.id,
        event_type=body.event_type,
        position_seconds=body.position_seconds,
        client_timestamp=_to_naive_utc(body.client_timestamp),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def compute_engagement(
    db: Session, episode: StudentEpisode
) -> tuple[float, float, datetime | None]:
    """Returns (total_listened_seconds, completion_pct, last_played_at) for one episode."""
    events = list(
        db.exec(
            select(ListeningEvent).where(ListeningEvent.student_episode_id == episode.id)
        )
    )
    if not events:
        return 0.0, 0.0, None

    heartbeats = [e for e in events if e.event_type == ListeningEventType.heartbeat]
    total_listened_seconds = len(heartbeats) * HEARTBEAT_INTERVAL_SECONDS

    max_position = max((e.position_seconds for e in events), default=0.0)
    completion_pct = 0.0
    if episode.audio_cache_id is not None:
        audio = db.get(AudioCache, episode.audio_cache_id)
        if audio is not None and audio.duration_seconds > 0:
            completion_pct = min(100.0, round((max_position / audio.duration_seconds) * 100, 1))

    last_played_at = max(e.client_timestamp for e in events)
    return float(total_listened_seconds), completion_pct, last_played_at
