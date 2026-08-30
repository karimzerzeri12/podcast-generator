# Podcast Generator — Demo Hosting & Roadmap to 100 Students

*Prepared for the supervisor review.*

## What the tool does (current status)

A working web app that generates personalized, course-grounded educational **podcasts**
for students. A student logs in, picks a **topic** and a **format** (single-narrator
monologue, guest-expert interview, two-host conversation, or debate), picks the **voice(s)**,
and the app writes a script with an LLM grounded in the course's own material (RAG), then
synthesizes it to audio. Every episode is saved to the student and is replayable and
downloadable. An **admin dashboard** shows per-student listening engagement and controls
the episode length and a per-student generation limit.

**Status: functional end-to-end and verified over a public link.** Course content is loaded
from the instructor's PDFs (auto-split into topics), generation and playback work, and the
whole flow — including the admin dashboard and audio streaming — has been tested through a
live public URL.

---

## Part 1 — Hosting for the demo (Cloudflare quick tunnel)

For a demo or a quick share, the app is exposed with a **Cloudflare quick tunnel**: it runs
on the presenter's machine and Cloudflare gives it a temporary public HTTPS link. No cloud
account, no Docker, no deployment.

### How to run it

From the project folder, one command:

```powershell
.\share.ps1
```

It builds the app, starts the backend, and opens a tunnel, printing a public URL like:

```
https://<random-words>.trycloudflare.com
```

- **Student view:** the base URL. Log in with a roster email/code (see
  `backend/app/seed/data/roster.csv`).
- **Admin view:** the same URL + `/#/admin`, protected by the admin token.

Send the audience the **base URL** and a student login. Keep the admin URL and token private.

### Before sharing the link — set real secrets

The app ships with placeholder secrets. On a public URL these must be changed, because the
tunnel is reachable by anyone with the link:

- `SESSION_SECRET` — signs student login tokens (a known value lets anyone forge a session).
- `ADMIN_TOKEN` — the admin dashboard password.

Set both to long random strings in `.env`, then restart (`.\share.ps1`).

### Honest limitations of the tunnel (why it's demo-only)

| Limitation | Impact |
|---|---|
| Runs on the presenter's laptop | The link only works while the laptop is on and the script is running |
| URL changes each run | Must re-share the link if restarted |
| One generation at a time | Fine for a demo; a class generating at once would queue |
| Free API tiers | ~20 script generations/day (Gemini free) and ~2 audio episodes (ElevenLabs free) before limits |

**Conclusion:** the tunnel is perfect for tomorrow's demo and a small trial. It is **not**
the setup for 100 students — that's Part 2.

---

## Part 2 — Roadmap to ship to 100 students

Five workstreams, roughly in priority order. None is large; the total is on the order of a
few days plus a budget decision on the paid APIs.

### 1. Always-on hosting (replace the laptop tunnel) — **required**

Move from the laptop to a persistent server so the link is permanent and data never resets.

- **Recommended: Oracle Cloud "Always Free" VM** — a genuinely free, always-on Linux server
  with a persistent disk. Generated podcasts and engagement data accumulate and survive
  restarts. Full step-by-step already written in **`DEPLOY-ORACLE.md`**; the app is
  containerized (`Dockerfile` + `docker-compose.yml`) so it's one command to run there.
- **Add HTTPS** with a real certificate (Caddy + a domain, or a named Cloudflare Tunnel) so
  login tokens are encrypted.
- *Effort: ~half a day.*

### 2. API capacity & cost (the real ceiling) — **required, needs a budget decision**

Hosting is free; the **AI APIs are the true limit and the main recurring cost.**

- **Gemini (scripts):** the free tier allows only ~20 generations/day. **Enable billing** —
  Gemini Flash is extremely cheap (a script costs a fraction of a cent), so a whole class is
  typically a few dollars. This removes the daily cap.
- **ElevenLabs (audio):** the dominant cost, billed per character of audio. The free tier is
  ~two 5-minute episodes. A **paid plan sized to expected audio minutes** is needed.
- **Cost is controlled by caching, not student count.** Because identical choices are cached
  and shared, you pay for roughly *(topics × formats × voices)* distinct generations — **not**
  that number times 100 students. Pre-warming (below) means you spend the quota **once**.
- *Effort: low (enable billing / pick a plan); requires a budget sign-off.*

### 3. Performance for a class at once — **recommended**

Generation runs on a single background worker (one podcast at a time), so 100 students all
requesting *new, different* podcasts simultaneously would queue.

- **Pre-warm the cache before class** — generate every topic/format/voice combination once
  ahead of time. Then when students arrive, every pick is an **instant cache hit** — any
  number of them at once, no queue, no per-student API cost. This is the single most
  effective step. *(A one-command pre-warm script can be added on request.)*
- *(Optional, only if needed):* increase the number of generation workers — a small change,
  but then bounded by the API rate limits above.
- *Effort: low (pre-warm script).*

### 4. Security hardening — **required**

- Strong `SESSION_SECRET` and `ADMIN_TOKEN` (same as the demo step, permanent this time).
- HTTPS (covered by hosting step 1).
- Rotate any API keys that were used during development.
- The **per-student generation limit** (already built into the admin dashboard) bounds
  abuse and runaway cost.
- *Effort: low.*

### 5. Content & roster finalization — **required**

- Load the **final course content** from the instructor's PDFs (`build_course`), and review
  the auto-generated topic titles/descriptions (cleaner descriptions come from the LLM once
  Gemini billing is on).
- Replace the sample roster with the **real 100-student roster** (emails + access codes) in
  `backend/app/seed/data/roster.csv`.
- *Effort: low–moderate.*

### Operations (ongoing, lightweight)

- **Backups:** the server's data folder (database + audio) is the whole state — back it up
  on a schedule.
- **Monitoring:** watch logs and disk usage.

### Beyond 100 students (not needed now)

The current design (SQLite, local files, single worker) comfortably fits one VM for 100
students. If it ever grows much larger, the migration path is well understood: PostgreSQL
instead of SQLite, object storage (S3/R2) for audio, and a multi-worker task queue.

---

## Summary

| Item | Status | Needed for 100 students |
|---|---|---|
| Core app (generate, play, archive, admin) | ✅ Done & verified | — |
| Course content from PDFs + RAG | ✅ Done | Load final content |
| Caching to share work across students | ✅ Done | Pre-warm before class |
| Per-student limit + engagement dashboard | ✅ Done | — |
| Public link for the demo | ✅ Cloudflare tunnel | — |
| Always-on persistent hosting | ▢ Planned | **Yes** (Oracle VM, ~½ day) |
| Paid Gemini + ElevenLabs | ▢ Decision needed | **Yes** (budget) |
| Pre-warm cache for concurrency | ▢ Planned | **Yes** (script) |
| Strong secrets + HTTPS | ▢ Planned | **Yes** |
| Real roster | ▢ Planned | **Yes** |

**Bottom line:** the product works today and can be demoed live over a public link. Reaching
100 students is a short, well-scoped list — a persistent free VM, paid API tiers (the only
real cost), cache pre-warming, and standard security/roster finalization.
