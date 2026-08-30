import shutil
from collections.abc import Callable
from pathlib import Path

import httpx
from pydub import AudioSegment

from app.config import get_settings

TARGET_CHUNK_CHARS = 1000
INTER_CHUNK_SILENCE_MS = 400

VOICE_SETTINGS = {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0, "use_speaker_boost": True}

ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


def split_for_tts(script_text: str, target_chars: int = TARGET_CHUNK_CHARS) -> list[str]:
    """Paragraph-aware chunking so each ElevenLabs call stays under length limits and
    cuts land on natural pauses rather than mid-sentence."""
    paragraphs = [p.strip() for p in script_text.split("\n\n") if p.strip()]
    if len(paragraphs) <= 1:
        paragraphs = [p.strip() for p in script_text.split("\n") if p.strip()]

    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        candidate = f"{current}\n\n{para}".strip() if current else para
        if len(candidate) > target_chars and current:
            chunks.append(current)
            current = para
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def _synthesize_chunk(text: str, voice_id: str) -> bytes:
    settings = get_settings()
    resp = httpx.post(
        ELEVENLABS_TTS_URL.format(voice_id=voice_id),
        headers={"xi-api-key": settings.elevenlabs_api_key, "Content-Type": "application/json"},
        json={
            "text": text,
            "model_id": settings.elevenlabs_model_id,
            "voice_settings": VOICE_SETTINGS,
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.content


def _synthesize_and_concat(
    items: list[tuple[str, str]],
    job_id: int,
    output_path: Path,
    on_progress: Callable[[int, int], None] | None,
) -> float:
    """Synthesizes an ordered list of (voice_id, text) pieces and concatenates them
    with a short silence between each, exporting a single mp3 at output_path.
    Returns duration in seconds. Shared by monologue and dialogue synthesis so both
    stay in sync on chunking/progress/cleanup behavior."""
    settings = get_settings()
    chunk_dir = settings.resolved_path(settings.audio_dir) / "chunks" / str(job_id)
    chunk_dir.mkdir(parents=True, exist_ok=True)

    combined = AudioSegment.empty()
    silence = AudioSegment.silent(duration=INTER_CHUNK_SILENCE_MS)

    try:
        for idx, (voice_id, text) in enumerate(items):
            audio_bytes = _synthesize_chunk(text, voice_id)
            chunk_path = chunk_dir / f"{idx}.mp3"
            chunk_path.write_bytes(audio_bytes)

            segment = AudioSegment.from_mp3(chunk_path)
            combined += segment if idx == 0 else silence + segment

            if on_progress:
                on_progress(idx + 1, len(items))

        output_path.parent.mkdir(parents=True, exist_ok=True)
        combined.export(output_path, format="mp3")
        return len(combined) / 1000.0
    finally:
        shutil.rmtree(chunk_dir, ignore_errors=True)


def synthesize_script(
    script_text: str,
    voice_id: str,
    job_id: int,
    output_path: Path,
    on_progress: Callable[[int, int], None] | None = None,
) -> float:
    """Single-narrator (monologue) synthesis: chunks the script and synthesizes each
    chunk with one consistent voice."""
    chunks = split_for_tts(script_text)
    return _synthesize_and_concat(
        [(voice_id, chunk) for chunk in chunks], job_id, output_path, on_progress
    )


def synthesize_dialogue(
    turns: list[tuple[int, str]],
    voice_id: str,
    voice_id_2: str,
    job_id: int,
    output_path: Path,
    on_progress: Callable[[int, int], None] | None = None,
) -> float:
    """Two-speaker synthesis: each (speaker, text) turn is synthesized with that
    speaker's voice (1 -> voice_id, 2 -> voice_id_2) and concatenated in order."""
    voice_for_speaker = {1: voice_id, 2: voice_id_2}
    items = [(voice_for_speaker[speaker], text) for speaker, text in turns]
    return _synthesize_and_concat(items, job_id, output_path, on_progress)
