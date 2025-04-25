import os
import logging
import tempfile
import math
from pydub import AudioSegment
from tqdm import tqdm # Für die Fortschrittsanzeige
from datetime import datetime
import time
# Annahmen: WhisperRecognizer und LearningManager sind relativ zum Projekt-Root importierbar
# Pfade müssen evtl. angepasst werden, wenn das Modul von woanders aufgerufen wird.
try:
    from ..speech.whisper_recognition import WhisperRecognizer
    from ..llm.learning_manager import LearningManager
except ImportError:
    # Fallback für den Fall, dass das Skript direkt ausgeführt wird (testing)
    # Dies erfordert, dass das Skript vom Projekt-Root ausgeführt wird.
    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
    from src.speech.whisper_recognition import WhisperRecognizer
    from src.llm.learning_manager import LearningManager


# Logging konfigurieren (könnte zentralisiert werden)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Standard-Chunk-Länge in Millisekunden (z.B. 60 Sekunden)
DEFAULT_AUDIO_CHUNK_MS = 60 * 1000
# Log-Datei für verarbeitete Hörbücher
PROCESSED_LOG_FILE = "data/learning/processed_audiobooks.log"

# Globale Instanzen (oder besser übergeben?)
# Für den Moment als globale Variablen, um den Start zu vereinfachen.
# TODO: Diese sollten idealerweise von außen injiziert werden.
whisper_recognizer_instance: WhisperRecognizer = None
learning_manager_instance: LearningManager = None

# Konstanten
AUDIOBOOK_TEMP_DIR = "data/temp/audiobook_processing"
CHUNK_LENGTH_MS = 10000  # 10 Sekunden pro Chunk
TARGET_SAMPLE_RATE = 16000 # 16kHz für Whisper
PROCESSED_FILES_LOG = os.path.join(AUDIOBOOK_TEMP_DIR, "processed_files.log")

# Sicherstellen, dass das Temp-Verzeichnis existiert
os.makedirs(AUDIOBOOK_TEMP_DIR, exist_ok=True)

def initialize_dependencies(lm_instance=None, wr_instance=None):
    """Initialisiert globale Abhängigkeiten (Whisper, LearningManager)."""
    global whisper_recognizer_instance, learning_manager_instance

    if lm_instance:
        learning_manager_instance = lm_instance
        logger.info("LearningManager Instanz übergeben.")
    else:
        if learning_manager_instance is None:
             logger.info("Initialisiere neuen LearningManager für Audiobook Processing...")
             learning_manager_instance = LearningManager()
             # TODO: Sicherstellen, dass die Initialisierung erfolgreich war?
             if not learning_manager_instance.collection:
                  logger.error("Konnte LearningManager nicht initialisieren.")
                  return False
             logger.info("Neuer LearningManager initialisiert.")

    if wr_instance:
        whisper_recognizer_instance = wr_instance
        logger.info("WhisperRecognizer Instanz übergeben.")
    else:
        if whisper_recognizer_instance is None:
            logger.info("Initialisiere neuen WhisperRecognizer für Audiobook Processing...")
            # Annahme: WhisperRecognizer kann ohne Argumente initialisiert werden
            # und lädt das Modell selbst. Konfiguration könnte hier fehlen.
            whisper_recognizer_instance = WhisperRecognizer()
            if not whisper_recognizer_instance.model:
                 logger.error("Konnte WhisperRecognizer Modell nicht laden.")
                 return False
            logger.info("Neuer WhisperRecognizer initialisiert.")

    # Prüfen ob beide Instanzen verfügbar sind
    if learning_manager_instance and whisper_recognizer_instance:
         return True
    else:
         logger.error("Abhängigkeiten (LearningManager oder WhisperRecognizer) konnten nicht initialisiert werden.")
         return False

def is_already_processed(mp3_file_path: str) -> bool:
    """Prüft, ob die MP3-Datei bereits verarbeitet wurde (laut Log-Datei)."""
    if not os.path.exists(PROCESSED_LOG_FILE):
        return False
    try:
        with open(PROCESSED_LOG_FILE, 'r', encoding='utf-8') as f:
            processed_files = {line.strip() for line in f}
        return os.path.basename(mp3_file_path) in processed_files
    except Exception as e:
        logger.error(f"Fehler beim Lesen der Log-Datei {PROCESSED_LOG_FILE}: {e}")
        return False # Im Zweifel lieber neu verarbeiten

