import hmac

from fastapi import Depends, Header, HTTPException, status
from sqlmodel import Session

from app.auth.service import verify_token
from app.config import get_settings
from app.db import get_session
from app.models import Student

SessionDep = Session


def get_db():
    yield from get_session()


def get_current_student(
    authorization: str = Header(default=""),
    token: str = "",
    db: Session = Depends(get_db),
) -> Student:
    if authorization.startswith("Bearer "):
        bearer_token = authorization.removeprefix("Bearer ").strip()
    elif token:
        # <audio>/<video> elements can't set custom headers on their src URL, so
        # streaming endpoints accept the token as a query param as a fallback.
        bearer_token = token
    else:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")

    student_id = verify_token(bearer_token)
    if student_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Student not found")
    return student


def require_admin(x_admin_token: str = Header(default="")) -> None:
    settings = get_settings()
    # Constant-time compare so the token can't be recovered byte-by-byte via response timing.
    if not x_admin_token or not hmac.compare_digest(x_admin_token, settings.admin_token):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid admin token")
