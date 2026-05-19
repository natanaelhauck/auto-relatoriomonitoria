"""Inspect Google Forms HTML and list entry IDs."""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from html import unescape
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from src.forms_client import FORM_VIEW_URL

DEBUG_HTML_PATH = Path("data/form_debug.html")
ENTRIES_JSON_PATH = Path("data/form_entries_found.json")

ENTRY_PATTERN = re.compile(r"entry\.(\d+)(?:_[a-z]+)?")
ENTRY_IN_ARRAY_PATTERN = re.compile(r'\[\[\s*"entry\.(\d+)"')
ENTRY_NAME_PATTERN = re.compile(r'name=["\']entry\.(\d+)(?:_[a-z]+)?["\']')
FB_PUBLIC_LOAD_DATA_PATTERN = re.compile(
    r"var\s+FB_PUBLIC_LOAD_DATA_\s*=\s*(\[.*?\]);\s*</script>",
    re.DOTALL,
)
TAG_PATTERN = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class FormEntry:
    """Entry discovered in the Google Forms HTML."""

    probable_field: str
    entry_id: str
    nearby_text: str


def inspect_form() -> int:
    """Download the configured Google Form HTML and print discovered entries."""
    load_dotenv()

    form_url = os.getenv("FORM_URL", FORM_VIEW_URL).strip() or FORM_VIEW_URL
    html = _download_form_html(form_url)

    DEBUG_HTML_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEBUG_HTML_PATH.write_text(html, encoding="utf-8")

    entries = _extract_entries(html)
    ENTRIES_JSON_PATH.write_text(
        json.dumps([asdict(entry) for entry in entries], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"FORM_URL: {form_url}")
    print(f"HTML salvo em: {DEBUG_HTML_PATH}")
    print(f"JSON salvo em: {ENTRIES_JSON_PATH}")
    print(f"Entries encontrados: {len(entries)}")
    print()
    _print_table(entries)

    if len(entries) < 8:
        print()
        print("Poucos campos encontrados. Verifique data/form_debug.html manualmente.")

    return 0


def _download_form_html(form_url: str) -> str:
    response = requests.get(
        form_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
            )
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.text


def _extract_entries(html: str) -> list[FormEntry]:
    fields_by_entry = _extract_entries_from_fb_public_data(html)
    discovered_ids = set(fields_by_entry)

    for pattern in (ENTRY_PATTERN, ENTRY_IN_ARRAY_PATTERN, ENTRY_NAME_PATTERN):
        discovered_ids.update(f"entry.{match.group(1)}" for match in pattern.finditer(html))

    entries = []
    for entry_id in sorted(discovered_ids, key=_entry_sort_key):
        probable_field = fields_by_entry.get(entry_id, "")
        entries.append(
            FormEntry(
                probable_field=probable_field or "(nao identificado)",
                entry_id=entry_id,
                nearby_text=_nearby_text(html, entry_id),
            )
        )

    return entries


def _extract_entries_from_fb_public_data(html: str) -> dict[str, str]:
    match = FB_PUBLIC_LOAD_DATA_PATTERN.search(html)
    if not match:
        return {}

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return _extract_entries_from_fb_public_data_text(match.group(1))

    questions = _find_question_arrays(data)
    entries: dict[str, str] = {}

    for question in questions:
        title = _clean_text(question[1]) if len(question) > 1 else ""
        entry_id = _entry_id_from_question(question)
        if title and entry_id:
            entries[f"entry.{entry_id}"] = title

    return entries


def _extract_entries_from_fb_public_data_text(data_text: str) -> dict[str, str]:
    entries: dict[str, str] = {}
    question_pattern = re.compile(
        r'\[(\d+),"([^"]+)",null,\d+,\[\[(\d+),',
        re.DOTALL,
    )

    for match in question_pattern.finditer(data_text):
        entries[f"entry.{match.group(3)}"] = _clean_text(match.group(2))

    return entries


def _find_question_arrays(value: Any) -> list[list[Any]]:
    questions: list[list[Any]] = []

    if isinstance(value, list):
        if _looks_like_question(value):
            questions.append(value)
        for item in value:
            questions.extend(_find_question_arrays(item))

    return questions


def _looks_like_question(value: list[Any]) -> bool:
    return (
        len(value) > 4
        and isinstance(value[0], int)
        and isinstance(value[1], str)
        and isinstance(value[4], list)
    )


def _entry_id_from_question(question: list[Any]) -> int | None:
    fields = question[4]
    if not fields:
        return None

    first_field = fields[0]
    if isinstance(first_field, list) and first_field and isinstance(first_field[0], int):
        return first_field[0]

    return None


def _nearby_text(html: str, entry_id: str, window: int = 700) -> str:
    candidates = [entry_id]
    if entry_id.startswith("entry."):
        candidates.append(entry_id.removeprefix("entry."))

    positions = [html.find(candidate) for candidate in candidates]
    positions = [position for position in positions if position != -1]
    if not positions:
        return ""

    position = min(positions)
    start = max(0, position - window)
    end = min(len(html), position + len(entry_id) + window)
    return _clean_text(html[start:end])[:260]


def _clean_text(value: Any) -> str:
    text = unescape(str(value))
    text = TAG_PATTERN.sub(" ", text)
    text = text.replace("\\u003c", " ").replace("\\u003e", " ")
    text = text.replace("\\n", " ")
    return re.sub(r"\s+", " ", text).strip()


def _entry_sort_key(entry_id: str) -> int:
    match = re.search(r"\d+", entry_id)
    if match:
        return int(match.group(0))
    return 0


def _print_table(entries: list[FormEntry]) -> None:
    headers = ("campo provável", "entry id", "trecho próximo")
    rows = [(entry.probable_field, entry.entry_id, entry.nearby_text) for entry in entries]
    widths = [
        max(len(headers[index]), *(len(row[index]) for row in rows)) if rows else len(header)
        for index, header in enumerate(headers)
    ]

    print(" | ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print("-+-".join("-" * width for width in widths))

    for row in rows:
        print(" | ".join(row[index].ljust(widths[index]) for index in range(len(headers))))


def main() -> None:
    """CLI entry point."""
    raise SystemExit(inspect_form())


if __name__ == "__main__":
    main()