def mark_as_processed(mp3_file_path: str):
    """Markiert eine MP3-Datei als erfolgreich verarbeitet in der Log-Datei."""
    try:
        os.makedirs(os.path.dirname(PROCESSED_LOG_FILE), exist_ok=True)
        with open(PROCESSED_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{os.path.basename(mp3_file_path)}\n")
        logger.info(f"'{os.path.basename(mp3_file_path)}' als verarbeitet markiert.")
    except Exception as e:
        logger.error(f"Fehler beim Schreiben der Log-Datei {PROCESSED_LOG_FILE}: {e}")

def _load_processed_files():
    """Lädt die Liste der bereits verarbeiteten Dateien."""
    if not os.path.exists(PROCESSED_FILES_LOG):
        return set()
    try:
        with open(PROCESSED_FILES_LOG, 'r', encoding='utf-8') as f:
            return set(line.strip() for line in f)
    except Exception as e:
        logger.error(f"Fehler beim Lesen der Log-Datei für verarbeitete Dateien: {e}")
        return set()

def _log_processed_file(file_path):
    """Fügt eine Datei zur Liste der verarbeiteten Dateien hinzu."""
    try:
        with open(PROCESSED_FILES_LOG, 'a', encoding='utf-8') as f:
            f.write(file_path + '\n')
    except Exception as e:
        logger.error(f"Fehler beim Schreiben in die Log-Datei für verarbeitete Dateien: {e}")

def process_audiobook(mp3_file_path: str, learning_manager: LearningManager, whisper_recognizer_instance: WhisperRecognizer):
    """
    Verarbeitet eine einzelne MP3-Hörbuchdatei.

    Args:
        mp3_file_path: Der Pfad zur MP3-Datei.
        learning_manager: Instanz des LearningManagers zum Speichern der Transkripte.
        whisper_recognizer_instance: Instanz des WhisperRecognizers für die Transkription.
    """
    filename = os.path.basename(mp3_file_path)
    logger.info(f"Starte Verarbeitung für Hörbuch: {mp3_file_path}")
    processed_files = _load_processed_files()

    # Überspringen, wenn schon verarbeitet (basierend auf Pfad im Log)
    if mp3_file_path in processed_files:
        logger.info(f"Datei '{filename}' wurde bereits verarbeitet (laut Log). Überspringe.")
        return True # Signalisiert, dass diese Datei übersprungen wurde

    # Optional: Zusätzliche Prüfung in der DB
    try:
        existing_doc = learning_manager.collection.get(
            where={"$and": [{"$or": [{"entry_type": "audiobook_chunk"}, {"entry_type": "document"}]}, {"source": filename}]},
            limit=1,
            include=[]
        )
        if len(existing_doc['ids']) > 0:
            logger.info(f"Dokument '{filename}' scheint bereits in der DB zu existieren. Überspringe Verarbeitung und markiere als verarbeitet.")
            _log_processed_file(mp3_file_path)
            return True
    except Exception as db_check_error:
        logger.error(f"Fehler bei der DB-Dublettenprüfung für {filename}: {db_check_error}. Fahre fort mit Verarbeitung.")

    start_time = time.time()
    total_transcribed_length = 0
    processed_chunks = 0
    total_chunks = 0

    try:
        # 1. Audiodatei laden
        logger.info("Lade Audiodatei mit pydub...")
        audio = AudioSegment.from_mp3(mp3_file_path)
        duration_seconds = len(audio) / 1000.0
        logger.info(f"Audiodatei geladen. Dauer: {duration_seconds:.2f} Sekunden.")

        # 2. Audio in Chunks aufteilen
        total_chunks = math.ceil(len(audio) / CHUNK_LENGTH_MS)
        logger.info(f"Teile Audio in {total_chunks} Chunks von ca. {CHUNK_LENGTH_MS / 1000.0:.1f}s Länge.")
        chunks = [audio[i:i + CHUNK_LENGTH_MS] for i in range(0, len(audio), CHUNK_LENGTH_MS)]

        # 3. Chunks verarbeiten (Transkription + Speichern)
        # Verwende tqdm für eine einfache Fortschrittsanzeige im Log/Konsole
        for i, chunk in enumerate(tqdm(chunks, desc=f"Verarbeite Chunks für {filename}")):
            chunk_start_time_s = (i * CHUNK_LENGTH_MS) / 1000.0
            chunk_end_time_s = min(((i + 1) * CHUNK_LENGTH_MS) / 1000.0, duration_seconds)
            
            # Erzeuge temporäre WAV-Datei für Whisper
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir=AUDIOBOOK_TEMP_DIR) as temp_wav_file:
                temp_wav_path = temp_wav_file.name
                try:
                    # Konvertiere zu Mono und setze Sample Rate
                    chunk = chunk.set_channels(1).set_frame_rate(TARGET_SAMPLE_RATE)
                    chunk.export(temp_wav_path, format="wav")

                    # Transkribiere den Chunk
                    transcript = whisper_recognizer_instance.transcribe_wav(temp_wav_path)
                    if transcript:
                        total_transcribed_length += len(transcript)
                        
                        # Speichere Transkript im LearningManager
                        metadata = {
                            "entry_type": "audiobook_chunk",
                            "source": filename, # Original MP3-Dateiname
                            "source_path": mp3_file_path, # Voller Pfad zur MP3
                            "chunk_index": i + 1,
                            "total_chunks": total_chunks,
                            "start_time_s": chunk_start_time_s,
                            "end_time_s": chunk_end_time_s,
                            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                        }
                        # Eindeutige ID für jeden Chunk
                        doc_id = f"audiobook_{filename}_chunk_{i+1}"
                        learning_manager.add_entry(doc_id=doc_id, content=transcript, metadata=metadata)
                        processed_chunks += 1
                    else:
                        logger.warning(f"Kein Transkript für Chunk {i+1} von {filename} erhalten.")
                except Exception as e:
                    logger.error(f"Fehler bei der Verarbeitung von Chunk {i+1} aus {filename}: {e}")
                finally:
                    # Lösche temporäre WAV-Datei
                    if os.path.exists(temp_wav_path):
                        try:
                            os.remove(temp_wav_path)
                        except Exception as remove_e:
                            logger.warning(f"Konnte temporäre Datei nicht löschen: {temp_wav_path} - {remove_e}")
            
        # Verarbeitung abgeschlossen
        end_time = time.time()
        logger.info(f"Verarbeitung abgeschlossen für {filename}.")
        logger.info(f"  Verarbeitete Chunks: {processed_chunks} / {total_chunks}")
        logger.info(f"  Gesamtlänge des transkribierten Texts: {total_transcribed_length} Zeichen")
        logger.info(f"  Benötigte Zeit: {end_time - start_time:.2f} Sekunden")

        # Markiere die Datei als verarbeitet im Log
        _log_processed_file(mp3_file_path)
        return True

    except Exception as e:
        logger.error(f"Fehler bei der Hauptverarbeitung von {filename}: {e}", exc_info=True)
        return False

