from sqlmodel import Session, select

import app.generation.jobs as jobs_module
import app.generation.service as service
import app.materials.service as materials_service
from app.db import engine
from app.materials.service import upsert_topic_material
from app.models import EpisodeFormat, GenerationJob, Topic


def test_reingest_unchanged_material_is_noop(db_session, course_and_topic, monkeypatch):
    course, _ = course_and_topic
    ingest_calls = {"count": 0}

    def fake_ingest_topic(db, topic_id):
        ingest_calls["count"] += 1
        return 0

    monkeypatch.setattr(materials_service, "ingest_topic", fake_ingest_topic)

    topic_1, changed_1, action_1 = upsert_topic_material(
        db_session,
        course_id=course.id,
        title="New Topic",
        description="d",
        filename="f.txt",
        raw_text="Hello world.",
    )
    assert changed_1 is True
    assert action_1 == "created"
    assert ingest_calls["count"] == 1
    assert topic_1.material_version == 1

    topic_2, changed_2, action_2 = upsert_topic_material(
        db_session,
        course_id=course.id,
        title="New Topic",
        description="d",
        filename="f.txt",
        raw_text="Hello world.",  # identical content
    )
    assert changed_2 is False
    assert action_2 == "unchanged"
    assert ingest_calls["count"] == 1, "unchanged material must not trigger re-ingestion"
    assert topic_2.material_version == 1, "an unchanged doc must not bump material_version"


def test_dry_run_changes_nothing(db_session, course_and_topic, monkeypatch):
    course, _ = course_and_topic
    ingest_calls = {"count": 0}
    monkeypatch.setattr(
        materials_service, "ingest_topic", lambda db, tid: ingest_calls.__setitem__("count", 1)
    )

    topic, changed, action = upsert_topic_material(
        db_session,
        course_id=course.id,
        title="Dry Run Topic",
        description="d",
        filename="f.txt",
        raw_text="content",
        dry_run=True,
    )
    assert changed is True
    assert action == "created"
    assert topic is None
    assert ingest_calls["count"] == 0

    found = db_session.exec(select(Topic).where(Topic.title == "Dry Run Topic")).first()
    assert found is None, "dry_run must not write anything to the DB"


def test_changing_one_topic_does_not_invalidate_another(
    db_session, course_and_topic, student, monkeypatch
):
    """The scenario requirement #4 exists for: editing one topic's source material
    must regenerate only that topic on next request, while every other topic's
    cached script/audio stays valid and is served without hitting Gemini/ElevenLabs
    again."""
    course, _ = course_and_topic

    monkeypatch.setattr(materials_service, "ingest_topic", lambda db, tid: 0)

    topic_a, _, _ = upsert_topic_material(
        db_session,
        course_id=course.id,
        title="Topic A",
        description="a",
        filename="a.txt",
        raw_text="Original content for topic A.",
    )
    topic_b, _, _ = upsert_topic_material(
        db_session,
        course_id=course.id,
        title="Topic B",
        description="b",
        filename="b.txt",
        raw_text="Original content for topic B.",
    )

    def fake_enqueue(job_id):
        with Session(engine) as db:
            job = db.get(GenerationJob, job_id)
            service.run_job(db, job)

    monkeypatch.setattr(jobs_module, "enqueue_job", fake_enqueue)

    calls = {"script": 0}

    def fake_generate_script(topic_title, format, context, length_minutes=5):
        calls["script"] += 1
        return "word " * 700

    def fake_synthesize(script_text, voice_id, job_id, output_path, on_progress=None):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-audio-bytes")
        if on_progress:
            on_progress(1, 1)
        return 10.0

    monkeypatch.setattr(service, "retrieve_topic_context", lambda db, topic: "ctx")
    monkeypatch.setattr(service, "generate_script", fake_generate_script)
    monkeypatch.setattr(service, "synthesize_script", fake_synthesize)

    service.request_generation(db_session, student, topic_a.id, EpisodeFormat.monologue, "voiceA")
    service.request_generation(db_session, student, topic_b.id, EpisodeFormat.monologue, "voiceA")
    assert calls["script"] == 2

    db_session.expire_all()
    upsert_topic_material(
        db_session,
        course_id=course.id,
        title="Topic A",
        description="a",
        filename="a.txt",
        raw_text="Completely different content now.",
    )

    cache_hit_b, _, _ = service.request_generation(
        db_session, student, topic_b.id, EpisodeFormat.monologue, "voiceA"
    )
    assert cache_hit_b is True
    assert calls["script"] == 2, "topic B's cache must be untouched by topic A's material change"

    cache_hit_a, _, _ = service.request_generation(
        db_session, student, topic_a.id, EpisodeFormat.monologue, "voiceA"
    )
    assert cache_hit_a is False
    assert calls["script"] == 3, "topic A must regenerate after its own material changed"
