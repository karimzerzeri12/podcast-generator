from sqlmodel import Session, select

from app.models import AudioCache, CacheStatus, GenerationJob, JobStage, ScriptCache, StudentEpisode, Topic
from app.schemas import EpisodeOut


def resolve_script_cache(db: Session, episode: StudentEpisode) -> ScriptCache | None:
    """A student's episode may have its script ready before its audio (still
    synthesizing) or, for a cache hit, both ready immediately — so the script
    cache can be reached via either the audio cache or the underlying job."""
    if episode.audio_cache_id is not None:
        audio = db.get(AudioCache, episode.audio_cache_id)
        if audio is not None:
            return db.get(ScriptCache, audio.script_cache_id)
    if episode.generation_job_id is not None:
        job = db.get(GenerationJob, episode.generation_job_id)
        if job is not None and job.script_cache_id is not None:
            return db.get(ScriptCache, job.script_cache_id)
    return None


def resolve_stage(db: Session, episode: StudentEpisode) -> JobStage:
    if episode.audio_cache_id is not None:
        return JobStage.done
    if episode.generation_job_id is not None:
        job = db.get(GenerationJob, episode.generation_job_id)
        if job is not None:
            return job.stage
    return JobStage.queued


def list_student_episodes(db: Session, student_id: int) -> list[EpisodeOut]:
    episodes = db.exec(
        select(StudentEpisode)
        .where(StudentEpisode.student_id == student_id)
        .order_by(StudentEpisode.generated_at.desc())
    ).all()

    rows: list[EpisodeOut] = []
    for episode in episodes:
        topic = db.get(Topic, episode.topic_id)
        if topic is None:
            continue
        script_cache = resolve_script_cache(db, episode)
        rows.append(
            EpisodeOut(
                id=episode.id,
                topic_id=topic.id,
                topic_title=topic.title,
                format=episode.format,
                voice_id=episode.voice_id,
                voice_id_2=episode.voice_id_2,
                generated_at=episode.generated_at,
                stage=resolve_stage(db, episode),
                audio_cache_id=episode.audio_cache_id,
                has_script=script_cache is not None and script_cache.status == CacheStatus.ready,
            )
        )
    return rows
