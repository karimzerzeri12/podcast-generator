import re

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from app.config import get_settings
from app.deps import get_current_student, get_db
from app.generation.service import request_generation
from app.models import (
    AudioCache,
    CacheStatus,
    EpisodeFormat,
    GenerationJob,
    Student,
    StudentEpisode,
    Topic,
)
from app.podcast_settings import get_max_generations_per_student
from app.schemas import GenerateRequest, GenerateResponse, JobOut

router = APIRouter(tags=["generation"])

# ElevenLabs voice IDs are short alphanumeric tokens. Enforcing this charset stops a
# crafted voice_id from (a) traversing out of the audio dir when used in an output
# filename or (b) redirecting the ElevenLabs request URL to another API path.
_VOICE_ID_RE = re.compile(r"^[A-Za-z0-9]{1,64}$")


def _validate_voice_id(voice_id: str) -> None:
    if not _VOICE_ID_RE.match(voice_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid voice id")
    # When the operator has curated a voice list, only those may be requested — a
    # student can't drive TTS spend (or synthesis) with arbitrary account voices.
    allow_list = get_settings().voice_id_list
    if allow_list and voice_id not in allow_list:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Voice not available")


@router.post("/generate", response_model=GenerateResponse)
def generate(
    body: GenerateRequest,
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
) -> GenerateResponse:
    topic = db.get(Topic, body.topic_id)
    if topic is None or topic.course_id != student.course_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Topic not found")

    # Admin-controlled per-student generation cap (0 == unlimited). Each generate request
    # produces one StudentEpisode, so we count those. Checked before any work is queued.
    limit = get_max_generations_per_student(db)
    if limit > 0:
        used = len(
            db.exec(
                select(StudentEpisode.id).where(StudentEpisode.student_id == student.id)
            ).all()
        )
        if used >= limit:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"You've reached your limit of {limit} generated podcasts.",
            )

    _validate_voice_id(body.voice_id)

    if body.format == EpisodeFormat.monologue:
        voice_id_2 = ""
    else:
        if not body.voice_id_2:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "This format needs a second voice")
        if body.voice_id_2 == body.voice_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Pick two different voices")
        _validate_voice_id(body.voice_id_2)
        voice_id_2 = body.voice_id_2

    cache_hit, job, episode_id = request_generation(
        db, student, body.topic_id, body.format, body.voice_id, voice_id_2
    )
    return GenerateResponse(
        cache_hit=cache_hit,
        job=JobOut(
            id=job.id,
            stage=job.stage,
            progress_pct=job.progress_pct,
            error_message=job.error_message,
            audio_cache_id=job.audio_cache_id,
        ),
        student_episode_id=episode_id,
    )


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
) -> JobOut:
    job = db.get(GenerationJob, job_id)
    # Ownership is via the StudentEpisode linkage, not job.student_id: when students
    # share one in-flight job (the dedup path in request_generation), later students
    # legitimately poll a job first created for someone else, but each still has their
    # own StudentEpisode pointing at it.
    linked = db.exec(
        select(StudentEpisode.id).where(
            StudentEpisode.student_id == student.id,
            StudentEpisode.generation_job_id == job_id,
        )
    ).first()
    if job is None or linked is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return JobOut(
        id=job.id,
        stage=job.stage,
        progress_pct=job.progress_pct,
        error_message=job.error_message,
        audio_cache_id=job.audio_cache_id,
    )


def _resolve_owned_audio_path(db: Session, audio_cache_id: int, student: Student):
    # Audio files are shared across students by the cache, so access is gated on the
    # student having a StudentEpisode that resolved to this audio — not on who first
    # generated it. Without this check any student could stream any other student's
    # audio by iterating audio_cache_id (IDOR).
    owns = db.exec(
        select(StudentEpisode.id).where(
            StudentEpisode.student_id == student.id,
            StudentEpisode.audio_cache_id == audio_cache_id,
        )
    ).first()
    if owns is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Audio not found")
    audio = db.get(AudioCache, audio_cache_id)
    if audio is None or audio.status != CacheStatus.ready:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Audio not ready")
    return get_settings().resolved_path(audio.audio_path)


@router.get("/audio/{audio_cache_id}/stream")
def stream_audio(
    audio_cache_id: int,
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
) -> FileResponse:
    path = _resolve_owned_audio_path(db, audio_cache_id, student)
    return FileResponse(path, media_type="audio/mpeg")


@router.get("/audio/{audio_cache_id}/download")
def download_audio(
    audio_cache_id: int,
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
) -> FileResponse:
    path = _resolve_owned_audio_path(db, audio_cache_id, student)
    return FileResponse(path, media_type="audio/mpeg", filename=path.name)