def find_and_process_audio_in_folder(folder_path: str, learning_manager: LearningManager, whisper_recognizer_instance: WhisperRecognizer):
    """
    Durchsucht einen Ordner rekursiv nach MP3-Dateien und verarbeitet sie.

    Args:
        folder_path: Der Pfad zum Ordner, der durchsucht werden soll.
        learning_manager: Instanz des LearningManagers.
        whisper_recognizer_instance: Instanz des WhisperRecognizers.

    Yields:
        Statusmeldungen über den Fortschritt (z.B. gefundene Dateien, aktuelle Datei).
    """
    logger.info(f"Starte Suche nach MP3-Dateien in Ordner: {folder_path}")
    yield f"Suche MP3s in: {folder_path}..."

    mp3_files = []
    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith(".mp3"):
                mp3_files.append(os.path.join(root, file))
    
    total_files_found = len(mp3_files)
    logger.info(f"{total_files_found} MP3-Dateien gefunden.")
    yield f"{total_files_found} MP3-Dateien gefunden."

    processed_count = 0
    skipped_count = 0
    error_count = 0

    if not mp3_files:
        yield "Keine MP3-Dateien im Ordner gefunden."
        return

    for i, file_path in enumerate(mp3_files):
        filename = os.path.basename(file_path)
        yield f"Verarbeite Datei {i+1}/{total_files_found}: {filename}..."
        logger.info(f"Starte Verarbeitung für Datei {i+1}/{total_files_found}: {file_path}")

        try:
            # Rufe die Verarbeitungsfunktion auf
            success = process_audiobook(file_path, learning_manager, whisper_recognizer_instance)
            if success:
                # process_audiobook gibt True zurück, auch wenn übersprungen wurde
                # Wir müssen im Log nachsehen oder die Logik komplexer machen, um genau zu zählen.
                # Einfacher Ansatz: Wir zählen es als 'verarbeitet' im Sinne von 'abgehakt'.
                processed_count += 1
                yield f"Datei '{filename}' abgeschlossen."
            else:
                error_count += 1
                yield f"Fehler bei Datei '{filename}'."
        except Exception as e:
            logger.error(f"Unerwarteter Fehler bei der Verarbeitung von {filename}: {e}", exc_info=True)
            error_count += 1
            yield f"Schwerer Fehler bei Datei '{filename}'."

    # Nach Abschluss aller Dateien
    final_message = f"Audiobook-Import abgeschlossen. {processed_count} Dateien verarbeitet/übersprungen, {error_count} Fehler."
    logger.info(final_message)
    yield final_message
    
    # Optional: Vektoren und DB speichern, wenn neue Daten hinzugefügt wurden
    # Dies könnte auch der aufrufende Thread übernehmen.
    # if processed_count > skipped_count: # Grobe Schätzung, ob etwas Neues gelernt wurde
    #     try:
    #         logger.info("Aktualisiere Vektoren und speichere DB nach Audiobook-Import...")
    #         yield "Aktualisiere Wissens-Vektoren..."
    #         learning_manager.update_vectors()
    #         yield "Speichere Wissensbasis..."
    #         learning_manager.save_knowledge_base()
    #         yield "Wissensbasis aktualisiert."
    #     except Exception as e:
    #         logger.error(f"Fehler beim Aktualisieren/Speichern der DB nach Audiobook-Import: {e}")
    #         yield f"Fehler beim DB Update: {e}"

