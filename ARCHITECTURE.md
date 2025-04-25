# JARVIS Projekt - Architekturübersicht

## 1. Einleitung / Projektziel

JARVIS ist ein sprachgesteuerter KI-Assistent mit dem Ziel, natürliche Konversation zu ermöglichen und dabei kontinuierlich aus Interaktionen zu lernen. Er soll lokal auf dem Benutzergerät laufen und verschiedene Aufgaben durch Sprachbefehle erledigen können.

## 2. Kernkomponenten

Die Architektur von JARVIS basiert auf mehreren modularen Komponenten:

-   **GUI (`src/gui`):**
    -   Technologie: PyQt6
    -   Verantwortlich für die Benutzeroberfläche (`MainWindow`), Interaktionselemente (Buttons, Textfelder), Statusanzeigen und Debug-Informationen.
-   **Konfiguration (`config.py`, `config.json`, `src/config/api_config.py`):**
    -   Lädt allgemeine Einstellungen (Pfade, etc.) aus `config.json` über die `Config`-Klasse in `config.py`.
    -   Die `Config`-Klasse bietet eine `.get()`-Methode zum einfachen Zugriff.
    -   `src/config/api_config.py` definiert eine `APIConfig`-Klasse (dataclass) speziell für API-Parameter (z.B. Modellname, Temperatur), die über `api_settings.json` geladen werden kann (aktuell ggf. nicht direkt von allen Managern genutzt).
-   **Audio-Eingabe (`src/audio/audio_thread.py`, `src/audio/audio_processor.py`):
    -   `AudioProcessThread` (nutzt PyAudio) für die Aufnahme in separatem Thread.
    -   `AudioProcessor` koordiniert Aufnahme, Speicherung und ggf. Vorverarbeitung.
-   **Spracherkennung (ASR - `src/speech/whisper_recognition.py`):**
    -   Technologie: `faster-whisper` (GPU-optimiert, Modell `large-v2`).
    -   Wandelt die aufgenommenen Audiodaten in Text (Transkript) um.
-   **LLM Interaktion (`src/llm/llm_manager.py`):**
    -   Erhält das Haupt-`Config`-Objekt bei der Initialisierung für den Zugriff auf allgemeine Einstellungen (z.B. Pfade, Ollama URL).
    -   Initialisiert intern den `LearningManager` und `ConversationArchive`.
    -   Kommuniziert mit einem lokalen LLM über die Ollama API.
    -   Holt relevanten Kontext aus dem `LearningManager` und `ConversationArchive`.
    -   Erstellt den finalen Prompt für das LLM.
    -   Verarbeitet die Antwort des LLM (inkl. Sicherheitscheck über `SafetyManager`).
-   **Lernen / Gedächtnis (`src/llm/learning_manager.py`):**
    -   Wird intern vom `LLMManager` initialisiert.
    -   Benötigt aktuell keine externe Konfiguration beim Start (verwendet interne Konstanten für Pfade/Modelle).
    -   Technologie: Vektordatenbank ChromaDB (`v0.4.24`) für Persistenz.
    -   Nutzt Sentence Transformers (`paraphrase-multilingual-MiniLM-L12-v2`) zur Erstellung von Embeddings für Texte.
    -   Speichert und ruft Konversationsteile oder explizit Gelerntes basierend auf semantischer Ähnlichkeit ab.
-   **Konversationsarchiv (`src/llm/conversation_archive.py`):**
    -   Wird intern vom `LLMManager` initialisiert.
    -   Speichert vollständige Konversationsverläufe als JSON-Dateien.
    -   Ermöglicht die Suche nach ähnlichen vergangenen Konversationen.
-   **Sprachausgabe (TTS - `src/audio/tts_manager.py`):**
    -   Technologie: Piper TTS (via Aufruf der externen `piper.exe`).
    -   Wandelt die Textantwort des LLM in hörbare Sprache um.
-   **Sicherheit (`src/llm/safety_manager.py`):**
    -   Wird intern vom `LLMManager` initialisiert.
    -   Prüft Eingaben und LLM-Antworten auf Basis konfigurierbarer Regeln (`config/safety_rules.json`).

## 3. Technologie-Stack

-   **Programmiersprache:** Python 3.11 (aktiv in `venv_py311`)
-   **GUI:** PyQt6
-   **Vektordatenbank / Suche:** ChromaDB
-   **Embedding Modell:** Sentence Transformers (`paraphrase-multilingual-MiniLM-L12-v2`)
-   **ASR (Spracherkennung):** Faster Whisper (`large-v2`)
-   **LLM Backend:** Ollama (lokal, z.B. mit Llama 3)
-   **TTS (Sprachausgabe):** Piper TTS (extern)
-   **Audio I/O:** PyAudio
-   **Audio-Verarbeitung:** SoundFile, Librosa
-   **Abhängigkeiten:** NumPy, etc. (siehe `requirements.txt`, falls vorhanden)

