# JARVIS Projekt - Fortschrittsdokumentation

## Aktuelle Umgebung
- Python 3.10
- CUDA 11.8
- PyTorch mit GPU-Unterstützung
- Faster-Whisper (GPU-optimiert)

## Implementierte Komponenten
- [x] GUI mit Qt5
- [x] Audioaufnahme-System
- [x] Whisper Integration
- [x] GPU-Unterstützung
- [x] System-Monitor
- [x] Debug-Monitor
- [x] Mikrofonauswahl und -speicherung
- [x] Lokale Modell-Verwaltung
- [x] Feedback-System (positiv/negativ) für LLM & River Intent
- [x] Prompt-Editor in GUI

## Feature: Hörbuch-Lernen aus Ordnern (26.04.2024)
- [x] **UI-Integration:** Button "Audiobücher lernen (Ordner)" in `MainWindow` hinzugefügt.
- [x] **Ordnerauswahl:** `QFileDialog.getExistingDirectory` implementiert.
- [x] **Hintergrundverarbeitung:** `AudiobookImportThread` (in `MainWindow`) implementiert, um die UI nicht zu blockieren.
- [x] **Rekursive Suche:** Funktion `find_and_process_audio_in_folder` in `audiobook_learning.py` hinzugefügt, die Ordner rekursiv nach MP3s durchsucht (`os.walk`).
- [x] **Audio-Verarbeitung:** Modul `src/learning/audiobook_learning.py` erstellt/angepasst:
    - Lädt MP3s mit `pydub`. **Abhängigkeit: `pydub` und `ffmpeg/avconv` müssen installiert sein.**
    - Teilt Audio in Chunks definierter Länge.
    - Konvertiert Chunks zu temporären WAV-Dateien (Mono, 16kHz).
- [x] **Transkription:** Ruft `WhisperRecognizer` für jeden Audio-Chunk auf.
- [x] **Speicherung:** Übergibt transkribierte Chunks mit Metadaten (Quelle, Chunk-Index etc.) an den `LearningManager` zum Speichern in ChromaDB.
- [x] **Status-Updates:** Thread sendet Fortschrittsmeldungen (`yield` / `pyqtSignal`) an die Statusleiste der `MainWindow`.
- [x] **Dublettenprüfung:** Einfache Prüfung implementiert, um bereits verarbeitete Dateien (laut Log-Datei oder DB-Eintrag) zu überspringen.

## Test Scripts
- `verify_gpu.py`: Überprüft GPU-Verfügbarkeit
- `gpu_cpu_test.py`: Benchmark für GPU vs CPU

## Aktuelle Tasks
- [x] CUDA Installation
- [x] System Neustart
- [x] GPU-Benchmarks durchgeführt
- [x] Mikrofonauswahl verbessert
- [x] Aufnahme-Button Farbgebung optimiert
- [x] Debug-Monitor implementiert
- [x] Whisper-Erkennung optimiert
- [x] Audio-Verarbeitung verbessert

## Benchmark Ergebnisse
- GPU Durchschnittszeit: 1.66 Sekunden
- CPU Durchschnittszeit: 3.22 Sekunden
- Geschwindigkeitsvorteil GPU: ~1.9x

## Aktuelle Änderungen (30.03.2024)
- Whisper-Modell Anzeige in der Sidebar implementiert
- Upgrade auf large-v2 Modell für verbesserte Genauigkeit
- Performance-Test und überflüssige Debug-Ausgaben entfernt
- GUI-Layout optimiert für bessere Übersichtlichkeit
  - Kompaktere Nachrichtendarstellung
  - Reduzierte Abstände und Schriftgrößen
  - Verbesserte Platznutzung

## Nächste Schritte (geplant)
- [ ] LLM Integration für Konversation
  - API-Anbindung (OpenAI/GPT)
  - Konversationsmanagement
  - Streaming-Antworten
  - Sichere API-Key Verwaltung

## Bekannte Probleme
- [x] Whisper Modell-Initialisierung optimiert
- [x] GPU-Nutzung verbessert
- [x] Modell-Status Anzeige implementiert
- [ ] Konversationsfähigkeit noch nicht implementiert

## Performance
- Whisper large-v2 Modell
  - Verbesserte Genauigkeit (~40-50% besser als small)
  - VRAM Nutzung: ~4.5-6 GB
  - Optimiert für NVIDIA RTX 4080

