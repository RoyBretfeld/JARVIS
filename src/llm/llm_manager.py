import os
import json
from typing import List, Dict, Optional
import requests
from datetime import datetime
from .conversation_archive import ConversationArchive
from .learning_manager import LearningManager
from .safety_manager import SafetyManager
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import logging
import re # Importiere Regex Modul
from .providers.ollama_provider import OllamaProvider
from .providers.base_provider import LLMProvider
import uuid
import time
from bs4 import BeautifulSoup
from .search_manager import SearchManager
from ..local_packages.nlp_processor import LocalNLPProcessor
from ..intent_classifier import IntentClassifier # NEU: Importiere IntentClassifier

# Logger für dieses Modul
logger = logging.getLogger(__name__)

# Schlüsselwörter für Meta-Fragen, bei denen Kontext ignoriert werden soll
META_QUESTION_KEYWORDS = [
    'llm', ' large language model', 'language model', 'modell', 
    'wer bist du', 'dein name', 'jarvis', 'ollama', 'konfiguration', 
    'programmiert', 'entwickelt', 'gemacht', 'erstellt'
]

class LLMManager:
    def __init__(self, config):
        """Initialisiert den LLM Manager mit einer Konfigurationsinstanz."""
        self.config = config
        self.conversation_history: List[Dict[str, str]] = []
        self.max_history = 10
        self.last_response_id = None  # Speichert die ID der letzten Antwort
        
        # Lade System-Prompts
        self.prompts = self.load_prompts()
        
        # Initialisiere Sub-Manager mit Pfaden aus der Config
        archive_dir = self.config.get("archive.archive_dir", "data/conversations")
        learning_dir = self.config.get("learning.learning_dir", "data/learning")
        safety_config_path = self.config.get("safety.config_path", "config/safety_rules.json")
        
        self.archive = ConversationArchive(archive_dir=archive_dir)
        self.learning = LearningManager(learning_dir=learning_dir)
        self.safety = SafetyManager(config_path=safety_config_path)
        
        # SearchManager und NLPProcessor instanziieren
        self.search_manager = SearchManager(config=config) # Übergib config, falls später benötigt
        self.nlp_processor = LocalNLPProcessor()
        
        # NEU: IntentClassifier instanziieren
        self.intent_classifier = IntentClassifier()
        
        # NEU: Definiere spezialisierte System-Prompts (könnten auch aus prompts.json geladen werden)
        self.specialized_prompts = {
            "code": self.prompts.get("system_code", "Du bist JARVIS, ein Experte für Programmierung. Gib präzise Code-Beispiele und Erklärungen."),
            "tech_support": self.prompts.get("system_tech", "Du bist JARVIS, ein Technikexperte. Hilf bei der Lösung von Hardware- und Softwareproblemen."),
            "knowledge": self.prompts.get("system_knowledge", "Du bist JARVIS, ein Faktenassistent. Beantworte Wissensfragen klar und präzise."),
            "chat": self.prompts.get("system_chat", "Du bist JARVIS, ein freundlicher Konversationspartner.")
        }
        self.default_system_prompt = self.prompts.get("system_default", "Du bist JARVIS, ein hilfreicher KI-Assistent. Antworte immer auf Deutsch.") # Fallback
        
        self.providers: Dict[str, LLMProvider] = {}
        self.current_provider: Optional[LLMProvider] = None
        
        # Initialisiere Provider
        self._init_providers()
        
        # NEU: Hole den formatierten System-Prompt und setze ihn für alle Provider
        formatted_system_prompt = self.get_system_prompt()
        logger.info(f"Setze System-Prompt für alle initialisierten Provider: {formatted_system_prompt}")
        for provider_name, provider_instance in self.providers.items():
            if hasattr(provider_instance, 'update_system_prompt'):
                provider_instance.update_system_prompt(formatted_system_prompt)
            else:
                logger.warning(f"Provider '{provider_name}' hat keine 'update_system_prompt' Methode.")

        self.learning_manager = self.learning
        self.online_mode = True  # Standardmäßig online
        
        # Debug-Logging für Wetter-Konfiguration
        logger.info("Lade Wetter-API-Konfiguration...")
        self.weather_api_key = self.config.get('weather.api_key')
        logger.info(f"Geladener API-Key: {self.weather_api_key}")
        self.weather_city = self.config.get('weather.city', fallback='Dresden,01139,DE')
        self.weather_units = self.config.get('weather.units', fallback='metric')
        self.weather_language = self.config.get('weather.language', fallback='de')
        self.weather_cache = {
            'data': None,
            'timestamp': None,
            'cache_duration': 300  # 5 Minuten Cache
        }
        logger.info(f"Wetter-API-Konfiguration geladen: API-Key={self.weather_api_key}, Stadt={self.weather_city}")
        logger.info("LLM Manager initialisiert")
        
    def _init_providers(self):
        """Initialisiert den in der Konfiguration festgelegten LLM-Provider."""
        provider_name = self.config.get("llm.provider", "Ollama") # Standard auf Ollama
        logger.info(f"Versuche, LLM-Provider '{provider_name}' zu initialisieren...")
        
        provider_instance: Optional[LLMProvider] = None

        if provider_name == "Ollama":
            try:
                ollama_provider = OllamaProvider(self.config)
                if ollama_provider.initialize(): # initialize prüft jetzt Modell & lädt ggf. herunter
                    self.providers["Ollama"] = ollama_provider
                    provider_instance = ollama_provider
                    logger.info(f"Ollama Provider erfolgreich initialisiert.")
                else:
                    logger.error("Initialisierung des Ollama Providers fehlgeschlagen.")
            except Exception as e:
                 logger.error(f"Ausnahme bei der Initialisierung des Ollama Providers: {e}", exc_info=True)

        # elif provider_name == "Hermes": # Entfernt
        #      try:
        #         # Annahme: HermesProvider hat auch eine initialize() Methode
        #         hermes_provider = HermesProvider(self.config)
        #         # if hermes_provider.initialize(): # Auskommentiert, falls initialize nicht existiert/gebraucht wird
        #         self.providers["Hermes"] = hermes_provider
        #         provider_instance = hermes_provider
        #         logger.info(f"Hermes Provider erfolgreich initialisiert (oder zumindest instanziiert).")
        #         # else:
        #         #    logger.error("Initialisierung des Hermes Providers fehlgeschlagen.")
        #      except Exception as e:
        #           logger.error(f"Ausnahme bei der Initialisierung des Hermes Providers: {e}", exc_info=True)
                  
        # Hier könnten weitere Provider hinzugefügt werden (elif provider_name == "XYZ": ...)
        
        else:
            logger.error(f"Unbekannter LLM-Provider in der Konfiguration: '{provider_name}'")

        # Setze den initialisierten Provider als aktuellen Provider
        if provider_instance:
            self.current_provider = provider_instance
            logger.info(f"Aktiver LLM-Provider gesetzt auf: {provider_instance.name}")
        else:
             logger.error("Kein LLM-Provider konnte erfolgreich initialisiert werden!")
             self.current_provider = None # Explizit auf None setzen

    def get_available_providers(self) -> list:
        """Gibt eine Liste der verfügbaren Provider zurück."""
        return list(self.providers.keys())
        
    def set_provider(self, provider_name: str) -> bool:
        """Setzt den aktiven LLM Provider."""
        if provider_name in self.providers:
            self.current_provider = self.providers[provider_name]
            logger.info(f"Provider gewechselt zu: {provider_name}")
            return True
        logger.error(f"Provider {provider_name} nicht verfügbar")
        return False
        
    def get_provider(self) -> str:
        """Gibt den Namen des aktiven Providers zurück."""
        return self.current_provider.name if self.current_provider else "Kein Provider"
        
    def get_active_provider(self) -> LLMProvider:
        """Gibt die aktive Provider-Instanz zurück."""
        return self.current_provider
        
    def get_response(self, text: str, context: str = "") -> str:
        """Sendet eine Anfrage an den aktuellen Provider."""
        if not self.current_provider:
            return "[Fehler: Kein LLM-Provider initialisiert]"
            
        response_data = self.current_provider.get_response(text, context=context)
        
        # Extrahiere die Antwort aus dem Rückgabewert
        if isinstance(response_data, dict):
            return response_data.get("response", "")
        return response_data
        
    def get_current_model(self) -> str:
        """Gibt das aktuell verwendete Modell zurück."""
        return self.current_provider.get_current_model() if self.current_provider else "Kein Modell"
        
    def get_available_models(self) -> list:
        """Gibt die verfügbaren Modelle des aktiven Providers zurück."""
        return self.current_provider.get_available_models() if self.current_provider else []
        
    def set_model(self, model_name: str) -> bool:
        """Setzt das zu verwendende Modell."""
        if not self.current_provider:
            return False
        return self.current_provider.set_model(model_name)
        
    def check_connection(self) -> bool:
        """Prüft die Verbindung zum aktiven Provider."""
        if not self.current_provider:
            return False
        return self.current_provider.check_connection()
        
    def get_current_system_prompt(self) -> str:
        """Gibt den aktuellen System-Prompt des aktiven Providers zurück."""
        if self.current_provider and hasattr(self.current_provider, 'system_prompt'):
            # Gebe den Prompt des Providers zurück, oder den Standard-Fallback, wenn er None ist
            return self.current_provider.system_prompt or "Du bist JARVIS, ein hilfreicher KI-Assistent. Antworte immer auf Deutsch."
        elif self.current_provider:
            logger.warning(f"Aktiver Provider '{self.current_provider.name}' hat kein 'system_prompt' Attribut.")
            return "" # Leerer String oder Standard-Prompt?
        else:
            logger.warning("Kein aktiver Provider, kann System-Prompt nicht abrufen.")
            return "" # Leerer String oder Standard-Prompt?
        
    def load_prompts(self) -> dict:
        """Lädt die Prompts aus der JSON-Datei"""
        try:
            prompts_file = os.path.join("data", "config", "prompts.json")
            if os.path.exists(prompts_file):
                with open(prompts_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                print("Warnung: prompts.json nicht gefunden, verwende Standard-Prompts")
                return {
                    "system_prompt": {
                        "content": "Du bist JARVIS, ein hilfreicher KI-Assistent.",
                        "rules": ["Antworte IMMER auf Deutsch"]
                    }
                }
        except Exception as e:
            print(f"Fehler beim Laden der Prompts: {str(e)}")
            return {}
            
    def get_system_prompt(self) -> str:
        """Erstellt den formatierten System-Prompt"""
        if not self.prompts:
            return "Du bist JARVIS, ein hilfreicher KI-Assistent. Antworte immer auf Deutsch."
            
        prompt = self.prompts.get("system_prompt", {})
        content = prompt.get("content", "")
        rules = prompt.get("rules", [])
        
        # Formatiere den kompletten Prompt
        formatted_prompt = [content]
        
        if rules:
            formatted_prompt.append("\nRegeln:")
            formatted_prompt.extend([f"- {rule}" for rule in rules])
            
        return "\n".join(formatted_prompt)
        
    def process_feedback(self, is_positive: bool, feedback_text: str = "") -> bool:
        """
        Verarbeitet Feedback zur letzten Antwort.
        
        Args:
            is_positive: True für positives Feedback (Daumen hoch), False für negatives (Daumen runter)
            feedback_text: Optionaler Feedback-Text
            
        Returns:
            bool: True wenn das Feedback erfolgreich verarbeitet wurde
        """
        if not self.last_response_id:
            logger.warning("Keine letzte Antwort-ID verfügbar für Feedback")
            return False
            
        return self.learning.add_feedback(self.last_response_id, is_positive, feedback_text)

    def process_text(self, text: str) -> str:
        """Verarbeitet die Nutzereingabe, führt optionale Aktionen aus und fragt das LLM an."""
        logger.info(f"Verarbeite Text: '{text[:50]}...'")

        # 0. Safety Check für die Eingabe
        is_safe, reason = self.safety.check_input(text)
        if not is_safe:
            logger.warning(f"Unsichere Eingabe erkannt und blockiert: {reason}")
            self.add_message("user", text) # Füge die blockierte Nachricht trotzdem hinzu
            self.add_message("assistant", reason) # Gib den Grund an den Nutzer zurück
            return reason
        
        # NEU: 1. Intent Klassifizierung
        intent = self.intent_classifier.classify_intent(text)
        logger.info(f"Erkannter Intent: {intent}")

        # NEU: 2. System-Prompt basierend auf Intent auswählen und setzen
        selected_prompt = self.specialized_prompts.get(intent, self.default_system_prompt)
        self.update_system_prompt(selected_prompt)
        logger.info(f"System-Prompt für Intent '{intent}' gesetzt.")

        # 1. Prüfe auf Wetter-Trigger
        if any(trigger in text.lower() for trigger in ["wetter", "temperatur", "regen", "sonne"]):
            logger.info("Wetter-Trigger erkannt. Versuche Wetterdaten abzurufen...")
            weather_data = self.get_weather_data()
            if weather_data:
                weather_info = f"Das Wetter in {weather_data['city']} ist {weather_data['description']}. Die Temperatur beträgt {weather_data['temp']}°C, es fühlt sich {weather_data['feels_like']}°C an. Die Luftfeuchtigkeit beträgt {weather_data['humidity']}%, der Wind weht mit {weather_data['wind_speed']} m/s. Es ist {weather_data['description']}."
                self.add_message("assistant", weather_info)
            else:
                self.add_message("assistant", "Entschuldigung, ich konnte die Wetterdaten nicht abrufen.")
            return weather_info
        
        # NEU: Intent-basierte Verarbeitung
        if intent == 'web_search' and 'query' in self.intent_classifier.classify_intent(text):
            logger.info("Intent 'web_search' erkannt. Führe Suche durch...")
            search_results = self.search_manager.web_search(text, max_results=3)
            if search_results:
                search_context = "\n\n--- Aktuelle Suchergebnisse ---\n"
                for i, res in enumerate(search_results):
                    search_context += f"{i+1}) Titel: {res.get('title', 'N/A')}\n   Snippet: {res.get('snippet', 'N/A')}\n   URL: {res.get('url', 'N/A')}\n"
                search_context += "-- Ende Suchergebnisse ---\n"
                self.add_message("assistant", search_context)
                return search_context
            else:
                self.add_message("assistant", "Websuche ergab keine Treffer.")
                return "Websuche ergab keine Treffer."
        
        # 3. Verarbeite den Text normal
        try:
            # Hole relevanten Kontext aus der DB
            db_context = self.learning.get_relevant_context(text)
            
            # Baue den gesamten Kontext mit der überarbeiteten build_context Methode
            # Übergib Web-Kontext, DB-Kontext und aktuelle Konversationshistorie
            final_combined_context = self.build_context(
                web_search_context="",
                db_context=db_context,
                current_history=self.conversation_history # Übergib die aktuelle Historie
            )
            
            # 6. Kontext für LLM bauen (Web + DB + History)
            # Baue den Kontext *nachdem* relevante Infos (Wetter, etc.) hinzugefügt wurden
            context = self.build_context(web_search_context="", db_context=db_context, current_history=self.conversation_history)
            
            # 7. LLM Abfrage mit Kontext
            logger.info("Sende Anfrage an LLM...")
            start_time = time.time()
            response_data = self.query_llm(text, context) # Nutze die neue Methode
            end_time = time.time()
            processing_time = end_time - start_time
            logger.info(f"LLM-Antwort erhalten nach {processing_time:.2f} Sekunden.")

            # Verarbeite die Antwort (extrahiere Text, etc.)
            response_text = response_data.get("response", "")
            response_id = response_data.get("response_id", str(uuid.uuid4())) # Generiere ID, falls nicht vorhanden
            self.last_response_id = response_id # Speichere die ID der letzten Antwort
            
            # --- NEU/WIEDERHERGESTELLT: <think> Blöcke entfernen --- 
            if isinstance(response_text, str):
                # Verwende re.sub zum Entfernen des gesamten Blocks
                # re.DOTALL lässt '.' auch Newlines matchen
                cleaned_response = re.sub(r'<think>.*?</think>', '', response_text, flags=re.DOTALL | re.IGNORECASE)
                # Entferne führende/folgende Leerzeichen, die übrig bleiben könnten
                response_text = cleaned_response.strip()
                logger.debug(f"Antwort nach Bereinigung: '{response_text[:100]}...'" ) # Debug Log hinzugefügt
            # --- Ende Bereinigung ---
            
            # Metadaten
            metadata = {
                "entry_type": "response",
                "query_text": text,
                "provider": self.current_provider.name,
                "model": self.current_provider.get_current_model(),
                "timestamp": datetime.now().isoformat(),
                "feedback_stats": json.dumps({"positive": 0, "negative": 0})
            }
            
            # Speichere in LearningManager
            self.learning.add_entry(doc_id=response_id, content=response_text, metadata=metadata)
            
            return response_text
            
        except Exception as e:
            # Korrigierter Fehler: Verwende festen String statt self.log_prefix
            error_msg = f"[LLMManager] Fehler bei der Textverarbeitung: {e}" 
            logger.error(error_msg)
            # Stelle sicher, dass traceback importiert ist (sollte oben sein)
            import traceback 
            logger.error(traceback.format_exc()) 
            return "Entschuldigung, ich konnte deine Anfrage nicht verarbeiten."
            
    def clear_conversation(self):
        """Löscht die aktuelle Konversation."""
        self.conversation_history = []
        
    def is_server_available(self) -> bool:
        """
        Prüft, ob der Ollama-Server verfügbar ist.
        
        Returns:
            True wenn der Server läuft, False sonst
        """
        try:
            response = requests.get(f"{self.config.get('llm.ollama.url', default='http://localhost:11434')}/api/tags")
            return response.status_code == 200
        except:
            return False

    def add_message(self, role: str, content: str) -> None:
        """Fügt eine neue Nachricht zur Konversationshistorie hinzu"""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        self.conversation_history.append(message)
        
        # Begrenze die Historie auf die letzten N Nachrichten
        if len(self.conversation_history) > self.max_history:
            self.conversation_history = self.conversation_history[-self.max_history:]
    
    def build_context(self, web_search_context: str, db_context: str, current_history: List[Dict]) -> str:
        """Baut den Kontext für die Antwortgenerierung mit klarer Struktur und Priorisierung."""
        context_parts = []
        logger.debug("[LLMManager.build_context] Baue kombinierten Kontext...")

        # 1. Websuche-Kontext (falls vorhanden)
        if web_search_context and web_search_context.strip():
            logger.debug("[LLMManager.build_context] Füge Websuche-Kontext hinzu.")
            # Der web_search_context enthält bereits die Trenner
            context_parts.append(web_search_context.strip()) 
            context_parts.append("") # Leerzeile für Abstand
        else:
            logger.debug("[LLMManager.build_context] Kein Websuche-Kontext vorhanden.")

        # 2. DB-Kontext (Lernerfahrungen) (falls vorhanden)
        if db_context and db_context.strip(): # Prüfe, ob nicht leer oder nur Whitespace
            logger.debug("[LLMManager.build_context] Füge DB-Kontext (Lernerfahrungen) hinzu.")
            context_parts.append("### Relevante Informationen aus der Wissensbasis ###") # Klarer Trenner
            context_parts.append(db_context) # Der String enthält bereits Formatierung?
            context_parts.append("### Ende Informationen Wissensbasis ###") # Klarer Trenner
            context_parts.append("") # Leerzeile für Abstand
        else:
             logger.debug("[LLMManager.build_context] Kein relevanter DB-Kontext gefunden oder leer.")

        # 3. Aktuelle Konversation (falls vorhanden)
        if current_history:
            logger.debug(f"[LLMManager.build_context] Füge {len(current_history)} Nachrichten aus aktueller Konversation hinzu.")
            context_parts.append("### Aktuelles Gespräch (letzte Nachrichten) ###") # Klarer Trenner
            # Nimm die letzten N Nachrichten (wie bisher)
            history_limit = 6 
            relevant_history_messages = current_history[-history_limit:]
            for msg in relevant_history_messages:
                 role = msg.get('role', 'Unbekannt').capitalize()
                 content = msg.get('content', '')
                 context_parts.append(f"{role}: {content}")
            context_parts.append("### Ende aktuelles Gespräch ###") # Klarer Trenner
            context_parts.append("") # Leerzeile für Abstand
        else:
            logger.debug("[LLMManager.build_context] Keine aktuelle Konversationshistorie vorhanden.")

        # Früheren Archiv-Kontext vorerst weglassen, um Komplexität zu reduzieren
        # Kann später wieder hinzugefügt werden, falls nötig.
        logger.debug("[LLMManager.build_context] Hinweis: Frühere Gespräche (Archiv) werden aktuell nicht in den Kontext eingefügt.")

        context_str = "\n".join(context_parts).strip() # Am Ende ggf. Leerzeichen entfernen
        context_preview = context_str[:500].replace('\n', ' ')
        logger.debug(f"[LLMManager.build_context] Kontextstring gebaut (Länge: {len(context_str)} Zeichen). Anfang: '{context_preview}...'")
        return context_str
        
    def is_german_response(self, text: str) -> bool:
        """Prüft ob die Antwort auf Deutsch ist"""
        # Liste deutscher Wörter/Artikel die typisch sind
        german_indicators = [
            " der ", " die ", " das ", " den ", " dem ", " des ",
            "ich ", "ist ", "sind ", "und ", "oder ", "aber ",
            "für ", "mit ", "bei ", "seit ", "von ", "bis ",
            "Ich ", "Sie ", "Wir ", "Können ", "Möchten ", "Bitte "
        ]
        
        # Prüfe ob mindestens 2 deutsche Indikatoren vorhanden sind
        count = sum(1 for indicator in german_indicators if indicator in f" {text} ")
        return count >= 2
    
    def clear_history(self) -> None:
        """Löscht die Konversationshistorie"""
        self.conversation_history = []
        
    def get_statistics(self) -> Dict:
        """Gibt kombinierte Statistiken zurück"""
        return {
            "learning_stats": self.learning.get_statistics(),
            "safety_stats": self.safety.get_statistics(),
            "archive_stats": self.archive.get_statistics()
        }

    def search_similar(self, query: str, texts: List[str], threshold: float = 0.5) -> Optional[Dict]:
        """Findet ähnliche Texte"""
        try:
            if not texts:
                return None
                
            # Vektorisiere Texte
            vectorizer = TfidfVectorizer(stop_words=None)
            vectors = vectorizer.fit_transform([query] + texts)
            
            # Berechne Ähnlichkeiten
            similarities = cosine_similarity(vectors[0:1], vectors[1:])[0]
            
            # Finde besten Match
            best_idx = np.argmax(similarities)
            best_score = similarities[best_idx]
            
            if best_score >= threshold:
                return {
                    "text": texts[best_idx],
                    "score": float(best_score),
                    "index": best_idx
                }
            return None
            
        except Exception as e:
            print(f"Fehler bei der Ähnlichkeitssuche: {str(e)}")
            return None 

    def update_system_prompt(self, new_prompt: str):
        """Aktualisiert den System-Prompt für den aktuellen Provider."""
        logger.info(f"Versuche System-Prompt zu aktualisieren: '{new_prompt[:50]}...'")
        if self.current_provider:
            if hasattr(self.current_provider, 'update_system_prompt'):
                self.current_provider.update_system_prompt(new_prompt)
                logger.info(f"System-Prompt für Provider '{self.current_provider.name}' aktualisiert.")
            else:
                logger.warning(f"Provider '{self.current_provider.name}' unterstützt 'update_system_prompt' nicht.")
        else:
            logger.warning("Kein aktiver Provider zum Aktualisieren des System-Prompts.")

    def set_online_mode(self, is_online: bool) -> bool:
        """Setzt den Online-Modus für den LLM-Manager.
        
        Args:
            is_online (bool): True für Online-Modus, False für Offline-Modus
            
        Returns:
            bool: True wenn erfolgreich, False bei Fehler
        """
        try:
            self.online_mode = is_online
            logger.info(f"Online-Modus auf {is_online} gesetzt")
            return True
        except Exception as e:
            logger.error(f"Fehler beim Setzen des Online-Modus: {str(e)}")
            return False
            
    def is_online(self) -> bool:
        """Gibt den aktuellen Online-Status zurück."""
        return self.online_mode 

    def test_weather_api(self) -> bool:
        """Testet die Wetter-API-Verbindung."""
        try:
            logger.info(f"Teste Wetter-API mit Stadt: {self.weather_city}, API-Key: {self.weather_api_key}")
            url = f"https://api.openweathermap.org/data/2.5/weather?q={self.weather_city}&appid={self.weather_api_key}&units={self.weather_units}&lang={self.weather_language}"
            logger.info(f"API URL: {url}")
            response = requests.get(url)
            logger.info(f"API Antwort Status: {response.status_code}")
            logger.info(f"API Antwort Text: {response.text}")
            
            if response.status_code == 200:
                logger.info("Wetter-API-Test erfolgreich: API ist erreichbar")
                return True
            elif response.status_code == 401:
                logger.error("Wetter-API-Test fehlgeschlagen: Ungültiger API-Key")
                return False
            else:
                logger.error(f"Wetter-API-Test fehlgeschlagen: Status Code {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Wetter-API-Test fehlgeschlagen: {str(e)}")
            return False

    def get_weather_data(self) -> Optional[Dict]:
        """Holt aktuelle Wetterdaten von OpenWeatherMap."""
        try:
            # Teste zuerst die API-Verbindung
            if not self.test_weather_api():
                logger.error("Wetter-API ist nicht erreichbar")
                return None

            url = f"https://api.openweathermap.org/data/2.5/weather?q={self.weather_city}&appid={self.weather_api_key}&units={self.weather_units}&lang={self.weather_language}"
            response = requests.get(url)
            
            if response.status_code != 200:
                logger.error(f"Fehler bei der Wetter-API-Anfrage: Status Code {response.status_code}")
                return None
                
            data = response.json()
            
            weather_data = {
                "temp": data["main"]["temp"],
                "feels_like": data["main"]["feels_like"],
                "description": data["weather"][0]["description"],
                "humidity": data["main"]["humidity"],
                "wind_speed": data["wind"]["speed"],
                "icon": data["weather"][0]["icon"],
                "city": data["name"]
            }
            
            logger.info("Wetterdaten erfolgreich abgerufen")
            return weather_data
            
        except Exception as e:
            logger.error(f"Fehler beim Abrufen der Wetterdaten: {str(e)}")
            return None

    def scrape_webpage(self, url):
        """
        Führt Web-Scraping für die angegebene URL durch.
        
        Args:
            url (str): Die zu scrapende URL
            
        Returns:
            dict: Ein Dictionary mit dem Titel und Text der Webseite
            oder None bei einem Fehler
        """
        try:
            # User-Agent hinzufügen um Blocking zu vermeiden
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            # Webseite abrufen
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # BeautifulSoup Parser erstellen
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Titel extrahieren
            title = soup.title.string if soup.title else "Kein Titel gefunden"
            
            # Text aus p, h1-h6 Tags extrahieren
            text_elements = []
            for tag in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                if tag.string:
                    text_elements.append(tag.string.strip())
            
            # Text zusammenfügen
            content = "\n".join(text_elements)
            
            logging.info(f"Web-Scraping erfolgreich für URL: {url}")
            return {
                'title': title,
                'content': content
            }
            
        except Exception as e:
            logging.error(f"Fehler beim Web-Scraping von {url}: {str(e)}")
            return None 

    def query_llm(self, user_input: str, context: str = "") -> Dict:
        """Stellt eine Anfrage an den aktiven LLM-Provider mit dem aktuellen Konversationsverlauf.
        
        Args:
            user_input (str): Die aktuelle Nutzereingabe.
            context (str): Zusätzlicher Kontext (optional).

        Returns:
            Dict: Ein Dictionary mit der Antwort und Metadaten (z.B. response_id).
                  Format: {'response': str, 'response_id': str, ...andere Provider-Daten}
        """
        if not self.current_provider:
            logger.error("Kein LLM-Provider aktiv.")
            return {"response": "[Fehler: Kein LLM-Provider initialisiert]", "response_id": None}

        # Füge die aktuelle Benutzernachricht zum Verlauf hinzu (wird *vor* der Anfrage gemacht)
        # Das Hinzufügen der Assistant-Antwort erfolgt *nach* Erhalt in process_text
        self.add_message("user", user_input)

        # Hole den aktuellen Konversationsverlauf für den Provider
        # Stelle sicher, dass die History nicht zu lang wird
        current_history = self.conversation_history[-self.max_history:]

        logger.debug(f"Sende Anfrage an Provider '{self.current_provider.name}' mit Verlauf (letzte {len(current_history)} Nachrichten) und Kontext:")
        # logger.debug(f"History: {current_history}")
        # logger.debug(f"Context: {context[:100]}...") # Nur Anfang loggen

        try:
            # Rufe die get_response Methode des *Providers* auf
            # Der Provider ist verantwortlich für das korrekte Formatieren der Anfrage
            # (z.B. Einbau des System-Prompts, History, Context, User-Input)
            response_data = self.current_provider.get_response(current_history, context=context) 
            
            if not isinstance(response_data, dict):
                # Falls der Provider nur einen String zurückgibt, packe ihn in ein Dict
                logger.warning(f"Provider '{self.current_provider.name}' gab nur einen String zurück. Erstelle Standard-Dict.")
                response_data = {"response": str(response_data), "response_id": str(uuid.uuid4())}
            elif "response" not in response_data:
                 logger.error(f"Antwort-Dict vom Provider '{self.current_provider.name}' enthält keinen 'response'-Schlüssel.")
                 response_data["response"] = "[Fehler: Ungültige Antwort vom Provider]"
            
            # Stelle sicher, dass eine response_id vorhanden ist
            if "response_id" not in response_data or not response_data["response_id"]:
                response_data["response_id"] = str(uuid.uuid4())

            return response_data

        except Exception as e:
            logger.error(f"Fehler bei der Abfrage des LLM Providers '{self.current_provider.name}': {e}", exc_info=True)
            return {"response": f"[Fehler bei der LLM-Anfrage: {e}]", "response_id": None} 