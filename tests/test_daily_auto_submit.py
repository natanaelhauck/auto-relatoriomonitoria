"""Tests for daily automatic agenda + Read IA submission."""

import csv
import shutil
from pathlib import Path

from src import daily_auto_submit as daily


def test_daily_auto_submit_dry_run_nao_envia(capsys) -> None:
    preview_dir = _make_dir("tests/_tmp_daily_preview_dry")
    log_dir = _make_dir("tests/_tmp_daily_logs_dry")
    sent = []

    def preview_runner(*, report_date: str, preview_dir: Path) -> int:
        _write_preview(
            preview_dir,
            report_date,
            [
                {
                    "status": "Presente",
                    "nome": "Aluno Presente",
                    "matricula": "PDITA001",
                    "readia_summary": "Aluno consumiu Banco de Dados.",
                    "readia_report_url": "https://docs.google.com/document/d/doc1/edit",
                }
            ],
        )
        return 0

    try:
        exit_code = daily.daily_auto_submit(
            dry_run=True,
            report_date="2026-05-26",
            preview_dir=preview_dir,
            log_dir=log_dir,
            preview_runner=preview_runner,
            submitter=sent.append,
        )
    finally:
        shutil.rmtree(preview_dir, ignore_errors=True)
        shutil.rmtree(log_dir, ignore_errors=True)

    output = capsys.readouterr().out
    assert exit_code == 0
    assert sent == []
    assert "[DRY-RUN]" in output
    assert "'status': 'Presente'" in output


def test_daily_auto_submit_yes_envia_sem_confirmacao(monkeypatch) -> None:
    preview_dir = _make_dir("tests/_tmp_daily_preview_yes")
    log_dir = _make_dir("tests/_tmp_daily_logs_yes")
    sent = []

    def preview_runner(*, report_date: str, preview_dir: Path) -> int:
        _write_preview(
            preview_dir,
            report_date,
            [
                {
                    "status": "Falta",
                    "nome": "Aluno Falta",
                    "matricula": "PDITA002",
                }
            ],
        )
        return 0

    def submitter(payload):
        sent.append(payload)
        return _Response()

    monkeypatch.setattr("builtins.input", lambda prompt="": (_ for _ in ()).throw(AssertionError))
    monkeypatch.setattr("src.submission_runner.time.sleep", lambda seconds: None)

    try:
        exit_code = daily.daily_auto_submit(
            dry_run=False,
            assume_yes=True,
            report_date="2026-05-26",
            preview_dir=preview_dir,
            log_dir=log_dir,
            preview_runner=preview_runner,
            submitter=submitter,
        )
    finally:
        shutil.rmtree(preview_dir, ignore_errors=True)
        shutil.rmtree(log_dir, ignore_errors=True)

    assert exit_code == 0
    assert len(sent) == 1
    assert sent[0].status == "Falta"
    assert sent[0].motivo_falta == "Sem resposta"


def _make_dir(path: str) -> Path:
    directory = Path(path)
    shutil.rmtree(directory, ignore_errors=True)
    directory.mkdir(parents=True)
    return directory


def _write_preview(
    preview_dir: Path,
    report_date: str,
    rows: list[dict[str, str]],
) -> None:
    fieldnames = [
        "categoria",
        "status",
        "nome",
        "matricula",
        "readia_summary",
        "readia_report_url",
        "motivo_falta",
    ]
    with (preview_dir / f"preview_agenda_monitoria_{report_date}.csv").open(
        "w",
        newline="",
        encoding="utf-8",
    ) as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class _Response:
    ok = True
    status_code = 200
    text = ""
