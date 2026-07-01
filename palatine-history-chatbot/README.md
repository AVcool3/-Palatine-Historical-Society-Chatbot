# 🏛️ Palatine History Chatbot

A searchable chatbot for the history of **Palatine, Illinois**. It combines:

1. **Seeded historical records** — factual notes on Palatine's founding, timeline,
   the Clayson House, the Historical Society, and notable events
   (`data/historical_records/`).
2. **The Palatine Historical Society website** — a scraper that pulls every page
   from [palatinehistoricalsociety.com](https://palatinehistoricalsociety.com)
   into `data/historical_society/`.
3. **Your own documents** — drop anything into `data/my_documents/`
   (notes, PDFs, and **photos of documents that get transcribed automatically**).

Everything is indexed together, and you can chat with it in a **web app** or the
**command line**.

---

## Quick start

```bash
cd palatine-history-chatbot
python -m venv .venv && source .venv/bin/activate     # optional but recommended
pip install -r requirements.txt

cp .env.example .env         # then paste your ANTHROPIC_API_KEY into .env
python -m src.ingest         # build the search index from the seeded records

python app.py                # open http://127.0.0.1:5000
#   …or…
python cli.py                # chat in the terminal
```

> **No API key?** It still runs in **search-only mode** — you'll get the most
> relevant passages for any question (just not AI-written prose or photo
> transcription). Set `ANTHROPIC_API_KEY`, or `AI_PROVIDER=local` with
> [Ollama](https://ollama.com), for full features.

> **Want it on a public website?** See **[DEPLOY.md](./DEPLOY.md)** — one-click
> deploy to Render (free tier) with a `render.yaml`, plus a `Dockerfile` for
> any other host. Rate limiting and upload caps are built in for public use.

---

## Adding more information

### 1. Pull the Historical Society website
```bash
pip install requests beautifulsoup4
python scripts/scrape_historical_society.py
python -m src.ingest          # re-index
```
Saves every page to `data/historical_society/`. Run it from a normal internet
connection — some networks/proxies block the site.

### 2. Pull other online records
```bash
python scripts/fetch_records.py
# or a specific page:
python scripts/fetch_records.py https://en.wikipedia.org/wiki/Palatine,_Illinois
```

### 3. Add your own files
Put text, Markdown, or PDF files into **`data/my_documents/`**
(the stand-in folder for "all the files I want to add in"), then:
```bash
python -m src.ingest
```

### 4. Transcribe photos of documents
Drop photos into **`data/my_documents/photos/`** and run:
```bash
python scripts/transcribe_photos.py
python -m src.ingest
```
Each photo gets a `.transcription.md` next to it, which becomes searchable.
In the **web app** you can also just tap the 📷 button to upload + transcribe +
index a photo in one step.

---

## How it works

```
        data/historical_records/   data/historical_society/   data/my_documents/
                     \                     |                        /
                      \                    |                       /
                       ▼                   ▼                      ▼
                 src/ingest.py  →  chunk + build data/search_index.json
                                          │
                        src/retriever.py  │  (BM25 keyword search, offline)
                                          ▼
                 src/chatbot.py  →  retrieve top passages ─┐
                                                           ▼
                 src/ai_backend.py  →  Claude / OpenAI / local writes the answer
                                          │
                        app.py (web)  &  cli.py (terminal)
```

- **Retrieval** is a pure-Python BM25 ranker — no embedding service required, so
  search works fully offline.
- **Answers & photo transcription** go through a pluggable backend
  (`src/ai_backend.py`) so you can choose Claude, OpenAI, or a local model.
- **Photo transcription** uses vision models (Claude/OpenAI) or Tesseract OCR
  (local).

## Configuration

All settings live in `config.py` and can be overridden via `.env` — see
`.env.example`. Key ones: `AI_PROVIDER`, `ANTHROPIC_API_KEY`, `CLAUDE_MODEL`,
`TOP_K`, `PORT`.

## Project layout

```
palatine-history-chatbot/
├── app.py                  # Flask web app (chat + photo upload)
├── cli.py                  # command-line chat
├── config.py               # all settings
├── requirements.txt
├── .env.example
├── templates/index.html    # web UI
├── src/
│   ├── ingest.py           # load docs, chunk, build index
│   ├── retriever.py        # BM25 search
│   ├── chatbot.py          # retrieve + answer
│   └── ai_backend.py       # Claude / OpenAI / local providers
├── scripts/
│   ├── scrape_historical_society.py
│   ├── fetch_records.py
│   └── transcribe_photos.py
└── data/
    ├── historical_records/ # seeded facts (+ web fetches)
    ├── historical_society/ # scraped site (populated by the scraper)
    └── my_documents/       # YOUR files + photos/  ← stand-in drop folder
```

## A note on sources & accuracy

The seeded records in `data/historical_records/` were compiled from public
sources (Wikipedia, the Village of Palatine, and the Palatine Historical
Society) — see `data/historical_records/SOURCES.md`. Verify important dates and
figures against primary sources. Museum hours and contact details change over
time. When scraping the Historical Society's site heavily, please be respectful
of their bandwidth and terms.