## Aktuelle Status
1. Modell-Verwaltung:
   - Lokale Speicherung implementiert
   - Automatische Modell-Erkennung
   - Konfigurationsspeicherung
   - Download-Management

2. GPU-Integration:
   - CUDA-Optimierungen aktiviert
   - Explizite GPU-Übertragung
   - Performance-Monitoring
   - Speicher-Management

3. Spracherkennung:
   - Whisper-Modell "small" aktiv
   - Optimierte Parameter
   - Verbesserte Fehlerbehandlung

## Optimierungspotential
1. Performance:
   - GPU-Auslastung optimieren
   - Batch-Verarbeitung implementieren
   - Modell-Caching verbessern

2. Audio-Qualität:
   - Rauschunterdrückung implementieren
   - Automatische Gain-Kontrolle
   - Silence Detection verbessern

3. Modell-Management:
   - Modell-Updates implementieren
   - Verschiedene Modellgrößen unterstützen
   - Konfigurationsbackup erstellen

## Hilfreiche Befehle
```bash
# Virtuelle Umgebung aktivieren
.\venv_py310_gpu\Scripts\activate

# CUDA Verfügbarkeit testen
python -c "import torch; print(torch.cuda.is_available())"

# Anwendung starten
python jarvis.py

# Schnellstart über Desktop-Verknüpfung
start_jarvis.bat

# GPU-Status überprüfen
nvidia-smi

# CUDA-Version anzeigen
nvcc --version

# Modell-Verzeichnis anzeigen
dir data\models\whisper
```

## Nächste Schritte
1. GPU-Auslastung analysieren
2. Performance-Profiling durchführen
3. Audioqualität verbessern
4. Modell-Update-System implementieren
5. Backup-System für Modelle erstellen

## Debug-Informationen
- Modell wird lokal gespeichert
- GPU wird für Berechnungen genutzt
- Speichernutzung wird überwacht
- Performance-Metriken werden gesammelt
- Modell-Konfiguration wird dokumentiert
- Audio-Stream wird korrekt verarbeitet
- Chunk-Größe: 4096 Samples
- Sample-Rate: 44.1 kHz
- Aufnahmedauer wird getrackt
- GPU-Status wird überwacht

# Fortschritt JARVIS

## 05.04.2025 - Aktueller Stand

### Kernfunktionalität (Stufe 1) - Status:
✅ **Erfolge:**
- LLM antwortet jetzt konsistent auf Deutsch (Konfigurations- und Prompt-Anpassungen waren erfolgreich).
- Aufnahme lässt sich korrekt starten und stoppen (Button-Logik und Thread-Handling korrigiert).
- Whisper-Modell-Initialisierung verbessert (korrekte Pfad-/Cache-Verwendung).
- LLaMA-Verbindungsstatus wird korrekt angezeigt (`check_connection` implementiert).
- Konfigurationshandling (`config.json`, `Config`-Klasse) robuster gestaltet.

🚧 **Offene Probleme / Nächste Schritte (Stufe 1):**
1.  **Fehlerhafte Whisper-Transkription:** Gibt konstant falschen Text aus ("Untertitel der Amara.org-Community"). **-> Untersuchung nötig (Audioqualität, VAD, Modellparameter?).**
2.  **Fehler bei Ähnlichkeitssuche:** `ValueError: The truth value of an array... ambiguous` tritt in `ConversationArchive.search_similar` (oder `LearningManager.find_similar`) auf. **-> Debugging mit hinzugefügten Logs erforderlich.**
3.  **Falscher LLM-Kontext:** Irrelevante Informationen ("Stephanie Geiges") gelangen in den LLM-Kontext, wahrscheinlich durch die fehlerhafte Ähnlichkeitssuche. **-> Sollte sich nach Behebung von Punkt 2 klären.**

### Sicherheit (Stufe 2) - Geplant:
- Implementierung der offenen Protokolle aus `Sicherheit.txt`.
- Vollständige Integration des `SafetyManager`.

### Sprachausgabe (Stufe 3) - Geplant:
- Integration einer Text-to-Speech (TTS) Komponente.

## 01.04.2025 - Aktueller Stand (Ende des Tages)

