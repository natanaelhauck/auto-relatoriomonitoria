"""Tests for batch submission options."""

import csv
import shutil
from pathlib import Path

import pytest

from src.submission_runner import build_payloads, build_parser, run_batch, run_prepared_batch


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


def test_duplicado_e_pulado_quando_ja_existe_log(capsys: pytest.CaptureFixture[str]) -> None:
    log_dir = Path("tests/_tmp_submission_logs")
    shutil.rmtree(log_dir, ignore_errors=True)
    log_dir.mkdir(parents=True)

    try:
        log_path = log_dir / "previous.csv"
        with log_path.open("w", newline="", encoding="utf-8") as log_file:
            writer = csv.DictWriter(
                log_file,
                fieldnames=[
                    "timestamp",
                    "nome",
                    "matricula",
                    "data",
                    "agente",
                    "status",
                    "resultado",
                    "detalhe",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "timestamp": "2026-05-05T15:00:00-03:00",
                    "nome": "Aluno Um",
                    "matricula": "PDITA001",
                    "data": "2026-05-05",
                    "agente": "Natanael",
                    "status": "Aluno não agendado(Fantasma)",
                    "resultado": "OK",
                    "detalhe": "HTTP 200",
                }
            )

        payloads, _ = build_payloads(
            ROWS[:1],
            "Aluno não agendado(Fantasma)",
            "2026-05-05",
        )
        exit_code = run_prepared_batch(
            payloads,
            dry_run=True,
            total_rows=1,
            skip_existing=True,
            log_dir=log_dir,
        )
    finally:
        shutil.rmtree(log_dir, ignore_errors=True)

    output = capsys.readouterr().out

    assert exit_code == 0
    assert "PULADO - Aluno Um - PDITA001 - já enviado nesta data/status" in output
    assert "[DRY-RUN]" not in output


def test_faltas_sem_motivo_usam_sem_resposta() -> None:
    payloads, ignored = build_payloads(
        ROWS[:1],
        "Falta",
        "2026-05-05",
        payload_defaults={"motivo_falta": "Sem resposta"},
    )

    assert ignored == []
    assert payloads[0].motivo_falta == "Sem resposta"


def test_presentes_aceitam_relatorio_e_link_readia() -> None:
    payloads, ignored = build_payloads(
        [
            {
                "nome": "Aluno Presente",
                "matricula": "PDITA999",
                "agente": "Natanael",
                "relatorio_readia": "Resumo",
                "link_readia": "https://read.ai/report",
                "cursos_consumidos": "Não consumiu",
            }
        ],
        "Presente",
        "2026-05-05",
    )

    assert ignored == []
    assert payloads[0].relatorio_readia == "Resumo"
    assert payloads[0].link_readia == "https://read.ai/report"
    assert payloads[0].cursos_consumidos == ["Não consumiu"]
