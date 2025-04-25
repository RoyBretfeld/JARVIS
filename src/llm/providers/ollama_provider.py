import requests
from typing import List, Dict, Any
from .base_provider import LLMProvider
import logging
import json

logger = logging.getLogger(__name__)

class OllamaProvider(LLMProvider):
    """Ollama-spezifische Implementierung des LLM-Providers."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.name = "Ollama"
        self.url = config.get("ollama", "url", "http://localhost:11434")
        self.current_model = config.get("ollama", "model", "llama2")
        self.system_prompt = None
        
    def initialize(self) -> bool:
        """Initialisiert die Ollama-Verbindung."""
        try:
            response = requests.get(f"{self.url}/api/tags", timeout=10)
            if response.status_code == 200:
                self.is_initialized = True
                logger.info(f"[{self.name}] Verbindung erfolgreich hergestellt")
                return True
            return False
        except Exception as e:
            logger.error(f"[{self.name}] Fehler bei der Initialisierung: {e}")
            return False
            
    def get_response(self, text: str, context: str = "") -> str:
        """Sendet eine Anfrage an Ollama und gibt die Antwort zurück."""
        try:
            # Baue den Prompt
            prompt = text
            if context:
                prompt = f"{context}\n\nAktuelle Anfrage: {text}"
            
            # Sende Anfrage an Ollama
            response = requests.post(
                f"{self.url}/api/generate",
                json={
                    "model": self.current_model,
                    "prompt": prompt,
                    "system": self.system_prompt or "Du bist JARVIS, ein hilfreicher KI-Assistent. Antworte immer auf Deutsch.",
                    "stream": False
                }
            )
            
            if response.status_code == 200:
                return response.json()["response"]
            else:
                raise Exception(f"Ollama-Anfrage fehlgeschlagen mit Status {response.status_code}")
                
        except Exception as e:
            logger.error(f"Fehler bei Ollama-Anfrage: {str(e)}")
            return f"[Fehler bei der Verarbeitung: {str(e)}]"
            
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
        """Setzt das zu verwendende Modell und lädt es herunter falls nötig."""
        try:
            # Prüfe ob das Modell bereits verfügbar ist
            available_models = self.get_available_models()
            if model_name not in available_models:
                logger.info(f"Modell {model_name} nicht lokal verfügbar. Starte Download...")
                
                # Starte Download
                response = requests.post(
                    f"{self.url}/api/pull",
                    json={"name": model_name},
                    stream=True
                )
                
                if response.status_code == 200:
                    # Verarbeite den Stream für Fortschrittsanzeige
                    for line in response.iter_lines():
                        if line:
                            status = json.loads(line)
                            if 'status' in status:
                                logger.info(f"Download Status: {status['status']}")
                            if 'error' in status:
                                raise Exception(status['error'])
                    logger.info(f"Modell {model_name} erfolgreich heruntergeladen")
                else:
                    raise Exception(f"Download fehlgeschlagen mit Status {response.status_code}")
            
            # Setze das Modell als aktuelles Modell
            self.current_model = model_name
            logger.info(f"Modell gewechselt zu: {model_name}")
            return True
            
        except Exception as e:
            logger.error(f"Fehler beim Setzen/Herunterladen des Modells {model_name}: {str(e)}")
            return False
            
    def update_system_prompt(self, new_prompt: str):
        """Aktualisiert den System-Prompt."""
        self.system_prompt = new_prompt
        logger.info("System-Prompt im Ollama-Provider aktualisiert") 