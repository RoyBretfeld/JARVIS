import logging
import sys
import os

# Stelle sicher, dass das 'src' Verzeichnis im Python-Pfad ist
# (besonders wenn das Skript direkt ausgeführt wird)
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(script_dir, 'src'))

try:
    from utils.secrets_manager import SecretsManager
except ImportError as e:
    print(f"FEHLER beim Import von SecretsManager: {e}")
    print("Stellen Sie sicher, dass src/utils/secrets_manager.py existiert und Python das 'src'-Verzeichnis finden kann.")
    sys.exit(1)

# Einfaches Logging für das Skript
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

if __name__ == "__main__":
    print("Versuche, SecretsManager zu initialisieren...")
    try:
        # Verwende relative Pfade, um sicherzustellen, dass die Dateien im selben Ordner gesucht werden
        key_file_path = os.path.join(script_dir, "encryption.key")
        manager = SecretsManager(key_path=key_file_path)

        print("SecretsManager initialisiert. Versuche, Schlüssel zu generieren...")
        if manager.generate_key():
            print(f"Erfolg: Schlüsseldatei '{key_file_path}' wurde generiert.")
            print("Bitte bewahren Sie diese Datei sicher auf und fügen Sie sie NICHT zu Git hinzu.")
            sys.exit(0) # Erfolgreich beenden
        else:
            # Wenn generate_key False zurückgibt, existiert der Schlüssel wahrscheinlich schon
            if os.path.exists(key_file_path):
                 print(f"Hinweis: Schlüsseldatei '{key_file_path}' existiert bereits. Es wurde kein neuer Schlüssel generiert.")
                 sys.exit(0) # Auch hier erfolgreich beenden, da der Schlüssel ja da ist
            else:
                 print("Fehler: Schlüssel konnte nicht generiert werden (Fehler beim Speichern?).")
                 sys.exit(1) # Mit Fehler beenden

    except Exception as e:
        print(f"Ein unerwarteter Fehler ist aufgetreten: {e}")
        logging.exception("Stack Trace:") # Logge den vollen Traceback
        sys.exit(1) 