import os
import tempfile
from pathlib import Path

import pytest

_TEST_STORAGE = Path(tempfile.mkdtemp(prefix="podcast-gen-test-"))

os.environ.setdefault("ELEVENLABS_API_KEY", "test-elevenlabs-key")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")
os.environ.setdefault("SESSION_SECRET", "test-secret")
os.environ.setdefault("ADMIN_TOKEN", "test-admin-token")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TEST_STORAGE.as_posix()}/test.sqlite3")
os.environ.setdefault("CHROMA_DIR", str(_TEST_STORAGE / "chroma"))
os.environ.setdefault("SCRIPTS_DIR", str(_TEST_STORAGE / "scripts"))
os.environ.setdefault("AUDIO_DIR", str(_TEST_STORAGE / "audio"))
os.environ.setdefault("ELEVENLABS_VOICE_IDS", "voiceA,voiceB")
os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")

from sqlmodel import Session, SQLModel  # noqa: E402

from app.auth.service import hash_access_code  # noqa: E402
from app.db import engine, init_db  # noqa: E402
from app.models import Course, Student, Topic  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_db():
    SQLModel.metadata.drop_all(engine)
    init_db()
    yield
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def db_session():
    with Session(engine) as session:
        yield session


@pytest.fixture
def course_and_topic(db_session):
    course = Course(title="Test Course", description="")
    db_session.add(course)
    db_session.commit()
    db_session.refresh(course)

    topic = Topic(
        course_id=course.id, title="Test Topic", order_index=1, description="A test topic"
    )
    db_session.add(topic)
    db_session.commit()
    db_session.refresh(topic)
    return course, topic


@pytest.fixture
def student(db_session, course_and_topic):
    course, _ = course_and_topic
    s = Student(
        email="test@example.edu",
        access_code=hash_access_code("pw123"),
        name="Test Student",
        course_id=course.id,
    )
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)
    return s
