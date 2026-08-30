# Deploying on an Oracle Cloud Always Free VM (persistent, $0)

This gives you a real always-on server with a persistent disk: **nothing resets** —
generated podcasts, student episode history, and engagement data all accumulate and
survive restarts and reboots. It's genuinely free (Oracle's "Always Free" tier, not a
time-limited trial), but it's more setup than a Hugging Face Space. Budget ~30–45 minutes
the first time.

You run everything with Docker via the repo's `Dockerfile` + `docker-compose.yml`. The app
is one container; a host folder (`./data`) is mounted as its storage, which is what makes
data persist.

> **Still true regardless of host:** ElevenLabs is the real cost. Its free tier is
> ~10,000 characters/month (≈ two 5-minute episodes). Size a plan to your use and set the
> per-student generation limit on the admin dashboard.

---

## Step 0 — Prepare your course content first (on your laptop)

Do this **before** deploying so your course ships with the server. Load your PDF into the
seed data:

```powershell
cd c:\Users\ELITE\Downloads\podcast-generator\backend
.\.venv\Scripts\python -m app.build_course "C:\path\to\your-course.pdf"
```

That writes your course into `backend/app/seed/data/`. It will be seeded automatically the
first time the server boots. (You can update it later — see the end of this doc.)

## Step 1 — Create the VM

1. Sign up at <https://www.oracle.com/cloud/free/> (needs a card for identity; the Always
   Free resources never charge).
2. In the console: **Compute → Instances → Create instance**.
   - **Image**: Ubuntu 22.04.
   - **Shape**: click **Change shape → Ampere (Arm)** and pick **VM.Standard.A1.Flex**.
     Give it **2 OCPUs and 12 GB RAM** (well within Always Free, which allows up to 4
     OCPUs / 24 GB). **Do not use the tiny AMD "Micro" shape (1 GB RAM)** — this app loads
     an embedding model and will run out of memory on 1 GB.
   - **SSH keys**: let it generate a key pair and **download the private key** (you'll need
     it to log in). On Windows, save it somewhere like `C:\Users\ELITE\.ssh\oracle.key`.
   - Create. Note the instance's **public IP address** once it's running.

## Step 2 — Open the firewall (BOTH layers — this is the #1 gotcha)

Oracle blocks inbound traffic in **two** places. You must open **both**, or the site will
look dead even though the app is running.

**a) Cloud firewall (in the console):**
- Go to your instance → click its **Virtual Cloud Network** → **Security Lists** → the
  default one → **Add Ingress Rule**:
  - Source CIDR: `0.0.0.0/0`
  - IP Protocol: `TCP`
  - Destination Port Range: `80`
  - (Add another for `443` if you set up HTTPS later.)

**b) The VM's own firewall (over SSH — see Step 3 for connecting):** Oracle's Ubuntu image
ships with restrictive `iptables` rules. Add and persist a rule for port 80:
```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo netfilter-persistent save
```

## Step 3 — Connect and install Docker

SSH in from your laptop (PowerShell), using the private key you downloaded:
```powershell
ssh -i C:\Users\ELITE\.ssh\oracle.key ubuntu@YOUR_SERVER_IP
```
Then, on the VM, install Docker:
```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker    # apply the group without logging out
```

## Step 4 — Get the code onto the VM

Two options:

- **git** (if you've pushed this project to GitHub/GitLab):
  ```bash
  git clone <your-repo-url> podcast-generator
  cd podcast-generator
  ```
- **scp** from your laptop (run this in PowerShell, not on the VM), copying your local
  project up (excluding the heavy/unneeded folders):
  ```powershell
  scp -i C:\Users\ELITE\.ssh\oracle.key -r `
    c:\Users\ELITE\Downloads\podcast-generator `
    ubuntu@YOUR_SERVER_IP:/home/ubuntu/podcast-generator
  ```
  (If it's slow, delete `backend/.venv`, `frontend/node_modules`, and `backend/storage`
  locally first — they're rebuilt in the container and aren't needed on the server.)

## Step 5 — Add your secrets

On the VM, in the project folder:
```bash
cp .env.production.example .env.production
nano .env.production      # fill in real values, then Ctrl-O, Enter, Ctrl-X to save
```
Set `ELEVENLABS_API_KEY`, `GEMINI_API_KEY`, `SESSION_SECRET`, `ADMIN_TOKEN`,
`ELEVENLABS_VOICE_IDS`, and `CORS_ORIGINS=http://YOUR_SERVER_IP`.

## Step 6 — Build and run

```bash
docker compose up -d --build
```
The first build takes several minutes (installs ffmpeg, Python deps, and pre-downloads the
embedding model). Watch logs with:
```bash
docker compose logs -f
```
When you see `Application startup complete.` and the seed line, it's live.

## Step 7 — Open it

Visit **http://YOUR_SERVER_IP/** in a browser. You should see the login page. Log in with a
roster account (see `backend/app/seed/data/roster.csv`), or the admin dashboard at
`http://YOUR_SERVER_IP/#/admin` with your `ADMIN_TOKEN`.

Send your professor that URL plus a roster email/code. Because the disk is persistent,
everything they and their students generate stays put across restarts and reboots.

---

## Everyday operations

- **See logs:** `docker compose logs -f`
- **Restart:** `docker compose restart`
- **Stop / start:** `docker compose down` / `docker compose up -d`
- **Update the app after changing code:** `git pull` (or re-`scp`), then
  `docker compose up -d --build`. Your `./data` (database + audio) is untouched by rebuilds.
- **Back up everything:** the `./data` folder is your whole world — copy it somewhere safe
  (`tar czf backup.tgz data`).

## Updating course content on the running server

Because the disk persists, the seed only runs on the very first boot (when the database is
empty). To apply course-content changes later **without wiping episodes/engagement**,
update the seed data and re-run the seed inside the container:
```bash
# after editing seed data or running build_course and copying the new files up:
docker compose exec app python -m app.seed.seed_data
```
This upserts changed/new topics (regenerating only those topics' cached podcasts) and
leaves students, episodes, and engagement intact.

## Adding HTTPS (recommended before real use)

Over plain HTTP, login tokens travel unencrypted. For a quick professor demo on the IP
that's a low risk, but for real use add TLS. Easiest options:

- **Caddy + a domain** — point a domain at the server's IP, then run Caddy as a reverse
  proxy in front of the app; it fetches and renews a free Let's Encrypt certificate
  automatically. (Ask me and I'll add a Caddy service to `docker-compose.yml`.)
- **Cloudflare Tunnel** — install `cloudflared` on the VM; it gives you an HTTPS URL without
  opening ports or managing certificates. Good if you don't have a domain handy.

---

## If you'd rather have a quick, zero-VM option instead

`DEPLOY.md` covers **Hugging Face Spaces** — no VM, builds on their servers, live in
minutes — at the cost of an *ephemeral* disk (generated podcasts and engagement reset on
each rebuild/sleep). Good for a fast look; this Oracle path is the one that persists.
