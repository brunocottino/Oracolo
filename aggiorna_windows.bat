@echo off
rem Aggiornamento di Oracolo: lo lancia il pianificatore di Windows (vedi installa_aggiornamento_windows.bat).
cd /d %~dp0
if exist .venv\Scripts\python.exe (
  .venv\Scripts\python.exe aggiorna.py
) else (
  python aggiorna.py
)
