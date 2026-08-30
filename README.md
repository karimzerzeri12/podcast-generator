# Podcast Generator (MVP)

Generates personalized English educational podcasts for students in a course, at a
target length (5-20 minutes) the admin controls for the whole course. Each student picks
a **format** — single-narrator monologue, guest expert interview, two-host conversation,
or debate/steelman — and, for the three dialogue formats, a voice (ElevenLabs) for each
of the two speakers. Scripts are generated with Gemini grounded in course material via a
small RAG pipeline, then synthesized to audio. Scripts are cached per (topic, format,
episode length) and audio per (script, voice(s)), so 100 students sharing choices only
trigger a handful of real LLM/TTS calls. Every generated script and audio file is saved
and associated with the student who generated it, viewable and downloadable from their
"My Episodes" list. Per-student listening engagement (time listened, completion %) is
tracked and viewable on an admin dashboard.

See `../.claude/plans/swirling-popping-deer.md` (or ask your assistant) for the full
design write-up.

## Prerequisites

- Python 3.11+
- Node.js 20+
- ffmpeg on PATH (required by `pydub` for audio concatenation)
- An [ElevenLabs](https://elevenlabs.io) API key, with at least **Voices: Read** and
  **Text to Speech** permissions enabled on the key
- A [Gemini API key](https://ai.google.dev) (free tier)
- (Optional) A [LangSmith](https://smith.langchain.com) API key, for tracing

> **Windows note:** if you just installed Node.js or ffmpeg (e.g. via `winget`) and a
> terminal that was already open still reports `npm`/`node`/`ffmpeg` as "not recognized",
> that terminal's PATH predates the install — open a fresh terminal (or PowerShell tab)
> rather than debugging further.

## Setup

1. Copy `.env.example` to `.env` in the project root and fill in real values —
   `.env.example` should only ever contain placeholders, never real keys:
   - `ELEVENLABS_API_KEY`
   - `ELEVENLABS_VOICE_IDS` — comma-separated ElevenLabs voice IDs to offer students.
     These must be voices that actually exist in *your* ElevenLabs account — fetch the
     list with `GET https://api.elevenlabs.io/v1/voices` (or from the
     [dashboard](https://elevenlabs.io/app/voice-library)) and pick the IDs you want to
     curate; don't reuse IDs from someone else's account or from documentation examples.
   - `GEMINI_API_KEY`
   - `SESSION_SECRET` / `ADMIN_TOKEN` — use long random strings. `SESSION_SECRET` signs
     student auth tokens and `ADMIN_TOKEN` gates the whole `/admin` API, so treat both as
     real secrets even in dev (don't ship the `change-me-*` placeholders to anything
     reachable by others).
   - `CORS_ORIGINS` — comma-separated list of exact frontend origins. Must not be `*`:
     the API sends credentialed requests, and the backend refuses to start with a
     wildcard origin (that combination would let any website call the API as a logged-in
     user).
   - (optional) `LANGCHAIN_TRACING_V2=true`, `LANGCHAIN_API_KEY` — to enable LangSmith tracing

2. Backend:
   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\pip install -r requirements.txt
   .\.venv\Scripts\uvicorn app.main:app --reload
   ```
   On first run, since no `.env` exists yet at the project root, `app/config.py` reads
   from process environment variables — either set them in your shell, or make sure
   `.env` exists at `podcast-generator/.env` (one level above `backend/`).

   On startup the app auto-seeds a sample course, its topics (with real short source
   material — plain text or PDF), and a handful of sample students (see
   `app/seed/data/roster.csv` for login credentials) if the database is empty — so the
   whole pipeline is testable without your real roster. See **Adding course material**
   below for how to load your own.

3. Frontend:
   ```powershell
   cd frontend
   npm install
   copy .env.local.example .env.local
   npm run dev
   ```
   Open http://localhost:5173.

4. Log in as a student using the email/access code from `backend/app/seed/data/roster.csv`
   (or your real roster). Topic browsing, format/voice selection, podcast generation, and
   your past episodes (playable, downloadable — audio and script) all live on one page.

5. Admin dashboard: open http://localhost:5173/#/admin and enter the `ADMIN_TOKEN` from
   your `.env` to view per-student engagement (or download a CSV), set the target podcast
   length, and set the per-student generation limit (both described below). Course content
   is managed in code, not here — see **Adding course material**.

## Podcast formats

- **Monologue** — a single narrator, one voice.
- **Guest expert interview** — a host interviews a practitioner/researcher; needs two voices.
- **Two-host conversation** — two co-hosts think through the topic together, including
  constructive disagreement; needs two voices.
- **Debate / steelman** — two fairly-argued opposing positions, best for contested topics;
  needs two voices.

For the three dialogue formats, Gemini is prompted to output strict `SPEAKER_1:`/
`SPEAKER_2:`-labeled turns, which are synthesized turn-by-turn with each speaker's chosen
voice and concatenated. Scripts/audio are cached per (topic, format, episode length) and
per (script, voice(s)) respectively — the same sharing behavior as before, just with format
and a voice pair instead of a single tone/voice.

## Podcast length

The target episode length (5-20 minutes) is set course-wide by the admin, on the admin
dashboard — students don't choose it. It's stored in the database (not `.env`), so it
takes effect immediately, no restart needed. Changing it only affects newly generated
episodes: it bumps the effective cache key for scripts (same mechanism as a material
change), so a length change doesn't retroactively invalidate or delete anything already
cached, and reverting to a previous length re-serves what's already cached for it instead
of regenerating.

## Per-student generation limit

The admin can cap how many podcasts each student may generate, on the admin dashboard
(**0 = unlimited**, the default). The cap counts each podcast a student generates; a
student who reaches it gets a clear "limit reached" message on the next attempt but can
still play and download episodes they already generated. Lowering the cap never deletes
anything already generated. Useful for keeping LLM/TTS spend bounded across a large roster.

## Adding course material

Course content is managed in code, not through the app — there is deliberately **no
admin upload page**. The admin dashboard is for engagement, podcast length, and the
per-student generation limit only. Three ways to load material:

**1. `python -m app.build_course <course.pdf>` — build a whole course from one PDF.**
The fastest path if your material is a single PDF with chapters. It splits the PDF by its
**bookmarks/outline**: each top-level chapter becomes a topic (the bookmark name is the
title, the chapter's pages are its text), a one-line description is generated per topic
(via Gemini, grounded in that chapter), and the result is written as reviewable **seed
data** — `course.json`, `topics.json`, and one text file per topic under `topics/`.
```powershell
cd backend
.\.venv\Scripts\python -m app.build_course C:\path\to\course.pdf --dry-run  # preview chapters
.\.venv\Scripts\python -m app.build_course C:\path\to\course.pdf            # write seed data
.\.venv\Scripts\python -m app.seed.seed_data                                # load it (non-destructive)
```
If the PDF has **no** bookmarks (common for journal articles and simple exports), the whole
document becomes **one topic** instead — Gemini pulls the paper's real title and writes a
description, and RAG retrieves across the whole document at generation time. So the command
always produces something usable.

**Splitting a bookmark-less PDF into several topics:** if the chapters are only *visual*
headings in the text (e.g. `Module 3`, `Chapter 4`) rather than real bookmarks, pass
`--split-on` with a regex for those headings and each becomes its own topic:
```powershell
.\.venv\Scripts\python -m app.build_course "C:\path\to\reader.pdf" --split-on "Module \d+" --dry-run
```
Run with `--dry-run` first to check the split looks right, then again without it to write.

**Two-level chapters → sub-chapters:** to split into fine-grained sub-topics *and* group
them under a parent chapter (the student first picks a chapter, then a sub-chapter), pass
both `--split-on` (the sub-topic pattern) and `--chapter-on` (the chapter pattern):
```powershell
.\.venv\Scripts\python -m app.build_course "C:\path\to\reader.pdf" `
  --split-on "[0-9]+\.[0-9]+ [A-Z]" --chapter-on "Module \d+" --dry-run
```
Each sub-topic is tagged with the chapter it falls under, and the web UI presents the
chapter → sub-chapter selection automatically. Anchor the sub-topic pattern to real section
numbers (e.g. `[34]\.[0-9]+` for chapters 3–4) to avoid matching decimals in the body text.

Useful flags: `--title` / `--description` to override the course/topic name, `--min-chars N`
to skip tiny chapters, `--no-llm` to skip Gemini (uses the opening lines as the description
and the file name as the title instead — no API quota needed), `--out DIR` to write
elsewhere. Review the generated titles and descriptions before loading — they're
auto-generated and usually good, but not always ideal.

**2. `python -m app.ingest` — scripted loading from a folder or bucket you control.**
Set `SOURCE_ROOT` in `.env` to a local/network path (bare path or `file://` URI) or an
S3-compatible URI (`s3://bucket/prefix` — credentials from the standard AWS env vars;
set `S3_ENDPOINT_URL` too for non-AWS S3-compatible storage like Cloudflare R2), and put a
`topics.json` manifest there (same shape as `backend/app/seed/data/topics.json` — `title`,
`description`, `order_index`, `filename`, `.txt` or `.pdf`). Then:
```powershell
cd backend
.\.venv\Scripts\python -m app.ingest --dry-run   # preview: what would change
.\.venv\Scripts\python -m app.ingest             # apply
```
This is idempotent and non-destructive: unchanged files are a no-op (skipped by content
hash, so re-runs are fast), a changed file re-ingests only that topic (other topics' cached
scripts/audio are untouched), a new title creates a topic, and a title that's in the DB but
missing from the manifest is left alone with a warning — never deleted. It never touches
students, engagement records, or generated audio. A misconfigured `SOURCE_ROOT` (bad
path, unreachable share, wrong bucket) fails loudly at backend startup too, not at a
student's first request.

**3. Editing seed data directly** — the underlying format the other two produce. Edit
`backend/app/seed/data/` (`course.json`, `topics.json`, `roster.csv`, files under
`topics/`) by hand, then run `python -m app.seed.seed_data` to apply it. Running the seed
is **non-destructive**: it updates topics whose text changed (regenerating only those
topics' cached podcasts), adds new topics/students, and leaves existing episodes and
engagement intact. For a full clean rebuild instead, delete `backend/storage/db.sqlite3`
and `backend/storage/chroma/` and restart — that wipes generated audio/engagement too.

> **Note on the course title:** the course is matched by title, so changing `title` in
> `course.json` creates a *new* course and orphans the existing students. Change topics
> and material freely, but keep the course title stable once students exist.

## Running tests

```powershell
cd backend
.\.venv\Scripts\pytest
```

Tests mock the Gemini and ElevenLabs calls (no API keys/network needed) and assert the
caching contract directly: identical requests don't re-trigger generation, a voice-only
change reuses the cached script, a format change triggers full regeneration, concurrent
identical requests share one in-flight job, re-ingesting unchanged material is a no-op,
changing one topic's material doesn't invalidate another topic's cache, and changing the
admin-controlled episode length triggers regeneration while a revert reuses the original
cache instead of regenerating a third time.

## Troubleshooting

- **`npm`/`node`/`ffmpeg` "not recognized"** right after installing: open a new terminal
  so it picks up the updated PATH (see the Windows note above).
- **ElevenLabs 401 on `/voices`**: the API key is invalid, or lacks the `Voices: Read`
  permission (ElevenLabs keys can be scoped) — check both on the
  [API keys page](https://elevenlabs.io/app/settings/api-keys).
- **Voice list loads but is empty**: `ELEVENLABS_VOICE_IDS` in `.env` doesn't match any
  voice in your account — fetch `GET https://api.elevenlabs.io/v1/voices` with your key
  and use IDs from that response.
- **Changed `.env` but nothing changed**: settings are read once at process startup and
  cached — restart the backend after editing `.env`.
