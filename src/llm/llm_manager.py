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
from data.models.hermes.hermes_runner import query_hermes
from .providers.hermes_provider import HermesProvider
import uuid
import time
from bs4 import BeautifulSoup

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
        archive_dir = self.config.get("archive", "archive_dir", "data/conversations")
        learning_dir = self.config.get("learning", "learning_dir", "data/learning")
        safety_config_path = self.config.get("safety", "config_path", "config/safety_rules.json")
        
        self.archive = ConversationArchive(archive_dir=archive_dir)
        self.learning = LearningManager(learning_dir=learning_dir)
        self.safety = SafetyManager(config_path=safety_config_path)
        
        self.providers: Dict[str, LLMProvider] = {}
        self.current_provider: Optional[LLMProvider] = None
        
        # Initialisiere Provider
        self._init_providers()
        
        self.learning_manager = self.learning
        self.online_mode = True  # Standardmäßig online
        
        # Debug-Logging für Wetter-Konfiguration
        logger.info("Lade Wetter-API-Konfiguration...")
        self.weather_api_key = self.config.get('weather', 'api_key')
        logger.info(f"Geladener API-Key: {self.weather_api_key}")
        self.weather_city = self.config.get('weather', 'city', fallback='Dresden,01139,DE')
        self.weather_units = self.config.get('weather', 'units', fallback='metric')
        self.weather_language = self.config.get('weather', 'language', fallback='de')
        self.weather_cache = {
            'data': None,
            'timestamp': None,
            'cache_duration': 300  # 5 Minuten Cache
        }
        logger.info(f"Wetter-API-Konfiguration geladen: API-Key={self.weather_api_key}, Stadt={self.weather_city}")
        logger.info("LLM Manager initialisiert")
        
    def _init_providers(self):
        """Initialisiert alle verfügbaren LLM-Provider."""
        # Ollama Provider
        ollama_provider = OllamaProvider(self.config)
        if ollama_provider.initialize():
            self.providers["Ollama"] = ollama_provider
            # Setze das Modell auf llama3:8b
            ollama_provider.set_model("llama3:8b")
            
        # Hermes Provider
        hermes_provider = HermesProvider(self.config)
        self.providers["Hermes"] = hermes_provider
        
        # Setze Ollama als Standard-Provider
        self.current_provider = ollama_provider
        logger.info(f"Standard-Provider gesetzt auf: {ollama_provider.name}")
        
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
        """Verarbeitet einen Text und gibt eine Antwort zurück."""
        logger.info(f"[LLMManager] Verarbeite Text: {text}...")
        
        if not text or not isinstance(text, str):
            return "Entschuldigung, ich habe keine Eingabe erhalten."
            
        try:
            # Normalisiere den Text
            normalized_text = text.lower().strip()
            
            # Prüfe auf Zeitabfrage
            if any(keyword in normalized_text for keyword in ['wie spät', 'uhrzeit', 'aktuelle zeit']):
                try:
                    current_time = datetime.now().strftime("%H:%M Uhr")
                    return f"Die aktuelle Uhrzeit ist {current_time}."
                except Exception as time_error:
                    logger.error(f"Fehler bei der Zeitabfrage: {str(time_error)}")
                    return "Entschuldigung, ich konnte die aktuelle Uhrzeit nicht abrufen."
            
            # Wenn keine Zeitabfrage, verarbeite normal
            try:
                # Hole relevanten Kontext
                context = self.learning.get_relevant_context(text)
                
                # Generiere Antwort
                response_data = self.current_provider.get_response(text, context=context)
                
                # Extrahiere Antwort
                if isinstance(response_data, dict):
                    response = response_data.get("response", "")
                    model = response_data.get("model", self.current_provider.get_current_model())
                else:
                    response = response_data
                    model = self.current_provider.get_current_model()
                
                # Generiere ID und speichere
                response_id = f"response_{datetime.now().isoformat()}_{uuid.uuid4()}"
                self.last_response_id = response_id
                
                # Metadaten
                metadata = {
                    "entry_type": "response",
                    "query_text": text,
                    "provider": self.current_provider.name,
                    "model": model,
                    "timestamp": datetime.now().isoformat(),
                    "feedback_stats": json.dumps({"positive": 0, "negative": 0})
                }
                
                # Speichere in LearningManager
                self.learning.add_entry(doc_id=response_id, content=response, metadata=metadata)
                
                return response
                
            except Exception as e:
                # Korrigierter Fehler: Verwende festen String statt self.log_prefix
                error_msg = f"[LLMManager] Fehler bei der Textverarbeitung: {e}" 
                logger.error(error_msg)
                # Stelle sicher, dass traceback importiert ist (sollte oben sein)
                import traceback 
                logger.error(traceback.format_exc()) 
                return "Entschuldigung, ich konnte deine Anfrage nicht verarbeiten."
                
        except Exception as e:
            error_msg = f"Fehler bei der Textverarbeitung: {str(e)}"
            logger.error(error_msg)
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
            response = requests.get(f"{self.config.get('ollama', 'url', default='http://localhost:11434')}/api/tags")
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
    
    def build_context(self, archive_history: List[Dict], learning_context: str) -> str:
        """Baut den Kontext für die Antwortgenerierung - jetzt mit klareren Trennern."""
        context_parts = [] # Geändert zu context_parts für Klarheit
        
        # Füge Archivkontext hinzu
        if archive_history:
            logger.debug(f"[LLMManager.build_context] Füge {len(archive_history)} Konversation(en) aus dem Archiv zum Kontext hinzu.")
            context_parts.append("### Relevante frühere Gespräche ###") # Klarer Trenner
            for conv in archive_history:
                conv_id = conv.get('id', 'Unbekannte ID')
                conv_score = conv.get('score', -1.0)
                logger.debug(f"[LLMManager.build_context] - Archiv-Konv. ID: {conv_id}, Score: {conv_score:.4f}")
                messages = conv.get("messages", [])[-3:] # Nutze die letzten 3 Nachrichten jeder Konversation
                for msg in messages:
                    role = msg.get('role', 'Unbekannt').capitalize()
                    content = msg.get('content', '')
                    context_parts.append(f"{role}: {content}")
            context_parts.append("### Ende frühere Gespräche ###") # Klarer Trenner
            context_parts.append("") # Leerzeile für Abstand
            
        # Füge Lernkontext hinzu
        if learning_context and learning_context.strip(): # Prüfe, ob nicht leer oder nur Whitespace
            logger.debug("[LLMManager.build_context] Füge Lernkontext hinzu.")
            context_parts.append("### Relevante Lernerfahrungen ###") # Klarer Trenner
            context_parts.append(learning_context) # Der String enthält bereits Formatierung
            context_parts.append("### Ende Lernerfahrungen ###") # Klarer Trenner
            context_parts.append("") # Leerzeile für Abstand
        else:
             logger.debug("[LLMManager.build_context] Kein relevanter Lernkontext gefunden oder leer.")

        # Füge aktuelle Konversation hinzu
        if self.conversation_history:
            logger.debug(f"[LLMManager.build_context] Füge {len(self.conversation_history)} Nachrichten aus aktueller Konversation hinzu.")
            context_parts.append("### Aktuelles Gespräch (letzte Nachrichten) ###") # Klarer Trenner
            # Nimm die letzten max_history/2 Paare oder max 6 Nachrichten?
            # Nehmen wir die letzten 6 Nachrichten für den Prompt
            history_limit = 6
            relevant_history_messages = self.conversation_history[-history_limit:]
            for msg in relevant_history_messages:
                 role = msg.get('role', 'Unbekannt').capitalize()
                 content = msg.get('content', '')
                 context_parts.append(f"{role}: {content}")
            context_parts.append("### Ende aktuelles Gespräch ###") # Klarer Trenner
            context_parts.append("") # Leerzeile für Abstand
        else:
            logger.debug("[LLMManager.build_context] Keine aktuelle Konversationshistorie vorhanden.")

        context_str = "\n".join(context_parts)
        logger.debug(f"[LLMManager.build_context] Kontextstring gebaut (Länge: {len(context_str)} Zeichen).")
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
        """Aktualisiert den System-Prompt im Manager und im aktiven Provider."""
        logger.info(f"Aktualisiere System-Prompt im LLMManager...")
        # Hier könnten wir auch self.prompts aktualisieren und speichern,
        # aber das Wichtigste ist, den Provider zu informieren.
        if self.current_provider and hasattr(self.current_provider, 'update_system_prompt'):
            try:
                self.current_provider.update_system_prompt(new_prompt)
                logger.info("System-Prompt erfolgreich an den aktiven Provider weitergegeben.")
            except Exception as e:
                logger.error(f"Fehler beim Weitergeben des System-Prompts an den Provider: {e}", exc_info=True)
        elif not self.current_provider:
            logger.warning("Kein aktiver Provider zum Aktualisieren des System-Prompts vorhanden.")
        else: # Provider existiert, aber hat keine update_system_prompt Methode
            logger.warning(f"Aktiver Provider '{self.current_provider.name}' unterstützt das Aktualisieren des System-Prompts nicht.")
        
    def ask_llm(self, prompt: str) -> str:
        """Sendet einen einfachen Prompt an das LLM (für interne Zwecke)."""
        return query_hermes(prompt) 

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