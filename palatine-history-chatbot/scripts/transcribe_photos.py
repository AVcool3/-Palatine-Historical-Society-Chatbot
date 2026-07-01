"""Transcribe photos of documents into searchable text.

Walks data/my_documents/ (recursively) for image files and, for each one,
writes a "<image>.transcription.md" file next to it containing the transcribed
text. Already-transcribed images are skipped unless --force is given.

Usage:
    python scripts/transcribe_photos.py            # transcribe new photos
    python scripts/transcribe_photos.py --force    # re-transcribe everything
    python scripts/transcribe_photos.py path/to/one_image.jpg

Uses the configured AI backend (Claude/OpenAI vision, or local Tesseract OCR).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from src import ai_backend  # noqa: E402


def _iter_images(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in config.IMAGE_EXTENSIONS:
            yield path


def transcribe_one(image_path: Path, force: bool = False) -> bool:
    md_path = image_path.with_suffix(image_path.suffix + ".transcription.md")
    if md_path.exists() and not force:
        print(f"  · skip (already done): {image_path.name}")
        return False
    print(f"  … transcribing {image_path.name}")
    try:
        text = ai_backend.transcribe_image(image_path)
    except ai_backend.BackendError as exc:
        print(f"  ! {image_path.name}: {exc}", file=sys.stderr)
        return False
    import datetime as dt

    md_path.write_text(
        f"# Transcription of {image_path.name}\n\n"
        f"*Transcribed on {dt.date.today().isoformat()} via {config.AI_PROVIDER}.*\n\n"
        f"{text}\n",
        encoding="utf-8",
    )
    print(f"  ✓ wrote {md_path.name}")
    return True


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--force"]
    force = "--force" in sys.argv

    if args:
        targets = [Path(a) for a in args]
    else:
        targets = list(_iter_images(config.MY_DOCUMENTS_DIR))

    if not targets:
        print(f"No images found under {config.MY_DOCUMENTS_DIR}. "
              f"Drop photos into data/my_documents/photos/ and try again.")
        return

    print(f"Provider: {config.AI_PROVIDER} (configured: {ai_backend.is_configured()})")
    print(f"Found {len(targets)} image(s).")
    done = sum(transcribe_one(p, force=force) for p in targets)
    print(f"\nTranscribed {done} image(s). Rebuild the index:  python -m src.ingest")


if __name__ == "__main__":
    main()
