from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.config import get_settings
from app.generation.script_gen import generate_script, parse_dialogue_turns
from app.generation.tts import synthesize_dialogue, synthesize_script
from app.models import (
    AudioCache,
    CacheStatus,
    EpisodeFormat,
    GenerationJob,
    JobStage,
    ScriptCache,
    Student,
    StudentEpisode,
    Topic,
)
from app.podcast_settings import get_episode_length_minutes
from app.rag.retriever import retrieve_topic_context

NON_TERMINAL_STAGES = (JobStage.queued, JobStage.generating_script, JobStage.synthesizing_audio)


def _find_ready_script(db: Session, topic_id: int, format: EpisodeFormat) -> ScriptCache | None:
    topic = db.get(Topic, topic_id)
    if topic is None:
        return None
    length_minutes = get_episode_length_minutes(db)
    return db.exec(
        select(ScriptCache).where(
            ScriptCache.topic_id == topic_id,
            ScriptCache.format == format,
            ScriptCache.material_version == topic.material_version,
            ScriptCache.length_minutes == length_minutes,
            ScriptCache.status == CacheStatus.ready,
        )
    ).first()


def _find_ready_audio(
    db: Session, script_cache_id: int, voice_id: str, voice_id_2: str
) -> AudioCache | None:
    return db.exec(
        select(AudioCache).where(
            AudioCache.script_cache_id == script_cache_id,
            AudioCache.voice_id == voice_id,
            AudioCache.voice_id_2 == voice_id_2,
            AudioCache.status == CacheStatus.ready,
        )
    ).first()


def _find_reusable_job(
    db: Session, topic_id: int, format: EpisodeFormat, voice_id: str, voice_id_2: str
) -> GenerationJob | None:
    return db.exec(
        select(GenerationJob).where(
            GenerationJob.topic_id == topic_id,
            GenerationJob.format == format,
            GenerationJob.voice_id == voice_id,
            GenerationJob.voice_id_2 == voice_id_2,
            GenerationJob.stage.in_(NON_TERMINAL_STAGES),
        )
    ).first()


