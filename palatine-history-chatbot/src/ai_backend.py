"""Provider-agnostic AI backend.

Supports three providers, selected by config.AI_PROVIDER:

  * "claude"  -> Anthropic Claude (chat + vision transcription)
  * "openai"  -> OpenAI GPT (chat + vision transcription)
  * "local"   -> Ollama-compatible local model (chat) + Tesseract OCR (photos)

Each provider is imported lazily so you only need the library for the one you
actually use. If no provider is configured/available, chat falls back to simply
returning the retrieved passages, and transcription raises a clear error.
"""
from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Optional

import config


class BackendError(RuntimeError):
    """Raised when a backend is asked to do something it cannot."""


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------
def is_configured() -> bool:
    """True if the selected provider has the credentials it needs."""
    if config.AI_PROVIDER == "claude":
        return bool(config.ANTHROPIC_API_KEY)
    if config.AI_PROVIDER == "openai":
        return bool(config.OPENAI_API_KEY)
    if config.AI_PROVIDER == "gemini":
        return bool(config.GEMINI_API_KEY)
    if config.AI_PROVIDER == "local":
        return True  # assume a local server is running
    return False


def generate_answer(system_prompt: str, user_prompt: str) -> str:
    """Return a chat completion for the given prompts."""
    provider = config.AI_PROVIDER
    if provider == "claude":
        return _claude_chat(system_prompt, user_prompt)
    if provider == "openai":
        return _openai_chat(system_prompt, user_prompt)
    if provider == "gemini":
        return _gemini_chat(system_prompt, user_prompt)
    if provider == "local":
        return _local_chat(system_prompt, user_prompt)
    raise BackendError(f"Unknown AI_PROVIDER: {provider!r}")


def transcribe_image(image_path: Path, instructions: Optional[str] = None) -> str:
    """Transcribe the text/content of an image file to plain text."""
    provider = config.AI_PROVIDER
    prompt = instructions or (
        "Transcribe ALL text visible in this image exactly as written, "
        "preserving line breaks, headings, dates, and names. If the image is a "
        "historical document, letter, newspaper clipping, or photo caption, "
        "also add a brief 1-2 sentence description of what the image shows. "
        "If some text is illegible, mark it as [illegible]. Do not invent text."
    )
    if provider == "claude":
        return _claude_vision(image_path, prompt)
    if provider == "openai":
        return _openai_vision(image_path, prompt)
    if provider == "gemini":
        return _gemini_vision(image_path, prompt)
    if provider == "local":
        return _tesseract_ocr(image_path)
    raise BackendError(f"Unknown AI_PROVIDER: {provider!r}")


# --------------------------------------------------------------------------
# Claude
# --------------------------------------------------------------------------
def _claude_client():
    if not config.ANTHROPIC_API_KEY:
        raise BackendError(
            "ANTHROPIC_API_KEY is not set. Add it to your environment or .env, "
            "or set AI_PROVIDER=local to run without a paid API."
        )
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover
        raise BackendError("The 'anthropic' package is not installed. Run: pip install anthropic") from exc
    return anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)


def _claude_chat(system_prompt: str, user_prompt: str) -> str:
    client = _claude_client()
    resp = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return "".join(block.text for block in resp.content if getattr(block, "type", "") == "text").strip()


def _claude_vision(image_path: Path, prompt: str) -> str:
    client = _claude_client()
    media_type, data = _encode_image(image_path)
    resp = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=2048,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": data},
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )
    return "".join(block.text for block in resp.content if getattr(block, "type", "") == "text").strip()


# --------------------------------------------------------------------------
# OpenAI
# --------------------------------------------------------------------------
def _openai_client():
    if not config.OPENAI_API_KEY:
        raise BackendError("OPENAI_API_KEY is not set.")
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover
        raise BackendError("The 'openai' package is not installed. Run: pip install openai") from exc
    return OpenAI(api_key=config.OPENAI_API_KEY)


def _openai_chat(system_prompt: str, user_prompt: str) -> str:
    client = _openai_client()
    resp = client.chat.completions.create(
        model=config.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return (resp.choices[0].message.content or "").strip()


def _openai_vision(image_path: Path, prompt: str) -> str:
    client = _openai_client()
    media_type, data = _encode_image(image_path)
    resp = client.chat.completions.create(
        model=config.OPENAI_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{data}"}},
                ],
            }
        ],
    )
    return (resp.choices[0].message.content or "").strip()


