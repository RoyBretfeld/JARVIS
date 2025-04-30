@echo off
REM Startet das PowerShell-Skript, das JARVIS ausführt.

REM Finde das Verzeichnis, in dem diese Batch-Datei liegt
set SCRIPT_DIR=%~dp0

REM Rufe PowerShell auf, um das .ps1 Skript auszuführen
REM powershell.exe -ExecutionPolicy Bypass -NoProfile -File "%SCRIPT_DIR%start_jarvis.ps1"
C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe -ExecutionPolicy Bypass -NoProfile -File "%SCRIPT_DIR%start_jarvis.ps1"

REM Pause nur, wenn PowerShell selbst einen Fehler zurückgibt (selten)
if %ERRORLEVEL% neq 0 (
    echo Fehler beim Starten von PowerShell oder dem Skript.
    pause
) 