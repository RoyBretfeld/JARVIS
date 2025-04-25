import json
import os
from typing import Dict, Any

class Config:
    def __init__(self):
        self.config_dir = os.path.join("data", "config")
        self.config_file = os.path.join(self.config_dir, "gui_config.json")
        self.config: Dict[str, Any] = self.load_config()
        
    def load_config(self) -> Dict[str, Any]:
        """Lädt die Konfiguration aus der JSON-Datei"""
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)
            
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Fehler beim Laden der Konfiguration: {e}")
                return self.get_default_config()
        else:
            return self.get_default_config()
    
    def save_config(self):
        """Speichert die Konfiguration in die JSON-Datei"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Fehler beim Speichern der Konfiguration: {e}")
    
    def get_default_config(self) -> Dict[str, Any]:
        """Gibt die Standard-Konfiguration zurück"""
        return {
            "microphone": {
                "index": None,
                "name": None
            },
            "audio": {
                "sample_rate": 44100,
                "channels": 1,
                "chunk_size": 1024
            }
        }
    
    def set_microphone(self, index: int, name: str):
        """Speichert die Mikrofon-Einstellungen"""
        self.config["microphone"]["index"] = index
        self.config["microphone"]["name"] = name
        self.save_config()
    
    def get_microphone(self) -> tuple[int, str]:
        """Gibt die gespeicherten Mikrofon-Einstellungen zurück"""
        return (
            self.config["microphone"]["index"],
            self.config["microphone"]["name"]
        ) 