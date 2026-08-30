from datetime import datetime, timezone

from app.analytics.service import HEARTBEAT_INTERVAL_SECONDS, compute_engagement
from app.models import (
    AudioCache,
    CacheStatus,
    EpisodeFormat,
    ListeningEvent,
    ListeningEventType,
    ScriptCache,
    StudentEpisode,
)


def _make_episode(db_session, topic, student, duration_seconds=1200.0):
    script = ScriptCache(
        topic_id=topic.id,
        format=EpisodeFormat.monologue,
        script_path="x.txt",
        word_count=700,
        status=CacheStatus.ready,
    )
    db_session.add(script)
    db_session.commit()
    db_session.refresh(script)

    audio = AudioCache(
        script_cache_id=script.id,
        voice_id="voiceA",
        audio_path="x.mp3",
        duration_seconds=duration_seconds,
        status=CacheStatus.ready,
    )
    db_session.add(audio)
    db_session.commit()
    db_session.refresh(audio)

    episode = StudentEpisode(
        student_id=student.id,
        topic_id=topic.id,
        audio_cache_id=audio.id,
        format=EpisodeFormat.monologue,
        voice_id="voiceA",
    )
    db_session.add(episode)
    db_session.commit()
    db_session.refresh(episode)
    return episode


def test_compute_engagement_aggregates_heartbeats_and_completion(
    db_session, course_and_topic, student
):
    _, topic = course_and_topic
    episode = _make_episode(db_session, topic, student, duration_seconds=1200.0)

    # Stored as naive UTC to match app.models.utcnow()/analytics.service._to_naive_utc
    # — SQLite drops tzinfo on round-trip, so the app standardizes on naive UTC.
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    events = [
        (ListeningEventType.play, 0),
        (ListeningEventType.heartbeat, 15),
        (ListeningEventType.heartbeat, 30),
        (ListeningEventType.heartbeat, 45),
        (ListeningEventType.ended, 1200),
    ]
    for event_type, position in events:
        db_session.add(
            ListeningEvent(
                student_episode_id=episode.id,
                event_type=event_type,
                position_seconds=position,
                client_timestamp=now,
            )
        )
    db_session.commit()

    total_listened, completion_pct, last_played = compute_engagement(db_session, episode)

    assert total_listened == 3 * HEARTBEAT_INTERVAL_SECONDS
    assert completion_pct == 100.0
    assert last_played == now


def test_compute_engagement_with_no_events_is_zero(db_session, course_and_topic, student):
    _, topic = course_and_topic
    episode = _make_episode(db_session, topic, student)

    total_listened, completion_pct, last_played = compute_engagement(db_session, episode)

    assert total_listened == 0.0
    assert completion_pct == 0.0
    assert last_played is None


def test_compute_engagement_partial_completion(db_session, course_and_topic, student):
    _, topic = course_and_topic
    episode = _make_episode(db_session, topic, student, duration_seconds=1000.0)

    now = datetime.now(timezone.utc)
    db_session.add(
        ListeningEvent(
            student_episode_id=episode.id,
            event_type=ListeningEventType.heartbeat,
            position_seconds=250,
            client_timestamp=now,
        )
    )
    db_session.commit()

    _, completion_pct, _ = compute_engagement(db_session, episode)
    assert completion_pct == 25.0
