import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import get_settings
from app.models import EpisodeFormat

MONOLOGUE_SYSTEM_PROMPT = """You are an expert podcast scriptwriter creating spoken-word educational \
content for a university course.

Your output is fed directly into a text-to-speech engine, so it must be PURE SPOKEN PROSE:
- No markdown, no headers, no bullet points, no numbered lists, no tables.
- No stage directions, no labels like "Segment 1:" or "[intro]".
- No visual references like "as shown below" or "see the table".
- Convert any list-like source material into flowing spoken sentences \
(e.g. "There are three key factors: first... second... and third..." spoken as connected \
prose, never as a list).

Target length: approximately {word_low}-{word_high} words, timed for a {length_minutes}-minute \
spoken episode at natural podcast pacing (about 130-150 words per minute).

Structure the episode as continuous prose with:
1. A short, engaging hook/intro that draws the listener in and previews what they'll learn.
2. A body that develops the topic progressively, using spoken transitions like \
"now let's talk about..." or "here's where it gets interesting..." instead of visual \
structure, and using analogies and concrete examples rather than dry lists of facts.
3. A brief outro that recaps the key takeaway and closes naturally with a sign-off line.

Base the episode strictly on the course material provided by the user. Do not introduce \
facts unsupported by it, but you may add illustrative analogies or examples to aid \
understanding.
"""

DIALOGUE_SYSTEM_PROMPT_TEMPLATE = """You are an expert podcast scriptwriter creating a two-person spoken-word \
educational dialogue for a university course.

Your output is fed directly into a text-to-speech engine using two distinct voices, so it must \
be formatted as strict speaker-labeled turns:
- Every turn starts on its own line with exactly "SPEAKER_1:" or "SPEAKER_2:" followed by that \
turn's spoken words — nothing else on that line.
- No markdown, no stage directions, no scene-setting text outside those labels.
- Turns should be natural conversational lengths (one to a few sentences), not long monologue \
blocks — this is a back-and-forth conversation, not two alternating speeches.

{persona_directive}

Target length: approximately {word_low}-{word_high} words total across both speakers, timed for \
a {length_minutes}-minute spoken episode at natural podcast pacing.

Structure the conversation with:
1. A short opening exchange that hooks the listener and introduces the topic.
2. A developing conversation that explores the topic, with genuine back-and-forth — questions, \
reactions, and building on (or, where the format calls for it, pushing back on) each other's points.
3. A brief closing exchange that recaps the key takeaway and signs off naturally.

Base the conversation strictly on the course material provided by the user. Do not introduce \
facts unsupported by it, but you may add illustrative analogies or examples to aid understanding.
"""

FORMAT_PERSONAS = {
    EpisodeFormat.interview: (
        "Format: guest expert interview. SPEAKER_1 is the host — curious, asks clear focused "
        "questions, guides the pacing, and reacts genuinely to what they learn. SPEAKER_2 is a "
        "practitioner or researcher being interviewed — answers with real authority and practical "
        "grounding, showing what the discipline looks like in practice, not just textbook "
        "definitions."
    ),
    EpisodeFormat.two_host: (
        "Format: two-host conversation. SPEAKER_1 and SPEAKER_2 are co-hosts with equal footing, "
        "thinking through the topic together. Constructive disagreement is valuable here — have "
        "them occasionally hold slightly different views, ask each other genuine questions, and "
        "reason out loud, so students see the reasoning process rather than just polished "
        "conclusions."
    ),
    EpisodeFormat.debate: (
        "Format: debate. SPEAKER_1 argues one well-developed, good-faith position on the topic; "
        "SPEAKER_2 argues a genuinely opposing position, steelmanned rather than strawmanned — "
        "both sides should be argued as their strongest real proponents would argue them. Ground "
        "the disagreement in genuine tensions or open questions within the source material; if the "
        "material doesn't support a real controversy, focus the disagreement on interpretation, "
        "emphasis, or implications rather than manufacturing false conflict."
    ),
}

# Calibrated so a 5-minute episode (the original fixed length) works out to the same
# 650/700/750/550 numbers this prompt always used.
WORDS_PER_MINUTE = 140
RANGE_PAD_PER_5MIN = 50
MIN_ACCEPTABLE_PAD_PER_5MIN = 150

_SPEAKER_TURN_RE = re.compile(r"^SPEAKER_([12])\s*:\s*(.+)$", re.IGNORECASE)


def word_targets(length_minutes: int) -> tuple[int, int, int]:
    """Returns (word_low, word_high, min_acceptable_words) for a target episode length."""
    mid = round(length_minutes * WORDS_PER_MINUTE)
    scale = length_minutes / 5
    word_low = round(mid - RANGE_PAD_PER_5MIN * scale)
    word_high = round(mid + RANGE_PAD_PER_5MIN * scale)
    min_acceptable = round(mid - MIN_ACCEPTABLE_PAD_PER_5MIN * scale)
    return word_low, word_high, min_acceptable


def _system_prompt(format: EpisodeFormat, length_minutes: int, word_low: int, word_high: int) -> str:
    if format == EpisodeFormat.monologue:
        return MONOLOGUE_SYSTEM_PROMPT.format(
            length_minutes=length_minutes, word_low=word_low, word_high=word_high
        )
    return DIALOGUE_SYSTEM_PROMPT_TEMPLATE.format(
        persona_directive=FORMAT_PERSONAS[format],
        length_minutes=length_minutes,
        word_low=word_low,
        word_high=word_high,
    )


def _build_user_message(
    topic_title: str, format: EpisodeFormat, context: str, word_low: int, word_high: int
) -> str:
    reminder = (
        f"Reminder: output pure spoken prose only, no formatting, target {word_low}-{word_high} words."
        if format == EpisodeFormat.monologue
        else (
            "Reminder: output ONLY SPEAKER_1:/SPEAKER_2: labeled turns, target "
            f"{word_low}-{word_high} words total."
        )
    )
    return (
        f"Episode topic: {topic_title}\n\n"
        f"Course material to base the episode on:\n{context}\n\n"
        f"{reminder}"
    )


def _get_llm() -> ChatGoogleGenerativeAI:
    settings = get_settings()
    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
        temperature=0.7,
    )


def generate_script(
    topic_title: str, format: EpisodeFormat, context: str, length_minutes: int = 5
) -> str:
    word_low, word_high, min_acceptable = word_targets(length_minutes)

    llm = _get_llm()
    system_prompt = _system_prompt(format, length_minutes, word_low, word_high)
    user_message = _build_user_message(topic_title, format, context, word_low, word_high)
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_message)]

    response = llm.invoke(messages)
    script = response.text.strip()

    if len(script.split()) < min_acceptable:
        word_mid = round((word_low + word_high) / 2)
        retry_message = (
            user_message
            + "\n\nYour previous attempt was too short. Expand the body with more "
            f"examples and depth to reach approximately {word_mid} words."
        )
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=retry_message)]
        response = llm.invoke(messages)
        script = response.text.strip()

    return script


def parse_dialogue_turns(script_text: str) -> list[tuple[int, str]]:
    """Parses a SPEAKER_1:/SPEAKER_2:-labeled script into (speaker_index, text) turns.
    A line that doesn't start a new speaker label is treated as a continuation of the
    previous turn (the model occasionally wraps a turn across lines)."""
    turns: list[tuple[int, str]] = []
    for raw_line in script_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = _SPEAKER_TURN_RE.match(line)
        if match:
            turns.append((int(match.group(1)), match.group(2).strip()))
        elif turns:
            speaker, text = turns[-1]
            turns[-1] = (speaker, f"{text} {line}")
    return turns
