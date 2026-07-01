"""Fetch historical records from a list of online sources and save them as
Markdown into data/historical_records/.

Edit the SOURCES list below (or pass URLs on the command line) and run:

    python scripts/fetch_records.py
    python scripts/fetch_records.py https://en.wikipedia.org/wiki/Palatine,_Illinois

Requires:  pip install requests beautifulsoup4

This complements the pre-seeded records already in data/historical_records/.
Run it from a normal internet connection (some proxies block these hosts).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402

# Good public starting points for Palatine, IL history.
SOURCES = [
    "https://en.wikipedia.org/wiki/Palatine,_Illinois",
    "https://en.wikipedia.org/wiki/George_Clayson_House",
    "https://en.wikipedia.org/wiki/Brown's_Chicken_massacre",
]


def _slug(url: str) -> str:
    p = urlparse(url)
    base = (p.netloc + p.path).strip("/")
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", base).strip("_")[:120] or "record"


def fetch(url: str) -> None:
    import requests
    from bs4 import BeautifulSoup

    session = requests.Session()
    session.headers.update({"User-Agent": config.SCRAPER_USER_AGENT})
    resp = session.get(url, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "table", "sup", "nav", "footer"]):
        tag.decompose()
    title = (soup.title.get_text(strip=True) if soup.title else url)
    main = soup.find(id="mw-content-text") or soup.find("main") or soup.find("article") or soup.body or soup

    parts = [f"# {title}", "", f"*Source: {url}*", ""]
    for el in main.find_all(["h2", "h3", "p", "li"]):
        text = el.get_text(" ", strip=True)
        if not text:
            continue
        if el.name in ("h2", "h3"):
            parts.append(f"\n## {text}\n")
        elif el.name == "li":
            parts.append(f"- {text}")
        else:
            parts.append(text + "\n")
    md = re.sub(r"\n{3,}", "\n\n", "\n".join(parts)).strip() + "\n"

    out = config.HISTORICAL_RECORDS_DIR / f"web_{_slug(url)}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    print(f"  ✓ {url} -> {out.name}")


def main() -> None:
    try:
        import requests  # noqa: F401
        from bs4 import BeautifulSoup  # noqa: F401
    except ImportError:
        print("Needs: pip install requests beautifulsoup4", file=sys.stderr)
        sys.exit(1)

    urls = sys.argv[1:] or SOURCES
    print(f"Fetching {len(urls)} record(s)…")
    for url in urls:
        try:
            fetch(url)
        except Exception as exc:
            print(f"  ! {url} -> {exc}", file=sys.stderr)
    print("\nDone. Rebuild the index:  python -m src.ingest")


if __name__ == "__main__":
    main()
