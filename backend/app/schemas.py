from datetime import datetime

from pydantic import BaseModel

from app.models import EpisodeFormat, JobStage, ListeningEventType


class LoginRequest(BaseModel):
    email: str
    access_code: str


class StudentOut(BaseModel):
    id: int
    name: str
    email: str
    course_id: int


class LoginResponse(BaseModel):
    token: str
    student: StudentOut


class TopicOut(BaseModel):
    id: int
    title: str
    order_index: int
    description: str
    chapter: str = ""
    chapter_description: str = ""


class VoiceOut(BaseModel):
    id: str
    name: str
    description: str = ""
    preview_url: str | None = None


class GenerateRequest(BaseModel):
    topic_id: int
    format: EpisodeFormat
    voice_id: str
    voice_id_2: str = ""


class JobOut(BaseModel):
    id: int
    stage: JobStage
    progress_pct: int
    error_message: str
    audio_cache_id: int | None = None


class GenerateResponse(BaseModel):
    cache_hit: bool
    job: JobOut
    student_episode_id: int


class ListeningEventIn(BaseModel):
    student_episode_id: int
    event_type: ListeningEventType
    position_seconds: float
    client_timestamp: datetime


class EngagementRow(BaseModel):
    student_id: int
    student_name: str
    student_email: str
    topic_id: int
    topic_title: str
    format: EpisodeFormat
    voice_id: str
    voice_id_2: str
    generated_at: datetime
    total_listened_seconds: float
    completion_pct: float
    last_played_at: datetime | None


class PodcastSettingsOut(BaseModel):
    episode_length_minutes: int
    min_minutes: int
    max_minutes: int
    max_generations_per_student: int
    max_generations_cap: int


class PodcastSettingsUpdate(BaseModel):
    # Both optional so the admin can update either setting independently.
    episode_length_minutes: int | None = None
    max_generations_per_student: int | None = None


class EpisodeOut(BaseModel):
    id: int
    topic_id: int
    topic_title: str
    format: EpisodeFormat
    voice_id: str
    voice_id_2: str
    generated_at: datetime
    stage: JobStage
    audio_cache_id: int | None = None
    has_script: bool
