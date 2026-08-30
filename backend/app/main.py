from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select

from app.admin.router import router as admin_router
from app.analytics.router import router as analytics_router
from app.auth.router import router as auth_router
from app.config import apply_langsmith_env, get_settings
from app.courses.router import router as courses_router
from app.db import engine, init_db
from app.episodes.router import router as episodes_router
from app.generation.jobs import reset_stale_jobs, start_worker
from app.generation.router import router as generation_router
from app.materials.storage import check_source_root
from app.models import Student
from app.voices.router import router as voices_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    apply_langsmith_env()
    check_source_root()
    init_db()
    with Session(engine) as db:
        reset_stale_jobs(db)
        has_students = db.exec(select(Student)).first() is not None
    if not has_students:
        from app.seed.seed_data import run as run_seed

        run_seed()
    start_worker()
    yield


app = FastAPI(title="Podcast Generator", lifespan=lifespan)

settings = get_settings()
# Credentialed CORS must never be combined with a wildcard origin — that would let any
# site issue authenticated requests against this API. Fail fast rather than serve it.
if "*" in settings.cors_origin_list:
    raise RuntimeError(
        "CORS_ORIGINS must list explicit origins (no '*') because credentialed requests "
        "are enabled. Set CORS_ORIGINS to your frontend origin(s)."
    )
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(courses_router)
app.include_router(voices_router)
app.include_router(generation_router)
app.include_router(analytics_router)
app.include_router(admin_router)
app.include_router(episodes_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# In a bundled deployment (see Dockerfile), the built React frontend is copied to
# ./static and served from this same app, so the whole tool lives at one URL with no
# separate frontend server and no cross-origin requests. Mounted LAST so it only catches
# paths the API routers above didn't claim. The frontend uses HashRouter, so the server
# only ever serves index.html at "/" (client-side routing lives in the URL fragment) —
# no server-side SPA fallback needed. In local dev this directory doesn't exist and the
# mount is simply skipped (you run Vite separately).
_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if _STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="static")
