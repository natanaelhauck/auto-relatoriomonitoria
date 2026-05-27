"""Google Drive/Docs client for Read IA meeting notes."""

from __future__ import annotations

import json
import os
import re
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
        raw_text = get_google_doc_text(services["docs"], str(file["id"]))
        reports.append(extract_readia_doc_report(file, raw_text))
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


def get_google_doc_text(docs_service: Any, document_id: str) -> str:
    """Read a Google Docs document and return its plain text content."""
    document = docs_service.documents().get(documentId=document_id).execute()
    return google_doc_to_text(document)


def google_doc_to_text(document: dict[str, Any]) -> str:
    """Extract plain text from a Google Docs API document payload."""
    chunks: list[str] = []
    for content in document.get("body", {}).get("content", []):
        _collect_structural_text(content, chunks)
    return "".join(chunks).strip()


def extract_readia_doc_report(
    file: dict[str, Any],
    raw_text: str,
) -> dict[str, Any]:
    """Extract the fields used by the monitoring flow from one Read IA doc."""
    title = str(file.get("name", "")).strip()
    report_url = str(file.get("webViewLink", "")).strip()
    document_id = str(file.get("id", "")).strip()
    if not report_url and document_id:
        report_url = f"https://docs.google.com/document/d/{document_id}/edit"

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
        "report_url": report_url,
        "raw_text": raw_text,
        "payload_json": raw_text,
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


def _extract_field(raw_text: str, field_name: str) -> str:
    lines = [line.strip() for line in raw_text.splitlines()]
    field_key = field_name.casefold()
    for index, line in enumerate(lines):
        if not line:
            continue
        if line.casefold().startswith(f"{field_key}:"):
            return line.split(":", 1)[1].strip()
        if line.casefold() == field_key:
            for next_line in lines[index + 1 :]:
                if next_line:
                    return next_line.strip()
    return ""


def _extract_section(raw_text: str, heading: str) -> str:
    lines = raw_text.splitlines()
    heading_key = heading.casefold()
    collecting = False
    section_lines: list[str] = []

    for line in lines:
        clean_line = line.strip()
        normalized = clean_line.rstrip(":").casefold()
        if not collecting:
            if normalized == heading_key or clean_line.casefold().startswith(
                f"{heading_key}:"
            ):
                collecting = True
                if ":" in clean_line:
                    remainder = clean_line.split(":", 1)[1].strip()
                    if remainder:
                        section_lines.append(remainder)
            continue

        if normalized in SECTION_HEADINGS and normalized != heading_key:
            break
        section_lines.append(line)

    return "\n".join(section_lines).strip()


def _extract_date(value: Any) -> str:
    text = str(value or "")
    match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    return match.group(0) if match else ""


def _escape_drive_query(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")
