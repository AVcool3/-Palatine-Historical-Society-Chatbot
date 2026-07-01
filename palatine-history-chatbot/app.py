"""Flask web app for the Palatine History Chatbot.

    python app.py    # then open http://127.0.0.1:5000

Features:
  * Chat with the history knowledge base.
  * Upload a photo of a document; it is transcribed, saved into
    data/my_documents/photos/, indexed, and becomes searchable.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

from flask import Flask, jsonify, render_template, request

import config
from src import ai_backend
from src.chatbot import Chatbot
from src.ingest import build_index, save_index
from src.retriever import BM25Retriever

app = Flask(__name__)

# Cap upload size to protect the server (config.MAX_UPLOAD_MB, default 10 MB).
app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_MB * 1024 * 1024

# --- Rate limiting (protects a public deployment / your API bill) ----------
# Optional: only active if Flask-Limiter is installed. Limits are configurable
# via env (see config.py). On a public site this stops strangers from draining
# your AI credits or hammering the (expensive) upload+reindex endpoint.
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address

    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=[config.RATE_LIMIT_DEFAULT],
        storage_uri="memory://",
    )
except Exception:  # pragma: no cover - limiter is optional
    limiter = None


def _limit(rule: str):
    """Apply a rate limit decorator if Flask-Limiter is available, else no-op."""
    if limiter is not None:
        return limiter.limit(rule)
    return lambda f: f


# Lazily-built chatbot; rebuilt when new content is ingested.
_bot: Chatbot | None = None


def get_bot(rebuild: bool = False) -> Chatbot:
    global _bot
    if _bot is None or rebuild:
        if rebuild:
            chunks = build_index()
            save_index(chunks)
            _bot = Chatbot(BM25Retriever(chunks))
        else:
            _bot = Chatbot()
    return _bot


@app.route("/")
def index():
    return render_template(
        "index.html",
        provider=config.AI_PROVIDER,
        configured=ai_backend.is_configured(),
    )


@app.get("/healthz")
def healthz():
    """Lightweight health check for the hosting platform."""
    return jsonify({"status": "ok", "provider": config.AI_PROVIDER})


@app.post("/api/ask")
@_limit(config.RATE_LIMIT_ASK)
def api_ask():
    question = (request.json or {}).get("question", "").strip()
    if not question:
        return jsonify({"error": "Empty question"}), 400
    answer = get_bot().ask(question)
    return jsonify(
        {
            "answer": answer.text,
            "used_ai": answer.used_ai,
            "sources": [
                {"n": i + 1, "source": r.chunk.source, "title": r.chunk.title, "doc_id": r.chunk.doc_id}
                for i, r in enumerate(answer.sources)
            ],
        }
    )


@app.post("/api/upload")
@_limit(config.RATE_LIMIT_UPLOAD)
def api_upload():
    """Accept an image, transcribe it, save transcription, and re-index."""
    if "photo" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file = request.files["photo"]
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400
    ext = Path(file.filename).suffix.lower()
    if ext not in config.IMAGE_EXTENSIONS:
        return jsonify({"error": f"Unsupported image type: {ext}"}), 400

    photos_dir = config.MY_DOCUMENTS_DIR / "photos"
    photos_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _dt.datetime.now().strftime("%Y%m%d_%H%M%S_") + Path(file.filename).name
    image_path = photos_dir / safe_name
    file.save(image_path)

    try:
        transcription = ai_backend.transcribe_image(image_path)
    except ai_backend.BackendError as exc:
        return jsonify({"error": str(exc), "saved_as": safe_name}), 502

    md_path = image_path.with_suffix(image_path.suffix + ".transcription.md")
    md_path.write_text(
        f"# Transcription of {safe_name}\n\n"
        f"*Transcribed on {_dt.date.today().isoformat()} via {config.AI_PROVIDER}.*\n\n"
        f"{transcription}\n",
        encoding="utf-8",
    )

    # Re-index so the new transcription is immediately searchable.
    get_bot(rebuild=True)

    return jsonify(
        {
            "saved_as": safe_name,
            "transcription": transcription,
            "transcription_file": str(md_path.relative_to(config.ROOT)),
        }
    )


@app.post("/api/reindex")
@_limit(config.RATE_LIMIT_UPLOAD)
def api_reindex():
    get_bot(rebuild=True)
    return jsonify({"status": "ok"})


@app.errorhandler(413)
def too_large(_):
    return jsonify({"error": f"File too large (max {config.MAX_UPLOAD_MB} MB)."}), 413


@app.errorhandler(429)
def rate_limited(_):
    return jsonify({"error": "Too many requests — please slow down and try again shortly."}), 429


# Warm the index at import time so it's ready under a WSGI server (gunicorn),
# where the __main__ block below does not run.
get_bot()


if __name__ == "__main__":
    print(f"Palatine History Chatbot → http://{config.HOST}:{config.PORT}")
    print(f"AI provider: {config.AI_PROVIDER} (configured: {ai_backend.is_configured()})")
    app.run(host=config.HOST, port=config.PORT, debug=False)
