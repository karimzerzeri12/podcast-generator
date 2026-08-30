import logging
import queue
import threading

from sqlmodel import Session, select

from app.models import GenerationJob, JobStage

logger = logging.getLogger("generation")

_job_queue: queue.Queue[int] = queue.Queue()
_worker_thread: threading.Thread | None = None

NON_TERMINAL_STAGES = (JobStage.queued, JobStage.generating_script, JobStage.synthesizing_audio)

# Shown to students on a failed job. The raw exception (which can carry upstream URLs,
# provider internals, or stack context) is logged server-side instead of being stored on
# the job and returned over the API.
_GENERIC_FAILURE_MESSAGE = (
    "Generation failed. Please try again in a little while; if it keeps happening, "
    "contact your administrator."
)


def enqueue_job(job_id: int) -> None:
    _job_queue.put(job_id)


def _worker_loop() -> None:
    from app.db import engine
    from app.generation.service import run_job

    while True:
        job_id = _job_queue.get()
        try:
            with Session(engine) as db:
                job = db.get(GenerationJob, job_id)
                if job is None or job.stage not in NON_TERMINAL_STAGES:
                    continue
                try:
                    run_job(db, job)
                except Exception:  # noqa: BLE001 — worker must not die on a bad job
                    logger.exception("Generation job %s failed", job_id)
                    job = db.get(GenerationJob, job_id)
                    if job is not None:
                        job.stage = JobStage.failed
                        job.error_message = _GENERIC_FAILURE_MESSAGE
                        db.add(job)
                        db.commit()
        finally:
            _job_queue.task_done()


def start_worker() -> None:
    global _worker_thread
    if _worker_thread is not None:
        return
    _worker_thread = threading.Thread(target=_worker_loop, daemon=True)
    _worker_thread.start()


def reset_stale_jobs(db: Session) -> None:
    """On startup, any job left mid-flight from a previous process (e.g. server
    restart) can never resume — mark it failed so the UI doesn't poll forever."""
    stale = db.exec(
        select(GenerationJob).where(GenerationJob.stage.in_(NON_TERMINAL_STAGES))
    ).all()
    for job in stale:
        job.stage = JobStage.failed
        job.error_message = "Server restarted before this job finished."
        db.add(job)
    db.commit()
