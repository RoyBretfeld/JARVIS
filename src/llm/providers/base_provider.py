from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class LLMProvider(ABC):
    """Abstrakte Basisklasse für LLM-Provider."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = "Base Provider"
        self.is_initialized = False
        
    @abstractmethod
    def initialize(self) -> bool:
        """Initialisiert den Provider."""
        pass
        
    @abstractmethod
    def get_response(self, prompt: str, context: str = "") -> str:
        """Sendet eine Anfrage an den LLM und gibt die Antwort zurück."""
        pass
        
    @abstractmethod
    def get_available_models(self) -> list:
        """Gibt eine Liste der verfügbaren Modelle zurück."""
        pass
        
    @abstractmethod
    def get_current_model(self) -> str:
        """Gibt Informationen über das aktuell verwendete Modell zurück."""
        pass
        
    @abstractmethod
    def set_model(self, model_name: str) -> bool:
        """Setzt das zu verwendende Modell."""
        pass
        
    def check_connection(self) -> bool:
        """Prüft die Verbindung zum LLM-Service."""
        return self.is_initialized 