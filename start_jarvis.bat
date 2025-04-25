@echo off
REM Startet JARVIS mit der vorkonfigurierten virtuellen Umgebung und prueft Pakete.

REM *** WICHTIG: Verwende die neue Umgebung venv_py311 ***
set VENV_PATH=C:\python\venv_py311

REM Pfade zu Python und Pip in der venv
set PYTHON_EXE="%VENV_PATH%\Scripts\python.exe"
set PIP_EXE="%VENV_PATH%\Scripts\pip.exe"

REM Pruefe, ob die venv existiert
if not exist %PYTHON_EXE% (
    echo FEHLER: Python Interpreter nicht in %VENV_PATH% gefunden!
    echo Stelle sicher, dass die virtuelle Umgebung korrekt erstellt wurde.
    goto :error_exit
)

echo Aktiviere virtuelle Umgebung (Versuch) %VENV_PATH%...
call "%VENV_PATH%\Scripts\activate.bat"

echo Pruefe notwendige Pakete...

REM --- Kritische Pakete pruefen (vereinfacht) ---
echo   - Pruefe Paket: PyQt6
%PIP_EXE% show PyQt6 > nul 2> nul
if errorlevel 1 (
    echo FEHLER: Paket 'PyQt6' nicht in der Umgebung '%VENV_PATH%' gefunden!
    echo.
    echo Bitte installieren mit:
    echo %PYTHON_EXE% -m pip install PyQt6
    goto :error_exit
)

echo   - Pruefe Paket: numpy
%PIP_EXE% show numpy > nul 2> nul
if errorlevel 1 (
    echo FEHLER: Paket 'numpy' nicht in der Umgebung '%VENV_PATH%' gefunden!
    echo.
    echo Bitte installieren mit:
    echo %PYTHON_EXE% -m pip install numpy
    goto :error_exit
)

REM Add more checks here in the same pattern...
REM echo   - Pruefe Paket: pyaudio
REM %PIP_EXE% show pyaudio > nul 2> nul
REM if errorlevel 1 ( echo FEHLER... & goto :error_exit )

REM echo   - Pruefe Paket: soundfile
REM %PIP_EXE% show soundfile > nul 2> nul
REM if errorlevel 1 ( echo FEHLER... & goto :error_exit )

REM ... usw. für alle Pakete ...


echo Wichtige Pakete scheinen vorhanden zu sein (vereinfachte Pruefung).

echo Starte JARVIS mit explizitem Interpreter aus %VENV_PATH%...
%PYTHON_EXE% jarvis.py

echo.
echo JARVIS wurde beendet. Druecken Sie eine Taste zum Schliessen...
goto :end

:error_exit
echo.
echo Start abgebrochen wegen fehlender Pakete oder Fehler.
pause
exit /b 1

:end
pause 