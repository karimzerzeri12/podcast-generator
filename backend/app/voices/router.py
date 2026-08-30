from fastapi import APIRouter, Depends

from app.deps import get_current_student
from app.models import Student
from app.schemas import VoiceOut
from app.voices.service import list_voices

router = APIRouter(prefix="/voices", tags=["voices"])


@router.get("", response_model=list[VoiceOut])
def get_voices(student: Student = Depends(get_current_student)) -> list[VoiceOut]:
    return list_voices()
