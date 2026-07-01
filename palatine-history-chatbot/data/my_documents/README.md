# Your own documents (drop-in folder)

**This folder is the stand-in for "all the files I want to add in."**

Put anything you want the chatbot to know about here. When you run the chatbot
(or `python -m src.ingest`), everything in this folder is indexed alongside the
scraped historical records.

## What you can add

- **Text & Markdown** (`.txt`, `.md`) — notes, transcripts, articles.
- **PDFs** (`.pdf`) — scanned documents, newsletters, books. Text is extracted
  automatically (see `requirements.txt` for the optional PDF library).
- **Photos of documents / letters / newspaper clippings** (`.jpg`, `.png`,
  `.heic`, `.tif`) — drop them in the `photos/` subfolder, then run
  `python scripts/transcribe_photos.py`. Each photo is transcribed into a `.md`
  file placed right next to it, and the transcription is then indexed and
  searchable.

## Folder layout

```
my_documents/
├── README.md                 <- this file
├── photos/                   <- put photos here to be transcribed
│   └── sample_clipping.txt   <- example describing a photo you'd upload
├── family_notes_example.md   <- example of your own written note
└── (add your own files here)
```

## After adding files

Re-run the ingest so the new content is searchable:

```bash
python -m src.ingest          # rebuild the search index
python scripts/transcribe_photos.py   # (if you added photos)
```

Then ask the chatbot about them.
