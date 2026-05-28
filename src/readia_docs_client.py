"""Google Drive/Docs client for Read IA meeting notes."""

from __future__ import annotations

import json
import os
import re
import unicodedata
from typing import Any

from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = (
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/documents.readonly",
)
DEFAULT_FOLDER_NAME = "Read AI Meeting Notes"
GOOGLE_DOC_MIME_TYPE = "application/vnd.google-apps.document"
SECTION_HEADINGS = {
    "summary",
    "action items",
    "key questions",
    "chapters topics",
    "chapters and topics",
    "transcript",
}


def list_readia_docs_for_date(report_date: str) -> list[dict[str, Any]]:
    """Return normalized Read IA Google Docs reports for a date."""
    services = build_readia_docs_services()
    folder_id = find_readia_notes_folder_id(services["drive"])
    files = list_readia_doc_files(
        services["drive"],
        folder_id=folder_id,
        report_date=report_date,
    )
    reports = []
    for file in files:
        document = get_google_doc(services["docs"], str(file["id"]))
        reports.append(extract_readia_doc_report_from_google_doc(file, document))
    return reports


def build_readia_docs_services() -> dict[str, Any]:
    """Build Google Drive and Google Docs API services."""
    load_dotenv()
    service_account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    service_account_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()
    if not service_account_json and not service_account_file:
        raise RuntimeError(
            "Missing required environment variable: "
            "GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SERVICE_ACCOUNT_FILE"
        )

    credentials = _build_service_account_credentials(
        service_account_file=service_account_file or None,
        service_account_json=service_account_json or None,
    )
    return {
        "drive": build("drive", "v3", credentials=credentials, cache_discovery=False),
        "docs": build("docs", "v1", credentials=credentials, cache_discovery=False),
    }


