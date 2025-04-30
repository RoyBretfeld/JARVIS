import requests
from typing import List, Dict, Any
from .base_provider import LLMProvider
import logging
import json

logger = logging.getLogger(__name__)

class OllamaProvider(LLMProvider):
    """Ollama-spezifische Implementierung des LLM-Providers."""
    
    def __init__(self, config: 'Config'):
        super().__init__(config)
        self.config = config
        self.name = "Ollama"
        self.url = self.config.get("llm.ollama.url", "http://localhost:11434")
        self.current_model = self.config.get("llm.ollama.model", "qwen3:14b")
        self.system_prompt = None
        self.is_initialized = False
        
    def initialize(self) -> bool:
        """Initialisiert die Ollama-Verbindung und stellt sicher, dass das Modell verfügbar ist."""
        if self.is_initialized:
             logger.debug(f"[{self.name}] bereits initialisiert.")
             return True
             
        logger.info(f"[{self.name}] Initialisiere Provider für Modell '{self.current_model}' unter URL '{self.url}'...")
        
        # 1. Prüfe generelle Verbindung
        try:
            response = requests.get(f"{self.url}/api/tags", timeout=10)
            response.raise_for_status()
            logger.info(f"[{self.name}] Verbindung zu Ollama-Server erfolgreich.")
        except requests.exceptions.RequestException as e:
            logger.error(f"[{self.name}] Fehler bei der Verbindung zum Ollama-Server unter {self.url}: {e}")
            self.is_initialized = False
            return False
            
        # 2. Prüfe Verfügbarkeit des spezifischen Modells und lade es ggf. herunter
        model_name = self.current_model
        try:
            available_models = self.get_available_models()
            if model_name not in available_models:
                logger.info(f"[{self.name}] Modell '{model_name}' nicht lokal verfügbar. Starte Download...")

                # Starte Download über Ollama API
                pull_response = requests.post(
                    f"{self.url}/api/pull",
                    json={"name": model_name, "stream": False},
                    timeout=None
                )
                pull_response.raise_for_status()

                # Überprüfe die Antwort (Stream=False gibt finale Antwort)
                pull_result = pull_response.json()
                if "status" in pull_result and pull_result["status"] == "success":
                     logger.info(f"[{self.name}] Modell '{model_name}' erfolgreich heruntergeladen.")
                     # Nach erfolgreichem Download nochmal prüfen kann nicht schaden
                     available_models = self.get_available_models()
                     if model_name not in available_models:
                          logger.error(f"[{self.name}] Modell '{model_name}' nach Download immer noch nicht gelistet?")
                elif "error" in pull_result:
                    raise Exception(f"Ollama API Fehler beim Download: {pull_result['error']}")
                else:
                     logger.warning(f"[{self.name}] Unerwartete Antwort vom Ollama Pull Endpunkt: {pull_result}")

            else:
                 logger.info(f"[{self.name}] Modell '{model_name}' ist lokal verfügbar.")

            # Wenn wir hier sind, ist das Modell entweder vorhanden oder wurde (hoffentlich) geladen
            self.is_initialized = True
            logger.info(f"[{self.name}] Provider erfolgreich initialisiert mit Modell '{self.current_model}'.")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"[{self.name}] Netzwerkfehler beim Prüfen/Herunterladen des Modells '{model_name}': {e}")
            self.is_initialized = False
            return False
        except Exception as e:
            logger.error(f"[{self.name}] Fehler beim Initialisieren/Herunterladen des Modells '{model_name}': {e}")
            self.is_initialized = False
            return False
            
    def get_response(self, history: List[Dict[str, str]], context: str = "") -> Dict:
        """Sendet eine Anfrage an Ollama unter Verwendung des messages-Formats und gibt die Antwort zurück.

        Args:
            history: Der Konversationsverlauf als Liste von Dictionaries ({"role": ..., "content": ...}).
            context: Zusätzlicher Kontext.

        Returns:
            Ein Dictionary mit der Antwort und Metadaten (oder ein Fehler-Dict).
        """
        if not self.is_initialized:
             error_msg = f"[{self.name}] Provider nicht initialisiert."
             logger.error(error_msg)
             return {"response": error_msg, "response_id": None}

        try:
            # Baue das messages-Array
            messages = []
            
            # Füge den System-Prompt hinzu (falls vorhanden)
            # Methode 1: Als separater Parameter (beibehalten, falls es funktioniert)
            system_content = self.system_prompt or "Du bist JARVIS, ein hilfreicher KI-Assistent. Antworte immer auf Deutsch."
            
            # Methode 2: Als erste Nachricht (alternativ, falls Methode 1 nicht geht)
            # if self.system_prompt:
            #     messages.append({"role": "system", "content": self.system_prompt})
            
            # Füge den Kontext hinzu (optional, z.B. als System-Nachricht oder User-Nachricht vor der letzten)
            # Hier als Teil des System-Prompts hinzugefügt für Einfachheit:
            if context:
                 system_content += "\n\n--- Zusätzlicher Kontext ---\n" + context + "\n--- Ende Kontext ---"
                 
            # Füge die eigentliche Konversationshistorie hinzu
            messages.extend(history)
            
            if not messages or messages[-1]["role"] != "user":
                error_msg = "Die Anfrage an Ollama muss mit einer User-Nachricht enden."
                logger.error(error_msg)
                return {"response": f"[Fehler: {error_msg}]", "response_id": None}
                
            # Stelle sicher, dass der letzte Content ein String ist
            if not isinstance(messages[-1]["content"], str):
                logger.warning(f"Letzter Nachrichteninhalt ist kein String: {type(messages[-1]['content'])}. Konvertiere zu String.")
                messages[-1]["content"] = str(messages[-1]["content"])

            # Sende Anfrage an Ollama mit messages Format
            logger.debug(f"Sende an Ollama /api/chat mit {len(messages)} Nachrichten.") # Geändert zu /api/chat?
            # Ollama's /api/generate unterstützt auch 'messages', aber /api/chat ist oft besser dafür
            # Wir versuchen es erst weiter mit /api/generate, aber passen die Payload an.
            payload = {
                "model": self.current_model,
                "messages": messages,
                "system": system_content, # Methode 1: System-Prompt separat
                "stream": False
            }
            
            response = requests.post(f"{self.url}/api/chat", json=payload, timeout=120) # Geändert zu /api/chat Endpoint
            # response = requests.post(f"{self.url}/api/generate", json=payload, timeout=120) # Alte Zeile: /api/generate

            response.raise_for_status() # Löst HTTPError für 4xx/5xx aus
                
            response_data = response.json()
            
            # Passe die Rückgabe an das erwartete Dict-Format an
            # /api/generate gibt bei messages input oft die Antwort in 'response' zurück
            # /api/chat gibt die Antwort in response_data['message']['content'] zurück
            # Priorisiere jetzt das /api/chat Format:
            if "message" in response_data and isinstance(response_data["message"], dict) and "content" in response_data["message"]: # Für /api/chat
                 final_response = response_data["message"]["content"]
                 response_id = response_data.get("conversation_id") # ID hier holen? (Hinweis: /api/chat gibt keine response_id standardmäßig)
            elif "response" in response_data: # Fallback für /api/generate mit messages
                 final_response = response_data["response"]
                 response_id = response_data.get("context", {}).get("conversation_id") # Versuche ID zu extrahieren
            else:
                 logger.warning(f"Unerwartetes Antwortformat von Ollama (/api/chat): {response_data}")
                 final_response = "[Fehler: Unerwartetes Antwortformat von Ollama]"
                 response_id = None
                 
            # NEU: Explizit leere Antworten loggen
            if not final_response or final_response.strip() == "":
                 logger.warning(f"Ollama hat eine leere Antwort zurückgegeben für Modell {self.current_model}.")
                 
            return {"response": final_response, "response_id": response_id}

        except requests.exceptions.HTTPError as http_err:
             status_code = http_err.response.status_code
             error_body = http_err.response.text
             error_msg = f"Ollama-Anfrage fehlgeschlagen mit Status {status_code}. Antwort: {error_body}"
             logger.error(f"Fehler bei Ollama-Anfrage: {error_msg}")
             return {"response": f"[Fehler bei der Verarbeitung: {error_msg}]", "response_id": None}
        except Exception as e:
            error_msg = f"Fehler bei Ollama-Anfrage: {e}"
            logger.error(error_msg, exc_info=True)
            return {"response": f"[Fehler bei der Verarbeitung: {error_msg}]", "response_id": None}
            
    def get_available_models(self) -> list:
        """Gibt eine Liste der verfügbaren Modelle zurück."""
        try:
            response = requests.get(f"{self.url}/api/tags")
            if response.status_code == 200:
                models = response.json().get("models", [])
                return [model["name"] for model in models]
            return []
        except Exception as e:
            logger.error(f"Fehler beim Abrufen der verfügbaren Modelle: {str(e)}")
            return []
            
    def get_current_model(self) -> str:
        """Gibt den Namen des aktuellen Modells zurück."""
        return self.current_model
        
    def check_connection(self) -> bool:
        """Prüft die Verbindung zum Ollama-Server."""
        try:
            response = requests.get(f"{self.url}/api/tags")
            return response.status_code == 200
        except:
            return False
            
    def set_model(self, model_name: str) -> bool:
        """Setzt das zu verwendende Modell (Download-Logik jetzt in initialize)."""
        logger.warning(f"[{self.name}] set_model aufgerufen für '{model_name}'. Modell wird primär über Konfiguration gesteuert.")
        
        # Prüfe zumindest, ob das Modell existiert (ohne Download)
        available_models = self.get_available_models()
        if model_name in available_models:
            self.current_model = model_name
            logger.info(f"[{self.name}] Aktuelles Modell auf '{model_name}' gesetzt (war bereits verfügbar).")
            # Optional: System Prompt neu setzen oder andere Aktionen?
            return True
        else:
            logger.error(f"[{self.name}] Versuch, auf nicht verfügbares Modell '{model_name}' zu wechseln. Modell muss zuerst über Ollama verfügbar sein.")
            return False
            
    def update_system_prompt(self, new_prompt: str):
        """Aktualisiert den System-Prompt."""
        self.system_prompt = new_prompt
        logger.info("System-Prompt im Ollama-Provider aktualisiert") 