# --------------------------------------------------------------------------
# Google Gemini (free tier: chat + vision transcription)
# --------------------------------------------------------------------------
def _gemini_client():
    if not config.GEMINI_API_KEY:
        raise BackendError(
            "GEMINI_API_KEY is not set. Get a free key at "
            "https://aistudio.google.com/apikey and add it to your environment "
            "or .env (no credit card required)."
        )
    try:
        from google import genai
    except Exception as exc:  # not installed, or a broken transitive dep
        raise BackendError(
            "Could not load the 'google-genai' package. Run: pip install google-genai"
        ) from exc
    return genai.Client(api_key=config.GEMINI_API_KEY)


def _gemini_chat(system_prompt: str, user_prompt: str) -> str:
    from google.genai import types

    client = _gemini_client()
    try:
        resp = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=1024,
            ),
        )
    except Exception as exc:  # quota exhausted, network, etc. -> graceful fallback
        raise BackendError(_gemini_error_hint(exc)) from exc
    return (resp.text or "").strip()


def _gemini_vision(image_path: Path, prompt: str) -> str:
    from google.genai import types

    client = _gemini_client()
    media_type, raw = _image_bytes(image_path)
    try:
        resp = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=[
                types.Part.from_bytes(data=raw, mime_type=media_type),
                prompt,
            ],
            config=types.GenerateContentConfig(max_output_tokens=2048),
        )
    except Exception as exc:
        raise BackendError(_gemini_error_hint(exc)) from exc
    return (resp.text or "").strip()


def _gemini_error_hint(exc: Exception) -> str:
    msg = str(exc)
    if "429" in msg or "quota" in msg.lower() or "RESOURCE_EXHAUSTED" in msg:
        return ("Gemini free-tier limit reached for now — try again later "
                "(the site keeps working in search mode meanwhile).")
    return f"Gemini request failed: {msg}"


# --------------------------------------------------------------------------
# Local (Ollama chat + Tesseract OCR)
# --------------------------------------------------------------------------
def _local_chat(system_prompt: str, user_prompt: str) -> str:
    try:
        import requests
    except ImportError as exc:  # pragma: no cover
        raise BackendError("The 'requests' package is required for the local backend.") from exc
    url = f"{config.LOCAL_BASE_URL.rstrip('/')}/api/chat"
    payload = {
        "model": config.LOCAL_MODEL,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    try:
        r = requests.post(url, json=payload, timeout=120)
        r.raise_for_status()
    except Exception as exc:
        raise BackendError(
            f"Could not reach local model at {url}. Is Ollama running "
            f"(`ollama serve`) and is model '{config.LOCAL_MODEL}' pulled?"
        ) from exc
    return r.json().get("message", {}).get("content", "").strip()


def _tesseract_ocr(image_path: Path) -> str:
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:  # pragma: no cover
        raise BackendError(
            "Local transcription needs 'pytesseract' and 'Pillow' plus the "
            "Tesseract binary. Run: pip install pytesseract pillow  and install "
            "tesseract-ocr for your OS."
        ) from exc
    return pytesseract.image_to_string(Image.open(image_path)).strip()


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _image_bytes(image_path: Path) -> tuple[str, bytes]:
    """Return (media_type, raw_bytes) for a vision API, converting formats the
    vision models don't accept (HEIC/TIFF/BMP) to PNG."""
    media_type = mimetypes.guess_type(str(image_path))[0] or "image/jpeg"
    if media_type not in {"image/jpeg", "image/png", "image/gif", "image/webp"}:
        return _convert_to_png(image_path)
    return media_type, image_path.read_bytes()


def _encode_image(image_path: Path) -> tuple[str, str]:
    """Return (media_type, base64_data) for APIs that want base64."""
    media_type, raw = _image_bytes(image_path)
    return media_type, base64.standard_b64encode(raw).decode("ascii")


def _convert_to_png(image_path: Path) -> tuple[str, bytes]:
    try:
        from io import BytesIO

        from PIL import Image

        try:  # enable HEIC support if pillow-heif is present
            import pillow_heif  # type: ignore

            pillow_heif.register_heif_opener()
        except Exception:
            pass

        img = Image.open(image_path).convert("RGB")
        buf = BytesIO()
        img.save(buf, format="PNG")
        return "image/png", buf.getvalue()
    except Exception as exc:
        raise BackendError(
            f"Could not read/convert image {image_path.name}. Install Pillow "
            f"(and pillow-heif for HEIC) to support this format."
        ) from exc
