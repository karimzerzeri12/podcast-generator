from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings

settings = get_settings()

_db_path = Path(settings.database_url.replace("sqlite:///", ""))
_db_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})


def init_db() -> None:
    import app.models  # noqa: F401 — ensure models are registered before create_all

    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
