"""Tests for daily agenda preview submissions."""

import csv
import shutil
from pathlib import Path

import pytest

from src.course_detection import detect_consumed_courses_from_text
from src import submit_monitoria_agenda_do_dia as submit_agenda


def test_submit_agenda_dry_run_envia_presentes_e_faltas(capsys) -> None:
    preview_dir = _make_dir("tests/_tmp_agenda_preview")
    log_dir = _make_dir("tests/_tmp_agenda_logs")
    try:
        _write_preview(
            preview_dir,
            [
                {
                    "status": "Presente",
                    "nome": "Aluno Presente",
                    "matricula": "PDITA001",
                    "readia_summary": "Resumo Read IA",
                    "readia_report_url": "https://read.ai/report/1",
                    "observacao": "match confirmado",
                },
                {
                    "status": "Falta",
                    "nome": "Aluno Falta",
                    "matricula": "PDITA002",
                    "observacao": "sem match Read IA no dia",
                },
                {
                    "status": "Revisar",
                    "nome": "Aluno Revisar",
                    "matricula": "PDITA003",
                },
            ],
        )

        exit_code = submit_agenda.submit_monitoria_agenda_do_dia(
            dry_run=True,
            report_date="2026-05-22",
            preview_dir=preview_dir,
            log_dir=log_dir,
        )
    finally:
        shutil.rmtree(preview_dir, ignore_errors=True)
        shutil.rmtree(log_dir, ignore_errors=True)

    output = capsys.readouterr().out
    assert exit_code == 0
    assert output.count("[DRY-RUN]") == 2
    assert "'status': 'Presente'" in output
    assert "'relatorio_readia': 'Resumo Read IA'" in output
    assert "'link_readia': 'https://read.ai/report/1'" in output
    assert "'cursos_consumidos': ['Não consumiu']" in output
    assert "'motivo_deteccao_curso':" in output
    assert "'status': 'Falta'" in output
    assert "'motivo_falta': 'Sem resposta'" in output
    assert "Aluno Revisar" not in output


def test_submit_agenda_falta_usa_sem_resposta(capsys) -> None:
    preview_dir = _make_dir("tests/_tmp_agenda_preview_reason")
    log_dir = _make_dir("tests/_tmp_agenda_logs_reason")
    try:
        _write_preview(
            preview_dir,
            [
                {
                    "categoria": "faltas_candidatas",
                    "status": "Falta",
                    "nome": "Aluno Falta",
                    "matricula": "PDITA998",
                    "motivo_falta": "Atestado informado manualmente",
                },
            ],
        )

        exit_code = submit_agenda.submit_monitoria_agenda_do_dia(
            dry_run=True,
            report_date="2026-05-22",
            preview_dir=preview_dir,
            log_dir=log_dir,
        )
    finally:
        shutil.rmtree(preview_dir, ignore_errors=True)
        shutil.rmtree(log_dir, ignore_errors=True)

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "'motivo_falta': 'Sem resposta'" in output
    assert "Atestado informado manualmente" not in output


def test_submit_agenda_detecta_cursos_pelo_resumo_readia(capsys) -> None:
    preview_dir = _make_dir("tests/_tmp_agenda_preview_courses")
    log_dir = _make_dir("tests/_tmp_agenda_logs_courses")
    try:
        _write_preview(
            preview_dir,
            [
                {
                    "status": "Presente",
                    "nome": "Aluno Curso",
                    "matricula": "PDITA010",
                    "readia_summary": (
                        "O aluno consumiu Banco de Dados e assistiu Python intermediário."
                    ),
                    "readia_report_url": "https://read.ai/report/course",
                },
            ],
        )

        exit_code = submit_agenda.submit_monitoria_agenda_do_dia(
            dry_run=True,
            report_date="2026-05-22",
            preview_dir=preview_dir,
            log_dir=log_dir,
        )
    finally:
        shutil.rmtree(preview_dir, ignore_errors=True)
        shutil.rmtree(log_dir, ignore_errors=True)

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "'cursos_consumidos': ['Banco de Dados', 'Python II']" in output
    assert "'motivo_deteccao_curso':" in output


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Aluno consumiu Banco de Dados", ["Banco de Dados"]),
        ("Aluno assistiu Python intermediário", ["Python II"]),
        ("Meta para próxima semana Banco de Dados", ["Não consumiu"]),
        ("Foi orientado a assistir Fundamentos de interface", ["Não consumiu"]),
        (
            "Perguntei se consumiu Python intermediário e passei como meta Banco de Dados",
            ["Python II"],
        ),
        ("Texto sem curso", ["Não consumiu"]),
    ],
)
def test_detect_consumed_courses_from_text_casos_obrigatorios(
    text: str,
    expected: list[str],
) -> None:
    assert detect_consumed_courses_from_text(text) == expected


