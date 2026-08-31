# Publishing this project to GitHub (via SSH)

This walks through taking the project from "just a folder on my laptop" to a real GitHub
repository, authenticated with an SSH key instead of a password/token. Verified against
this machine's actual setup: Git 2.55.0 and OpenSSH 10.3 are installed; the GitHub CLI
(`gh`) is **not**, so this uses the plain `git` + github.com website flow.

This assumes you already have an SSH key set up. If it's already added to your GitHub
account, skip straight to step 1.

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

## 1. Confirm your SSH key is working with GitHub

```powershell
ssh -T git@github.com
```

A successful result looks like:
```
Hi <your-username>! You've successfully authenticated, but GitHub does not provide shell access.
```
That message (yes, even though it says it's not providing "shell access") means you're
good to go — skip to step 2.

If instead you get `Permission denied (publickey)`, your key isn't registered with
GitHub yet (or isn't loaded in your agent). To fix:

1. Print your public key:
   ```powershell
   Get-Content "$env:USERPROFILE\.ssh\id_ed25519.pub"
   ```
   (adjust the filename if your key has a different name, e.g. `id_rsa.pub`)
2. Go to **[github.com/settings/keys](https://github.com/settings/keys)** → **New SSH key**.
3. Paste it in, give it a title identifying this machine, and save.
4. Make sure it's loaded in your agent: `ssh-add -l` should list it. If not:
   ```powershell
   ssh-add "$env:USERPROFILE\.ssh\id_ed25519"
   ```
5. Re-run the `ssh -T git@github.com` test above.

---

## 2. Initialize the repository

Open PowerShell in the project root (`podcast-generator-transfer`) and run:

```powershell
git init
git branch -M main
```

---

## 3. Stage everything and make the first commit

```powershell
git add .
git status
```

**Before committing**, read through the `git status` output. You're looking for exactly
one thing: **`.env` should NOT appear** in the list of files to be committed. If it does
appear, stop and fix that before proceeding rather than commit real secrets to git
history.

Once that looks right:

```powershell
git commit -m "Initial commit"
```

---

## 4. Create the repository on GitHub

1. Go to [github.com/new](https://github.com/new).
2. Repository name: e.g. `podcast-generator`.
3. **Do not** check "Add a README", "Add .gitignore", or "Choose a license" — the repo
   needs to start empty so it doesn't conflict with the commit you already made locally.
4. Choose **Private** or **Public** — private if this should only be visible to people
   you explicitly invite (e.g. your professor as a collaborator), public if anyone should
   see it. Either is fine; no real student data is ever in the repo (that stays local in
   the gitignored `backend/storage/`).
5. Click **Create repository**.

---

## 5. Connect your local repo to GitHub over SSH, and push

Use the **SSH** URL GitHub shows you (starts with `git@github.com:`, not `https://`):

```powershell
git remote add origin git@github.com:<your-username>/podcast-generator.git
git push -u origin main
```

With your key already set up, this pushes straight through with no password/token
prompt.

Once it finishes, refresh the GitHub page — your files should be there.

---

## 6. Verify nothing sensitive made it up

As a final sanity check, search the pushed repo on GitHub's website (use the code search
bar) for `GEMINI_API_KEY` or `ELEVENLABS_API_KEY`. Nothing should turn up, since `.env`
was never staged. If something *did* leak, don't just delete it and push again — a
leaked key needs to be **rotated** (generate a new one from ElevenLabs/Gemini and update
your local `.env`), because the old one remains visible in git history even after a
later commit removes the file.

---

## 7. Keeping it updated later

Every time you make changes you want to publish:

```powershell
git add .
git commit -m "Describe what changed"
git push
```

No re-authentication needed — your SSH key keeps handling it.

---

## Optional: using the GitHub CLI instead

If you install `gh` (`winget install --id GitHub.cli`) at some point, steps 4–5 collapse
into one command run from the project root (it can use either SSH or HTTPS under the
hood, based on your `gh` config):

```powershell
gh repo create podcast-generator --private --source=. --remote=origin --push
```

---

## One thing to consider before making this public: `.env.production.example`

The project already has `.env.production.example` — a template with placeholder values
instead of real keys. This file **is safe to commit** (it's not in `.gitignore`, and it
should stay that way) since it lets anyone who clones the repo know which environment
variables they need to set, without exposing yours. Worth mentioning in a README so a
collaborator (or future you, on a new machine) knows to copy it to `.env` and fill in
real values — `SETUP-NEW-LAPTOP.md` already covers this for the laptop-transfer case.
