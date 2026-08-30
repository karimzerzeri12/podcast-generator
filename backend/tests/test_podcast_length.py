import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

import app.generation.jobs as jobs_module
import app.generation.service as service
from app.db import engine
from app.generation.script_gen import word_targets
from app.main import app
from app.models import EpisodeFormat, GenerationJob
from app.podcast_settings import (
    MAX_LENGTH_MINUTES,
    MIN_LENGTH_MINUTES,
    get_episode_length_minutes,
    set_episode_length_minutes,
)


def test_default_length_is_five_minutes(db_session):
    assert get_episode_length_minutes(db_session) == 5


def test_set_length_within_range(db_session):
    assert set_episode_length_minutes(db_session, 15) == 15
    assert get_episode_length_minutes(db_session) == 15


@pytest.mark.parametrize("minutes", [MIN_LENGTH_MINUTES - 1, MAX_LENGTH_MINUTES + 1, 0, -5])
def test_set_length_out_of_range_rejected(db_session, minutes):
    with pytest.raises(ValueError):
        set_episode_length_minutes(db_session, minutes)
    # unchanged
    assert get_episode_length_minutes(db_session) == 5


def test_word_targets_match_original_five_minute_numbers():
    low, high, min_acceptable = word_targets(5)
    assert (low, high, min_acceptable) == (650, 750, 550)


def test_word_targets_scale_with_length():
    low, high, min_acceptable = word_targets(20)
    assert low > 650 and high > 750 and min_acceptable > 550
    # roughly 4x the 5-minute midpoint (140 wpm * 20 minutes)
    assert 2700 <= round((low + high) / 2) <= 2900


def _run_jobs_synchronously(monkeypatch):
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

    monkeypatch.setattr(service, "retrieve_topic_context", fake_retrieve)
    monkeypatch.setattr(service, "generate_script", fake_generate_script)
    monkeypatch.setattr(service, "synthesize_script", fake_synthesize)
    return calls


def test_changing_length_setting_triggers_regeneration_and_is_isolated(
    db_session, course_and_topic, student, monkeypatch
):
    """Requirement: episode length is admin-controlled and applies going forward, without
    destroying what's already cached — a length change should trigger fresh generation for
    the new setting, and reverting the setting should serve the original cached script again
    rather than regenerating a third time."""
    _run_jobs_synchronously(monkeypatch)
    calls = _mock_pipeline(monkeypatch)
    _, topic = course_and_topic

    cache_hit_1, _, _ = service.request_generation(
        db_session, student, topic.id, EpisodeFormat.monologue, "voiceA"
    )
    assert cache_hit_1 is False
    assert calls["script"] == 1

    set_episode_length_minutes(db_session, 15)
    db_session.expire_all()

    cache_hit_2, _, _ = service.request_generation(
        db_session, student, topic.id, EpisodeFormat.monologue, "voiceA"
    )
    assert cache_hit_2 is False, "a changed length setting must not reuse the old-length script"
    assert calls["script"] == 2

    set_episode_length_minutes(db_session, 5)
    db_session.expire_all()

    cache_hit_3, _, _ = service.request_generation(
        db_session, student, topic.id, EpisodeFormat.monologue, "voiceA"
    )
    assert cache_hit_3 is True, "reverting to the original length must reuse its existing cache"
    assert calls["script"] == 2, "no third generation should have happened"


def test_admin_settings_requires_admin_token():
    with TestClient(app) as client:
        resp = client.get("/admin/settings")
        assert resp.status_code == 401


def test_admin_can_read_and_update_length_setting():
    with TestClient(app) as client:
        headers = {"X-Admin-Token": "test-admin-token"}

        resp = client.get("/admin/settings", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["episode_length_minutes"] == 5
        assert resp.json()["max_generations_per_student"] == 0

        resp = client.put("/admin/settings", headers=headers, json={"episode_length_minutes": 20})
        assert resp.status_code == 200
        assert resp.json()["episode_length_minutes"] == 20

        resp = client.get("/admin/settings", headers=headers)
        assert resp.json()["episode_length_minutes"] == 20


def test_admin_settings_rejects_out_of_range_value():
    with TestClient(app) as client:
        headers = {"X-Admin-Token": "test-admin-token"}
        resp = client.put("/admin/settings", headers=headers, json={"episode_length_minutes": 45})
        assert resp.status_code == 400


def test_admin_can_update_generation_limit_independently():
    with TestClient(app) as client:
        headers = {"X-Admin-Token": "test-admin-token"}

        # update only the limit — length must be untouched
        resp = client.put(
            "/admin/settings", headers=headers, json={"max_generations_per_student": 3}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["max_generations_per_student"] == 3
        assert body["episode_length_minutes"] == 5

        resp = client.put(
            "/admin/settings", headers=headers, json={"max_generations_per_student": -1}
        )
        assert resp.status_code == 400
