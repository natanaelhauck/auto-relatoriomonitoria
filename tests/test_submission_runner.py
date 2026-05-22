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


def test_mesmo_aluno_status_e_semana_e_duplicado(
    capsys: pytest.CaptureFixture[str],
) -> None:
    log_dir = _make_log_dir()
    try:
        _write_log(
            log_dir,
            matricula="PDITA001",
            data="2026-05-04",
            status="Aluno não agendado(Fantasma)",
            iso_year="2026",
            iso_week="19",
        )
        payloads, _ = build_payloads(
            ROWS[:1],
            "Aluno não agendado(Fantasma)",
            "2026-05-08",
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
    assert "PULADO - Aluno Um - PDITA001 - ja enviado nesta semana/status" in output
    assert "[DRY-RUN]" not in output


def test_mesmo_aluno_mesma_semana_status_diferente_e_permitido(
    capsys: pytest.CaptureFixture[str],
) -> None:
    log_dir = _make_log_dir()
    try:
        _write_log(
            log_dir,
            matricula="PDITA001",
            data="2026-05-04",
            status="Aluno finalizou o curso",
            iso_year="2026",
            iso_week="19",
        )
        payloads, _ = build_payloads(
            ROWS[:1],
            "Aluno não agendado(Fantasma)",
            "2026-05-08",
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
    assert "[DRY-RUN]" in output
    assert "PULADO" not in output


def test_mesmo_aluno_semana_diferente_e_permitido(
    capsys: pytest.CaptureFixture[str],
) -> None:
    log_dir = _make_log_dir()
    try:
        _write_log(
            log_dir,
            matricula="PDITA001",
            data="2026-04-27",
            status="Aluno não agendado(Fantasma)",
            iso_year="2026",
            iso_week="18",
        )
        payloads, _ = build_payloads(
            ROWS[:1],
            "Aluno não agendado(Fantasma)",
            "2026-05-08",
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
    assert "[DRY-RUN]" in output
    assert "PULADO" not in output


def test_log_antigo_sem_iso_year_week_continua_funcionando(
    capsys: pytest.CaptureFixture[str],
) -> None:
    log_dir = _make_log_dir()
    try:
        _write_log(
            log_dir,
            matricula="PDITA001",
            data="2026-05-04",
            status="Aluno não agendado(Fantasma)",
            include_iso=False,
        )
        payloads, _ = build_payloads(
            ROWS[:1],
            "Aluno não agendado(Fantasma)",
            "2026-05-08",
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
    assert "PULADO - Aluno Um - PDITA001 - ja enviado nesta semana/status" in output


def test_faltas_sem_motivo_usam_sem_resposta() -> None:
    payloads, ignored = build_payloads(
        ROWS[:1],
        "Falta",
        "2026-05-05",
        payload_defaults={"motivo_falta": "Sem resposta"},
    )

    assert ignored == []
    assert payloads[0].motivo_falta == "Sem resposta"


def test_faltas_com_motivo_mantem_valor() -> None:
    payloads, ignored = build_payloads(
        [
            {
                "nome": "Aluno Um",
                "matricula": "PDITA001",
                "agente": "Natanael",
                "motivo_falta": "Questões Médicas",
            }
        ],
        "Falta",
        "2026-05-05",
        payload_defaults={"motivo_falta": "Sem resposta"},
    )

    assert ignored == []
    assert payloads[0].motivo_falta == "Questões Médicas"


def test_faltas_aplicam_duplicidade_semanal(
    capsys: pytest.CaptureFixture[str],
) -> None:
    log_dir = _make_log_dir()
    try:
        _write_log(
            log_dir,
            matricula="PDITA001",
            data="2026-05-04",
            status="Falta",
            iso_year="2026",
            iso_week="19",
        )
        payloads, _ = build_payloads(
            ROWS[:1],
            "Falta",
            "2026-05-08",
            payload_defaults={"motivo_falta": "Sem resposta"},
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
    assert "PULADO - Aluno Um - PDITA001" in output
    assert "Total puladas por duplicidade: 1" in output
    assert "[DRY-RUN]" not in output


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


def _make_log_dir() -> Path:
    log_dir = Path("tests/_tmp_submission_logs")
    shutil.rmtree(log_dir, ignore_errors=True)
    log_dir.mkdir(parents=True)
    return log_dir


def _write_log(
    log_dir: Path,
    *,
    matricula: str,
    data: str,
    status: str,
    include_iso: bool = True,
    iso_year: str = "",
    iso_week: str = "",
) -> None:
    fieldnames = [
        "timestamp",
        "nome",
        "matricula",
        "data",
        "agente",
        "status",
        "resultado",
        "detalhe",
    ]
    if include_iso:
        fieldnames.insert(4, "iso_year")
        fieldnames.insert(5, "iso_week")

    row = {
        "timestamp": "2026-05-05T15:00:00-03:00",
        "nome": "Aluno Um",
        "matricula": matricula,
        "data": data,
        "agente": "Natanael",
        "status": status,
        "resultado": "OK",
        "detalhe": "HTTP 200",
    }
    if include_iso:
        row["iso_year"] = iso_year
        row["iso_week"] = iso_week

    with (log_dir / "previous.csv").open("w", newline="", encoding="utf-8") as log_file:
        writer = csv.DictWriter(log_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(row)
