# PowerShell Script zum Starten von JARVIS

# Pfad zur virtuellen Umgebung (bitte ggf. anpassen)
$venvPath = "C:\python\venv_py311"

# Pfad zum Python Interpreter in der venv
$pythonExe = Join-Path $venvPath "Scripts\python.exe"

# Prüfen, ob der Python Interpreter existiert
if (-not (Test-Path $pythonExe)) {
    Write-Error "FEHLER: Python Interpreter nicht in '$venvPath' gefunden!"
    Write-Host "Stelle sicher, dass die virtuelle Umgebung korrekt erstellt wurde."
    Read-Host "Drücke Enter zum Beenden..."
    exit 1
}

# ChromaDB Telemetrie deaktivieren (nur für diese Sitzung)
$env:ANONYMIZED_TELEMETRY = "False"
Write-Host "ChromaDB Telemetrie deaktiviert."

# Aktuelles Verzeichnis als Arbeitsverzeichnis verwenden (wichtig!)
$scriptPath = Split-Path -parent $MyInvocation.MyCommand.Definition
Set-Location $scriptPath
Write-Host "Arbeitsverzeichnis gesetzt auf: $scriptPath"

# JARVIS starten
Write-Host "DEBUG: Variable pythonExe = $pythonExe"
Write-Host "Starte JARVIS mit Interpreter: $pythonExe ..."
try {
    # Führe Python aus (Versuch 1: Weiterhin mit & Operator)
    & $pythonExe jarvis.py

    # Alternativer Versuch mit Start-Process (auskommentiert):
    # Start-Process -FilePath $pythonExe -ArgumentList "jarvis.py" -Wait -NoNewWindow

    # $LASTEXITCODE enthält den Exit-Code von Python
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "JARVIS wurde mit Fehlercode $LASTEXITCODE beendet."
    } else {
        Write-Host "JARVIS wurde normal beendet."
    }
} catch {
    Write-Error "FEHLER beim Ausführen von jarvis.py:"
    Write-Error $_ # Gibt die komplette Fehlermeldung aus
}

# Pause am Ende, damit das Fenster nicht sofort schließt
Read-Host "Drücke Enter zum Schließen des Fensters..." 