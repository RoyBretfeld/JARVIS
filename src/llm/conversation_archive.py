import os
import json
from datetime import datetime
from typing import List, Dict, Optional
from ..security.encryption_manager import EncryptionManager
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import logging # Logger importieren

# Logger für dieses Modul
logger = logging.getLogger(__name__)

class ConversationArchive:
    def __init__(self, archive_dir: str = "data/conversations"):
        """Initialisiert das Konversationsarchiv"""
        self.archive_dir = archive_dir
        self.current_file = None
        self.max_file_size = 10 * 1024 * 1024  # 10MB
        self.encryption = EncryptionManager()
        
        # Stelle sicher, dass Verzeichnis existiert
        os.makedirs(self.archive_dir, exist_ok=True)
        
    def init_archive(self):
        """Initialisiert das Archiv-Verzeichnis"""
        os.makedirs(self.archive_dir, exist_ok=True)
        self.current_file = self.get_current_file()
        
    def get_current_file(self) -> str:
        """Ermittelt die aktuelle oder erstellt eine neue Archivdatei"""
        files = self.get_archive_files()
        
        if not files:
            return self.create_new_file()
            
        latest_file = files[-1]
        
        # Prüfe Dateigröße
        if os.path.getsize(latest_file) >= self.max_file_size:
            return self.create_new_file()
            
        return latest_file
        
    def create_new_file(self) -> str:
        """Erstellt eine neue Archivdatei"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(self.archive_dir, f"conversation_{timestamp}.json")
        
        # Erstelle leere Datei mit Grundstruktur
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump({
                "metadata": {
                    "created": datetime.now().isoformat(),
                    "last_modified": datetime.now().isoformat(),
                    "message_count": 0
                },
                "conversations": []
            }, f, indent=4, ensure_ascii=False)
            
        return filename
        
    def get_archive_files(self) -> List[str]:
        """Gibt eine sortierte Liste aller relevanten Archivdateien (.enc) zurück"""
        if not os.path.exists(self.archive_dir):
            return []

        files = [
            os.path.join(self.archive_dir, f)
            for f in os.listdir(self.archive_dir)
            if f.startswith("conversation_") and f.endswith(".enc")
        ]
        return sorted(files)
        
    def add_conversation(self, messages: List[Dict]):
        """Fügt eine Konversation zum Archiv hinzu"""
        try:
            # Erstelle neues Archiv wenn nötig
            if not self.current_file or os.path.getsize(self.current_file) >= self.max_file_size:
                self.create_new_archive()
                
            # Bereite Konversationsdaten vor
            conversation = {
                "timestamp": datetime.now().isoformat(),
                "messages": messages
            }
            
            # Verschlüssele Daten
            encrypted_data = self.encryption.encrypt_data(conversation)
            if not encrypted_data:
                print("Fehler bei der Verschlüsselung der Konversation")
                return
                
            # Lade existierende Daten
            try:
                with open(self.current_file, 'rb') as f:
                    encrypted_content = f.read()
                    content = self.encryption.decrypt_data(encrypted_content) if encrypted_content else {"conversations": []}
            except:
                content = {"conversations": []}
                
            # Füge neue Konversation hinzu
            content["conversations"].append(conversation)
            
            # Verschlüssele und speichere
            encrypted_content = self.encryption.encrypt_data(content)
            if encrypted_content:
                with open(self.current_file, 'wb') as f:
                    f.write(encrypted_content)
                    
        except Exception as e:
            print(f"Fehler beim Hinzufügen der Konversation: {str(e)}")
            
    def create_new_archive(self):
        """Erstellt eine neue Archivdatei"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_file = os.path.join(
            self.archive_dir,
            f"conversation_{timestamp}.enc"
        )
        
    def search_similar(self, query: str, texts: List[str], threshold: float = 0.5) -> Optional[Dict]:
        """Findet ähnliche Texte (ohne übermäßiges Logging)."""
        # print(f"[Archive.search_similar] Suche Ähnlichkeit für Query: '{query[:100]}...'") # <<< Entfernt
        # print(f"[Archive.search_similar] Vergleiche mit {len(texts)} Texten.") # <<< Entfernt

        try:
            if not texts:
                # print("[Archive.search_similar] Keine Texte zum Vergleichen.") # <<< Entfernt
                return None

            # Vektorisiere Texte
            # print("[Archive.search_similar] Vektorisiere...") # <<< Entfernt
            vectorizer = TfidfVectorizer(stop_words=None)
            vectors = vectorizer.fit_transform([query] + texts)
            # print(f"[Archive.search_similar] Vektor-Shape: {vectors.shape}") # <<< Entfernt

            # Berechne Ähnlichkeiten
            # print("[Archive.search_similar] Berechne Cosine Similarity...") # <<< Entfernt
            if vectors.shape[0] < 2:
                 # print("[Archive.search_similar] Weniger als 2 Vektoren, kein Vergleich möglich.") # <<< Entfernt
                 return None

            similarities = cosine_similarity(vectors[0:1], vectors[1:])[0]
            # print(f"[Archive.search_similar] Ähnlichkeiten berechnet: {similarities}") # <<< Entfernt

            # Finde besten Match
            if len(similarities) == 0:
                 # print("[Archive.search_similar] Keine Ähnlichkeitswerte gefunden.") # <<< Entfernt
                 return None

            best_idx = np.argmax(similarities)
            best_score = similarities[best_idx]
            # print(f"[Archive.search_similar] Bester Match Index: {best_idx}, Score: {best_score}") # <<< Entfernt

            if best_score >= threshold:
                # print(f"[Archive.search_similar] Match gefunden über Threshold ({threshold}).") # <<< Entfernt
                return {
                    "text": texts[best_idx],
                    "score": float(best_score),
                    "index": best_idx
                }
            else:
                 # print(f"[Archive.search_similar] Kein Match über Threshold ({threshold}).") # <<< Entfernt
                 return None

        except ValueError as ve:
            logger.error(f"[ConversationArchive] ValueError bei Ähnlichkeitssuche: {str(ve)}", exc_info=True) # <<< Logger
            return None
        except Exception as e:
            logger.error(f"[ConversationArchive] Allgemeiner Fehler bei Ähnlichkeitssuche: {str(e)}", exc_info=True) # <<< Logger
            return None

    def search_conversations(self, query: str, max_results: int = 5, similarity_threshold: float = 0.2) -> List[Dict]:
        """Sucht nach relevanten Konversationen (optimiert, bereinigt)."""
        logger.debug(f"[ConversationArchive] Starte Suche nach relevanten Konversationen für Query: '{query[:50]}...' (Threshold={similarity_threshold})") # <<< Logger
        all_conversations = []
        all_texts = []
        conversation_indices = []

        try:
            archive_files = self.get_archive_files()
            if not archive_files:
                logger.debug("[ConversationArchive] Kein Archiv gefunden.") # <<< Logger
                return []

            # 1. Alle Konversationen und Texte sammeln
            logger.debug(f"[ConversationArchive] Lade Konversationen aus {len(archive_files)} Datei(en)...") # <<< Logger
            for file_index, file_path in enumerate(archive_files):
                # logger.debug(f"[ConversationArchive] Verarbeite Datei: {file_path}") # <<< Auskommentiert (optional)
                try:
                    with open(file_path, 'rb') as f:
                        encrypted_content = f.read()
                        if not encrypted_content:
                             logger.warning(f"[ConversationArchive] Datei {file_path} ist leer.") # <<< Logger
                             continue
                        # logger.debug(f"[ConversationArchive] Rufe decrypt_data für {file_path} auf ({len(encrypted_content)} bytes)...") # <<< Auskommentiert
                        content = self.encryption.decrypt_data(encrypted_content)

                    if not content:
                        logger.warning(f"[ConversationArchive] Entschlüsselung von {file_path} fehlgeschlagen oder Datei war leer/ungültig.") # <<< Logger
                        continue

                    if "conversations" not in content:
                        logger.warning(f"[ConversationArchive] Keine 'conversations' in Datei {file_path} gefunden.") # <<< Logger
                        continue

                    # logger.debug(f"[ConversationArchive] Datei {file_path} erfolgreich entschlüsselt. {len(content['conversations'])} Konversationen gefunden.") # <<< Auskommentiert
                    for conv_index_in_file, conv in enumerate(content["conversations"]):
                        conv_text = " ".join(msg.get("content", "") for msg in conv.get("messages", []))
                        if conv_text.strip():
                            all_conversations.append(conv)
                            all_texts.append(conv_text)
                            conversation_indices.append((file_index, conv_index_in_file))
                except Exception as e_file:
                    logger.error(f"[ConversationArchive] Kritischer Fehler beim Lesen/Entschlüsseln von Datei {file_path}: {e_file}", exc_info=True) # <<< Logger
                    continue

            if not all_texts:
                logger.debug("[ConversationArchive] Keine Konversationstexte im Archiv gefunden.") # <<< Logger
                return []

            logger.debug(f"[ConversationArchive] {len(all_texts)} Konversationstexte gesammelt. Starte Ähnlichkeitssuche...") # <<< Logger

            # 2. Einmalige Ähnlichkeitssuche für alle Texte
            # Hinweis: search_similar erwartet eine Liste von Texten, wir übergeben alle.
            # Es gibt den *besten* Match zurück. Für mehrere Matches bräuchten wir eine andere Funktion.
            # Wir brauchen eine Funktion, die uns die TOP N Matches liefert.

            # === Anpassung: Wir brauchen Top-N, nicht nur den besten ===
            # Berechnen wir die Ähnlichkeiten hier direkt neu für Top-N
            vectorizer = TfidfVectorizer(stop_words=None)
            try:
                vectors = vectorizer.fit_transform([query] + all_texts)
            except ValueError as ve:
                 logger.error(f"[ConversationArchive] ValueError beim Vektorisieren: {ve}", exc_info=True) # <<< Logger
                 return [] # Keine Ergebnisse möglich

            if vectors.shape[0] < 2:
                 logger.debug("[ConversationArchive] Zu wenige Vektoren für Vergleich.")
                 return []

            similarities = cosine_similarity(vectors[0:1], vectors[1:])[0]

            # 3. Top N Ergebnisse filtern und sortieren
            relevant_indices = np.where(similarities >= similarity_threshold)[0]
            if len(relevant_indices) == 0:
                 logger.debug("[ConversationArchive] Keine Konversationen über dem Schwellenwert gefunden.") # <<< Logger
                 return []

            # Sortiere die relevanten Indizes nach Ähnlichkeit (absteigend)
            sorted_indices = relevant_indices[np.argsort(similarities[relevant_indices])[::-1]]

            # 4. Ergebnisse zusammenstellen (max_results)
            results = []
            for idx in sorted_indices[:max_results]:
                original_conv = all_conversations[idx]
                # Füge optional die Ähnlichkeit hinzu
                original_conv["_similarity_score"] = float(similarities[idx])
                results.append(original_conv)

            logger.info(f"[ConversationArchive] {len(results)} relevante Konversation(en) für Kontext gefunden.") # <<< Logger (INFO Level)
            return results

        except Exception as e:
            logger.error(f"[ConversationArchive] Fehler bei der Konversationssuche: {e}", exc_info=True) # <<< Logger
            return []
            
    def get_statistics(self) -> Dict:
        """Gibt Statistiken über das Archiv zurück"""
        try:
            total_conversations = 0
            total_messages = 0
            file_sizes = []
            
            for file in os.listdir(self.archive_dir):
                if not file.endswith('.enc'):
                    continue
                    
                file_path = os.path.join(self.archive_dir, file)
                file_sizes.append(os.path.getsize(file_path))
                
                # Lade und entschlüssele Daten
                with open(file_path, 'rb') as f:
                    encrypted_content = f.read()
                    content = self.encryption.decrypt_data(encrypted_content)
                    
                if content:
                    total_conversations += len(content["conversations"])
                    for conv in content["conversations"]:
                        total_messages += len(conv["messages"])
                        
            return {
                "total_conversations": total_conversations,
                "total_messages": total_messages,
                "total_files": len(file_sizes),
                "total_size_mb": sum(file_sizes) / (1024 * 1024),
                "avg_file_size_mb": (sum(file_sizes) / len(file_sizes)) / (1024 * 1024) if file_sizes else 0
            }
            
        except Exception as e:
            print(f"Fehler beim Erstellen der Statistiken: {str(e)}")
            return {}
        
    def get_recent_conversations(self, limit: int = 5) -> List[Dict]:
        """Holt die letzten N Konversationen aus dem Archiv"""
        try:
            with open(self.current_file, 'r', encoding='utf-8') as f:
                archive = json.load(f)
                return archive["conversations"][-limit:]
        except Exception as e:
            print(f"Fehler beim Laden der letzten Konversationen: {str(e)}")
            return []

    def get_recent_history(self, limit: int = 3) -> List[Dict]:
        """Gibt die letzten Konversationen aus dem Archiv zurück."""
        try:
            if not os.path.exists(self.archive_dir):
                return []
                
            # Liste aller JSON-Dateien im Archiv
            files = [f for f in os.listdir(self.archive_dir) if f.endswith('.json')]
            if not files:
                return []
                
            # Sortiere nach Datum (neueste zuerst)
            files.sort(key=lambda x: os.path.getmtime(os.path.join(self.archive_dir, x)), reverse=True)
            
            recent_conversations = []
            for file in files[:limit]:
                file_path = os.path.join(self.archive_dir, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        conversation = json.load(f)
                        recent_conversations.append(conversation)
                except Exception as e:
                    logger.error(f"Fehler beim Laden der Konversation {file}: {e}")
                    
            return recent_conversations
            
        except Exception as e:
            logger.error(f"Fehler beim Abrufen der Konversationshistorie: {e}")
            return [] 