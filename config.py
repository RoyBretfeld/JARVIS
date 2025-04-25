import os
import json
from typing import Any, Optional

class Config:
    def __init__(self):
        """Initialisiert die Konfiguration"""
        self.config_file = "config.json"
        self.config = self.load_config()
        # Stelle sicher, dass Standardwerte vorhanden sind
        self.ensure_defaults()
    
    def load_config(self) -> dict:
        """Lädt die Konfiguration aus der JSON-Datei"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Fehler beim Laden der Konfiguration: {e}")
                # Gib leeres Dict zurück, damit defaults gesetzt werden können
                return {}
        # Gib leeres Dict zurück, wenn Datei nicht existiert
        return {}
    
    def ensure_defaults(self):
        """Stellt sicher, dass notwendige Standardwerte in der Konfiguration existieren."""
        changed = False
        # TTS Sektion sicherstellen
        if "tts" not in self.config:
            self.config["tts"] = {}
            changed = True # Markiere als geändert, auch wenn die Sektion nur erstellt wird

        # TTS Engine Standardwert
        if not self.has_option("tts", "engine"):
            self.set("tts", "engine", "piper")
            print("Setze Standard TTS Engine: piper") # Info für den User
            changed = True

        # Coqui TTS Speaker WAV Path Standardwert (leer)
        if not self.has_option("tts", "speaker_wav_path"):
            self.set("tts", "speaker_wav_path", "") # Leerer String als Default
            print("Setze Standard TTS speaker_wav_path: (leer)")
            changed = True

        # Optional: Hier könnten weitere Defaults hinzugefügt werden
        # if not self.has_option("ollama", "model"):
        #     self.set("ollama", "model", "llama2")
        #     changed = True

        if changed:
            self.save_config()
    
    def save_config(self):
        """Speichert die Konfiguration in die JSON-Datei"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Fehler beim Speichern der Konfiguration: {e}")
    
    def save(self):
        """Alias für save_config() für Kompatibilität"""
        self.save_config()
    
    def get(self, section: str, key: str, fallback: Any = None) -> Any:
        """Holt einen Konfigurationswert"""
        # Greife sicher auf Sektionen zu, falls sie nicht existieren
        section_data = self.config.get(section, {})
        return section_data.get(key, fallback)
    
    def set(self, section: str, key: str, value: Any):
        """Setzt einen Konfigurationswert"""
        if section not in self.config:
            self.config[section] = {}
        self.config[section][key] = value
    
    def has_option(self, section: str, option: str) -> bool:
        """Prüft ob eine Option in einer Sektion existiert"""
        return section in self.config and option in self.config[section]
    
    def get_config(self) -> dict:
        """Gibt die gesamte Konfiguration zurück"""
        return self.config
    
    def set_microphone(self, index: int, name: str):
        """Speichert die Mikrofonauswahl"""
        self.set('audio', 'microphone_index', str(index))
        self.set('audio', 'microphone_name', name)
        self.save() 