"""Tests for batch submission options."""

import pytest

from src.submission_runner import build_parser, run_batch


ROWS = [
    {"nome": "Aluno Um", "matricula": "PDITA001", "agente": "Natanael"},
    {"nome": "Aluno Dois", "matricula": "PDITA002", "agente": "Natanael"},
]


def test_date_valido_usa_data_informada(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = run_batch(
        ROWS,
        "Aluno não agendado(Fantasma)",
        dry_run=True,
        report_date="2026-05-05",
    )

    output = capsys.readouterr().out

    assert exit_code == 0
    assert "'data': '2026-05-05'" in output


def test_date_invalido_falha() -> None:
    parser = build_parser("teste")

    with pytest.raises(SystemExit):
        parser.parse_args(["--date", "05-05-2026"])


def test_limit_limita_envios(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = run_batch(
        ROWS,
        "Aluno não agendado(Fantasma)",
        dry_run=True,
        report_date="2026-05-05",
        limit=1,
    )

    output = capsys.readouterr().out

    assert exit_code == 0
    assert output.count("[DRY-RUN]") == 1
    assert "Aluno Um" in output
    assert "Aluno Dois" not in output


def test_only_matricula_filtra_corretamente(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = run_batch(
        ROWS,
        "Aluno não agendado(Fantasma)",
        dry_run=True,
        report_date="2026-05-05",
        only_matricula="PDITA002",
    )

    output = capsys.readouterr().out

    assert exit_code == 0
    assert output.count("[DRY-RUN]") == 1
    assert "Aluno Dois" in output
    assert "Aluno Um" not in output
