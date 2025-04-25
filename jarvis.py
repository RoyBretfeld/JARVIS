import os
import sys
import logging
from logging.handlers import RotatingFileHandler
import argparse
from datetime import datetime

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

# Füge den Projekt-Root zum Python-Pfad hinzu, damit src.* importiert werden kann
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# from src.config import Config # Falscher Pfad
from config import Config # Korrekter Import aus dem Hauptverzeichnis
# Importiere die Manager-Klassen
from src.llm.llm_manager import LLMManager
from src.llm.learning_manager import LearningManager
from src.learning.river_learning_manager import RiverLearningManager
# from src.audio.audio_manager import AudioManager # Entfernt, da Modul nicht existiert
# from src.config.api_config import APIConfig # APIConfig wird hier nicht direkt gebraucht
from src.gui.main_window import MainWindow

# --- Logging Setup ---
def setup_logging():
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"jarvis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logger = logging.getLogger("JARVIS")
    logger.debug("Logging auf DEBUG-Level initialisiert.")
    return logger

def main():
    """Hauptfunktion zum Starten der Anwendung"""
    logger = setup_logging()
    logger.info("Starte JARVIS...")

    try:
        # --- 1. Konfiguration laden ---
        # config_manager = APIConfig.load_from_file() # Falsche Config-Klasse
        config_manager = Config() # Korrekter Aufruf der Haupt-Config
        # config_data = config_manager.get_config() # get_config() gibt es hier?
        logger.info("Konfiguration geladen.")

        # --- 2. Manager initialisieren ---
        logger.info("Initialisiere Manager...")
        learning_manager = LearningManager() # Korrekter Aufruf ohne Argumente
        # LLM Manager benötigt Config
        # llm_manager = LLMManager(config=config_manager) # Übergibt Config-Objekt
        # Stelle sicher, dass LLMManager das korrekte Objekt erwartet.
        # Wenn LLMManager die .get Methode braucht, ist dies korrekt.
        llm_manager = LLMManager(config=config_manager)
        river_learning_manager = RiverLearningManager()
        logger.info("Manager initialisiert.")

        # --- 3. GUI erstellen und starten ---
        logger.info("Erstelle Hauptfenster...")
        app = QApplication(sys.argv)
        # Icon Pfad relativ zum Projekt-Root
        icon_path = os.path.join(project_root, "assets", "jarvis_icon.png")
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))
        else:
             logger.warning(f"Icon-Datei nicht gefunden unter: {icon_path}")

        # MainWindow MIT Argumenten aufrufen
        main_window = MainWindow(
            config_manager=config_manager,
            llm_manager=llm_manager,
            # audio_manager=audio_manager, # Entfernt
            learning_manager=learning_manager,
            river_learning_manager=river_learning_manager
            # Wenn LM nur vom LLMManager verwendet wird, könnten wir es hier entfernen.
            # Vorerst lassen wir es, falls die GUI direkten Zugriff braucht.
        )

        logger.info("Hauptfenster erstellt.")
        logger.info("Zeige Hauptfenster an...")
        main_window.show()

        # Initialisierung der Audio-/Whisper-Komponenten NACH dem Anzeigen des Fensters?
        # Oder innerhalb von MainWindow? -> Aktuell scheint es in MainWindow zu sein.
        # Hier könnte man z.B. das Laden des Whisper-Modells anstoßen, falls es nicht in MainWindow passiert.

        logger.info("JARVIS ist bereit und startet die Event Loop.")
        sys.exit(app.exec())

    except Exception as e:
        logger.critical(f"Fehler beim Starten von JARVIS: {e}", exc_info=True)
        print(f"Ein kritischer Fehler ist aufgetreten: {e}")
        # input("JARVIS wurde wegen eines Fehlers beendet. Druecken Sie eine Taste...") # Entfernt für automatische Ausführung
        sys.exit(1)

if __name__ == '__main__':
    main()
