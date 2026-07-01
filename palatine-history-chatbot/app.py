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


@app.post("/api/ask")
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
def api_reindex():
    get_bot(rebuild=True)
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    print(f"Palatine History Chatbot → http://{config.HOST}:{config.PORT}")
    print(f"AI provider: {config.AI_PROVIDER} (configured: {ai_backend.is_configured()})")
    get_bot()  # warm the index at startup
    app.run(host=config.HOST, port=config.PORT, debug=False)
