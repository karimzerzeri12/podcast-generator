from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlmodel import Session

from app.config import get_settings
from app.deps import get_current_student, get_db
from app.episodes.service import list_student_episodes, resolve_script_cache
from app.models import CacheStatus, Student, StudentEpisode
from app.schemas import EpisodeOut

router = APIRouter(prefix="/episodes", tags=["episodes"])


@router.get("", response_model=list[EpisodeOut])
def list_episodes(
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
) -> list[EpisodeOut]:
    return list_student_episodes(db, student.id)


def _get_owned_episode(db: Session, episode_id: int, student: Student) -> StudentEpisode:
    episode = db.get(StudentEpisode, episode_id)
    if episode is None or episode.student_id != student.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Episode not found")
    return episode


def _resolve_script_text(db: Session, episode: StudentEpisode) -> tuple[str, str]:
    """Returns (script_text, filename)."""
    script_cache = resolve_script_cache(db, episode)
    if script_cache is None or script_cache.status != CacheStatus.ready:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Script not ready yet")
    path = get_settings().resolved_path(script_cache.script_path)
    return path.read_text(encoding="utf-8"), path.name


@router.get("/{episode_id}/script")
def get_episode_script(
    episode_id: int,
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
) -> dict:
    episode = _get_owned_episode(db, episode_id, student)
    text, _filename = _resolve_script_text(db, episode)
    return {"text": text}


@router.get("/{episode_id}/script/download")
def download_episode_script(
    episode_id: int,
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
) -> FileResponse:
    episode = _get_owned_episode(db, episode_id, student)
    script_cache = resolve_script_cache(db, episode)
    if script_cache is None or script_cache.status != CacheStatus.ready:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Script not ready yet")
    path = get_settings().resolved_path(script_cache.script_path)
    return FileResponse(path, media_type="text/plain", filename=path.name)
