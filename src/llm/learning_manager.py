import os
import json
from datetime import datetime
from typing import List, Dict, Optional, Any, Generator, Tuple
import numpy as np
import chromadb
from chromadb.utils import embedding_functions
from sentence_transformers import SentenceTransformer
import logging
import traceback
import uuid
from chromadb.config import Settings
# Neue Imports für Datei-Verarbeitung
from pypdf import PdfReader
import docx # python-docx
import re
from bs4 import BeautifulSoup # Import für HTML
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# <<< Logger wieder aktivieren >>>
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s') # Level auf INFO
logger = logging.getLogger(__name__)

# --- Konstanten ---
DEFAULT_LEARNING_DIR = "data/learning"
CHROMA_DB_PATH = "data/knowledge_base/chroma_db" # Neuer Speicherort für DB-Daten
COLLECTION_NAME = "jarvis_knowledge"
# Mehrsprachiges Modell, gut für Deutsch/Englisch
EMBEDDING_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
# Migration Marker wird hier nicht mehr benötigt
# MIGRATION_MARKER_FILENAME = ".chroma_migration_done"

# --- Neue Chunking Konstanten ---
CHUNK_SIZE = 1000  # Zeichen pro Chunk
CHUNK_OVERLAP = 150 # Zeichen Überlappung

