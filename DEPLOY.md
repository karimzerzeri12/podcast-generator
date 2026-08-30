# Deploying (free) so your professor can try it

**Two free ways to host — pick based on whether data must persist:**

| | **Oracle Always Free VM** | **Hugging Face Space** (below) |
|---|---|---|
| Persistence | ✅ Nothing resets — podcasts + engagement accumulate | ❌ Ephemeral — resets on rebuild/sleep |
| Setup effort | ~30–45 min (real server) | ~10 min (builds on their servers) |
| Best for | Real use / a proper trial | A quick first look |

- **Want data to stick (recommended for a real trial): see [DEPLOY-ORACLE.md](DEPLOY-ORACLE.md).**
- **Just want the fastest look:** the Hugging Face Spaces guide below.

---

Goal: get the tool onto a public URL your professor can open — no terminals, no local
setup on their side. **Hugging Face Spaces (Docker)** is free, builds the
container on their servers (so you don't need Docker installed locally), allows the
outbound calls to Gemini/ElevenLabs, and installs `ffmpeg`.

The repo already contains everything needed: a `Dockerfile` that builds the React
frontend and serves it from the FastAPI backend as a **single app on one URL**.

> **The one real cost caveat:** hosting is free, but **ElevenLabs is not free at volume.**
> Its free tier is ~10,000 characters/month — roughly **two 5-minute episodes**. That's
> fine for your professor to *try* the tool; it is not enough to run a class. Size an
> ElevenLabs plan to your expected use, and use the per-student generation limit (admin
> dashboard) to bound spend.
>
> **Storage caveat:** the free Space has *ephemeral* disk — generated audio and the
> database reset whenever the Space rebuilds or goes to sleep. It re-seeds the sample
> course automatically on boot, so a trial still works; long-term persistence needs the
> paid "persistent storage" add-on (or a VM).

---

## Step 1 — Create a Hugging Face account + Space

1. Sign up at <https://huggingface.co/join> (free).
2. Go to <https://huggingface.co/new-space>.
   - **Owner**: you. **Space name**: e.g. `podcast-generator`.
   - **License**: any (e.g. MIT).
   - **Select the SDK**: **Docker** → **Blank**.
   - **Visibility**: **Public** is simplest — your professor just opens the URL and logs in
     with a roster code. (Everything still requires a login, so public exposure is low
     risk; the only concern is someone burning your ElevenLabs quota, which the login gate
     and the per-student limit mitigate.) Choose Private if you prefer, but then your
     professor needs a HF account and to be added as a collaborator.
3. Create the Space. Note its URL — it looks like
   `https://<your-username>-podcast-generator.hf.space`.

## Step 2 — Make the Space's README declare the Docker port

A Docker Space is configured by YAML frontmatter at the top of its `README.md`. Make sure
the Space's `README.md` starts with exactly this (edit it in the Space's **Files** tab, or
include it when you push in Step 3):

```
---
title: Podcast Generator
emoji: 🎙️
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
---
```

`app_port: 7860` matches the port the `Dockerfile` exposes. (Everything below the
frontmatter can be any description text.)

## Step 3 — Push the code to the Space

The Space is a git repository. From your machine (you need `git` installed and a Hugging
Face **access token** with *write* scope from <https://huggingface.co/settings/tokens>):

```powershell
# clone the empty Space repo (use your real username/space name)
git clone https://huggingface.co/spaces/<your-username>/podcast-generator hf-space
cd hf-space

# copy the project into it (adjust the source path if different)
robocopy c:\Users\ELITE\Downloads\podcast-generator . /E /XD .git node_modules .venv storage dist /XF .env .env.local

# keep the Docker frontmatter README from Step 2 (don't let the project README overwrite
# the port config — if you copied the project README.md over, re-add the frontmatter block)

git add .
git commit -m "Deploy podcast generator"
git push
```

When prompted for a password during `git push`, paste your Hugging Face **access token**
(not your account password).

Hugging Face will automatically build the `Dockerfile` and start the container. The first
build takes several minutes (installing ffmpeg, Python deps, and pre-downloading the
embedding model). You can watch progress on the Space's **Logs** tab.

## Step 4 — Set the secrets

In the Space, open **Settings → Variables and secrets** and add:

**Secrets** (hidden — click "New secret"):
| Name | Value |
|---|---|
| `ELEVENLABS_API_KEY` | your ElevenLabs key (with Text-to-Speech permission + quota) |
| `GEMINI_API_KEY` | your Gemini key |
| `SESSION_SECRET` | a long random string |
| `ADMIN_TOKEN` | a long random string (this is your admin dashboard password) |

**Variables** (visible — click "New variable"):
| Name | Value |
|---|---|
| `ELEVENLABS_VOICE_IDS` | comma-separated voice IDs from *your* ElevenLabs account |
| `CORS_ORIGINS` | your Space URL, e.g. `https://<your-username>-podcast-generator.hf.space` |

After adding secrets, use **Settings → Factory reboot** (or push a commit) so the container
restarts and picks them up.

## Step 5 — Try it

Open the Space URL. You should see the login page. Log in with a seeded roster account
(e.g. `alice@example.edu` / `alice123` — see `backend/app/seed/data/roster.csv`), or the
admin dashboard at `<space-url>/#/admin` with your `ADMIN_TOKEN`.

Send your professor the Space URL plus a roster email/code. That's it — no terminals on
either side.

---

## Updating the deployed app later

Any change (including new course content in the seed data) goes live by committing and
pushing to the Space repo again:

```powershell
cd hf-space
# copy in your updated files, then:
git add .
git commit -m "Update"
git push
```

Hugging Face rebuilds automatically. Remember: on the free (ephemeral) Space a rebuild
also wipes generated audio and the database, re-seeding fresh — expected for a trial.

---

## If you outgrow the free trial

- **Persistence**: add Hugging Face persistent storage (paid) so data survives rebuilds,
  or move to a small always-free VM (e.g. Oracle Cloud Always Free), where SQLite + local
  audio persist normally.
- **More TTS**: a paid ElevenLabs plan sized to your class.
- **Heavier concurrency**: see the scaling notes at the end of `ARCHITECTURE.md`.
