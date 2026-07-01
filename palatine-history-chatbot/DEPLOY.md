# Deploying the Palatine History Chatbot to a public website

This guide gets the chatbot online at a public `https://` URL using **Render**
(free tier). The repo is already configured — you mainly click through a few
screens and paste your API key.

---

## What you need

- The GitHub repo this project lives in (you have it).
- An **Anthropic API key** (starts with `sk-ant-…`) from
  https://console.anthropic.com — this powers the answers and photo
  transcription, and Anthropic bills you per use.
- A free **Render** account: https://render.com

---

## Deploy to Render (recommended, ~5 minutes)

1. Go to the **Render dashboard** → **New** → **Blueprint**.
2. **Connect** your GitHub account and pick this repository.
3. Render detects [`render.yaml`](./render.yaml) and shows a service named
   **palatine-history-chatbot**. Click **Apply**.
4. When prompted for the **`ANTHROPIC_API_KEY`** environment variable, paste
   your key. (It's stored as a secret — `sync: false` — and never committed.)
5. Click **Create / Deploy**. The build runs
   `pip install -r requirements.txt && python -m src.ingest`, then starts the
   app with gunicorn.
6. After a few minutes you get a public URL like
   **`https://palatine-history-chatbot.onrender.com`** — that's your website.
   Share it, and anyone can chat and upload photos.

Render redeploys automatically whenever you push to the repo
(`autoDeploy: true`).

### Free-plan caveats
- **Cold starts:** free services sleep after ~15 min idle and take ~30–60s to
  wake on the first visit. Upgrade to the **Starter** plan to stay always-on.
- **Uploads aren't permanent:** the free filesystem is wiped on each
  deploy/restart, so photos uploaded through the site (and their
  transcriptions) disappear on the next deploy. The built-in historical records
  always survive because they're stored in git. To keep uploads, use a paid
  plan and enable the persistent **disk** block that's commented at the bottom
  of `render.yaml`, then set `MY_DOCUMENTS_DIR=/var/data`.

---

## Since the site is public — cost & abuse protection

Every question and photo hits the paid AI backend, so a public URL means
strangers can run up your bill. This project ships with guardrails:

- **Per-IP rate limits** (via Flask-Limiter) — defaults:
  - Ask: `20/minute`, `200/day`
  - Upload/reindex: `5/minute`, `30/day`
  - Tune with the `RATE_LIMIT_ASK` / `RATE_LIMIT_UPLOAD` env vars.
- **Upload size cap:** `MAX_UPLOAD_MB` (default 10 MB).
- **Set a monthly spend limit** in the Anthropic console
  (Billing → Usage limits) as a hard backstop — strongly recommended.

If abuse becomes a problem, the easiest next step is to add a shared password;
ask and it can be added.

---

## Other hosts

The app is a standard WSGI app (`app:app`) with a `Procfile` and a `Dockerfile`,
so it also runs on:

- **Railway / Fly.io:** point them at the repo; they'll use the `Dockerfile` or
  `Procfile`. Set the same env vars (`ANTHROPIC_API_KEY`, `AI_PROVIDER=claude`).
- **Any VPS / your own server:**
  ```bash
  docker build -t palatine-chatbot palatine-history-chatbot
  docker run -p 8080:8080 -e ANTHROPIC_API_KEY=sk-ant-... palatine-chatbot
  # then put it behind nginx/Caddy for https
  ```

---

## Local production test

To run the exact production server locally before deploying:

```bash
cd palatine-history-chatbot
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python -m src.ingest
gunicorn app:app --bind 0.0.0.0:8080 --workers 2 --preload
# open http://127.0.0.1:8080
```
