from datetime import datetime, timezone
from enum import StrEnum
from typing import Optional

from sqlmodel import Field, SQLModel, UniqueConstraint


def utcnow() -> datetime:
    # SQLite drops tzinfo on round-trip, so we standardize on naive UTC everywhere
    # (both here and for client-submitted timestamps in analytics/service.py) to
    # avoid aware/naive comparison bugs.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class EpisodeFormat(StrEnum):
    monologue = "monologue"
    interview = "interview"
    two_host = "two_host"
    debate = "debate"


class CacheStatus(StrEnum):
    pending = "pending"
    ready = "ready"
    failed = "failed"


class JobStage(StrEnum):
    queued = "queued"
    generating_script = "generating_script"
    synthesizing_audio = "synthesizing_audio"
    done = "done"
    failed = "failed"


class ListeningEventType(StrEnum):
    play = "play"
    pause = "pause"
    heartbeat = "heartbeat"
    seek = "seek"
    ended = "ended"


class Course(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    description: str = ""


class Student(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    access_code: str
    name: str
    course_id: int = Field(foreign_key="course.id")


class Topic(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="course.id")
    title: str
    order_index: int = 0
    description: str = ""
    # Optional grouping label (e.g. "Module 3 Drivers of Flavour perception"). Empty for
    # ungrouped courses. Lets the UI present a chapter -> sub-chapter selection flow.
    chapter: str = ""
    # Optional blurb shown under the chapter on the landing page. Denormalized onto every
    # topic in the chapter (they carry the same value); edited via seed/data/chapters.json.
    chapter_description: str = ""
    # Bumped whenever this topic's source material actually changes (by content
    # hash) — folded into ScriptCache's cache key so stale scripts/audio from
    # before the change are never served, while other topics' caches are untouched.
    material_version: int = 1


class SourceDocument(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    topic_id: int = Field(foreign_key="topic.id")
    filename: str
    raw_text: str
    content_hash: str = ""
    ingested_at: datetime = Field(default_factory=utcnow)


class ScriptCache(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint(
            "topic_id", "format", "material_version", "length_minutes",
            name="uq_script_topic_format_version_length",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    topic_id: int = Field(foreign_key="topic.id")
    format: EpisodeFormat
    material_version: int = 1
    # The admin-controlled target episode length (see PodcastSettings) at the time this
    # script was generated — folded into the cache key so changing the length setting
    # doesn't serve a script timed for the old length.
    length_minutes: int = 5
    script_path: str = ""
    word_count: int = 0
    status: CacheStatus = CacheStatus.pending
    created_at: datetime = Field(default_factory=utcnow)


class AudioCache(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("script_cache_id", "voice_id", "voice_id_2", name="uq_audio_script_voices"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    script_cache_id: int = Field(foreign_key="scriptcache.id")
    voice_id: str
    voice_id_2: str = ""  # second speaker's voice for dialogue formats; empty for monologue
    audio_path: str = ""
    duration_seconds: float = 0
    status: CacheStatus = CacheStatus.pending
    created_at: datetime = Field(default_factory=utcnow)


class GenerationJob(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="student.id")
    topic_id: int = Field(foreign_key="topic.id")
    format: EpisodeFormat
    voice_id: str
    voice_id_2: str = ""
    stage: JobStage = JobStage.queued
    progress_pct: int = 0
    error_message: str = ""
    script_cache_id: Optional[int] = Field(default=None, foreign_key="scriptcache.id")
    audio_cache_id: Optional[int] = Field(default=None, foreign_key="audiocache.id")
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class StudentEpisode(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="student.id")
    topic_id: int = Field(foreign_key="topic.id")
    audio_cache_id: Optional[int] = Field(default=None, foreign_key="audiocache.id")
    generation_job_id: Optional[int] = Field(default=None, foreign_key="generationjob.id")
    format: EpisodeFormat
    voice_id: str
    voice_id_2: str = ""
    generated_at: datetime = Field(default_factory=utcnow)


class PodcastSettings(SQLModel, table=True):
    """Single-row table of admin-controlled generation settings (not in .env, since
    the admin should be able to change these at runtime without a redeploy)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    episode_length_minutes: int = 5
    # Max podcasts a single student may generate. 0 means unlimited.
    max_generations_per_student: int = 0


class ListeningEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    student_episode_id: int = Field(foreign_key="studentepisode.id")
    event_type: ListeningEventType
    position_seconds: float = 0
    client_timestamp: datetime
    created_at: datetime = Field(default_factory=utcnow)
