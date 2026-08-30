import csv
import json
from pathlib import Path

from sqlmodel import Session, select

from app.auth.service import hash_access_code
from app.db import engine, init_db
from app.materials.service import upsert_topic_material
from app.models import Course, Student, Topic
from app.rag.ingest import extract_pdf_text

DATA_DIR = Path(__file__).resolve().parent / "data"


def _read_source_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return extract_pdf_text(path.read_bytes())
    return path.read_text(encoding="utf-8")


def _get_or_create_course(db: Session) -> Course:
    payload = json.loads((DATA_DIR / "course.json").read_text(encoding="utf-8"))
    course = db.exec(select(Course).where(Course.title == payload["title"])).first()
    if course is None:
        course = Course(title=payload["title"], description=payload["description"])
        db.add(course)
        db.commit()
        db.refresh(course)
    return course


def _get_or_create_topics(db: Session, course: Course) -> list[Topic]:
    """Seeds topics via the same shared upsert used by the admin upload endpoint and
    the `python -m app.ingest` CLI, so there's exactly one place that knows how to
    create/update a topic's material and re-ingest it."""
    manifest = json.loads((DATA_DIR / "topics.json").read_text(encoding="utf-8"))
    # Optional: chapters.json maps a chapter label -> the blurb shown under it on the
    # landing page. Missing file or missing entries just mean no blurb (a count is shown).
    chapters_file = DATA_DIR / "chapters.json"
    chapter_descriptions: dict[str, str] = (
        json.loads(chapters_file.read_text(encoding="utf-8")) if chapters_file.exists() else {}
    )
    topics: list[Topic] = []

    for entry in manifest:
        raw_text = _read_source_text(DATA_DIR / "topics" / entry["filename"])
        chapter = entry.get("chapter", "")
        topic, _changed, _action = upsert_topic_material(
            db,
            course_id=course.id,
            title=entry["title"],
            description=entry["description"],
            filename=entry["filename"],
            raw_text=raw_text,
            chapter=chapter,
            chapter_description=chapter_descriptions.get(chapter, ""),
        )
        topics.append(topic)

    return topics


def _get_or_create_students(db: Session, course: Course) -> list[Student]:
    students: list[Student] = []
    with open(DATA_DIR / "roster.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            email = row["email"].strip().lower()
            student = db.exec(select(Student).where(Student.email == email)).first()
            if student is None:
                student = Student(
                    email=email,
                    access_code=hash_access_code(row["access_code"]),
                    name=row["name"],
                    course_id=course.id,
                )
                db.add(student)
                db.commit()
                db.refresh(student)
            students.append(student)
    return students


def run() -> None:
    init_db()
    with Session(engine) as db:
        course = _get_or_create_course(db)
        topics = _get_or_create_topics(db, course)
        students = _get_or_create_students(db, course)

        print(f"Seed complete: course='{course.title}', {len(topics)} topics, {len(students)} students")


if __name__ == "__main__":
    run()
