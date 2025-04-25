import logging
import os
from typing import Optional, List, Dict, Any
from .base_provider import LLMProvider
from data.models.hermes.hermes_runner import query_hermes, SYSTEM_PROMPT

logger = logging.getLogger(__name__)

class HermesProvider(LLMProvider):
    """Provider für das lokale Hermes LLM."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.name = "Hermes"
        self.model_name = config.get("model_name", "openhermes-2-mistral-7b")
        self.model_base_path = os.path.join("data", "models", "hermes")
        self.default_models = ["openhermes-2-mistral-7b", "mistral-7b-instruct-v0.2", "meta-llama-3-8b"]
        self.system_prompt = SYSTEM_PROMPT
        self.is_initialized = True
        logger.info("Hermes Provider initialisiert")
        self.initialize()
        
    def initialize(self) -> bool:
        """Initialisiert den Provider."""
        try:
            self.set_model(self.model_name)
            return True
        except Exception as e:
            logger.error(f"Fehler bei der Initialisierung des Hermes Providers: {e}")
            return False
        
    def get_response(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Sendet eine Anfrage an das Hermes LLM und gibt die Antwort zurück."""
        try:
            if not self.is_initialized:
                raise Exception("Provider nicht initialisiert")
                
            max_tokens = kwargs.get("max_tokens", 400)
            threads = kwargs.get("threads", 10)
            model_name = kwargs.get("model_name", self.model_name)
            
            # Versuche das kleinere Modell, wenn das größere Probleme macht
            response = query_hermes(prompt, model_name=model_name, max_tokens=max_tokens, threads=threads)
            
            # Wenn die Antwort ein Fehler ist, versuche ein anderes Modell
            if response.startswith("[Fehler:"):
                logger.warning(f"Fehler mit Modell {model_name}, versuche Fallback-Modell")
                
                # Versuche Fallback-Modelle
                for fallback_model in self.default_models:
                    if fallback_model == model_name:
                        continue  # Überspringe das Modell, das bereits fehlgeschlagen ist
                        
                    logger.info(f"Versuche Fallback-Modell: {fallback_model}")
                    fallback_response = query_hermes(prompt, model_name=fallback_model, max_tokens=max_tokens, threads=threads)
                    
                    if not fallback_response.startswith("[Fehler:"):
                        # Fallback war erfolgreich, setze als Standard
                        self.model_name = fallback_model
                        logger.info(f"Fallback auf {fallback_model} erfolgreich")
                        return {"response": fallback_response, "model": fallback_model}
                
                # Alle Fallbacks fehlgeschlagen
                return {"response": response, "model": model_name}
            
            return {"response": response, "model": model_name}
            
        except Exception as e:
            logger.error(f"Fehler bei Hermes-Anfrage: {e}")
            return {"response": f"[Fehler: {str(e)}]", "model": model_name}
        
    def get_available_models(self) -> List[str]:
        """Gibt die verfügbaren Modelle zurück."""
        try:
            available_models = []
            if os.path.exists(self.model_base_path):
                for file in os.listdir(self.model_base_path):
                    if file.endswith(".Q4_K_M.gguf"):
                        model_name = file.replace(".Q4_K_M.gguf", "")
                        available_models.append(model_name)
            return available_models
        except Exception as e:
            logger.error(f"Fehler beim Abrufen der verfügbaren Modelle: {e}")
            return []
        
    def set_model(self, model_name: str) -> bool:
        """Setzt das zu verwendende Modell."""
        try:
            model_file = f"{model_name}.Q4_K_M.gguf"
            model_path = os.path.join(self.model_base_path, model_file)
            
            # Überprüfe zunächst, ob das angeforderte Modell existiert
            if os.path.exists(model_path):
                self.model_name = model_name
                logger.info(f"Modell erfolgreich gewechselt zu: {model_name}")
                return True
                
            # Wenn das angeforderte Modell nicht existiert, versuche ein Fallback-Modell
            for fallback_model in self.default_models:
                if fallback_model == model_name:
                    continue  # Überspringe das Modell, das bereits fehlgeschlagen ist
                    
                fallback_file = f"{fallback_model}.Q4_K_M.gguf"
                fallback_path = os.path.join(self.model_base_path, fallback_file)
                
                if os.path.exists(fallback_path):
                    self.model_name = fallback_model
                    logger.info(f"Fallback auf Modell: {fallback_model}, da {model_name} nicht gefunden wurde")
                    return True
                
            # Kein funktionierendes Modell gefunden
            logger.error(f"Modell {model_name} nicht gefunden und keine Fallback-Modelle verfügbar")
            return False
            
        except Exception as e:
            logger.error(f"Fehler beim Setzen des Modells {model_name}: {e}")
            return False
        
    def get_current_model(self) -> str:
        """Gibt das aktuell verwendete Modell zurück."""
        return self.model_name
        
    def process_text(self, text: str, max_tokens: int = 400) -> Optional[str]:
        """Verarbeitet einen Text mit dem Hermes LLM."""
        response_data = self.get_response(text, max_tokens=max_tokens)
        if isinstance(response_data, dict):
            return response_data.get("response", "")
        return response_data

    def get_name(self) -> str:
        return self.name 