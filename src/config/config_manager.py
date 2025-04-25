import os
import configparser
import logging

logger = logging.getLogger(__name__)

class ConfigManager:
    def __init__(self, config_file="config.ini"):
        self.config = configparser.ConfigParser()
        self.config_file = config_file
        self.load_config()
        
    def load_config(self):
        """Lädt die Konfiguration aus der INI-Datei."""
        try:
            if os.path.exists(self.config_file):
                logger.info(f"Lade Konfiguration aus {self.config_file}")
                self.config.read(self.config_file, encoding='utf-8')
                logger.debug(f"Verfügbare Sektionen: {self.config.sections()}")
            else:
                logger.warning(f"Konfigurationsdatei {self.config_file} nicht gefunden")
        except Exception as e:
            logger.error(f"Fehler beim Laden der Konfiguration: {str(e)}")
            
    def get(self, section: str, key: str, fallback=None):
        """Holt einen Wert aus der Konfiguration."""
        try:
            if section in self.config and key in self.config[section]:
                value = self.config[section][key]
                logger.debug(f"Konfigurationswert geladen - {section}.{key}: {value}")
                return value
            return fallback
        except Exception as e:
            logger.error(f"Fehler beim Lesen der Konfiguration {section}.{key}: {str(e)}")
            return fallback
            
    def set(self, section: str, key: str, value: str):
        """Setzt einen Wert in der Konfiguration."""
        try:
            if section not in self.config:
                self.config[section] = {}
            self.config[section][key] = value
            self.save_config()
        except Exception as e:
            logger.error(f"Fehler beim Setzen der Konfiguration {section}.{key}: {str(e)}")
            
    def save_config(self):
        """Speichert die Konfiguration in die INI-Datei."""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                self.config.write(f)
        except Exception as e:
            logger.error(f"Fehler beim Speichern der Konfiguration: {str(e)}")
            
    def get_section(self, section: str) -> dict:
        """Gibt alle Werte einer Sektion zurück."""
        try:
            if section in self.config:
                return dict(self.config[section])
            return {}
        except Exception as e:
            logger.error(f"Fehler beim Lesen der Sektion {section}: {str(e)}")
            return {} 