### Erreicht:
- GUI-System erweitert und verbessert
  - Vergrößertes Fenster (1000x800)
  - Separate Prompt-Editor Sektion
  - Verbesserte Status-Anzeigen
  - Neues Dark Theme
- Whisper-Integration erfolgreich (Modell: large-v2)
- LLaMA-Verbindung hergestellt
- Mikrofon-Auswahl und Audio-System implementiert
- Konversationsarchiv und Lernmanager integriert
- Ladebildschirm für bessere Benutzerführung

### Bekannte Probleme:
- System-Monitor Widget Fehler
- Initialisierungsreihenfolge muss optimiert werden
- Sprachmischung in LLaMA-Antworten (Deutsch/Englisch)
- Feinabstimmung der Konversationsarchivierung nötig

### Sicherheitsprotokolle - Status:
✅ Implementiert:
- Verschlüsselung der gespeicherten Lernmetriken
- Grundlegende Zugriffskontrollen
- Basis-Fehlerbehandlung

⏳ In Bearbeitung:
- Feedback-Kontrollsystem
- Anomalie-Erkennung
- Ethik-Check für Antworten

📋 Noch zu implementieren:
- Automatische Inhaltsfilterung
- Erweiterte Warnsysteme
- DSGVO-Compliance-System
- Automatisierte Sicherheitsberichte

### Nächste Schritte:
1. System-Monitor-Fehler beheben
2. Initialisierungsreihenfolge optimieren
3. Deutsche Sprachausgabe verbessern
4. Implementierung der ausstehenden Sicherheitsprotokolle 

# JARVIS Troubleshooting Fortschritt (Stand: 08.04.2025 Abend)

## Problembeschreibung

JARVIS startet nicht vollständig. Die Anwendung scheint während der Initialisierung des `LearningManager` zu hängen, speziell bei der erstmaligen Migration von Daten aus der alten `data/learning/knowledge_base.json` (enthält 90 Einträge) in die neue ChromaDB-Datenbank (`data/knowledge_base/chroma_db`).

## Beobachtungen

*   Die Logs zeigen, dass der `LearningManager` die JSON-Datei lädt, das Embedding-Modell initialisiert und die Embeddings für den ersten (und einzigen) Batch generiert.
*   Die letzte Log-Meldung vor dem Stillstand ist typischerweise `INFO - Füge X Einträge zu ChromaDB hinzu (Batch 1)...`.
*   Der Aufruf `self.collection.add(...)` zum Schreiben der Daten in die ChromaDB scheint zu blockieren oder sehr lange zu dauern, ohne dass weitere Logs (auch die neu hinzugefügten) erscheinen.
*   Der ChromaDB-Ordner (`data/knowledge_base/chroma_db`) enthält zwar initialisierte Dateien (`chroma.sqlite3`), aber die Migration der 90 Einträge scheint nicht abgeschlossen zu werden.
*   Die `knowledge_base.json` wurde überprüft und die Struktur der Einträge scheint korrekt zu sein.

## Letzte durchgeführte Maßnahmen

1.  **Detaillierteres Logging:** Zusätzliche Log-Ausgaben wurden in `src/llm/learning_manager.py` um die `self.collection.add(...)`-Aufrufe in der Migrationsschleife hinzugefügt, um den Fortschritt oder Fehler besser verfolgen zu können.
2.  **Batch-Größe reduziert:** Die `batch_size` für die Migration wurde von 100 auf 10 reduziert, um die Last pro Schreibvorgang zu verringern.
3.  **Pause hinzugefügt:** Eine kurze Pause (`time.sleep(0.1)`) wurde nach jedem erfolgreichen Batch-Schreibvorgang eingefügt.

## Nächste Schritte (09.04.2025)

1.  **JARVIS neu starten:** Die Anwendung soll mit `start_jarvis.bat` erneut gestartet werden.
2.  **Logs analysieren:** Die durch den Neustart erzeugten Logs müssen genau analysiert werden. Ziel ist es zu sehen, ob:
    *   Die Migration nun Batch für Batch (1 bis 9) fortschreitet, wie durch das neue Logging angezeigt wird.
    *   Der Prozess immer noch an einer bestimmten Stelle (z.B. bei einem spezifischen Batch oder immer beim ersten `add`-Aufruf) hängt.
    *   Neue Fehlermeldungen im Zusammenhang mit ChromaDB oder dem Daten-Hinzufügen auftreten.
