import httpx

from app.config import get_settings
from app.schemas import VoiceOut

ELEVENLABS_VOICES_URL = "https://api.elevenlabs.io/v1/voices"


def list_voices() -> list[VoiceOut]:
    settings = get_settings()
    resp = httpx.get(
        ELEVENLABS_VOICES_URL,
        headers={"xi-api-key": settings.elevenlabs_api_key},
        timeout=15,
    )
    resp.raise_for_status()
    all_voices = resp.json().get("voices", [])

    allow_list = set(settings.voice_id_list)
    if allow_list:
        all_voices = [v for v in all_voices if v["voice_id"] in allow_list]

    return [
        VoiceOut(
            id=v["voice_id"],
            name=v.get("name", v["voice_id"]),
            description=(v.get("labels") or {}).get("description", "") or v.get("description") or "",
            preview_url=v.get("preview_url"),
        )
        for v in all_voices
    ]
