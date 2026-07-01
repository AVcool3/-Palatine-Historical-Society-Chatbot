"""Crawl palatinehistoricalsociety.com and save every page as Markdown into
data/historical_society/, so the chatbot can search "every bit of information"
from the site.

Run from the project root:

    python scripts/scrape_historical_society.py

Requires:  pip install requests beautifulsoup4

Notes:
  * Stays strictly within the historical society's domain.
  * Polite: sends a descriptive User-Agent and waits SCRAPER_DELAY_SECONDS
    between requests. For heavy scraping, ask the Society's permission.
  * If your network blocks the site (e.g. a corporate/agent proxy), run this
    from a normal home/office connection.
"""
from __future__ import annotations

import re
import sys
import time
from collections import deque
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag

# Make the project root importable when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402


def _require_deps():
    try:
        import requests  # noqa: F401
        from bs4 import BeautifulSoup  # noqa: F401
    except ImportError:
        print("This scraper needs: pip install requests beautifulsoup4", file=sys.stderr)
        sys.exit(1)


def _slug_for(url: str) -> str:
    path = urlparse(url).path.strip("/")
    if not path:
        return "index"
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "_", path).strip("_")
    return slug or "index"


def _html_to_markdown(html: str, url: str) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "form", "noscript"]):
        tag.decompose()

    title = (soup.title.get_text(strip=True) if soup.title else "") or _slug_for(url)

    # Prefer the main content region if the theme marks one.
    main = soup.find("main") or soup.find("article") or soup.find(id="content") or soup.body or soup

    lines = [f"# {title}", "", f"*Source: {url}*", ""]
    for el in main.find_all(["h1", "h2", "h3", "h4", "li", "p", "blockquote"]):
        text = el.get_text(" ", strip=True)
        if not text:
            continue
        name = el.name
        if name in ("h1", "h2"):
            lines.append(f"\n## {text}\n")
        elif name in ("h3", "h4"):
            lines.append(f"\n### {text}\n")
        elif name == "li":
            lines.append(f"- {text}")
        elif name == "blockquote":
            lines.append(f"> {text}")
        else:
            lines.append(text + "\n")
    # Collapse excess blank lines.
    md = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip() + "\n"
    return md


def crawl():
    _require_deps()
    import requests
    from bs4 import BeautifulSoup

    base = config.HISTORICAL_SOCIETY_URL.rstrip("/")
    domain = urlparse(base).netloc
    out_dir = config.HISTORICAL_SOCIETY_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update({"User-Agent": config.SCRAPER_USER_AGENT})

    seen: set[str] = set()
    queue: deque[str] = deque([base + "/"])
    saved = 0

    print(f"Crawling {base} (max {config.SCRAPER_MAX_PAGES} pages)…")
    while queue and saved < config.SCRAPER_MAX_PAGES:
        url = urldefrag(queue.popleft())[0]
        if url in seen:
            continue
        seen.add(url)
        try:
            resp = session.get(url, timeout=30)
        except Exception as exc:
            print(f"  ! {url} -> {exc}", file=sys.stderr)
            continue
        if resp.status_code != 200 or "text/html" not in resp.headers.get("Content-Type", ""):
            print(f"  - skip {url} (status {resp.status_code})")
            continue

        md = _html_to_markdown(resp.text, url)
        out_path = out_dir / f"{_slug_for(url)}.md"
        out_path.write_text(md, encoding="utf-8")
        saved += 1
        print(f"  ✓ [{saved}] {url} -> {out_path.name}")

        # Enqueue same-domain links.
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", href=True):
            link = urldefrag(urljoin(url, a["href"]))[0]
            p = urlparse(link)
            if p.netloc == domain and p.scheme in ("http", "https") and link not in seen:
                # Skip obvious non-content links.
                if any(link.lower().endswith(ext) for ext in (".jpg", ".png", ".pdf", ".zip", ".gif")):
                    continue
                queue.append(link)

        time.sleep(config.SCRAPER_DELAY_SECONDS)

    print(f"\nDone. Saved {saved} pages to {out_dir}.")
    print("Now rebuild the search index:  python -m src.ingest")


if __name__ == "__main__":
    crawl()