def test_detect_courses_from_text_nao_confunde_python_i_com_python_ii() -> None:
    courses = submit_agenda.detect_courses_from_text("Aluno estudou Python II.")

    assert courses == ["Python II"]


def test_submit_agenda_filtros_presentes_only_e_only_matricula(capsys) -> None:
    preview_dir = _make_dir("tests/_tmp_agenda_preview_filter")
    log_dir = _make_dir("tests/_tmp_agenda_logs_filter")
    try:
        _write_preview(
            preview_dir,
            [
                {"status": "Presenca", "nome": "Aluno Um", "matricula": "PDITA001"},
                {"status": "Falta", "nome": "Aluno Dois", "matricula": "PDITA002"},
            ],
        )

        exit_code = submit_agenda.submit_monitoria_agenda_do_dia(
            dry_run=True,
            report_date="2026-05-22",
            only_matricula="PDITA001",
            presentes_only=True,
            preview_dir=preview_dir,
            log_dir=log_dir,
        )
    finally:
        shutil.rmtree(preview_dir, ignore_errors=True)
        shutil.rmtree(log_dir, ignore_errors=True)

    output = capsys.readouterr().out
    assert exit_code == 0
    assert output.count("[DRY-RUN]") == 1
    assert "Aluno Um" in output
    assert "Aluno Dois" not in output


def test_submit_agenda_presente_sem_summary_usa_resumo_indisponivel(capsys) -> None:
    preview_dir = _make_dir("tests/_tmp_agenda_preview_no_summary")
    log_dir = _make_dir("tests/_tmp_agenda_logs_no_summary")
    try:
        _write_preview(
            preview_dir,
            [
                {
                    "status": "Presente",
                    "nome": "Aluno Sem Summary",
                    "matricula": "PDITA004",
                    "observacao": "match confirmado",
                },
            ],
        )

        exit_code = submit_agenda.submit_monitoria_agenda_do_dia(
            dry_run=True,
            report_date="2026-05-22",
            preview_dir=preview_dir,
            log_dir=log_dir,
        )
    finally:
        shutil.rmtree(preview_dir, ignore_errors=True)
        shutil.rmtree(log_dir, ignore_errors=True)

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "'relatorio_readia': 'Resumo não disponível'" in output
    assert "match confirmado" not in output


def test_submit_agenda_aplica_duplicidade_diaria(capsys) -> None:
    preview_dir = _make_dir("tests/_tmp_agenda_preview_duplicate")
    log_dir = _make_dir("tests/_tmp_agenda_logs_duplicate")
    try:
        _write_preview(
            preview_dir,
            [{"status": "Falta", "nome": "Aluno Falta", "matricula": "PDITA002"}],
        )
        _write_log(
            log_dir,
            data="2026-05-22",
            status="Falta",
            matricula="PDITA002",
        )

        exit_code = submit_agenda.submit_monitoria_agenda_do_dia(
            dry_run=True,
            report_date="2026-05-22",
            preview_dir=preview_dir,
            log_dir=log_dir,
        )
    finally:
        shutil.rmtree(preview_dir, ignore_errors=True)
        shutil.rmtree(log_dir, ignore_errors=True)

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "ja enviado nesta data/status" in output
    assert "Total puladas por duplicidade: 1" in output
    assert "[DRY-RUN]" not in output


def _make_dir(path: str) -> Path:
    directory = Path(path)
    shutil.rmtree(directory, ignore_errors=True)
    directory.mkdir(parents=True)
    return directory


def _write_preview(preview_dir: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "categoria",
        "status",
        "nome",
        "matricula",
        "readia_summary",
        "readia_report_url",
        "motivo_falta",
        "observacao",
    ]
    with (preview_dir / "preview_agenda_monitoria_2026-05-22.csv").open(
        "w",
        newline="",
        encoding="utf-8",
    ) as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_log(
    log_dir: Path,
    *,
    data: str,
    status: str,
    matricula: str,
) -> None:
    fieldnames = [
        "timestamp",
        "nome",
        "matricula",
        "data",
        "iso_year",
        "iso_week",
        "agente",
        "status",
        "resultado",
        "detalhe",
    ]
    with (log_dir / "previous.csv").open("w", newline="", encoding="utf-8") as log_file:
        writer = csv.DictWriter(log_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(
            {
                "timestamp": "2026-05-22T15:00:00-03:00",
                "nome": "Aluno Falta",
                "matricula": matricula,
                "data": data,
                "iso_year": "2026",
                "iso_week": "21",
                "agente": "Natanael",
                "status": status,
                "resultado": "OK",
                "detalhe": "HTTP 200",
            }
        )