def find_readia_notes_folder_id(drive_service: Any) -> str:
    """Find the Read IA notes folder in Google Drive."""
    load_dotenv()
    configured_folder_id = os.getenv("READIA_DOCS_FOLDER_ID", "").strip()
    if configured_folder_id:
        return configured_folder_id

    folder_name = (
        os.getenv("READIA_DOCS_FOLDER_NAME", DEFAULT_FOLDER_NAME).strip()
        or DEFAULT_FOLDER_NAME
    )
    result = (
        drive_service.files()
        .list(
            q=(
                "mimeType = 'application/vnd.google-apps.folder' "
                f"and name = '{_escape_drive_query(folder_name)}' "
                "and trashed = false"
            ),
            spaces="drive",
            corpora="allDrives",
            fields="files(id,name)",
            pageSize=10,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute()
    )
    folders = result.get("files", [])
    if not folders:
        raise RuntimeError(
            f"Pasta do Read IA nao encontrada no Drive: {folder_name}. "
            "Compartilhe a pasta com a service account ou configure "
            "READIA_DOCS_FOLDER_ID no .env."
        )
    return str(folders[0]["id"])


def list_readia_doc_files(
    drive_service: Any,
    *,
    folder_id: str,
    report_date: str,
) -> list[dict[str, Any]]:
    """List Google Docs files from the Read IA folder for a date."""
    query = (
        f"'{_escape_drive_query(folder_id)}' in parents "
        f"and mimeType = '{GOOGLE_DOC_MIME_TYPE}' "
        f"and name contains '{_escape_drive_query(report_date)}' "
        "and trashed = false"
    )
    files: list[dict[str, Any]] = []
    page_token = None
    while True:
        result = (
            drive_service.files()
            .list(
                q=query,
                spaces="drive",
                corpora="allDrives",
                fields="nextPageToken,files(id,name,webViewLink,createdTime,modifiedTime)",
                pageSize=100,
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute()
        )
        files.extend(result.get("files", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            return sorted(files, key=lambda item: str(item.get("name", "")))


def get_google_doc(docs_service: Any, document_id: str) -> dict[str, Any]:
    """Read a Google Docs document payload."""
    return docs_service.documents().get(documentId=document_id).execute()


def get_google_doc_text(docs_service: Any, document_id: str) -> str:
    """Read a Google Docs document and return its plain text content."""
    return google_doc_to_text(get_google_doc(docs_service, document_id))


def google_doc_to_text(document: dict[str, Any]) -> str:
    """Extract plain text from a Google Docs API document payload."""
    chunks: list[str] = []
    for content in document.get("body", {}).get("content", []):
        _collect_structural_text(content, chunks)
    return "".join(chunks).strip()


def google_doc_meeting_link(document: dict[str, Any]) -> str:
    """Return the hyperlink attached to the Meeting field, when present."""
    lines = google_doc_lines_with_links(document)
    for index, line_runs in enumerate(lines):
        line_text = "".join(text for text, _ in line_runs).strip()
        if not line_text:
            continue

        label, _ = _split_labeled_line(line_text)
        if label == "meeting":
            return _first_link_after_label(line_runs, line_text) or ""

        if _normalize_heading(line_text) == "meeting":
            link = _first_link_in_runs(line_runs)
            if link:
                return link
            for next_line_runs in lines[index + 1 :]:
                if "".join(text for text, _ in next_line_runs).strip():
                    return _first_link_in_runs(next_line_runs) or ""
    return ""


def google_doc_lines_with_links(document: dict[str, Any]) -> list[list[tuple[str, str]]]:
    """Extract text lines from a Google Docs payload preserving run hyperlinks."""
    lines: list[list[tuple[str, str]]] = [[]]
    for content in document.get("body", {}).get("content", []):
        _collect_structural_lines_with_links(content, lines)
    return [line for line in lines if line]


def extract_readia_doc_report_from_google_doc(
    file: dict[str, Any],
    document: dict[str, Any],
) -> dict[str, Any]:
    """Extract report fields from a Drive file plus Google Docs API payload."""
    raw_text = google_doc_to_text(document)
    return extract_readia_doc_report(
        file,
        raw_text,
        readia_report_url=google_doc_meeting_link(document),
    )


def extract_readia_doc_report(
    file: dict[str, Any],
    raw_text: str,
    *,
    readia_report_url: str = "",
) -> dict[str, Any]:
    """Extract the fields used by the monitoring flow from one Read IA doc."""
    title = str(file.get("name", "")).strip()
    link_google_docs = str(file.get("webViewLink", "")).strip()
    document_id = str(file.get("id", "")).strip()
    if not link_google_docs and document_id:
        link_google_docs = f"https://docs.google.com/document/d/{document_id}/edit"

    readia_url = str(readia_report_url or "").strip() or link_google_docs

    meeting = _extract_field(raw_text, "Meeting")
    event_time = _extract_field(raw_text, "Event time")
    summary = _extract_section(raw_text, "Summary")
    transcript = _extract_section(raw_text, "Transcript")
    date = _extract_date(title) or _extract_date(event_time) or _extract_date(raw_text)

    return {
        "date": date,
        "title": title,
        "meeting": meeting,
        "event_time": event_time,
        "start_time": event_time,
        "summary": summary,
        "transcript": transcript,
        "readia_report_url": readia_url,
        "link_google_docs": link_google_docs,
        "report_url": readia_url,
        "raw_text": raw_text,
        "participants": [],
        "emails": [],
        "source": "google_docs",
        "document_id": document_id,
    }


def _build_service_account_credentials(
    *,
    service_account_file: str | None,
    service_account_json: str | None,
) -> service_account.Credentials:
    if service_account_json:
        try:
            service_account_info = json.loads(service_account_json)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "Invalid GOOGLE_SERVICE_ACCOUNT_JSON: expected complete service "
                "account JSON content."
            ) from exc

        return service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=SCOPES,
        )

    if service_account_file:
        return service_account.Credentials.from_service_account_file(
            service_account_file,
            scopes=SCOPES,
        )

    raise RuntimeError(
        "Missing required environment variable: "
        "GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SERVICE_ACCOUNT_FILE"
    )


def _collect_structural_text(value: dict[str, Any], chunks: list[str]) -> None:
    if "paragraph" in value:
        for element in value["paragraph"].get("elements", []):
            text_run = element.get("textRun")
            if text_run:
                chunks.append(str(text_run.get("content", "")))
        return

    if "table" in value:
        for row in value["table"].get("tableRows", []):
            for cell in row.get("tableCells", []):
                for content in cell.get("content", []):
                    _collect_structural_text(content, chunks)
        return

    if "tableOfContents" in value:
        for content in value["tableOfContents"].get("content", []):
            _collect_structural_text(content, chunks)


def _collect_structural_lines_with_links(
    value: dict[str, Any],
    lines: list[list[tuple[str, str]]],
) -> None:
    if "paragraph" in value:
        for element in value["paragraph"].get("elements", []):
            text_run = element.get("textRun")
            if text_run:
                text = str(text_run.get("content", ""))
                url = _text_run_link_url(text_run)
                _append_text_run_to_lines(lines, text, url)
        return

    if "table" in value:
        for row in value["table"].get("tableRows", []):
            for cell in row.get("tableCells", []):
                for content in cell.get("content", []):
                    _collect_structural_lines_with_links(content, lines)
        return

    if "tableOfContents" in value:
        for content in value["tableOfContents"].get("content", []):
            _collect_structural_lines_with_links(content, lines)


def _append_text_run_to_lines(
    lines: list[list[tuple[str, str]]],
    text: str,
    url: str,
) -> None:
    if not lines:
        lines.append([])

    for chunk in text.splitlines(keepends=True):
        line_text = chunk.rstrip("\r\n")
        if line_text:
            lines[-1].append((line_text, url))
        if chunk.endswith(("\n", "\r")):
            lines.append([])


def _text_run_link_url(text_run: dict[str, Any]) -> str:
    link = text_run.get("textStyle", {}).get("link", {})
    return str(link.get("url", "") or "").strip()


def _first_link_after_label(
    line_runs: list[tuple[str, str]],
    line_text: str,
) -> str:
    colon_index = line_text.find(":")
    target_start = colon_index + 1 if colon_index >= 0 else 0
    offset = 0
    fallback = ""
    for text, url in line_runs:
        next_offset = offset + len(text)
        if url and not fallback:
            fallback = url
        if url and next_offset > target_start:
            return url
        offset = next_offset
    return fallback


def _first_link_in_runs(line_runs: list[tuple[str, str]]) -> str:
    for _, url in line_runs:
        if url:
            return url
    return ""


def _extract_field(raw_text: str, field_name: str) -> str:
    lines = [line.strip() for line in raw_text.splitlines()]
    field_key = _normalize_heading(field_name)
    for index, line in enumerate(lines):
        if not line:
            continue
        label, value = _split_labeled_line(line)
        if label == field_key:
            return value
        if _normalize_heading(line) == field_key:
            for next_line in lines[index + 1 :]:
                if next_line:
                    return next_line.strip()
    return ""


def _extract_section(raw_text: str, heading: str) -> str:
    lines = raw_text.splitlines()
    heading_key = _normalize_heading(heading)
    collecting = False
    section_lines: list[str] = []

    for line in lines:
        clean_line = line.strip()
        normalized = _normalize_heading(clean_line)
        if not collecting:
            label, value = _split_labeled_line(clean_line)
            if normalized == heading_key or label == heading_key:
                collecting = True
                if label == heading_key and value:
                    section_lines.append(value)
            continue

        if heading_key != "transcript" and normalized in SECTION_HEADINGS:
            break
        section_lines.append(line)

    return "\n".join(section_lines).strip()


def _split_labeled_line(line: str) -> tuple[str, str]:
    if ":" not in line:
        return "", ""
    label, value = line.split(":", 1)
    return _normalize_heading(label), value.strip()


def _normalize_heading(value: Any) -> str:
    text = str(value or "").strip().casefold().replace("&", " and ")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_date(value: Any) -> str:
    text = str(value or "")
    match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    return match.group(0) if match else ""


def _escape_drive_query(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")
