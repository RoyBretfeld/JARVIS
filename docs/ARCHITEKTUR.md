# Systemarchitektur

## Übersicht

JARVIS ist ein modulares System, das aus mehreren Hauptkomponenten besteht, die über definierte Schnittstellen kommunizieren. Die Architektur folgt dem Prinzip der lose gekoppelten Komponenten, was eine einfache Erweiterung und Wartung ermöglicht.

## Verzeichnisstruktur

```
JARVIS/
├── data/                    # Daten und Konfiguration
│   ├── config/             # Konfigurationsdateien
│   ├── models/             # Modell-Dateien
│   └── knowledge/          # Wissensbasis
├── src/                    # Quellcode
│   ├── audio/             # Audio-Verarbeitung
│   ├── gui/               # Benutzeroberfläche
│   ├── llm/               # Sprachmodell-Integration
│   └── utils/             # Hilfsfunktionen
└── docs/                  # Dokumentation
```

## Komponentenarchitektur

### 1. GUI-Layer (src/gui/)
- **MainWindow**: Zentrale Steuerungskomponente
  - Verantwortlich für die Benutzeroberfläche
  - Koordiniert die Interaktion zwischen Subsystemen
  - Implementiert das Observer-Pattern für Ereignisse

### 2. Audio-Layer (src/audio/)
- **AudioProcessor**: Verarbeitet Roh-Audiodaten
  - Implementiert Signalverarbeitung
  - Handhabt Audio-Formatierung
  - Bietet Schnittstelle für Audio-Streaming

- **TTSManager**: Text-zu-Sprache Konvertierung
  - Verwendet Piper für Sprachsynthese
  - Unterstützt SSML für gemischte Sprache
  - Implementiert Caching für Performance

- **WhisperRecognizer**: Spracherkennung
  - Nutzt Whisper für Transkription
  - Unterstützt verschiedene Sprachen
  - Bietet Konfigurationsoptionen

### 3. LLM-Layer (src/llm/)
- **LLMManager**: Verwaltet LLM-Interaktionen
  - Unterstützt verschiedene LLM-Provider
  - Implementiert Kontext-Management
  - Handhabt Prompt-Engineering

- **LearningManager**: Wissensbasis
  - Speichert und verwaltet Kontext
  - Implementiert Retrieval-Augmented Generation
  - Bietet Schnittstelle für Wissensaktualisierung

### 4. Learning/Processing Layer (src/learning/)
- **audiobook_learning.py**: Modul zur Verarbeitung von Hörbüchern
  - Verantwortlich für das Laden und Verarbeiten von MP3-Dateien.
  - Nutzt `pydub` zum Laden und Chunking von Audio.
  *Benötigt `ffmpeg` oder `avconv` für MP3-Unterstützung.*
  - Ruft `WhisperRecognizer` zur Transkription der Chunks auf.
  - Übergibt die Transkripte chunkweise an den `LearningManager`.
  - Enthält Logik zum rekursiven Durchsuchen von Ordnern (`find_and_process_audio_in_folder`).
  - Wird über `AudiobookImportThread` (in `src/gui/main_window.py`) im Hintergrund ausgeführt.

## Datenfluss

### Spracheingabe
1. Audio wird vom Mikrofon aufgenommen
2. AudioProcessThread verarbeitet die Daten
3. WhisperRecognizer transkribiert die Sprache
4. TextProcessingThread verarbeitet den Text
5. LLMManager generiert eine Antwort
6. TTSManager konvertiert die Antwort in Sprache

### Texteingabe
1. Benutzer gibt Text ein
2. TextProcessingThread verarbeitet den Text
3. LLMManager generiert eine Antwort
4. TTSManager konvertiert die Antwort in Sprache

### Hörbuch-Import
1. Benutzer wählt einen Ordner über den Button "Audiobücher lernen (Ordner)" in der GUI (`MainWindow`).
2. `MainWindow` startet den `AudiobookImportThread`.
3. `AudiobookImportThread` ruft `find_and_process_audio_in_folder` (in `audiobook_learning.py`).
4. `find_and_process_audio_in_folder` durchsucht den Ordner rekursiv nach MP3-Dateien.
5. Für jede neue MP3-Datei wird `process_audiobook` aufgerufen.
6. `process_audiobook` lädt die MP3, zerlegt sie in Chunks und erstellt temporäre WAV-Dateien.
7. `WhisperRecognizer` transkribiert jeden WAV-Chunk.
8. `LearningManager` speichert jeden transkribierten Chunk mit Metadaten in der Wissensbasis (ChromaDB).
9. `AudiobookImportThread` sendet Status-Updates an die `MainWindow`.

## Konfiguration

Die Konfiguration erfolgt über JSON-Dateien im `data/config/` Verzeichnis:
- `config.json`: Hauptkonfiguration
- `llm_config.json`: LLM-spezifische Einstellungen
- `audio_config.json`: Audio-Einstellungen

## Erweiterbarkeit

Das System ist durch folgende Mechanismen erweiterbar:
- Plugin-System für neue Funktionalitäten
- Modulare Provider-Architektur für LLMs
- Konfigurierbare Audio-Pipeline
- Anpassbare Wissensbasis

## Sicherheit

- Konfigurationsdateien werden verschlüsselt gespeichert
- API-Keys werden sicher verwaltet
- Benutzerdaten werden lokal gespeichert
- Netzwerkkommunikation ist verschlüsselt 