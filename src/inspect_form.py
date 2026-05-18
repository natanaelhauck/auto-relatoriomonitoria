"""Inspect Google Forms HTML and list entry IDs."""

from __future__ import annotations

import os
import re
from html import unescape

import requests
from dotenv import load_dotenv

from src.forms_client import FORM_VIEW_URL

ENTRY_PATTERN = re.compile(r"entry\.\d+(?:_[a-z]+)?")
TAG_PATTERN = re.compile(r"<[^>]+>")


def inspect_form() -> int:
    """Download the configured Google Form HTML and print discovered entries."""
    load_dotenv()

    form_url = os.getenv("FORM_URL", FORM_VIEW_URL).strip() or FORM_VIEW_URL
    response = requests.get(form_url, timeout=30)
    response.raise_for_status()

    html = response.text
    entries = sorted(set(ENTRY_PATTERN.findall(html)))

    print(f"FORM_URL: {form_url}")
    print(f"Entries encontrados: {len(entries)}")

    for entry in entries:
        print(f"- {entry}: {_nearby_text(html, entry)}")

    return 0


def _nearby_text(html: str, entry: str, window: int = 500) -> str:
    position = html.find(entry)
    if position == -1:
        return ""

    start = max(0, position - window)
    end = min(len(html), position + len(entry) + window)
    snippet = html[start:end]
    text = unescape(TAG_PATTERN.sub(" ", snippet))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:240]


def main() -> None:
    """CLI entry point."""
    raise SystemExit(inspect_form())


if __name__ == "__main__":
    main()
