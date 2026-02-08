@echo off
cd /d "%~dp0"

if not exist ".venv" (
    echo Error: Virtual environment not found. Please run install script first.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat

python main.py
