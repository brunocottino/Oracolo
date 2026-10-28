@echo off
cd /d %~dp0
python -m venv .venv
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python tests\run_all.py
call installa_aggiornamento_windows.bat
echo.
echo Fatto. Ora scrivi:  claude
pause
