import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.auth.service import hash_access_code, issue_token
from app.main import app
from app.models import (
    AudioCache,
    CacheStatus,
    EpisodeFormat,
    GenerationJob,
    JobStage,
    ScriptCache,
    Student,
    StudentEpisode,
)


def _auth(student: Student) -> dict:
    return {"Authorization": f"Bearer {issue_token(student.id)}"}


def _second_student(db_session, course) -> Student:
    other = Student(
        email="mallory@example.edu",
        access_code=hash_access_code("pw123"),
        name="Mallory",
        course_id=course.id,
    )
    db_session.add(other)
    db_session.commit()
    db_session.refresh(other)
    return other


def _make_ready_episode(db_session, topic, student) -> tuple[StudentEpisode, AudioCache, GenerationJob]:
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

    audio_file = Path(tempfile.mkdtemp(prefix="sec-test-")) / "episode.mp3"
    audio_file.write_bytes(b"fake-audio-bytes")
    audio = AudioCache(
        script_cache_id=script.id,
        voice_id="voiceA",
        audio_path=str(audio_file),
        duration_seconds=100.0,
        status=CacheStatus.ready,
    )
    db_session.add(audio)
    db_session.commit()
    db_session.refresh(audio)

    job = GenerationJob(
        student_id=student.id,
        topic_id=topic.id,
        format=EpisodeFormat.monologue,
        voice_id="voiceA",
        stage=JobStage.done,
        progress_pct=100,
        script_cache_id=script.id,
        audio_cache_id=audio.id,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    episode = StudentEpisode(
        student_id=student.id,
        topic_id=topic.id,
        audio_cache_id=audio.id,
        generation_job_id=job.id,
        format=EpisodeFormat.monologue,
        voice_id="voiceA",
    )
    db_session.add(episode)
    db_session.commit()
    db_session.refresh(episode)
    return episode, audio, job


def test_generate_rejects_voice_id_with_path_traversal(db_session, course_and_topic, student):
    _, topic = course_and_topic
    with TestClient(app) as client:
        resp = client.post(
            "/generate",
            headers=_auth(student),
            json={
                "topic_id": topic.id,
                "format": "monologue",
                "voice_id": "../../../../etc/passwd",
            },
        )
        assert resp.status_code == 400


def test_generate_rejects_voice_not_in_allow_list(db_session, course_and_topic, student):
    # conftest sets ELEVENLABS_VOICE_IDS=voiceA,voiceB — a syntactically valid but
    # non-curated voice must be rejected before any TTS spend.
    _, topic = course_and_topic
    with TestClient(app) as client:
        resp = client.post(
            "/generate",
            headers=_auth(student),
            json={"topic_id": topic.id, "format": "monologue", "voice_id": "notAllowedVoice"},
        )
        assert resp.status_code == 400


def test_cannot_stream_another_students_audio(db_session, course_and_topic, student):
    course, topic = course_and_topic
    _episode, audio, _job = _make_ready_episode(db_session, topic, student)
    mallory = _second_student(db_session, course)

    with TestClient(app) as client:
        # owner passes the ownership check and gets the file
        owner_resp = client.get(f"/audio/{audio.id}/stream", headers=_auth(student))
        assert owner_resp.status_code == 200

        # a different student is blocked at the ownership check
        attacker_resp = client.get(f"/audio/{audio.id}/stream", headers=_auth(mallory))
        assert attacker_resp.status_code == 404


def test_cannot_read_another_students_job(db_session, course_and_topic, student):
    course, topic = course_and_topic
    _episode, _audio, job = _make_ready_episode(db_session, topic, student)
    mallory = _second_student(db_session, course)

    with TestClient(app) as client:
        owner_resp = client.get(f"/jobs/{job.id}", headers=_auth(student))
        assert owner_resp.status_code == 200

        attacker_resp = client.get(f"/jobs/{job.id}", headers=_auth(mallory))
        assert attacker_resp.status_code == 404


def test_admin_endpoint_rejects_wrong_token():
    with TestClient(app) as client:
        resp = client.get("/admin/settings", headers={"X-Admin-Token": "wrong-token"})
        assert resp.status_code == 401


def _make_episode(db_session, topic, student) -> StudentEpisode:
    episode = StudentEpisode(
        student_id=student.id,
        topic_id=topic.id,
        format=EpisodeFormat.monologue,
        voice_id="voiceA",
    )
    db_session.add(episode)
    db_session.commit()
    db_session.refresh(episode)
    return episode


def test_generation_limit_blocks_over_quota(db_session, course_and_topic, student):
    from app.podcast_settings import set_max_generations_per_student

    _, topic = course_and_topic
    set_max_generations_per_student(db_session, 2)
    # student already has 2 episodes → at the cap
    _make_episode(db_session, topic, student)
    _make_episode(db_session, topic, student)

    with TestClient(app) as client:
        resp = client.post(
            "/generate",
            headers=_auth(student),
            json={"topic_id": topic.id, "format": "monologue", "voice_id": "voiceA"},
        )
        assert resp.status_code == 429


def test_generation_limit_allows_under_quota(db_session, course_and_topic, student):
    """Under the cap the request must pass the quota gate and reach later validation —
    proven here by an invalid voice giving 400 (not 429), without running real generation."""
    from app.podcast_settings import set_max_generations_per_student

    _, topic = course_and_topic
    set_max_generations_per_student(db_session, 5)

    with TestClient(app) as client:
        resp = client.post(
            "/generate",
            headers=_auth(student),
            json={"topic_id": topic.id, "format": "monologue", "voice_id": "../bad"},
        )
        assert resp.status_code == 400
