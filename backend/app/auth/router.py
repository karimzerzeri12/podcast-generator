from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.auth.service import authenticate, issue_token
from app.deps import get_db
from app.schemas import LoginRequest, LoginResponse, StudentOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    student = authenticate(db, body.email, body.access_code)
    if student is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or access code")
    token = issue_token(student.id)
    return LoginResponse(
        token=token,
        student=StudentOut(
            id=student.id, name=student.name, email=student.email, course_id=student.course_id
        ),
    )