class LearningManager:
    def __init__(self, learning_dir: str = DEFAULT_LEARNING_DIR):
        self.learning_dir = learning_dir
        self.chroma_db_path = os.path.abspath(CHROMA_DB_PATH)
        self.collection_name = COLLECTION_NAME
        self.embedding_model_name = EMBEDDING_MODEL_NAME
        # Embedding-Modell selbst wird nur noch für get_embedding benötigt (falls das bleibt)
        self.embedding_model = None 
        self.embed_func = None
        self.client = None
        self.collection = None

        logger.info(f"Initialisiere LearningManager. DB Pfad: {self.chroma_db_path}") # Geändert zu INFO
        os.makedirs(os.path.dirname(self.chroma_db_path), exist_ok=True)

        # logger.info("Initialisiere LearningManager (expl. embed func + get_collection mit engem try)...") # Redundant
        try:
            # 1. Erstelle Embedding-Funktion wieder explizit
            logger.debug(f"Schritt 1: Erstelle Embedding-Funktion für: {self.embedding_model_name}...") # Bleibt DEBUG
            try:
                self.embed_func = embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name=self.embedding_model_name, device='cpu' # Oder 'cuda' wenn verfügbar/gewünscht
                )
                logger.debug("Schritt 1: Embedding-Funktion erfolgreich erstellt.") # Bleibt DEBUG
            except Exception as e_embed_func:
                logger.error(f"FEHLER beim Erstellen der Embedding-Funktion: {e_embed_func}", exc_info=True) # Bleibt ERROR
                raise

            # 2. Initialisiere ChromaDB Client
            logger.debug(f"Schritt 2: Initialisiere PersistentClient...") # Bleibt DEBUG
            try:
                self.client = chromadb.PersistentClient(path=self.chroma_db_path)
                # logger.debug("Schritt 2: PersistentClient initialisiert (Standard)." ) # Entfernt
                logger.debug("Schritt 2: PersistentClient erfolgreich initialisiert.") # Bleibt DEBUG
            except Exception as e_client:
                logger.error(f"FEHLER beim Initialisieren des PersistentClient: {e_client}", exc_info=True) # Bleibt ERROR
                raise

            # 3. Hole oder erstelle die Collection mit engem try/except
            logger.debug(f"Schritt 3: Hole oder erstelle Collection '{self.collection_name}'...") # Bleibt DEBUG
            collection_result = None
            try:
                # === Kritischer Aufruf: get_or_create_collection ===
                # Verwende get_or_create_collection, um sicherzustellen, dass sie existiert
                collection_result = self.client.get_or_create_collection(
                    name=self.collection_name,
                    embedding_function=self.embed_func # Wichtig: Embedding-Funktion hier übergeben
                )
                # === Aufruf beendet ===
                self.collection = collection_result # Zuweisung NACH Erfolg
                count = self.collection.count()
                logger.info(f"Collection '{self.collection_name}' erfolgreich geholt/erstellt. Einträge: {count}") # Bleibt INFO
                logger.debug("Schritt 3: get_or_create_collection erfolgreich beendet.") # Bleibt DEBUG
            except Exception as e_collection:
                # Fehlermeldung spezifischer machen
                logger.error(f"FEHLER bei get_or_create_collection für '{self.collection_name}': {e_collection}", exc_info=True) # Bleibt ERROR
                raise

            # 4. Migration prüfen (Auskommentiert) - Entfernt für Klarheit
            # logger.debug("Schritt 4: Prüfung auf Migration übersprungen.")

            logger.info("LearningManager Initialisierung erfolgreich abgeschlossen.") # Bleibt INFO

        except Exception as e_init:
            logger.critical(f"KRITISCHER FEHLER bei der Initialisierung des LearningManagers: {e_init}", exc_info=True) # Bleibt CRITICAL
            self.client = None
            self.collection = None
            self.embed_func = None
            logger.warning("LearningManager konnte nicht initialisiert werden und ist nicht funktionsfähig.") # Bleibt WARNING

    def get_embedding(self, text: str) -> Optional[List[float]]:
        """Generiert ein Embedding für den gegebenen Text (Behält manuelle Funktion)."""
        if not self.embedding_model:
            try:
                logger.info(f"Lade Embedding-Modell (für get_embedding): {self.embedding_model_name}...")
                self.embedding_model = SentenceTransformer(self.embedding_model_name, device='cpu')
                logger.info("Embedding-Modell (für get_embedding) geladen.")
            except Exception as e:
                 logger.error(f"Fehler beim Laden des Embedding-Modells für get_embedding: {e}", exc_info=True)
                 return None
        
        if not self.embedding_model:
            logger.error("Embedding-Modell nicht initialisiert in get_embedding.")
            return None
            
        try:
            # logger.debug(f"Generiere Embedding für: '{text[:50]}...'") # Optional: Nur bei Bedarf aktivieren
            embedding = self.embedding_model.encode([text], show_progress_bar=False)
            return embedding[0].tolist()
        except Exception as e:
            logger.error(f"Fehler beim Erstellen des Embeddings für Text: '{text[:50]}...': {e}", exc_info=True)
            return None
            
    def get_learning_context(self, query_text: str, max_entries: int = 3) -> str:
        """Sucht nach relevanten Einträgen in der ChromaDB."""
        if not self.collection:
            logger.warning("LearningManager nicht bereit für Kontextsuche (Collection fehlt).") # Geändert zu WARNING
            return "[Lernkontext nicht verfügbar]"
        try:
            logger.debug(f"Suche Kontext für: '{query_text[:50]}...', max_entries={max_entries}") # Bleibt DEBUG
            results = self.collection.query(
                query_texts=[query_text], 
                n_results=max_entries,
                include=['documents', 'metadatas', 'distances']
            )
            if not results or not results.get('ids') or not results['ids'][0]:
                 logger.debug("Keine relevanten Einträge im Lernkontext gefunden.") # Bleibt DEBUG
                 return ""
            
            context_parts = []
            # Detailliertes Logging der Ergebnisse auf DEBUG-Level verschoben
            logger.debug("Gefundene Kontexteinträge:") 
            for i in range(len(results['ids'][0])):
                doc_id = results['ids'][0][i]
                document = results['documents'][0][i] if results['documents'] else "[Kein Dokument]"
                distance = results['distances'][0][i] if results['distances'] else -1.0
                metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                
                # Logge Details im Debug-Modus
                logger.debug(f"  - ID: {doc_id}, Dist: {distance:.4f}, Meta: {metadata}, Doc: '{document[:100]}...'")

                entry_str = f"- Eintrag (Distanz: {distance:.4f}): {document}" # ID und Zeitstempel für Benutzer weniger relevant
                entry_type = metadata.get('entry_type')
                # source = metadata.get('source') # Quelle könnte interessant sein
                # if source: entry_str += f" (Quelle: {source})"
                if entry_type: entry_str += f" (Typ: {entry_type})"
                
                context_parts.append(entry_str)
                
            if not context_parts: return ""
            
            # Gib nur die zusammengesetzten Strings zurück, kein extra Logging hier
            return "\n".join(context_parts)
            
        except Exception as e:
            logger.error(f"Fehler bei der Kontextsuche: {e}", exc_info=True)
            return "[Fehler bei der Lernkontext-Suche]"

    def add_entry(self, doc_id: str, content: str, metadata: Dict[str, Any]):
        """Fügt einen Eintrag (z.B. einen Text-Chunk) zur ChromaDB Collection hinzu."""
        # Prüfe NUR die Collection am Anfang
        if not self.collection:
            logger.error("ChromaDB Collection nicht initialisiert. Kann Eintrag nicht hinzufügen.")
            return

        # Hole das Embedding. get_embedding lädt das Modell bei Bedarf oder gibt None zurück.
        embedding = self.get_embedding(content)
        if embedding is None:
            logger.error(f"Konnte kein Embedding für ID {doc_id} erstellen. Überspringe Eintrag.")
            return

        # Bereinige Metadaten für ChromaDB (nur str, int, float erlaubt)
        cleaned_metadata = self._clean_metadata(metadata)

        try:
            # Verwende upsert statt add, um bestehende Einträge mit gleicher ID zu aktualisieren
            self.collection.upsert(
                ids=[doc_id],
                embeddings=[embedding],
                metadatas=[cleaned_metadata],
                documents=[content] # Dokumentinhalt auch speichern
            )
            logger.debug(f"Eintrag {doc_id} erfolgreich hinzugefügt/aktualisiert.")
        except Exception as e:
            logger.error(f"Fehler beim Hinzufügen/Aktualisieren des Eintrags {doc_id} zu ChromaDB: {e}", exc_info=True)

    def _clean_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Stellt sicher, dass Metadaten nur erlaubte Typen enthalten."""
        cleaned = {}
        for key, value in metadata.items():
            if isinstance(value, (str, int, float, bool)): # Bool ist auch erlaubt
                cleaned[key] = value
            elif value is None:
                 continue # None ignorieren
            else:
                # Versuche, andere Typen in Strings zu konvertieren, logge aber eine Warnung
                try:
                    cleaned[key] = str(value)
                    logger.warning(f"Metadaten-Wert für Schlüssel '{key}' wurde in String konvertiert: {value}")
                except Exception:
                     logger.warning(f"Konnte Metadaten-Wert für Schlüssel '{key}' nicht in String konvertieren, überspringe: {value}")
        return cleaned

    def add_learning(self, content: str, context: str, success: bool, metrics: dict):
        """Lernt aus einer Interaktion und fügt sie zur DB hinzu."""
        timestamp = datetime.now().isoformat()
        interaction_id = f"interaction_{timestamp}_{uuid.uuid4()}" 
        metadata = {
            "entry_type": "interaction",
            "timestamp": timestamp,
            "context_provided_length": len(context), # Beispiel: Länge des Kontexts speichern
            "success": success, # Boolean ist jetzt erlaubt
            "metrics": metrics, # Dictionary ist jetzt erlaubt
            # Optional: context direkt speichern, wenn _clean_metadata es handhaben kann
            # "context": context 
        }
        # Detail-Logging der Metadaten auf DEBUG verschoben
        logger.debug(f"Füge Lernerfahrung hinzu: ID={interaction_id}, Success={success}, Metrics={metrics}")
        self.add_entry(doc_id=interaction_id, content=content, metadata=metadata)

    def add_interaction(self, user_input: str, system_response: str, context: Dict):
        """Fügt eine Interaktion zur Wissensbasis hinzu (unverändert)."""
        interaction_id = f"interaction_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        content = f"User: {user_input}\nSystem: {system_response}"
        metadata = {
            "entry_type": "interaction",
            "timestamp": datetime.now().isoformat(),
        }
        metadata.update(context) # Füge Kontext-Informationen hinzu
        self.add_entry(doc_id=interaction_id, content=content, metadata=metadata)

    def _get_text_chunks(self, text: str) -> Generator[str, None, None]:
        """Teilt den Text in Chunks auf und liefert sie einzeln (yield)."""
        start = 0
        text_length = len(text)

        while start < text_length:
            end = start + CHUNK_SIZE
            # Keine Sorge um Überlappung am Ende, da end sowieso auf text_length begrenzt wird
            # Wenn der letzte Chunk genau CHUNK_SIZE lang ist, ist das okay.
            # Wenn der letzte Chunk kürzer ist, ist das auch okay.

            chunk = text[start:min(end, text_length)] # Sicherstellen, dass end nicht überläuft
            if chunk.strip(): # Nur nicht-leere Chunks liefern
                 yield chunk

            # Nächsten Startpunkt berechnen
            next_start = start + CHUNK_SIZE - CHUNK_OVERLAP
            # Verhindere negative oder zu kleine Startpunkte bei sehr kurzen Texten/großer Überlappung
            start = max(next_start, start + 1) # Mindestens ein Zeichen vorrücken

            # Sicherheitscheck, um Endlosschleifen zu vermeiden (sollte nicht nötig sein)
            if start >= text_length:
                break

    def _extract_pages_from_pdf(self, file_path: str) -> Generator[Tuple[int, str], None, None]:
        """Extrahiert Text Seite für Seite aus einer PDF und liefert Seitenzahl und Text."""
        try:
            reader = PdfReader(file_path)
            num_pages = len(reader.pages)
            logger.info(f"Extrahiere Text aus PDF ({num_pages} Seiten): {file_path}")
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text and page_text.strip():
                    logger.debug(f"Text aus PDF-Seite {i+1}/{num_pages} extrahiert.")
                    yield i + 1, page_text # Liefert Seitenzahl (1-basiert) und Text
                else:
                    logger.debug(f"Kein Text auf PDF-Seite {i+1}/{num_pages} gefunden.")
        except Exception as e_pdf:
            logger.error(f"Fehler beim Lesen der PDF-Datei {file_path}: {e_pdf}", exc_info=True)
            # Hier keinen Fehler werfen, damit learn_from_file weiterlaufen kann (oder Fehler werfen?)
            # Vorerst: Einfach beenden, learn_from_file wird dann false zurückgeben.
            return # Beendet den Generator im Fehlerfall


    def learn_from_file(self, file_path: str) -> bool:
        """Verarbeitet eine Datei, extrahiert Text, teilt ihn in Chunks und fügt diese hinzu."""
        logger.info(f"Lerne aus Datei: {file_path}")

        if not os.path.isfile(file_path):
            logger.error(f"Datei nicht gefunden: {file_path}")
            return False

        try:
            file_extension = os.path.splitext(file_path)[1].lower()
            # Eindeutige ID für das *gesamte* Quelldokument
            source_doc_id = f"source_doc_{os.path.basename(file_path)}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            normalized_path = os.path.normpath(file_path)
            file_stat = os.stat(file_path)

            # Basis-Metadaten für alle Chunks dieser Datei vorbereiten
            base_metadata = {
                "entry_type": "document_chunk",
                "source_document_id": source_doc_id,
                "source_filename": os.path.basename(file_path),
                "full_path": normalized_path,
                "timestamp_learned": datetime.now().isoformat(),
                "timestamp_modified": datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                "timestamp_created": datetime.fromtimestamp(file_stat.st_ctime).isoformat(),
                # "total_chunks": ???, # Entfernt, da wir es nicht mehr im Voraus wissen
                "file_extension": file_extension,
                "original_size_bytes": file_stat.st_size,
            }

            total_added_chunks_count = 0

            # --- Verarbeitung je nach Dateityp ---
            if file_extension == ".pdf":
                # Seitenweise Verarbeitung für PDFs
                page_chunk_counter = 0 # Zählt Chunks über alle Seiten
                for page_num, page_content in self._extract_pages_from_pdf(file_path):
                    if not page_content:
                        continue
                    logger.debug(f"Verarbeite Chunks für PDF-Seite {page_num}...")
                    # Chunks für die aktuelle Seite generieren und hinzufügen
                    page_added_chunks = 0
                    for chunk_content in self._get_text_chunks(page_content):
                        page_chunk_counter += 1
                        chunk_id = f"chunk_{source_doc_id}_p{page_num}_c{page_chunk_counter}" # Detailliertere ID
                        chunk_metadata = base_metadata.copy()
                        chunk_metadata["chunk_number"] = page_chunk_counter # Fortlaufender Chunk-Zähler
                        chunk_metadata["page_number"] = page_num # Seitenzahl hinzufügen
                        # chunk_metadata["chunk_offset_start"] = ??? # Offset innerhalb der Seite schwer zu bestimmen

                        logger.debug(f"Füge PDF-Chunk {page_chunk_counter} hinzu (Seite {page_num}): ID={chunk_id}")
                        self.add_entry(doc_id=chunk_id, content=chunk_content, metadata=chunk_metadata)
                        page_added_chunks += 1
                    logger.debug(f"{page_added_chunks} Chunks von Seite {page_num} verarbeitet.")
                    total_added_chunks_count += page_added_chunks

                if total_added_chunks_count == 0:
                     logger.warning(f"Keine Text-Chunks aus PDF extrahiert oder verarbeitet: {file_path}")
                     return False # Kein Erfolg, wenn nichts gelernt wurde


            elif file_extension in [".docx", ".html", ".txt", ".md", ".py", ".json", ".xml", ".css", ".js"]:
                # Bisherige Verarbeitung für andere Textdateien (Gesamttext laden)
                content = ""
                if file_extension == ".docx":
                    try:
                        document = docx.Document(file_path)
                        text_parts = [para.text for para in document.paragraphs if para.text]
                        content = "\n".join(text_parts)
                        logger.info(f"Text aus DOCX extrahiert ({len(document.paragraphs)} Absätze): {file_path}")
                    except Exception as e_docx:
                        logger.error(f"Fehler beim Lesen der DOCX-Datei {file_path}: {e_docx}", exc_info=True)
                        return False
                elif file_extension == ".html":
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                           soup = BeautifulSoup(f, 'html.parser')
                        for script_or_style in soup(["script", "style"]):
                            script_or_style.decompose()
                        body = soup.find('body')
                        content = body.get_text(separator='\n', strip=True) if body else soup.get_text(separator='\n', strip=True)
                        logger.info(f"Text aus HTML extrahiert: {file_path}")
                    except Exception as e_html:
                        logger.error(f"Fehler beim Verarbeiten der HTML-Datei {file_path}: {e_html}", exc_info=True)
                        return False
                else: # TXT, MD, Code etc.
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f: content = f.read()
                    except UnicodeDecodeError:
                        logger.warning(f"UTF-8-Lesefehler für {file_path}. Versuche latin-1...")
                        try:
                            with open(file_path, 'r', encoding='latin-1') as f: content = f.read()
                        except Exception as e_read_alt:
                            logger.error(f"Konnte {file_path} auch mit latin-1 nicht lesen: {e_read_alt}", exc_info=True); return False
                    except Exception as e_read:
                        logger.error(f"Fehler beim Lesen der Textdatei {file_path}: {e_read}", exc_info=True); return False
                    logger.info(f"Text aus Datei geladen: {file_path}")

                if not content or not content.strip():
                    logger.warning(f"Kein Inhalt extrahiert oder Datei ist leer: {file_path}")
                    return False

                # Inhalt in Chunks aufteilen (Generator verwenden)
                chunk_counter = 0
                for chunk_content in self._get_text_chunks(content):
                    chunk_counter += 1
                    chunk_id = f"chunk_{source_doc_id}_{chunk_counter}" # Eindeutige ID für jeden Chunk
                    chunk_metadata = base_metadata.copy()
                    chunk_metadata["chunk_number"] = chunk_counter
                    # chunk_metadata["total_chunks"] = ??? # Nicht mehr einfach verfügbar

                    logger.debug(f"Füge Text-Chunk {chunk_counter} hinzu: ID={chunk_id}")
                    self.add_entry(doc_id=chunk_id, content=chunk_content, metadata=chunk_metadata)
                    total_added_chunks_count += 1

                if total_added_chunks_count == 0:
                    logger.warning(f"Konnte keine Text-Chunks aus Datei erstellen: {file_path}")
                    return False

                logger.info(f"Dateiinhalt in {total_added_chunks_count} Chunks aufgeteilt.")

            # NEU: Verarbeitung für Audio-Dateien
            elif file_extension in [".wav", ".mp3", ".ogg", ".flac"]:
                logger.info(f"Erkenne Audiodatei: {file_path}. Versuche Transkription...")
                try:
                    # Stelle sicher, dass Whisper Recognizer verfügbar ist
                    # TODO: WhisperRecognizer muss an den LearningManager übergeben oder hier instanziiert werden.
                    #       Aktuell ist er nur im MainWindow.
                    #       Provisorische Lösung: Instanziieren, wenn nicht vorhanden (kann langsam sein!)
                    if not hasattr(self, 'whisper_recognizer') or self.whisper_recognizer is None:
                         logger.warning("WhisperRecognizer nicht im LearningManager vorhanden. Instanziiere neu...")
                         from ..speech.whisper_recognition import WhisperRecognizer # Import hier
                         # Verwende Standardeinstellungen oder hole sie aus Config?
                         self.whisper_recognizer = WhisperRecognizer()
                         if not self.whisper_recognizer.model:
                              raise RuntimeError("Whisper-Modell konnte nicht geladen werden.")
                         logger.info("WhisperRecognizer im LearningManager neu instanziiert.")

                    # Transkribiere die Audiodatei
                    # Annahme: transcribe_wav kann verschiedene Formate verarbeiten (prüfen!)
                    # WhisperRecognizer erwartet .wav, daher ggf. Konvertierung nötig!
                    # TODO: Konvertierung von mp3/ogg/flac zu wav hinzufügen falls nötig!
                    #       Aktuell versuchen wir es direkt.
                    content = self.whisper_recognizer.transcribe_wav(file_path)

                    if content is None:
                         logger.error(f"Whisper-Transkription fehlgeschlagen für: {file_path}")
                         return False

                    logger.info(f"Audio erfolgreich transkribiert (Länge: {len(content)} Zeichen): {file_path}")

                except ImportError:
                    logger.error("WhisperRecognizer konnte nicht importiert werden. Audio-Transkription nicht möglich.")
                    return False
                except Exception as e_audio:
                    logger.error(f"Fehler bei der Audio-Transkription von {file_path}: {e_audio}", exc_info=True)
                    return False

                if not content or not content.strip():
                    logger.warning(f"Kein Inhalt aus Audiodatei transkribiert: {file_path}")
                    return False

                # --- Ab hier gemeinsamer Code für Text- und Audio-Inhalte ---
                # Inhalt in Chunks aufteilen (Generator verwenden)
                chunk_counter = 0
                for chunk_content in self._get_text_chunks(content):
                    chunk_counter += 1
                    chunk_id = f"chunk_{source_doc_id}_{chunk_counter}" # Eindeutige ID für jeden Chunk
                    chunk_metadata = base_metadata.copy()
                    chunk_metadata["chunk_number"] = chunk_counter
                    # chunk_metadata["total_chunks"] = ??? # Nicht mehr einfach verfügbar

                    logger.debug(f"Füge Text-Chunk {chunk_counter} hinzu: ID={chunk_id}")
                    self.add_entry(doc_id=chunk_id, content=chunk_content, metadata=chunk_metadata)
                    total_added_chunks_count += 1

                if total_added_chunks_count == 0:
                    logger.warning(f"Konnte keine Text-Chunks aus Datei erstellen: {file_path}")
                    return False

                logger.info(f"Dateiinhalt in {total_added_chunks_count} Chunks aufgeteilt.")

            else:
                logger.warning(f"Nicht unterstützter Dateityp zum Lernen übersprungen: {file_path}")
                return False # Nicht erfolgreich, da Typ nicht unterstützt


            logger.info(f"{total_added_chunks_count} Chunks aus Datei {file_path} insgesamt erfolgreich zur Wissensbasis hinzugefügt.")
            # Optional: Am Ende Metadaten des Quelldokuments aktualisieren (z.B. mit total_chunks)?
            # self.add_entry(doc_id=source_doc_id, content="", metadata={"entry_type": "document_source_info", "total_chunks": total_added_chunks_count, ...})
            return True # Erfolg signalisieren

        except Exception as e:
            logger.error(f"Unerwarteter Fehler beim Lernen aus Datei {file_path}: {e}", exc_info=True)
            return False # Fehler signalisieren

    def calculate_complexity(self, text: str) -> float:
        """Berechnet die Komplexität eines Texts (unverändert)"""
        try:
            length_score = min(len(text) / 1000, 1.0)
            words = text.lower().split()
            unique_words = len(set(words))
            diversity_score = min(unique_words / len(words), 1.0) if words else 0
            sentences = text.split('.')
            avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences) if sentences else 0
            sentence_score = min(avg_sentence_length / 20, 1.0)
            return (length_score * 0.3 + diversity_score * 0.4 + sentence_score * 0.3)
        except Exception as e:
            logger.warning(f"Fehler bei der Komplexitätsberechnung: {str(e)}")
            return 0.0

    def find_similar(self, query: str, n_results: int = 5, threshold: Optional[float] = None, entry_type_filter: Optional[str] = None) -> List[Dict]:
        """
        Findet die n_results ähnlichsten Einträge zum Query-Text in ChromaDB.
        Kann optional nach entry_type filtern und einen Distanz-Threshold anwenden.
        Distanz ist hier Kosinus-Distanz (0=identisch, >1 unähnlich).
        Ein Threshold von z.B. 0.6 bedeutet, nur Ergebnisse mit Distanz <= 0.6 zurückzugeben.
        """
        logger.debug(f"find_similar aufgerufen für Query: '{query[:100]}...', n_results={n_results}, threshold={threshold}, filter={entry_type_filter}")
        if not self.collection or not self.embedding_model:
             logger.error("ChromaDB Collection oder Embedding Model nicht initialisiert in find_similar.")
             return []

        query_embedding = self.get_embedding(query)
        if query_embedding is None:
            logger.error("Konnte kein Embedding für die Query erstellen.")
            return []

        # Filter-Argument für ChromaDB vorbereiten
        where_filter = None
        if entry_type_filter:
            where_filter = {"entry_type": entry_type_filter}
            logger.debug(f"Verwende Filter: {where_filter}")

        try:
            # Erhöhe n_results temporär leicht, falls Threshold angewendet wird, um genug Kandidaten zu bekommen
            query_n_results = n_results * 2 if threshold is not None else n_results

            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=query_n_results, # Frage mehr an, falls gefiltert wird
                where=where_filter, # Filter anwenden, falls definiert
                include=['documents', 'metadatas', 'distances'] # Welche Daten sollen zurückgegeben werden?
            )
            logger.debug(f"ChromaDB Query Roh-Ergebnisse: {results}")

            # Ergebnisse aufbereiten und ggf. nach Distanz filtern
            processed_results = []
            if results and results.get('ids') and results['ids'][0]: # Prüfen ob Ergebnisse vorhanden sind
                for i in range(len(results['ids'][0])):
                    distance = results['distances'][0][i]

                    # Standard-Threshold anwenden, falls gegeben
                    if threshold is not None and distance > threshold:
                        # print(f"Eintrag {results['ids'][0][i]} übersprungen (Distanz {distance:.4f} > Threshold {threshold}) - Kosinus-Distanz")
                        continue # Überspringe, wenn Distanz zu groß

                    # Lade Metadaten korrekt (sind Strings in DB)
                    metadata_raw = results['metadatas'][0][i]
                    metadata_processed = {}
                    for k, v in metadata_raw.items():
                         # Versuche JSON-Strings zurück zu konvertieren
                        if isinstance(v, str):
                            try:
                                # Speziell für 'metrics' und 'tags'
                                if k in ['metrics', 'tags']:
                                    metadata_processed[k] = json.loads(v)
                                elif k == 'success': # Booleschen Wert wiederherstellen
                                     metadata_processed[k] = v.lower() == 'true'
                                elif v == 'None': # None wiederherstellen
                                     metadata_processed[k] = None
                                else:
                                     metadata_processed[k] = v # Behalte andere Strings
                            except json.JSONDecodeError:
                                metadata_processed[k] = v # Behalte String, wenn kein gültiges JSON
                        else:
                            metadata_processed[k] = v # Behalte andere Typen


                    entry = {
                        "id": results['ids'][0][i],
                        "content": results['documents'][0][i],
                        "metadata": metadata_processed, # Verarbeitete Metadaten
                        "distance": distance
                    }
                    processed_results.append(entry)
            else:
                 logger.debug("Keine Roh-Ergebnisse von ChromaDB Query erhalten.")

            # Sortiere nach Distanz (kleinste zuerst = ähnlichste)
            processed_results.sort(key=lambda x: x['distance'])

            # Begrenze auf ursprüngliche n_results NACH dem Filtern
            final_results = processed_results[:n_results]

            logger.info(f"{len(final_results)} ähnliche Einträge gefunden und nach Filter/Threshold verarbeitet (ursprünglich angefragt: {n_results}).")
            return final_results

        except Exception as e:
            logger.error(f"Fehler bei der ChromaDB-Abfrage: {e}", exc_info=True)
            return []

    def get_statistics(self) -> Dict[str, Any]:
        """Gibt Statistiken über die Wissensbasis zurück."""
        stats = {"entry_count": 0, "entry_types": {}}
        if not self.collection:
            logger.warning("Statistiken können nicht abgerufen werden: Collection nicht initialisiert.")
            return stats
        try:
            count = self.collection.count()
            stats["entry_count"] = count
            
            # Hole Metadaten, um Typen zu zählen (kann bei großen Collections langsam sein)
            # Begrenze die Abfrage, wenn nötig
            limit = 10000 # Beispiel-Limit
            results = self.collection.get(limit=min(count, limit), include=['metadatas']) 
            
            type_counts = {}
            if results and results.get('metadatas'):
                for meta in results['metadatas']:
                    entry_type = meta.get('entry_type', 'unknown')
                    type_counts[entry_type] = type_counts.get(entry_type, 0) + 1
            stats["entry_types"] = type_counts
            
            logger.info(f"Statistiken abgerufen: {stats}") # Bleibt INFO
            return stats
        except Exception as e:
            logger.error(f"Fehler beim Abrufen der Statistiken: {e}", exc_info=True)
            stats["error"] = str(e)
            return stats
            
    def save_knowledge_base(self):
        """Speichert die Wissensbasis (ChromaDB PersistentClient speichert automatisch)."""
        # Bei PersistentClient ist kein explizites Speichern notwendig.
        # Die Daten werden kontinuierlich auf die Festplatte geschrieben.
        logger.info("Wissensbasis (ChromaDB) wird kontinuierlich gespeichert.") # Bleibt INFO
        # Optional: Führe client.persist() aus, um sicherzustellen, dass alles geschrieben wurde
        # try:
        #     if self.client:
        #         # logger.debug("Rufe client.persist() auf...") # DEBUG
        #         # self.client.persist() # persist() ist in neueren Versionen nicht mehr die Hauptmethode zum Speichern
        #         logger.info("ChromaDB PersistentClient speichert Daten automatisch.")
        # except Exception as e:
        #      logger.error(f"Fehler beim expliziten Persistieren der DB (sollte nicht nötig sein): {e}", exc_info=True)

    def load_knowledge_base(self):
        """Lädt die Wissensbasis (erfolgt im __init__ durch PersistentClient)."""
        # Das Laden geschieht bereits beim Initialisieren des PersistentClient.
        logger.info("Wissensbasis (ChromaDB) wird bei Initialisierung geladen.") # Bleibt INFO
        # Optional: Überprüfe, ob die Collection geladen wurde
        if self.collection:
             logger.info(f"Collection '{self.collection_name}' ist verfügbar mit {self.collection.count()} Einträgen.")
        else:
             logger.warning("Collection ist nach der Initialisierung nicht verfügbar.")
             
    def update_vectors(self):
         """Aktualisiert Vektoren (nicht notwendig bei ChromaDB mit Embedding Function)."""
         # ChromaDB erstellt Embeddings automatisch beim Hinzufügen/Upsert, wenn eine
         # Embedding-Funktion für die Collection definiert ist.
         logger.info("Vektor-Update nicht notwendig, ChromaDB managed Embeddings automatisch.") # Bleibt INFO

    # _migrate_from_json_if_needed ist veraltet und kann entfernt werden
    # def _migrate_from_json_if_needed(self): ...

    # Optional: delete_entry Funktion
    def delete_entry(self, doc_id: str) -> bool:
         """Löscht einen Eintrag anhand seiner ID."""
         if not self.collection:
             logger.error("Kann Eintrag nicht löschen: Collection nicht initialisiert.")
             return False
         try:
             logger.warning(f"Versuche Eintrag zu löschen: ID={doc_id}") # WARNING, da Löschen eine wichtige Aktion ist
             self.collection.delete(ids=[str(doc_id)])
             logger.info(f"Eintrag erfolgreich gelöscht: ID={doc_id}. Aktuelle Einträge: {self.collection.count()}")
             return True
         except Exception as e:
             logger.error(f"Fehler beim Löschen von Eintrag ID={doc_id}: {e}", exc_info=True)
             return False

    # Optional: get_entry Funktion
    def get_entry(self, doc_id: str) -> Optional[Dict]:
         """Holt einen Eintrag anhand seiner ID."""
         if not self.collection:
             logger.error("Kann Eintrag nicht abrufen: Collection nicht initialisiert.")
             return None
         try:
             logger.debug(f"Rufe Eintrag ab: ID={doc_id}") # DEBUG
             result = self.collection.get(ids=[str(doc_id)], include=['metadatas', 'documents'])
             if result and result.get('ids') and result['ids'][0] == doc_id:
                 entry = {
                     "id": result['ids'][0],
                     "document": result['documents'][0] if result.get('documents') else None,
                     "metadata": result['metadatas'][0] if result.get('metadatas') else None
                 }
                 logger.debug(f"Eintrag gefunden: {entry}") # DEBUG
                 return entry
             else:
                 logger.warning(f"Eintrag nicht gefunden: ID={doc_id}")
                 return None
         except Exception as e:
             logger.error(f"Fehler beim Abrufen von Eintrag ID={doc_id}: {e}", exc_info=True)
             return None

    # Getter für knowledge_base (gibt eine Liste der Dokumente zurück, kann teuer sein!)
    @property
    def knowledge_base(self) -> List[Dict[str, Any]]:
        """Gibt eine Liste aller Einträge zurück (potenziell speicherintensiv!). ACHTUNG: Enthält jetzt Chunks!"""
        if not self.collection:
            logger.warning("Wissensbasis kann nicht abgerufen werden: Collection nicht initialisiert.")
            return []
        try:
            count = self.collection.count()
            # Warnung anpassen, da jetzt Chunks enthalten sind
            logger.warning(f"Rufe ALLE {count} Einträge (inkl. Dokument-Chunks) aus der Wissensbasis ab. Dies kann lange dauern und viel Speicher benötigen!")
            # Begrenzung evtl. sinnvoll?
            limit = 20000 # Beispiel: Auf 20000 Einträge begrenzen?
            results = self.collection.get(limit=min(count, limit), include=['documents', 'metadatas']) 
            
            entries = []
            if results and results.get('ids'):
                processed_count = 0
                for i in range(len(results['ids'])):
                    metadata = results['metadatas'][i] if results.get('metadatas') else {}
                    # Optional: Filtere hier, wenn nur bestimmte Typen gewünscht sind
                    # entry_type = metadata.get('entry_type', 'unknown')
                    # if entry_type != 'document_chunk': continue
                    
                    entry = {
                        "id": results['ids'][i],
                        "content": results['documents'][i] if results.get('documents') else None,
                        "metadata": self._clean_metadata(metadata) # Verwende clean für Konsistenz
                    }
                    entries.append(entry)
                    processed_count += 1
                
                if count > limit:
                     logger.warning(f"Nur die ersten {limit} von {count} Einträgen wurden abgerufen.")
                logger.info(f"{processed_count} Einträge aus der Wissensbasis abgerufen.")
            return entries
        except Exception as e:
            logger.error(f"Fehler beim Abrufen der gesamten Wissensbasis: {e}", exc_info=True)
            return [] 

    def get_relevant_context(self, query: str) -> str:
        """Gibt den relevanten Lernkontext für eine Anfrage zurück."""
        try:
            if not self.collection:
                logger.warning("LearningManager nicht bereit für Kontextsuche (Collection fehlt).")
                return ""
                
            # Suche nach relevanten Einträgen in der ChromaDB
            results = self.collection.query(
                query_texts=[query],
                n_results=3,
                include=['documents', 'metadatas', 'distances']
            )
            
            if not results or not results.get('ids') or not results['ids'][0]:
                logger.debug("Keine relevanten Einträge im Lernkontext gefunden.")
                return ""
                
            # Extrahiere die relevantesten Dokumente
            context_parts = []
            for i in range(len(results['ids'][0])):
                doc_id = results['ids'][0][i]
                document = results['documents'][0][i] if results['documents'] else "[Kein Dokument]"
                distance = results['distances'][0][i] if results['distances'] else -1.0
                metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                
                # Nur Einträge mit Distanz <= 0.6 berücksichtigen
                if distance <= 0.6:
                    entry_str = f"- Eintrag (Distanz: {distance:.4f}): {document}"
                    entry_type = metadata.get('entry_type')
                    if entry_type:
                        entry_str += f" (Typ: {entry_type})"
                    context_parts.append(entry_str)
                    
            if not context_parts:
                return ""
                
            return "\n".join(context_parts)
            
        except Exception as e:
            logger.error(f"Fehler beim Abrufen des Lernkontexts: {e}")
            return "" 

    def add_feedback(self, response_id: str, is_positive: bool, feedback_text: str = "") -> bool:
        """
        Speichert Benutzerfeedback zu einer Antwort.
        
        Args:
            response_id: Die ID der Antwort, zu der das Feedback gehört
            is_positive: True für positives Feedback (Daumen hoch), False für negatives (Daumen runter)
            feedback_text: Optionaler Feedback-Text
            
        Returns:
            bool: True wenn das Feedback erfolgreich gespeichert wurde
        """
        if not self.collection:
            logger.error("Kann Feedback nicht speichern: Collection nicht initialisiert.")
            return False
            
        try:
            # Erstelle eine eindeutige ID für das Feedback
            feedback_id = f"feedback_{response_id}_{datetime.now().isoformat()}_{uuid.uuid4()}"
            
            # Erstelle Metadaten für das Feedback
            metadata = {
                "entry_type": "feedback",
                "response_id": response_id,
                "is_positive": is_positive,
                "timestamp": datetime.now().isoformat()
            }
            
            # Erstelle den Feedback-Inhalt
            content = f"Feedback: {'👍 Positiv' if is_positive else '👎 Negativ'}"
            if feedback_text:
                content += f"\nKommentar: {feedback_text}"
                
            # Speichere das Feedback
            self.add_entry(doc_id=feedback_id, content=content, metadata=metadata)
            
            # Aktualisiere die Metadaten der ursprünglichen Antwort
            try:
                original_entry = self.get_entry(response_id)
                if original_entry and original_entry.get('metadata'):
                    # Hole existierende Feedback-Statistiken oder initialisiere sie
                    feedback_stats = json.loads(original_entry['metadata'].get('feedback_stats', '{"positive": 0, "negative": 0}'))
                    # Aktualisiere die Statistiken
                    if is_positive:
                        feedback_stats['positive'] += 1
                    else:
                        feedback_stats['negative'] += 1
                    # Aktualisiere die Metadaten der Antwort
                    updated_metadata = original_entry['metadata'].copy()
                    updated_metadata['feedback_stats'] = json.dumps(feedback_stats)
                    updated_metadata['last_feedback'] = datetime.now().isoformat()
                    self.add_entry(doc_id=response_id, 
                                 content=original_entry['document'],
                                 metadata=updated_metadata)
            except Exception as e:
                logger.warning(f"Konnte Feedback-Statistiken für Antwort {response_id} nicht aktualisieren: {e}")
            
            logger.info(f"Feedback erfolgreich gespeichert: ID={feedback_id}, Positiv={is_positive}")
            return True
            
        except Exception as e:
            logger.error(f"Fehler beim Speichern des Feedbacks: {e}", exc_info=True)
            return False 