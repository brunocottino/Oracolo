@echo off
rem Una volta sola: Windows aggiorna Oracolo da solo dal lunedi al venerdi alle 7:30.
rem Se il computer e' spento a quell'ora, l'aggiornamento parte appena lo accendi.
cd /d %~dp0
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$a = New-ScheduledTaskAction -Execute '%~dp0aggiorna_windows.bat' -WorkingDirectory '%~dp0';" ^
  "$t = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 07:30;" ^
  "$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2);" ^
  "Register-ScheduledTask -TaskName 'Oracolo aggiorna' -Action $a -Trigger $t -Settings $s -Force | Out-Null"
if errorlevel 1 (
  echo Non sono riuscito a creare l'attivita' pianificata.
) else (
  echo Fatto: Oracolo si aggiorna da solo dal lunedi al venerdi alle 7:30.
  echo Primo aggiornamento adesso, ci vogliono alcuni minuti...
  call aggiorna_windows.bat
  echo Apri l'app ^(python app.py^) e vai su http://localhost:8000/oracolo
)
pause
