"""Fetch the explicitly approved public sources into their isolated corpora."""

from src.ingestion.web_source_sync import sync_catalog


if __name__ == "__main__":
    for path in sync_catalog():
        print(path)
