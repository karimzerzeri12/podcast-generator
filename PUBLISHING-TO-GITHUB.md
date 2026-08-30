# Publishing this project to GitHub

This walks through taking the project from "just a folder on my laptop" to a real GitHub
repository, step by step. Verified against this machine's actual setup: Git 2.55.0 is
installed; the GitHub CLI (`gh`) is **not**, so this uses the plain `git` + github.com
website flow. If you install `gh` later, there's a shortcut noted at the end.

---

## 0. What's already taken care of

The project already has a `.gitignore` that correctly excludes everything that shouldn't
go to GitHub:

```
.env                 <- your real API keys (ElevenLabs, Gemini, LangSmith secrets)
.env.local
__pycache__/
*.pyc
.venv/                <- the Python virtual environment
venv/
backend/storage/      <- the database, generated audio/scripts, vector store
node_modules/         <- frontend dependencies
dist/
frontend/dist/
```

You don't need to touch this file — it's already correct. The one thing worth
double-checking yourself before pushing: **`.env` holds your real, working API keys.**
Never remove it from `.gitignore`, and never `git add -f` it.

---

## 1. Initialize the repository

Open PowerShell in the project root (`podcast-generator-transfer`) and run:

```powershell
git init
git branch -M main
```

`git branch -M main` renames the default branch to `main` (GitHub's current default;
older Git versions sometimes default to `master`).

---

## 2. Stage everything and make the first commit

```powershell
git add .
git status
```

**Before committing**, read through the `git status` output. You're looking for exactly
one thing: **`.env` should NOT appear** in the list of files to be committed. If it does
appear, stop — that means something is wrong with `.gitignore` being picked up (rare, but
check you're in the right directory), and you should fix that before proceeding rather
than commit real secrets to git history.

Once that looks right:

```powershell
git commit -m "Initial commit"
```

---

## 3. Create the repository on GitHub

1. Go to [github.com/new](https://github.com/new) (you'll need to be logged in).
2. Repository name: e.g. `podcast-generator`.
3. **Do not** check "Add a README", "Add .gitignore", or "Choose a license" — the repo
   needs to start empty so it doesn't conflict with the commit you already made locally.
4. Choose **Private** or **Public**:
   - **Private** if this should only be visible to you and people you explicitly invite
     (e.g. your professor, added as a collaborator).
   - **Public** if anyone should be able to see it.
   - Given the repo will contain real student-facing app logic (though not real student
     data — that stays local in the gitignored `backend/storage/`), either is reasonable;
     it comes down to whether you want it discoverable.
5. Click **Create repository**. GitHub will show you a page with setup commands — you
   want the "…or push an existing repository from the command line" section, but the
   next step here covers the same thing.

---

## 4. Connect your local repo to GitHub and push

GitHub will have shown you a URL like `https://github.com/<your-username>/podcast-generator.git`.
Use it here:

```powershell
git remote add origin https://github.com/<your-username>/podcast-generator.git
git push -u origin main
```

The first push will prompt you to authenticate with GitHub (a browser window, or a
personal access token, depending on how Git is configured on this machine). Follow
whatever prompt appears.

Once it finishes, refresh the GitHub page — your files should be there.

---

## 5. Verify nothing sensitive made it up

As a final sanity check, search the pushed repo on GitHub's website (use the code search
bar) for `GEMINI_API_KEY` or `ELEVENLABS_API_KEY`. Nothing should turn up, since `.env`
was never staged. If something *did* leak, don't just delete it and push again — a
leaked key needs to be **rotated** (generate a new one from ElevenLabs/Gemini and update
your local `.env`), because the old one remains visible in git history even after a
later commit removes the file.

---

## 6. Keeping it updated later

Every time you make changes you want to publish:

```powershell
git add .
git commit -m "Describe what changed"
git push
```

---

## Optional: using the GitHub CLI instead

If you install `gh` (`winget install --id GitHub.cli`) at some point, steps 3–4 collapse
into one command run from the project root:

```powershell
gh repo create podcast-generator --private --source=. --remote=origin --push
```

This creates the GitHub repo, sets the remote, and pushes — all in one step. (Swap
`--private` for `--public` if you want it public.)

---

## One thing to consider before making this public: `.env.production.example`

The project already has `.env.production.example` — a template with placeholder values
instead of real keys. This file **is safe to commit** (it's not in `.gitignore`, and it
should stay that way) since it lets anyone who clones the repo know which environment
variables they need to set, without exposing yours. Worth mentioning in a README so a
collaborator (or future you, on a new machine) knows to copy it to `.env` and fill in
real values — `SETUP-NEW-LAPTOP.md` already covers this for the laptop-transfer case.
