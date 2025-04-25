from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)

class BaseTTSManager(ABC):
    """
    Abstrakte Basisklasse für Text-to-Speech Manager.
    """

    def __init__(self):
        self.is_ready = False

    @abstractmethod
    def speak(self, text: str):
        """
        Synthetisiert den gegebenen Text zu Sprache und spielt ihn ab.
        Die Implementierung sollte asynchron sein oder in einem eigenen Thread laufen,
        um die Hauptanwendung nicht zu blockieren.
        """
        pass

    def check_readiness(self) -> bool:
        """
        Gibt zurück, ob der TTS Manager einsatzbereit ist.
        """
        return self.is_ready

# Factory Funktion
def create_tts_manager(config):
    """
    Erstellt und gibt eine Instanz des konfigurierten TTS Managers zurück.
    """
    # Überprüfe den Typ von config und lese die Engine entsprechend aus
    if isinstance(config, dict):
        # Direkter Zugriff auf das Dictionary mit Standardwert 'piper'
        tts_engine = config.get("tts", {}).get("engine", "piper")
    elif hasattr(config, 'get'):
        # Annahme: Es ist ein Config-Objekt oder etwas Ähnliches mit einer get-Methode
        tts_engine = config.get("tts", "engine", fallback="piper") # Default auf piper
    else:
        logger.error("Ungültiger Konfigurationstyp für create_tts_manager erhalten.")
        return None

    logger.info(f'Erstelle TTS Manager für Engine: {tts_engine}')

    if tts_engine == "piper":
        try:
            from .piper_tts_manager import PiperTTSManager
            # Hole Pfade aus der Konfiguration oder verwende Defaults
            # Passe auch hier die Zugriffe an, falls nötig (vorerst belassen, falls Piper nur mit Config-Objekt geht)
            if isinstance(config, dict):
                tts_config = config.get("tts", {})
                piper_exe = tts_config.get("piper_executable_path", "piper/piper.exe")
                model_path = tts_config.get("model_path", "data/models/tts/de_DE-thorsten-high.onnx")
                config_path = tts_config.get("config_path") # Gibt None zurück wenn nicht vorhanden
            else: # Annahme: Config-Objekt
                piper_exe = config.get("tts", "piper_executable_path", fallback="piper/piper.exe")
                model_path = config.get("tts", "model_path", fallback="data/models/tts/de_DE-thorsten-high.onnx")
                config_path = config.get("tts", "config_path", fallback=None) # Optional

            return PiperTTSManager(piper_executable_path=piper_exe, model_path=model_path, config_path=config_path)
        except ImportError as e:
            logger.error(f'Fehler beim Importieren des PiperTTSManager: {e}. Ist Piper korrekt installiert?')
            return None
        except Exception as e:
            logger.error(f'Fehler beim Initialisieren des PiperTTSManager: {e}')
            return None

    elif tts_engine == "coqui":
        try:
            from .coqui_tts_manager import CoquiTTSManager
            # TODO: Konfiguration für Coqui hinzufügen (Modellname etc.)
            logger.warning("CoquiTTSManager wird erstellt, ist aber noch nicht implementiert.")
            return CoquiTTSManager() # Platzhalter
        except ImportError as e:
            logger.error(f'Fehler beim Importieren des CoquiTTSManager: {e}. Ist Coqui TTS korrekt installiert?')
            return None
        except Exception as e:
             logger.error(f'Fehler beim Initialisieren des CoquiTTSManager: {e}')
             return None

    else:
        logger.error(f'Unbekannte TTS Engine konfiguriert: {tts_engine}')
        return None 