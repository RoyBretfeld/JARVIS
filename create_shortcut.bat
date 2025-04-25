@echo off
echo Erstelle Desktop-Verknüpfung für JARVIS...
set SCRIPT_DIR=%~dp0
set ICON_PATH=%SCRIPT_DIR%icon.ico
echo Aktuelles Verzeichnis: %SCRIPT_DIR%
echo Desktop-Pfad: %USERPROFILE%\Desktop
echo Icon-Pfad: %ICON_PATH%

:: Prüfe, ob Icon-Datei existiert
if not exist "%ICON_PATH%" (
    echo Warnung: Icon-Datei nicht gefunden unter %ICON_PATH%!
    echo Stelle sicher, dass icon.ico im Projektverzeichnis liegt.
    echo Verknüpfung wird ohne benutzerdefiniertes Icon erstellt.
    set ICON_PATH=
) else (
    echo Icon-Datei gefunden.
)

set SCRIPT=%TEMP%\create_jarvis_shortcut.vbs
echo Set oWS = WScript.CreateObject("WScript.Shell") > %SCRIPT%
echo sLinkFile = "%USERPROFILE%\Desktop\JARVIS.lnk" >> %SCRIPT%
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> %SCRIPT%
echo oLink.TargetPath = "%SCRIPT_DIR%start_jarvis.bat" >> %SCRIPT%
echo oLink.WorkingDirectory = "%SCRIPT_DIR%" >> %SCRIPT%

:: Setze das Icon nur, wenn der Pfad gültig ist
if defined ICON_PATH (
    echo oLink.IconLocation = "%ICON_PATH%, 0" >> %SCRIPT%
) else (
    echo ' Kein Icon-Pfad definiert, verwende Standard-Icon >> %SCRIPT%
)

echo oLink.Description = "JARVIS - KI-Assistent" >> %SCRIPT%
echo oLink.Save >> %SCRIPT%

echo VBS-Script wird erstellt: %SCRIPT%
:: echo Inhalt des VBS-Scripts:
:: type %SCRIPT%

echo Führe VBS-Script aus...
"C:\Windows\System32\cscript.exe" /nologo %SCRIPT%

if exist "%USERPROFILE%\Desktop\JARVIS.lnk" (
    echo Desktop-Verknüpfung wurde erfolgreich erstellt oder aktualisiert!
) else (
    echo Fehler: Desktop-Verknüpfung konnte nicht erstellt werden!
)

del %SCRIPT%
echo.
echo Drücken Sie eine beliebige Taste zum Beenden...
pause > nul 