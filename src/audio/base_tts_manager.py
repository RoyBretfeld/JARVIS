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

    @abstractmethod
    def stop_playback(self):
        """
        Stoppt die aktuell laufende Sprachausgabe sofort.
        """
        pass

    def check_readiness(self) -> bool:
        """
        Gibt zurück, ob der TTS Manager einsatzbereit ist.
        """
        return self.is_ready

    @staticmethod
    def create(config):
        # tts_engine = config.get("tts", {}).get("engine", "piper") # Sicherere Variante, funktioniert auch
        # tts_engine = config.get("tts", "engine", fallback="piper") # Alt
        tts_engine = config.get("tts.engine", fallback="piper") # Neu
        logger.info(f"Bestimme TTS Engine: {tts_engine}")
        
        if tts_engine.lower() == 'piper':
            try:
                from .piper_tts_manager import PiperTTSManager
                # Lade Piper-spezifische Konfiguration
                # piper_exe = config.get("tts", "piper_executable_path", fallback="piper/piper.exe") # Alt
                piper_exe = config.get("tts.piper_executable_path", fallback="piper/piper.exe") # Neu
                # model_path = config.get("tts", "model_path", fallback="data/models/tts/de_DE-thorsten-high.onnx") # Alt
                model_path = config.get("tts.model_path", fallback="data/models/tts/de_DE-thorsten-high.onnx") # Neu
                # config_path = config.get("tts", "config_path", fallback=None) # Alt, optional
                config_path = config.get("tts.config_path", fallback=None) # Neu, optional
                
                logger.info(f"Piper Executable: {piper_exe}")
                return PiperTTSManager(piper_executable_path=piper_exe, model_path=model_path, config_path=config_path)
            except ImportError as e:
                logger.error(f'Fehler beim Importieren des PiperTTSManager: {e}. Ist Piper korrekt installiert?')
                return None
            except Exception as e:
                logger.error(f'Fehler beim Initialisieren des PiperTTSManager: {e}')
                return None

        elif tts_engine.lower() == 'coqui':
            try:
                from .coqui_tts_manager import CoquiTTSManager
                # TODO: Konfiguration für Coqui hinzufügen (Modellname etc.)
                return CoquiTTSManager(config)
            except ImportError as e:
                logger.error(f'Fehler beim Importieren des CoquiTTSManager: {e}. Ist Coqui TTS korrekt installiert?')
                return None

        else:
            logger.error(f'Unbekannte TTS Engine konfiguriert: {tts_engine}')
            return None 