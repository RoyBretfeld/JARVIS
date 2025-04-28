import os
import sys
import logging
from logging.handlers import RotatingFileHandler
import argparse
from datetime import datetime

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QTimer

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
# Import TaskManager
from src.tasks.task_manager import TaskManager

# --- Logging Setup ---
def setup_logging():
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    # Verwende einen festen Dateinamen zum Testen
    log_file = os.path.join(log_dir, "test_jarvis.log") 
    
    # Versuche, die Datei im Schreibmodus zu öffnen, um Berechtigungen früh zu testen
    try:
        with open(log_file, 'a') as f:
            f.write("---- Log Test Start ----\n")
        print(f"INFO: Testweise in {log_file} geschrieben.") # Konsolenausgabe zum Debuggen
    except Exception as e:
        print(f"WARNUNG: Konnte Testzeile nicht in {log_file} schreiben: {e}") # Konsolenausgabe zum Debuggen

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'), # Modus 'a' (append) ist Standard
            logging.StreamHandler(sys.stdout)
        ],
        force=True
    )
    logger = logging.getLogger("JARVIS")
    logger.debug("Logging auf DEBUG-Level initialisiert (force=True, fester Dateiname).")
    logger.info("*** TEST: Diese Zeile sollte in der Log-Datei erscheinen! ***") # Zusätzliche Testzeile
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
        # Create TaskManager instance
        task_manager = TaskManager()
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
            river_learning_manager=river_learning_manager,
            task_manager=task_manager
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
        exit_code = app.exec()
        logger.info(f"JARVIS Event Loop beendet mit Exit Code: {exit_code}")
        sys.exit(exit_code)

    except Exception as e:
        logger.critical(f"Fehler beim Starten von JARVIS: {e}", exc_info=True)
        print(f"Ein kritischer Fehler ist aufgetreten: {e}")
        # input("JARVIS wurde wegen eines Fehlers beendet. Druecken Sie eine Taste...") # Entfernt für automatische Ausführung
        logger.info("JARVIS wird nach kritischem Fehler beendet.")
        sys.exit(1)

if __name__ == '__main__':
    main()
