@echo off
if not exist "data\feeds" mkdir "data\feeds"

python -m venv .venv

.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt

.venv\Scripts\pip.exe --version
