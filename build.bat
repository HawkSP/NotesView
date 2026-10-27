@echo off
cd /d "%~dp0"
python -m PyInstaller --noconfirm --onefile --windowed --name NotesView --add-data "ui;ui" app.py
