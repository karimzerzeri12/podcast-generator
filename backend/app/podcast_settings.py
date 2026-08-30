from sqlmodel import Session, select

from app.models import PodcastSettings

DEFAULT_LENGTH_MINUTES = 5
MIN_LENGTH_MINUTES = 5
MAX_LENGTH_MINUTES = 20

# 0 == unlimited. There's no hard upper bound, but reject absurd values.
UNLIMITED_GENERATIONS = 0
MAX_GENERATIONS_CAP = 10000


def _get_or_create_row(db: Session) -> PodcastSettings:
    row = db.exec(select(PodcastSettings)).first()
    if row is None:
        row = PodcastSettings(episode_length_minutes=DEFAULT_LENGTH_MINUTES)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def get_episode_length_minutes(db: Session) -> int:
    return _get_or_create_row(db).episode_length_minutes


def set_episode_length_minutes(db: Session, minutes: int) -> int:
    if not (MIN_LENGTH_MINUTES <= minutes <= MAX_LENGTH_MINUTES):
        raise ValueError(
            f"episode_length_minutes must be between {MIN_LENGTH_MINUTES} and {MAX_LENGTH_MINUTES}"
        )
    row = _get_or_create_row(db)
    row.episode_length_minutes = minutes
    db.add(row)
    db.commit()
    db.refresh(row)
    return row.episode_length_minutes


def get_max_generations_per_student(db: Session) -> int:
    return _get_or_create_row(db).max_generations_per_student


def set_max_generations_per_student(db: Session, value: int) -> int:
    if not (UNLIMITED_GENERATIONS <= value <= MAX_GENERATIONS_CAP):
        raise ValueError(
            f"max_generations_per_student must be between {UNLIMITED_GENERATIONS} "
            f"(unlimited) and {MAX_GENERATIONS_CAP}"
        )
    row = _get_or_create_row(db)
    row.max_generations_per_student = value
    db.add(row)
    db.commit()
    db.refresh(row)
    return row.max_generations_per_student