def request_generation(
    db: Session,
    student: Student,
    topic_id: int,
    format: EpisodeFormat,
    voice_id: str,
    voice_id_2: str = "",
) -> tuple[bool, GenerationJob, int]:
    """Returns (cache_hit, job, student_episode_id). Cache-checks first; only enqueues
    real work (LLM/TTS) when nothing usable is cached, and reuses an in-flight job for
    the same (topic, format, voices) instead of starting a duplicate."""
    script_cache = _find_ready_script(db, topic_id, format)

    if script_cache is not None:
        audio_cache = _find_ready_audio(db, script_cache.id, voice_id, voice_id_2)
        if audio_cache is not None:
            job = GenerationJob(
                student_id=student.id,
                topic_id=topic_id,
                format=format,
                voice_id=voice_id,
                voice_id_2=voice_id_2,
                stage=JobStage.done,
                progress_pct=100,
                script_cache_id=script_cache.id,
                audio_cache_id=audio_cache.id,
            )
            db.add(job)
            db.commit()
            db.refresh(job)

            episode = StudentEpisode(
                student_id=student.id,
                topic_id=topic_id,
                audio_cache_id=audio_cache.id,
                format=format,
                voice_id=voice_id,
                voice_id_2=voice_id_2,
            )
            db.add(episode)
            db.commit()
            db.refresh(episode)
            return True, job, episode.id

    existing_job = _find_reusable_job(db, topic_id, format, voice_id, voice_id_2)
    if existing_job is not None:
        episode = StudentEpisode(
            student_id=student.id,
            topic_id=topic_id,
            format=format,
            voice_id=voice_id,
            voice_id_2=voice_id_2,
            generation_job_id=existing_job.id,
        )
        db.add(episode)
        db.commit()
        db.refresh(episode)
        return False, existing_job, episode.id

    job = GenerationJob(
        student_id=student.id,
        topic_id=topic_id,
        format=format,
        voice_id=voice_id,
        voice_id_2=voice_id_2,
        stage=JobStage.queued,
        script_cache_id=script_cache.id if script_cache else None,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    episode = StudentEpisode(
        student_id=student.id,
        topic_id=topic_id,
        format=format,
        voice_id=voice_id,
        voice_id_2=voice_id_2,
        generation_job_id=job.id,
    )
    db.add(episode)
    db.commit()
    db.refresh(episode)

    from app.generation.jobs import enqueue_job

    enqueue_job(job.id)
    return False, job, episode.id


def _get_or_create_script_cache(db: Session, topic: Topic, format: EpisodeFormat) -> ScriptCache:
    existing = _find_ready_script(db, topic.id, format)
    if existing is not None:
        return existing

    settings = get_settings()
    length_minutes = get_episode_length_minutes(db)
    context = retrieve_topic_context(db, topic)
    script_text = generate_script(topic.title, format, context, length_minutes)

    scripts_dir = settings.resolved_path(settings.scripts_dir)
    scripts_dir.mkdir(parents=True, exist_ok=True)
    script_path = (
        scripts_dir
        / f"topic{topic.id}__{format.value}__v{topic.material_version}__{length_minutes}min.txt"
    )
    script_path.write_text(script_text, encoding="utf-8")

    cache = ScriptCache(
        topic_id=topic.id,
        format=format,
        material_version=topic.material_version,
        length_minutes=length_minutes,
        script_path=str(script_path),
        word_count=len(script_text.split()),
        status=CacheStatus.ready,
    )
    db.add(cache)
    try:
        db.commit()
    except IntegrityError:
        # another job won the race and inserted this (topic_id, format, material_version,
        # length_minutes) first
        db.rollback()
        return _find_ready_script(db, topic.id, format)
    db.refresh(cache)
    return cache


def _get_or_create_audio_cache(
    db: Session, script_cache: ScriptCache, voice_id: str, voice_id_2: str, job_id: int
) -> tuple[AudioCache, float | None]:
    existing = _find_ready_audio(db, script_cache.id, voice_id, voice_id_2)
    if existing is not None:
        return existing, None

    settings = get_settings()
    script_text = settings.resolved_path(script_cache.script_path).read_text(encoding="utf-8")
    audio_dir = settings.resolved_path(settings.audio_dir)
    voice_suffix = voice_id if not voice_id_2 else f"{voice_id}+{voice_id_2}"
    # Keyed on script_cache.id (not just topic/format) so a later material or length-setting
    # change — which produces a new script_cache row — can never overwrite an older cached
    # audio file that's still referenced by past episodes.
    output_path = (
        audio_dir
        / f"topic{script_cache.topic_id}__{script_cache.format.value}__sc{script_cache.id}"
        f"__{voice_suffix}.mp3"
    )

    def on_progress(done_chunks: int, total_chunks: int) -> None:
        pct = 30 + int((done_chunks / total_chunks) * 65)
        _update_job_progress(job_id, JobStage.synthesizing_audio, pct)

    if script_cache.format == EpisodeFormat.monologue:
        duration = synthesize_script(script_text, voice_id, job_id, output_path, on_progress)
    else:
        turns = parse_dialogue_turns(script_text)
        duration = synthesize_dialogue(turns, voice_id, voice_id_2, job_id, output_path, on_progress)

    cache = AudioCache(
        script_cache_id=script_cache.id,
        voice_id=voice_id,
        voice_id_2=voice_id_2,
        audio_path=str(output_path),
        duration_seconds=duration,
        status=CacheStatus.ready,
    )
    db.add(cache)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return _find_ready_audio(db, script_cache.id, voice_id, voice_id_2), None
    db.refresh(cache)
    return cache, duration


def _update_job_progress(job_id: int, stage: JobStage, progress_pct: int) -> None:
    from app.db import engine

    with Session(engine) as db:
        job = db.get(GenerationJob, job_id)
        if job is None:
            return
        job.stage = stage
        job.progress_pct = progress_pct
        db.add(job)
        db.commit()


def run_job(db: Session, job: GenerationJob) -> None:
    topic = db.get(Topic, job.topic_id)

    script_cache = None
    if job.script_cache_id is not None:
        script_cache = db.get(ScriptCache, job.script_cache_id)

    if script_cache is None or script_cache.status != CacheStatus.ready:
        job.stage = JobStage.generating_script
        job.progress_pct = 5
        db.add(job)
        db.commit()

        script_cache = _get_or_create_script_cache(db, topic, job.format)
        job.script_cache_id = script_cache.id
        job.progress_pct = 30
        db.add(job)
        db.commit()

    job.stage = JobStage.synthesizing_audio
    db.add(job)
    db.commit()

    audio_cache, _ = _get_or_create_audio_cache(
        db, script_cache, job.voice_id, job.voice_id_2, job.id
    )

    job.stage = JobStage.done
    job.progress_pct = 100
    job.audio_cache_id = audio_cache.id
    db.add(job)
    db.commit()

    pending_episodes = db.exec(
        select(StudentEpisode).where(StudentEpisode.generation_job_id == job.id)
    ).all()
    for episode in pending_episodes:
        episode.audio_cache_id = audio_cache.id
        db.add(episode)
    db.commit()
