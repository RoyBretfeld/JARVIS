import logging
import sys
import os

# Stelle sicher, dass das 'src' Verzeichnis im Python-Pfad ist
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(script_dir, 'src'))

try:
    from utils.secrets_manager import SecretsManager
except ImportError as e:
    print(f"FEHLER beim Import von SecretsManager: {e}")
    print("Stellen Sie sicher, dass src/utils/secrets_manager.py existiert und Python das 'src'-Verzeichnis finden kann.")
    sys.exit(1)

# Einfaches Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

if __name__ == "__main__":
    print("Versuche, SecretsManager zu initialisieren...")
    try:
        key_file_path = os.path.join(script_dir, "encryption.key")
        secrets_file_path = os.path.join(script_dir, "secrets.json")
        encrypted_file_path = os.path.join(script_dir, "secrets.json.enc")

        # Stelle sicher, dass key und secrets existieren
        if not os.path.exists(key_file_path):
            print(f"FEHLER: Schlüsseldatei '{key_file_path}' nicht gefunden. Bitte zuerst `generate_enc_key.py` ausführen.")
            sys.exit(1)
        if not os.path.exists(secrets_file_path):
            print(f"FEHLER: Klartext-Secret-Datei '{secrets_file_path}' nicht gefunden. Bitte erstellen Sie diese Datei mit Ihren API-Schlüsseln.")
            sys.exit(1)

        manager = SecretsManager(key_path=key_file_path, secrets_file=secrets_file_path, encrypted_file=encrypted_file_path)
        print("SecretsManager initialisiert. Versuche, Secrets zu verschlüsseln...")

        if manager.encrypt_secrets():
            print(f"Erfolg: Secrets wurden erfolgreich nach '{encrypted_file_path}' verschlüsselt.")
            print(f"WICHTIG: Fügen Sie '{secrets_file_path}' zur .gitignore hinzu (falls noch nicht geschehen).""")
            sys.exit(0) # Erfolgreich beenden
        else:
            print("Fehler: Secrets konnten nicht verschlüsselt werden.")
            sys.exit(1) # Mit Fehler beenden

    except Exception as e:
        print(f"Ein unerwarteter Fehler ist aufgetreten: {e}")
        logging.exception("Stack Trace:")
        sys.exit(1) 