3.  **Abhängig von den Logs:** Weitere Schritte planen (z.B. Untersuchung von ChromaDB-Konflikten, Dateisystemberechtigungen, Ressourcenlimits oder Testen der Migration mit noch weniger Daten).

## Update (09.04.2025 Abend)

*   Das ursprüngliche Problem lag nicht bei der Migration selbst, sondern beim Initialisieren/Erstellen der ChromaDB Collection (`client.get_or_create_collection`).
*   Das Löschen des alten `data/knowledge_base/chroma_db`-Verzeichnisses behob dieses Problem, aber die Migration hing weiterhin beim ersten `collection.add`-Aufruf.
*   Um das ChromaDB-Problem zu isolieren, wurde die Initialisierung des `LearningManager` zuerst in `MainWindow` und dann im `LLMManager` (wo sie tatsächlich stattfand) auskommentiert.
*   Danach traten kleinere Fehler auf (`logger` nicht definiert, `update_chat_display` statt `add_chat_message`, `app.exec_` statt `app.exec`, fehlender `pyaudio` Import, fehlende `window.show()`-Zeilen), die alle behoben wurden.
*   JARVIS startete danach, die Aufnahme funktionierte, aber die Whisper-Transkription schlug fehl mit `Could not locate cudnn_ops64_9.dll`.
*   Die `PATH`-Variable war korrekt gesetzt, aber es stellte sich heraus, dass **alte cuDNN v8 DLLs** *zusammen mit* den neuen **cuDNN v9 DLLs** im CUDA `bin`-Verzeichnis vorhanden waren.
*   Die alten cuDNN v8 DLLs wurden nun **gelöscht**, sodass nur noch die korrekten v9 DLLs vorhanden sind.

## Nächste Schritte (10.04.2025)

1.  **JARVIS neu starten:** Nach dem Bereinigen der CUDA-DLLs muss die Anwendung erneut gestartet werden.
2.  **Whisper-Test:** Überprüfen, ob die Whisper-Transkription jetzt korrekt funktioniert und der `cudnn_ops64_9.dll`-Fehler behoben ist.
3.  **LearningManager Reaktivierung:** Wenn Whisper funktioniert, die Initialisierung des `LearningManager` in `src/llm/llm_manager.py` wieder **einkommentieren**.
4.  **ChromaDB Migration (erneut):** Beobachten, ob der `LearningManager` und die ChromaDB-Migration jetzt erfolgreich durchlaufen, oder ob der ursprüngliche Hänger bei `collection.add` wieder auftritt.

# ChromaDB Troubleshooting (12.04.2025)

## Problembeschreibung (Fortsetzung)

Nachdem die Probleme mit der Whisper/cuDNN-Konfiguration behoben waren, kehrte das ursprüngliche Problem zurück: JARVIS startet nicht vollständig und hängt sich während der Initialisierung des `LearningManager` auf. Der Absturz erfolgt **genau beim Aufruf** von `client.get_or_create_collection(...)` (in Schritt 3 der `__init__`-Methode), ohne dass eine Python-Exception protokolliert wird.

## Beobachtungen

*   Der `LearningManager` initialisiert das Embedding-Modell (Schritt 1) und den `PersistentClient` (Schritt 2) erfolgreich.
*   Die Log-Ausgabe stoppt abrupt nach `DEBUG - Schritt 3: Hole oder erstelle Collection 'jarvis_knowledge'...`.
*   Dies geschieht **unabhängig** davon, ob die Datenbank bereits durch das Migrationsskript erstellt wurde oder nicht.
*   Isolierte Tests (`migrate_json_to_chroma.py`, `test_chromadb.py`) zeigen, dass `get_or_create_collection` prinzipiell funktioniert.
*   Die Initialisierung des `WhisperRecognizer` in `jarvis.py` wurde testweise **deaktiviert**, das Problem bestand jedoch weiterhin.
*   Diverse Import- und Konfigurationsfehler (`NameError`, `ModuleNotFoundError`, `KeyError`) wurden während der Tests behoben.

## Aktueller Stand (12.04.2025 - Nachmittag)

