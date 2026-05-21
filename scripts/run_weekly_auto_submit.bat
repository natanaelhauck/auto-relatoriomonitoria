@echo off

cd /d "C:\Users\Natanael Hauck\Desktop\auto-relatoriomonitoria"

if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)

python -m src.weekly_auto_submit --yes

pause
