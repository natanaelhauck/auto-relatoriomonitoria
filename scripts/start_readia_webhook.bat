@echo off

cd /d "C:\Users\Natanael Hauck\Desktop\auto-relatoriomonitoria"

if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)

start cmd /k python -m src.webhook_readia
timeout /t 3
start cmd /k ngrok http 5000
