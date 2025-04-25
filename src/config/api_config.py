import os
from dataclasses import dataclass
from typing import Dict, Any
import json

@dataclass
class APIConfig:
    """Konfiguration für API-Einstellungen"""
    weather_api_key: str = "7dcccd22f8c2d34cf7c5736b8f5f0c59"
    weather_city: str = "Dresden,01139,DE"
    weather_units: str = "metric"
    weather_language: str = "de"
    
    def __post_init__(self):
        """Lädt die Konfiguration aus der config.json nach der Initialisierung."""
        self.load_from_json()
    
    def load_from_json(self, filepath: str = "config.json"):
        """Lädt die Konfiguration aus der config.json."""
        if not os.path.exists(filepath):
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            filepath = os.path.join(project_root, filepath)
            if not os.path.exists(filepath):
                return
            
        with open(filepath, 'r', encoding='utf-8') as f:
            config = json.load(f)
            
        if 'weather' in config:
            self.weather_api_key = config['weather'].get('api_key', self.weather_api_key)
            self.weather_city = config['weather'].get('city', self.weather_city)
            self.weather_units = config['weather'].get('units', self.weather_units)
            self.weather_language = config['weather'].get('language', self.weather_language)
    
    def get(self, section: str, key: str, default: Any = None, fallback: Any = None) -> Any:
        """Gibt einen Konfigurationswert zurück."""
        if section == 'weather':
            if key == 'api_key':
                return self.weather_api_key
            elif key == 'city':
                return self.weather_city
            elif key == 'units':
                return self.weather_units
            elif key == 'language':
                return self.weather_language
        
        if hasattr(self, key):
            return getattr(self, key)
        return fallback if fallback is not None else default

    @classmethod
    def load_from_file(cls, filepath: str = "config/api_settings.json") -> "APIConfig":
        """Lädt die Konfiguration aus einer JSON-Datei."""
        if not os.path.exists(filepath):
            return cls()
            
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return cls(**data)
            
    def save_to_file(self, filepath: str = "config/api_settings.json"):
        """Speichert die Konfiguration in einer JSON-Datei."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.__dict__, f, indent=4)
            
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiert die Konfiguration in ein Dictionary."""
        return self.__dict__
        
    @classmethod
    def get_default_config(cls) -> "APIConfig":
        """Gibt eine Standardkonfiguration zurück."""
        return cls() 