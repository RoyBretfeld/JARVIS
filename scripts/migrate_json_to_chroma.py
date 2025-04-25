import chromadb
import os
import shutil
import json
import logging
import time
import uuid
from datetime import datetime
from sentence_transformers import SentenceTransformer
from chromadb.utils import embedding_functions
from chromadb.config import Settings

# --- Konfiguration (Pfade relativ zum Hauptverzeichnis von JARVIS) ---
BASE_DIR = os.path.dirname(os.path.dirname(__file__)) # Geht zum JARVIS-Hauptverzeichnis
CHROMA_DB_PATH = os.path.join(BASE_DIR, "data", "knowledge_base", "chroma_db")
JSON_FILE_PATH = os.path.join(BASE_DIR, "data", "learning", "knowledge_base.json")
COLLECTION_NAME = "jarvis_knowledge" # Muss mit LearningManager übereinstimmen
EMBEDDING_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
MIGRATION_MARKER_FILENAME = ".chroma_migration_done"
MIGRATION_MARKER_PATH = os.path.join(os.path.dirname(JSON_FILE_PATH), MIGRATION_MARKER_FILENAME)

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ChromaDB_Migration_Script")

def migrate_data():
    logger.info("Starte separates Migrationsskript...")
    logger.info(f"Quell-JSON: {JSON_FILE_PATH}")
    logger.info(f"Ziel-ChromaDB: {CHROMA_DB_PATH}")
    logger.info(f"Ziel-Collection: {COLLECTION_NAME}")
    logger.info(f"Marker-Datei: {MIGRATION_MARKER_PATH}")

    # --- Vorbedingungen prüfen ---
    if not os.path.exists(JSON_FILE_PATH):
        logger.error(f"FEHLER: JSON-Datei nicht gefunden: {JSON_FILE_PATH}")
        return

    if os.path.exists(MIGRATION_MARKER_PATH):
        logger.warning(f"Migrations-Marker-Datei existiert bereits: {MIGRATION_MARKER_PATH}")
        logger.warning("Migration wird NICHT erneut durchgeführt. Löschen Sie die Marker-Datei, falls eine erneute Migration gewünscht ist.")
        return

    client = None
    try:
        # --- Umgebung vorbereiten (DB löschen für sauberen Start?) ---
        # Optional: Alte DB vor der Migration löschen?
        logger.warning(f"Lösche ZIEL-DB vor Migration: {CHROMA_DB_PATH}")
        if os.path.exists(CHROMA_DB_PATH):
            try:
                shutil.rmtree(CHROMA_DB_PATH)
                logger.info("Altes ChromaDB-Verzeichnis gelöscht.")
            except Exception as e:
                logger.error(f"Fehler beim Löschen des alten ChromaDB-Verzeichnisses: {e}")
                # return # Abbrechen?

        os.makedirs(os.path.dirname(CHROMA_DB_PATH), exist_ok=True)

        # --- ChromaDB initialisieren (wie im erfolgreichen Test) ---
        logger.info(f"Lade Embedding-Modell: {EMBEDDING_MODEL_NAME}...")
        embed_func = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL_NAME, device='cpu'
        )
        logger.info("Embedding-Funktion geladen.")

        logger.info(f"Initialisiere PersistentClient für Pfad: {CHROMA_DB_PATH}...")
        settings = Settings(
            persist_directory=CHROMA_DB_PATH,
            anonymized_telemetry=False
        )
        client = chromadb.PersistentClient(path=CHROMA_DB_PATH, settings=settings)
        logger.info("PersistentClient initialisiert.")

        logger.info(f"Hole oder erstelle Collection '{COLLECTION_NAME}'...")
        collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=embed_func
        )
        logger.info(f"Collection '{COLLECTION_NAME}' bereit. Aktuelle Einträge (vor Migration): {collection.count()}")

        # --- Migration durchführen ---
        logger.info(f"Lade Daten aus JSON-Datei: {JSON_FILE_PATH}...")
        with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
            old_knowledge_base = json.load(f)
        logger.info(f"{len(old_knowledge_base)} Einträge aus JSON geladen.")

        if not old_knowledge_base:
            logger.info("JSON-Datei ist leer, keine Migration notwendig.")
            # Trotzdem Marker erstellen?
            with open(MIGRATION_MARKER_PATH, 'w') as f: f.write(f'empty_json_migrated on {datetime.now().isoformat()}')
            return

        batch_size = 10 # Kleinere Batches
        batches = [old_knowledge_base[i:i + batch_size] for i in range(0, len(old_knowledge_base), batch_size)]
        total_migrated = 0
        migration_start_time = time.time()

        for i, batch in enumerate(batches):
            batch_start_time = time.time()
            logger.info(f"Verarbeite Migrations-Batch {i+1}/{len(batches)} (Größe: {len(batch)})... ")
            ids_to_upsert = []
            docs_to_upsert = []
            metadatas_to_upsert = []

            # Bereite Daten für Upsert vor
            for idx, entry in enumerate(batch):
                if isinstance(entry, dict) and "content" in entry and entry["content"] and isinstance(entry["content"], str):
                    global_index = i * batch_size + idx
                    doc_id = entry.get("id", f"migrated_{entry.get('timestamp', global_index)}_{uuid.uuid4()}")
                    content = entry["content"]
                    metadata = {}
                    for k, v in entry.items():
                        if k not in ["content", "id", "embedding"]:
                            if isinstance(v, (dict, list)):
                                try: metadata[k] = json.dumps(v)
                                except TypeError: metadata[k] = "[Nicht serialisierbar]"
                            elif v is None: metadata[k] = "None"
                            else: metadata[k] = v

                    ids_to_upsert.append(str(doc_id))
                    docs_to_upsert.append(content)
                    metadatas_to_upsert.append(metadata)
                else:
                    logger.warning(f"Ungültiger oder leerer Eintrag in JSON bei Index {global_index} wird übersprungen.")

            # Führe Upsert für den Batch aus
            if ids_to_upsert:
                logger.info(f"Führe Upsert für {len(ids_to_upsert)} Einträge aus Batch {i+1} durch...")
                try:
                    collection.upsert(
                        ids=ids_to_upsert,
                        documents=docs_to_upsert,
                        metadatas=metadatas_to_upsert
                    )
                    total_migrated += len(ids_to_upsert)
                    batch_duration = time.time() - batch_start_time
                    logger.info(f"Upsert für Batch {i+1} erfolgreich ({batch_duration:.2f}s). Bisher migriert: {total_migrated}/{len(old_knowledge_base)}")
                    # Keine Pause hier, Batch-Verarbeitung sollte schnell genug sein
                except Exception as upsert_err:
                    logger.error(f"FEHLER beim Upsert von Batch {i+1}: {upsert_err}", exc_info=True)
                    logger.warning(f"Überspringe Batch {i+1} aufgrund von Upsert-Fehler.")
            else:
                logger.info(f"Batch {i+1} enthält keine gültigen Einträge für Upsert.")

        migration_duration = time.time() - migration_start_time
        logger.info(f"Migration abgeschlossen nach {migration_duration:.2f}s. Insgesamt {total_migrated} von {len(old_knowledge_base)} Einträgen erfolgreich migriert.")

        # --- Abschluss --- 
        if total_migrated > 0 or not old_knowledge_base: # Marker auch bei leerem JSON setzen
            logger.info(f"Erstelle Migrationsmarker: {MIGRATION_MARKER_PATH}")
            with open(MIGRATION_MARKER_PATH, 'w') as f:
                f.write(f'migrated {total_migrated} entries on {datetime.now().isoformat()} via script')
            logger.info("Migrationsmarker erstellt.")

            # Alte JSON-Datei umbenennen
            try:
                migrated_json_path = JSON_FILE_PATH + ".migrated_by_script"
                os.rename(JSON_FILE_PATH, migrated_json_path)
                logger.info(f"Alte JSON-Datei umbenannt zu '{migrated_json_path}'.")
            except OSError as ren_err:
                logger.error(f"Fehler beim Umbenennen der alten JSON-Datei: {ren_err}")
        else:
            logger.warning("Keine Einträge wurden erfolgreich migriert. Marker wird nicht erstellt. Alte JSON bleibt bestehen.")

    except Exception as e:
        logger.error(f"Schwerwiegender Fehler während der Migration: {e}", exc_info=True)

    finally:
        if client:
            try:
                logger.info("Setze ChromaDB Client zurück...")
                client.reset()
                logger.info("Client erfolgreich zurückgesetzt.")
            except Exception as reset_err:
                logger.warning(f"Fehler beim Zurücksetzen des Clients: {reset_err}")
        logger.info("Migrationsskript beendet.")

# --- Hauptausführung ---
if __name__ == "__main__":
    migrate_data() 