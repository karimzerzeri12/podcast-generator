import base64
import hashlib
import hmac
import time

from passlib.context import CryptContext
from sqlmodel import Session, select

from app.config import get_settings
from app.models import Student

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

TOKEN_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days


def hash_access_code(raw_code: str) -> str:
    return pwd_context.hash(raw_code)


def _sign(payload: str) -> str:
    secret = get_settings().session_secret.encode()
    return hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()


def issue_token(student_id: int) -> str:
    payload = f"{student_id}:{int(time.time()) + TOKEN_TTL_SECONDS}"
    signature = _sign(payload)
    raw = f"{payload}:{signature}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def verify_token(token: str) -> int | None:
    try:
        raw = base64.urlsafe_b64decode(token.encode()).decode()
        student_id_str, expires_str, signature = raw.split(":")
    except (ValueError, UnicodeDecodeError, base64.binascii.Error):
        return None

    payload = f"{student_id_str}:{expires_str}"
    if not hmac.compare_digest(_sign(payload), signature):
        return None
    if int(expires_str) < int(time.time()):
        return None
    return int(student_id_str)


def authenticate(db: Session, email: str, access_code: str) -> Student | None:
    student = db.exec(select(Student).where(Student.email == email.strip().lower())).first()
    if student is None:
        # Run a dummy hash verification so an unknown email costs the same time as a
        # known one — otherwise response timing reveals which emails are registered.
        pwd_context.dummy_verify()
        return None
    if not pwd_context.verify(access_code, student.access_code):
        return None
    return student