*   Der `LearningManager` stürzt weiterhin bei `get_or_create_collection` ab, selbst wenn Whisper deaktiviert ist.
*   Alle notwendigen Konfigurationseinträge (`config.json`) und Python-Imports (`jarvis.py`) sind korrigiert.
*   Die virtuelle Umgebung (`venv_py311`) ist korrekt und die notwendigen Pakete (`chromadb`, `PyQt6` etc.) sind installiert.
*   **Hypothese:** Es besteht weiterhin ein Konflikt oder ein Ressourcenproblem im Kontext der laufenden JARVIS-Anwendung, das in den isolierten Skripten nicht auftritt. Möglicherweise Interferenzen mit anderen Bibliotheken (PyQt?, PyAudio?), Threading-Problemen oder Low-Level-Konflikten.

## Nächste Schritte (Bei Fortsetzung)

1.  **Weitere Komponenten deaktivieren:** Testweise die Initialisierung anderer Dienste in `jarvis.py` (z.B. `TTSManager`, `AudioProcessor`, ggf. sogar Teile der PyQt-App) auskommentieren, um den Konflikt weiter einzugrenzen.
2.  **Initialisierungsreihenfolge ändern:** Versuchen, den `LearningManager` zu einem anderen Zeitpunkt im `main`-Ablauf von `jarvis.py` zu initialisieren.
3.  **ChromaDB Debugging:** Tiefer in die ChromaDB-Bibliothek selbst schauen (falls möglich) oder deren Logging (falls vorhanden) erhöhen, um zu sehen, was intern beim `get_or_create_collection`-Aufruf passiert.
4.  **Minimalbeispiel in `jarvis.py`:** Ein extrem vereinfachtes ChromaDB-Setup direkt in `jarvis.py` (vor der App-Erstellung) versuchen, um zu sehen, ob das Problem auch dort auftritt.

## Fehlerbehebung (13.04.2025)

*   **ChromaDB v1.0.4 Bug:** Identifiziert, dass der stille Absturz beim Collection-Zugriff (`get_collection`/`get_or_create_collection`) innerhalb von `LearningManager` spezifisch für ChromaDB v1.0.4 im Kontext von `jarvis.py` auftrat.
*   **Downgrade auf v0.4.24:** Erfolgreiches Downgrade auf `chromadb==0.4.24`. Dies behob den stillen Absturz, führte aber zu einem erwarteten `sqlite3.OperationalError` wegen Schema-Inkompatibilität.
*   **Datenbank neu erstellt:** Datenbank und Migrationsmarker gelöscht, Migration mit v0.4.24 erfolgreich durchgeführt.
*   **`LearningManager` funktioniert:** Initialisierung des `LearningManager` (mit deaktivierten anderen Komponenten) funktioniert jetzt mit v0.4.24.
*   **`TypeError` in `TTSManager`:** Behoben durch Korrektur des Parameternamens (`piper_executable_path` statt `piper_path`) beim Aufruf in `jarvis.py`.
*   **`TypeError` in `LLMManager` (Aktuell):** Beim Reaktivieren des `LLMManager` tritt `TypeError: get expected at most 2 arguments, got 3` auf. Ursache: `LLMManager` wurde mit dem rohen `config_data`-Dictionary statt mit der `Config`-Klasseninstanz (`config_manager`) initialisiert, die eine eigene `get`-Methode mit 3 Argumenten hat.
*   **Nächster Schritt:** Korrektur des `LLMManager`-Aufrufs in `jarvis.py` zur Übergabe der `config_manager`-Instanz. **(Erledigt am 18.04.2025)**

## Fehlerbehebung (18.04.2025)

*   **`TypeError` in `jarvis.py`:** Behoben. Der Aufruf von `MainWindow()` wurde korrigiert, um die erforderlichen Manager-Instanzen (`config_manager`, `llm_manager`, `audio_manager`, `learning_manager`) zu übergeben. Zuvor fehlten diese Argumente, was zu einem `TypeError` führte.
*   **`NameError` / `AttributeError` in `main_window.py`:** Behoben. Nach UI-Umbau fehlten Definitionen von UI-Gruppen (`control_group` etc.) und die DB-Größenanzeige griff auf ein veraltetes Label zu. Die UI-Initialisierung und die Update-Methode wurden korrigiert.
*   **Aktueller Stand:** JARVIS sollte nun die Initialisierungsphase ohne die zuletzt aufgetretenen `TypeError`, `NameError` oder `AttributeError` durchlaufen.

