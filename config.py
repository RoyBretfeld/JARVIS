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
        
        # --- LLM Sektion sicherstellen ---
        if "llm" not in self.config:
            self.config["llm"] = {}
            changed = True

        # LLM Provider Standardwert
        if not self.has_option("llm", "provider"):
            self.set("llm", "provider", "Ollama")
            print("Setze Standard LLM Provider: Ollama")
            changed = True
        
        # Ollama Sub-Sektion sicherstellen
        if "ollama" not in self.config.get("llm", {}): # Sicherstellen, dass llm existiert
             if "llm" in self.config: # Nur erstellen, wenn llm Sektion existiert
                 self.config["llm"]["ollama"] = {}
                 changed = True

        # Ollama Modell Standardwert (verwende das gerade geladene 14b Modell)
        if self.has_option("llm", "provider") and self.get("llm", "provider") == "Ollama":
             if "ollama" in self.config.get("llm", {}) and not self.has_nested_option("llm", "ollama", "model"):
                 self.set_nested("llm", "ollama", "model", "qwen3:14b")
                 print("Setze Standard Ollama Modell: qwen3:14b")
                 changed = True

        # Ollama URL Standardwert
        if self.has_option("llm", "provider") and self.get("llm", "provider") == "Ollama":
            if "ollama" in self.config.get("llm", {}) and not self.has_nested_option("llm", "ollama", "url"):
                self.set_nested("llm", "ollama", "url", "http://localhost:11434")
                print("Setze Standard Ollama URL: http://localhost:11434")
                changed = True

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
    
    def get(self, key_path: str, fallback: Any = None) -> Any:
        """
        Holt einen Konfigurationswert, unterstützt verschachtelte Schlüssel mit Punktnotation.
        z.B. get('llm.ollama.model')
        """
        keys = key_path.split('.')
        value = self.config
        try:
            for key in keys:
                if isinstance(value, dict):
                    value = value[key]
                else:
                    # Wenn ein Zwischenschlüssel nicht zu einem Dict führt, ist der Pfad ungültig
                    return fallback
            return value
        except (KeyError, TypeError):
             # KeyError, wenn ein Schlüssel nicht existiert
             # TypeError, wenn versucht wird, auf ein Nicht-Dict zuzugreifen (sollte durch isinstance abgedeckt sein, aber sicher ist sicher)
            return fallback
    
    def set(self, section: str, key: str, value: Any):
        """Setzt einen Konfigurationswert (nur oberste Ebene)"""
        if section not in self.config:
            self.config[section] = {}
        self.config[section][key] = value
    
    def set_nested(self, section: str, sub_section: str, key: str, value: Any):
        """Setzt einen verschachtelten Konfigurationswert (z.B. llm.ollama.model)."""
        if section not in self.config:
            self.config[section] = {}
        if sub_section not in self.config[section]:
            self.config[section][sub_section] = {}
        self.config[section][sub_section][key] = value
    
    def has_option(self, section: str, option: str) -> bool:
        """Prüft ob eine Option in einer Sektion existiert"""
        return section in self.config and option in self.config[section]
    
    def has_nested_option(self, section: str, sub_section: str, option: str) -> bool:
        """Prüft, ob eine verschachtelte Option existiert (z.B. llm.ollama.model)."""
        return (
            section in self.config and
            isinstance(self.config[section], dict) and
            sub_section in self.config[section] and
            isinstance(self.config[section][sub_section], dict) and
            option in self.config[section][sub_section]
        )
    
    def get_config(self) -> dict:
        """Gibt die gesamte Konfiguration zurück"""
        return self.config
    
    def set_microphone(self, index: int, name: str):
        """Speichert die Mikrofonauswahl"""
        self.set('audio', 'microphone_index', str(index))
        self.set('audio', 'microphone_name', name)
        self.save() 