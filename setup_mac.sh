#!/bin/bash
cd "$(dirname "$0")"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python tests/run_all.py
# Aggiornamento automatico dal lunedi al venerdi alle 7:30 (python aggiorna.py), senza Claude.
DIR="$(pwd)"
( crontab -l 2>/dev/null | grep -v "aggiorna.py" ; echo "30 7 * * 1-5 cd \"$DIR\" && .venv/bin/python aggiorna.py >/dev/null 2>&1" ) | crontab -
echo; echo "Fatto. Oracolo si aggiorna da solo nei giorni feriali alle 7:30. Ora scrivi:  claude"