## 4. Datenfluss (Vereinfacht)

1.  **Aufnahme:** Nutzer spricht -> `AudioProcessThread` (PyAudio) nimmt auf.
2.  **Verarbeitung:** Rohe Audiodaten -> `AudioProcessor`.
3.  **Transkription:** Audiodaten -> `WhisperRecognizer` -> Text (Transkript).
4.  **Kontext & Prompt:** Transkript -> `LLMManager` -> Fragt `LearningManager` & `ConversationArchive` nach Kontext -> Erstellt Prompt.
5.  **Generierung:** Prompt -> Ollama (LLM) -> Text (Antwort).
6.  **Antwortverarbeitung:** Antwort -> `LLMManager` prüft mit `SafetyManager` -> Sichere Antwort.
7.  **Sprachausgabe:** Sichere Antwort -> `TTSManager` -> Piper -> Audio-Ausgabe.
8.  **Lernen:** Gesprächspaar (Frage/Antwort) -> `LearningManager` -> Speichert in ChromaDB.
9.  **Archivierung:** Konversationsverlauf -> `ConversationArchive` -> Speichert als JSON.
10. **GUI Update:** Statusmeldungen, Chat-Verlauf etc. -> `MainWindow`.

## 5. Verzeichnisstruktur (Überblick)

```
JARVIS/
│
├── src/                     # Hauptquellcode
│   ├── gui/
│   ├── llm/
│   ├── audio/
│   ├── speech/
│   ├── config/              # Spezifische Konfigurationsklassen (z.B. APIConfig)
│   └── (safety/ ?)
│
├── data/                    # Anwendungsdaten
│   ├── knowledge_base/      # ChromaDB Datenbank
│   ├── learning/            # JSON-Backup, Migrationsmarker
│   ├── models/              # Lokale Modelle (Whisper, TTS, Embeddings)
│   └── audio/               # Aufnahmen, TTS-Ausgaben (temporär?)
│
├── scripts/                 # Hilfsskripte (Migration, Tests)
├── tests/                   # Unit-/Integrationstests
├── logs/                    # Log-Dateien
├── assets/                  # Icons, Bilder
├── piper/                   # Externe Piper TTS Anwendung
│
├── config.json              # Haupt-Konfigurationsdatei
├── config.py                # Klasse zum Verwalten der Haupt-Konfiguration
├── jarvis.py                # Haupteinstiegspunkt der Anwendung
├── FORTSCHRITT.md           # Dieses Dokument
├── ARCHITECTURE.md          # Diese Datei
├── requirements.txt         # (Optional/Empfohlen) Python-Abhängigkeiten
└── README.md                # Projektbeschreibung
```

## 6. Konfigurationsmanagement

-   Die zentrale Konfiguration für allgemeine Einstellungen (Pfade, URLs, etc.) erfolgt über `config.json`.
-   Die Klasse `Config` in `config.py` liest diese Datei und stellt eine `.get(section, key, fallback)`-Methode für den Zugriff bereit.
-   Spezifischere Konfigurationen (z.B. für API-Parameter) können in separaten Klassen wie `APIConfig` in `src/config/` verwaltet werden, die eigene Lade-/Speichermechanismen haben können (z.B. aus `api_settings.json`).
-   Komponenten, die allgemeine Konfigurationen benötigen (wie `LLMManager`), erhalten das `Config`-Objekt bei ihrer Initialisierung.
-   Andere Komponenten (wie `LearningManager`) können intern konfiguriert sein oder spezifische Konfigurationswerte direkt übergeben bekommen.

## 7. Initialisierungsablauf (`jarvis.py`)

1.  **Logging einrichten:** Konfiguriert das Logging-System.
2.  **Haupt-Konfiguration laden:** Erstellt eine Instanz der `Config`-Klasse (aus `config.py`), die `config.json` lädt.
3.  **Learning Manager initialisieren:** Erstellt eine Instanz von `LearningManager`. Benötigt keine externe Konfiguration.
4.  **LLM Manager initialisieren:** Erstellt eine Instanz von `LLMManager`. Übergibt das `Config`-Objekt. Initialisiert intern `LearningManager`, `ConversationArchive` und `SafetyManager`.
5.  **MainWindow erstellen:** Erstellt die Haupt-GUI-Klasse `MainWindow`. Übergibt die Instanzen von `Config`, `LLMManager` und `LearningManager`.
6.  **GUI anzeigen:** Ruft `main_window.show()` auf.
7.  **Event Loop starten:** Startet die Qt-Anwendungs-Event-Loop mit `app.exec()`. 