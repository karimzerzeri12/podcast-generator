# Setting the project up on a new laptop

The project is self-contained. You copy the folder over, install a few tools, and run two
setup commands. Generated data (the database + past podcasts) does **not** transfer — the
app re-seeds your course fresh from the content files, which **do** transfer.

## 1. Install these on the new laptop (once)

- **Python 3.11+** — <https://www.python.org/downloads/> (tick "Add Python to PATH" during install)
- **Node.js 20+** — <https://nodejs.org> (LTS)
- **ffmpeg** — needed to stitch audio. Easiest: open PowerShell and run
  `winget install --id Gyan.FFmpeg` (then open a **new** terminal so it's on PATH).
- **cloudflared** — only if you'll share via `share.ps1`:
  `winget install --id Cloudflare.cloudflared`

Then allow local scripts to run (once, so `npm` and the `.ps1` helpers work):
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

> After installing Python/Node/ffmpeg, **open a fresh terminal** so it picks them up.

## 2. Copy the project folder

Put the whole `podcast-generator` folder on the new laptop (via USB, OneDrive/Drive, or the
transfer zip). It already includes your `.env` (your API keys) and all your course content.

> **The `.env` file contains real API keys — keep the copy private** (don't email it or put
> it in a public place). It's your ElevenLabs/Gemini/LangSmith secrets.

## 3. Set up the backend and frontend (once, on the new laptop)

Open PowerShell in the project folder.

**Backend:**
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
cd ..
```
(First run also downloads a small embedding model — needs internet, takes a minute.)

**Frontend:**
```powershell
cd frontend
npm install
cd ..
```

## 4. Run it

**For local use / development — two terminals:**
```powershell
# terminal 1
cd backend
.\.venv\Scripts\uvicorn app.main:app
```
```powershell
# terminal 2
cd frontend
npm run dev
```
Open http://localhost:5173. (First backend start re-seeds your course + roster.)

**To share a public link with your professor:**
```powershell
.\share.ps1
```
It prints a `trycloudflare.com` link (student link + admin link).

## 5. That's it

Your course content, students, settings, and all the helper scripts came with the folder.
Things that regenerate automatically on the new laptop:
- the Python virtual environment (`backend\.venv`)
- the Node packages (`frontend\node_modules`)
- the database + any previously generated podcasts (re-seeded fresh from your content files)

To change content later, it's the same as before: edit the files in
`backend\app\seed\data\` and run `.\apply-content.ps1`.