# Veralteter Code-Schnipsel (Beispiel)
# MainWindow OHNE Argumente aufrufen
# main_window = MainWindow() 

## 06.04.2025 - Aktuelle Änderungen

### Audio-System Verbesserungen:
1. **AudioProcessThread:**
   - Implementierung des `update_visualization` Signals
   - Verbesserte Fehlerbehandlung bei der Aufnahme
   - Optimierte Stream-Verwaltung mit `exception_on_overflow=False`
   - Echtzeit-Visualisierung der Audiodaten
   - Cleanup-Prozess für Stream und PyAudio-Instanz

2. **AudioProcessor:**
   - Verbesserte Audioverarbeitung
   - Rauschunterdrückung und Filterung
   - Dynamische Kompression
   - Normalisierung der Lautstärke
   - Robustere Fehlerbehandlung

### GUI-Verbesserungen:
- Echtzeit-Visualisierung der Audioaufnahme
- Verbesserte Status-Anzeigen
- Optimierte Fehlermeldungen

### Nächste Schritte:
1. **Audio-System:**
   - Integration mit Whisper-Modell
   - Verbesserung der Audioqualität
   - Optimierung der Verarbeitungspipeline

2. **Spracherkennung:**
   - Korrektur der Whisper-Transkription
   - Anpassung der Modellparameter
   - Verbesserung der VAD (Voice Activity Detection)

3. **LLM-Integration:**
   - Korrektur der Ähnlichkeitssuche
   - Optimierung des Kontext-Managements
   - Verbesserung der Antwortqualität 

# Fortschrittsdokumentation JARVIS

## 19.04.2025 - Aktueller Stand

### Implementierte Funktionen

1. **Wetter-Widget**
   - Integration der OpenWeatherMap API
   - Automatische Aktualisierung alle 5 Minuten
   - Anzeige von:
     - Aktueller Zeit
     - Stadt
     - Temperatur
     - Gefühlte Temperatur
     - Wetterbeschreibung
     - Luftfeuchtigkeit
     - Windgeschwindigkeit
   - Caching-System zur Optimierung der API-Aufrufe

2. **System-Ressourcen-Widget**
   - Echtzeit-Monitoring von:
     - CPU-Auslastung
     - RAM-Nutzung (in % und GB)
     - GPU-Auslastung (falls verfügbar)
   - Aktualisierung alle 2 Sekunden

3. **UI-Verbesserungen**
   - Optimierte Widget-Breiten (250px)
   - Verbesserte Lesbarkeit der Optionen
   - Konsistentes Styling aller Widgets
   - Entfernung des ML-Status-Widgets

4. **Internet-Modus**
   - Toggle-Funktion für Online/Offline-Modus
   - Visuelle Statusanzeige

### Nächste Schritte

1. **Wetter-Widget Erweiterungen**
   - Implementierung von Wettervorhersagen
   - Hinzufügen von Wetter-Icons
   - UV-Index und Regenwahrscheinlichkeit

2. **System-Monitoring**
   - Erweiterung um Festplattennutzung
   - Netzwerkaktivität
   - Prozessanzahl
   - Temperatur-Monitoring

3. **UI-Optimierungen**
   - Responsive Layout-Anpassungen
   - Dark/Light Mode Toggle
   - Verbesserte Fehlerbehandlung

4. **Dokumentation**
   - API-Dokumentation vervollständigen
   - Installationsanleitung erstellen
   - Troubleshooting-Guide

### Bekannte Probleme

1. **Wetter-Widget**
   - Keine bekannten Probleme

2. **System-Monitoring**
   - GPU-Informationen nicht auf allen Systemen verfügbar

3. **UI**
   - Keine bekannten Probleme

### Technische Details

- **API-Limits**: OpenWeatherMap (1000 Aufrufe/Tag)
- **Cache-Dauer**: 5 Minuten
- **Update-Intervalle**:
  - Wetter: 5 Minuten
  - System: 2 Sekunden
  - Datenbank: 10 Sekunden

### Konfiguration

- OpenWeatherMap API-Key konfiguriert
- Stadt: Dresden, 01139, DE
- Einheiten: Metrisch
- Sprache: Deutsch 