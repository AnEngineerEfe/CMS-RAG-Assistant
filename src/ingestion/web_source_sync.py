"""Synchronise explicitly approved public web sources into the RAG corpus.

This module intentionally does not crawl arbitrary links.  Every URL must be
reviewed in ``data/source_catalog.json`` first, which keeps provenance and the
scope of the knowledge base auditable.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

import requests

from src.config import DATA_DIR, RAW_DATA_PATH


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "nav", "footer", "noscript"}:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "nav", "footer", "noscript"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            cleaned = " ".join(unescape(data).split())
            if cleaned:
                self.parts.append(cleaned)


def sync_catalog(catalog_path: Path = DATA_DIR / "source_catalog.json") -> list[Path]:
    """Download approved HTML pages as provenance-preserving Markdown files."""
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    saved: list[Path] = []
    session = requests.Session()
    session.headers["User-Agent"] = "CMS-RAG-Assistant/1.0 (approved research ingestion)"

    failures: list[str] = []
    for source in catalog["sources"]:
        url = source["url"]
        if urlparse(url).scheme != "https":
            raise ValueError(f"Only HTTPS sources are permitted: {url}")
        try:
            if url.lower().endswith(".pdf"):
                # PDFs are kept as binary source material so page citations survive.
                response = session.get(url, timeout=30)
                response.raise_for_status()
                destination = RAW_DATA_PATH / source["collection"] / f"{source['id']}.pdf"
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(response.content)
                saved.append(destination)
                continue

            response = session.get(url, timeout=30)
            response.raise_for_status()
            parser = _TextExtractor()
            parser.feed(response.text)
            body = re.sub(r"\n{3,}", "\n\n", "\n\n".join(parser.parts))
            destination = RAW_DATA_PATH / source["collection"] / f"{source['id']}.md"
            destination.parent.mkdir(parents=True, exist_ok=True)
            front_matter = (
                "---\n"
                f"source_id: {source['id']}\ncollection: {source['collection']}\n"
                f"authority: {source['authority']}\nsource_url: {url}\n"
                f"retrieved_at: {datetime.now(UTC).isoformat()}\n---\n\n"
            )
            destination.write_text(front_matter + body, encoding="utf-8")
            saved.append(destination)
        except requests.RequestException as error:
            failures.append(f"{source['id']}: {error}")

    if failures:
        (RAW_DATA_PATH / "sync_failures.log").parent.mkdir(parents=True, exist_ok=True)
        (RAW_DATA_PATH / "sync_failures.log").write_text("\n".join(failures), encoding="utf-8")
    return saved
