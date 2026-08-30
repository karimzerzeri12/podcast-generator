# ---------- Stage 1: build the React frontend to static files ----------
FROM node:20-slim AS frontend
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
# Empty base URL => the frontend calls the API on its own origin (same host that serves
# it), so there are no cross-origin requests in the bundled deployment.
ENV VITE_API_BASE_URL=""
RUN npm run build

# ---------- Stage 2: Python backend that also serves the built frontend ----------
FROM python:3.11-slim

# ffmpeg is required by pydub to concatenate the per-chunk / per-speaker audio.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Model + library caches, and the app's own storage, must live in world-writable dirs so
# the app works whether the host runs the container as root or as an unprivileged user
# (Hugging Face Spaces runs as UID 1000).
ENV HF_HOME=/app/cache \
    SENTENCE_TRANSFORMERS_HOME=/app/cache \
    DATABASE_URL=sqlite:////app/storage/db.sqlite3 \
    CHROMA_DIR=/app/storage/chroma \
    SCRIPTS_DIR=/app/storage/scripts \
    AUDIO_DIR=/app/storage/audio

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the embedding model at build time so the first request isn't slowed by a
# model download (and so it never needs to write to a read-only cache at runtime).
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY backend/ ./
# The built frontend from stage 1 — app.main mounts ./static when it exists.
COPY --from=frontend /frontend/dist ./static

RUN mkdir -p /app/storage /app/cache && chmod -R 777 /app/storage /app/cache

# Hugging Face Spaces routes traffic to port 7860 by default.
EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