# Beispielaufruf (für Testzwecke, wird aus der GUI heraus anders aufgerufen)
if __name__ == "__main__":
    logger.info("Starte Audiobook Learning Modul im Testmodus (find_and_process)...")
    
    # --- Konfiguration für den Test --- 
    TEST_AUDIOBOOK_FOLDER = "data/audio/test_audiobooks" # Erstelle diesen Ordner und lege MP3s hinein!
    DB_PATH_TEST = "data/knowledge_base/chroma_db_audio_test" # Separater DB-Pfad für Tests
    WHISPER_MODEL_SIZE = "tiny" # Kleineres Modell für schnellere Tests
    WHISPER_DEVICE = "cpu" # CPU für Tests ohne GPU
    WHISPER_COMPUTE_TYPE = "int8"
    # --- Ende Konfiguration --- 

    if not os.path.exists(TEST_AUDIOBOOK_FOLDER):
        logger.error(f"Testordner '{TEST_AUDIOBOOK_FOLDER}' nicht gefunden. Bitte erstellen und MP3s hinzufügen.")
        exit()

    # Initialisiere notwendige Manager für den Test
    try:
        test_learning_manager = LearningManager(db_path=DB_PATH_TEST)
        test_whisper_recognizer = WhisperRecognizer(
            model_size=WHISPER_MODEL_SIZE, 
            device=WHISPER_DEVICE, 
            compute_type=WHISPER_COMPUTE_TYPE
        )
    except Exception as e:
        logger.error(f"Fehler bei der Initialisierung der Manager für den Test: {e}", exc_info=True)
        exit()

    logger.info("Starte Verarbeitung des Test-Ordners...")
    
    # Iteriere durch die Statusmeldungen
    for status in find_and_process_audio_in_folder(TEST_AUDIOBOOK_FOLDER, test_learning_manager, test_whisper_recognizer):
        logger.info(f"[Fortschritt] {status}")
        
    logger.info("Testlauf abgeschlossen.") 