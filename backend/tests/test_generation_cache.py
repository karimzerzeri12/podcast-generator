from sqlmodel import Session

import app.generation.jobs as jobs_module
import app.generation.service as service
from app.db import engine
from app.models import EpisodeFormat, GenerationJob, StudentEpisode


def _run_jobs_synchronously(monkeypatch):
    """Replaces the real background-thread enqueue with an inline call to run_job,
    so tests are deterministic and don't depend on worker-thread timing."""

    def fake_enqueue(job_id):
        with Session(engine) as db:
            job = db.get(GenerationJob, job_id)
            service.run_job(db, job)

    monkeypatch.setattr(jobs_module, "enqueue_job", fake_enqueue)


def _mock_pipeline(monkeypatch):
    calls = {"script": 0, "tts": 0}

    def fake_retrieve(db, topic):
        return "fake retrieved context"

    def fake_generate_script(topic_title, format, context, length_minutes=5):
        calls["script"] += 1
        return "word " * 2500

    def fake_synthesize(script_text, voice_id, job_id, output_path, on_progress=None):
        calls["tts"] += 1
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-audio-bytes")
        if on_progress:
            on_progress(1, 1)
        return 1234.5

    def fake_synthesize_dialogue(turns, voice_id, voice_id_2, job_id, output_path, on_progress=None):
        calls["tts"] += 1
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-audio-bytes")
        if on_progress:
            on_progress(1, 1)
        return 1234.5

    monkeypatch.setattr(service, "retrieve_topic_context", fake_retrieve)
    monkeypatch.setattr(service, "generate_script", fake_generate_script)
    monkeypatch.setattr(service, "synthesize_script", fake_synthesize)
    monkeypatch.setattr(service, "synthesize_dialogue", fake_synthesize_dialogue)
    return calls


def _fresh_job(db_session, job_id):
    db_session.expire_all()
    return db_session.get(GenerationJob, job_id)


def test_cache_hit_skips_regeneration(db_session, course_and_topic, student, monkeypatch):
    _run_jobs_synchronously(monkeypatch)
    calls = _mock_pipeline(monkeypatch)
    _, topic = course_and_topic

    cache_hit_1, job_1, _ = service.request_generation(
        db_session, student, topic.id, EpisodeFormat.monologue, "voiceA"
    )
    assert cache_hit_1 is False
    assert calls == {"script": 1, "tts": 1}
    job_1 = _fresh_job(db_session, job_1.id)
    assert job_1.audio_cache_id is not None

    cache_hit_2, job_2, _ = service.request_generation(
        db_session, student, topic.id, EpisodeFormat.monologue, "voiceA"
    )
    assert cache_hit_2 is True
    assert calls == {"script": 1, "tts": 1}, "cache hit must not trigger new LLM/TTS calls"
    assert job_2.audio_cache_id == job_1.audio_cache_id


def test_voice_change_reuses_script_only_new_tts(
    db_session, course_and_topic, student, monkeypatch
):
    _run_jobs_synchronously(monkeypatch)
    calls = _mock_pipeline(monkeypatch)
    _, topic = course_and_topic

    service.request_generation(db_session, student, topic.id, EpisodeFormat.monologue, "voiceA")
    assert calls == {"script": 1, "tts": 1}

    cache_hit, job, _ = service.request_generation(
        db_session, student, topic.id, EpisodeFormat.monologue, "voiceB"
    )
    assert cache_hit is False
    assert calls == {"script": 1, "tts": 2}, "same format must reuse the cached script"
    job = _fresh_job(db_session, job.id)
    assert job.audio_cache_id is not None


def test_format_change_triggers_full_regeneration(
    db_session, course_and_topic, student, monkeypatch
):
    _run_jobs_synchronously(monkeypatch)
    calls = _mock_pipeline(monkeypatch)
    _, topic = course_and_topic

    service.request_generation(db_session, student, topic.id, EpisodeFormat.monologue, "voiceA")
    service.request_generation(
        db_session, student, topic.id, EpisodeFormat.interview, "voiceA", "voiceB"
    )

    assert calls == {"script": 2, "tts": 2}


def test_student_episode_recorded_for_current_selection(
    db_session, course_and_topic, student, monkeypatch
):
    _run_jobs_synchronously(monkeypatch)
    _mock_pipeline(monkeypatch)
    _, topic = course_and_topic

    _, job, episode_id = service.request_generation(
        db_session, student, topic.id, EpisodeFormat.monologue, "voiceA"
    )
    job = _fresh_job(db_session, job.id)

    db_session.expire_all()
    episode = db_session.get(StudentEpisode, episode_id)
    assert episode.student_id == student.id
    assert episode.topic_id == topic.id
    assert episode.audio_cache_id == job.audio_cache_id


def test_concurrent_identical_requests_share_one_job(
    db_session, course_and_topic, student, monkeypatch
):
    """A second request for the same (topic, format, voices) while the first is still
    in-flight must reuse the same job instead of starting a duplicate generation."""
    # stub out the worker entirely — this test only checks dedup logic, so the
    # job must stay queued/non-terminal rather than actually being processed
    monkeypatch.setattr(jobs_module, "enqueue_job", lambda job_id: None)
    _, topic = course_and_topic

    cache_hit_1, job_1, _ = service.request_generation(
        db_session, student, topic.id, EpisodeFormat.monologue, "voiceA"
    )
    cache_hit_2, job_2, _ = service.request_generation(
        db_session, student, topic.id, EpisodeFormat.monologue, "voiceA"
    )

    assert cache_hit_1 is False
    assert cache_hit_2 is False
    assert job_1.id == job_2.id
