import os
import json
import logging
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

class SecretsManager:
    """Verwaltet das Ver- und Entschlüsseln von API-Schlüsseln."""

    def __init__(self, key_path="encryption.key", secrets_file="secrets.json", encrypted_file="secrets.json.enc"):
        self.key_path = key_path
        self.secrets_file = secrets_file
        self.encrypted_file = encrypted_file
        self.key = self._load_key()
        if self.key:
            self.fernet = Fernet(self.key)
        else:
            self.fernet = None
            logger.warning(f"Kein Verschlüsselungsschlüssel in '{self.key_path}' gefunden. Secrets können nicht geladen werden.")

    def _load_key(self):
        """Lädt den Schlüssel aus der Schlüsseldatei."""
        if os.path.exists(self.key_path):
            try:
                with open(self.key_path, "rb") as key_file:
                    return key_file.read()
            except Exception as e:
                logger.error(f"Fehler beim Laden des Schlüssels aus '{self.key_path}': {e}")
                return None
        return None

    def generate_key(self):
        """Generiert einen neuen Verschlüsselungsschlüssel und speichert ihn."""
        if os.path.exists(self.key_path):
            logger.warning(f"Schlüsseldatei '{self.key_path}' existiert bereits. Überschreibe nicht.")
            return False
        try:
            key = Fernet.generate_key()
            with open(self.key_path, "wb") as key_file:
                key_file.write(key)
            logger.info(f"Neuer Verschlüsselungsschlüssel erfolgreich in '{self.key_path}' generiert.")
            logger.warning(f"WICHTIG: Fügen Sie '{self.key_path}' zu Ihrer .gitignore hinzu und bewahren Sie den Schlüssel sicher auf!""")
            self.key = key
            self.fernet = Fernet(self.key)
            return True
        except Exception as e:
            logger.error(f"Fehler beim Generieren oder Speichern des Schlüssels: {e}")
            return False

    def encrypt_secrets(self):
        """Verschlüsselt die secrets.json Datei."""
        if not self.fernet:
            logger.error("Kein gültiger Fernet-Schlüssel zum Verschlüsseln vorhanden.")
            return False
        if not os.path.exists(self.secrets_file):
            logger.error(f"Secrets-Datei '{self.secrets_file}' nicht gefunden. Nichts zu verschlüsseln.")
            return False

        try:
            with open(self.secrets_file, "r", encoding="utf-8") as f:
                secrets_data = json.load(f)

            encrypted_data = self.fernet.encrypt(json.dumps(secrets_data).encode('utf-8'))

            with open(self.encrypted_file, "wb") as f:
                f.write(encrypted_data)
            logger.info(f"Secrets erfolgreich nach '{self.encrypted_file}' verschlüsselt.")
            logger.warning(f"WICHTIG: Fügen Sie '{self.secrets_file}' (die unverschlüsselte Version) zu Ihrer .gitignore hinzu!""")
            return True
        except json.JSONDecodeError:
            logger.error(f"Fehler: '{self.secrets_file}' enthält kein gültiges JSON.")
            return False
        except Exception as e:
            logger.error(f"Fehler beim Verschlüsseln der Secrets: {e}")
            return False

    def load_decrypted_secrets(self) -> dict:
        """Lädt und entschlüsselt die Secrets aus der verschlüsselten Datei."""
        if not self.fernet:
            logger.error("Kein gültiger Fernet-Schlüssel zum Entschlüsseln vorhanden.")
            return {}
        if not os.path.exists(self.encrypted_file):
            logger.info(f"Verschlüsselte Secrets-Datei '{self.encrypted_file}' nicht gefunden.")
            return {}

        try:
            with open(self.encrypted_file, "rb") as f:
                encrypted_data = f.read()

            decrypted_data = self.fernet.decrypt(encrypted_data)
            secrets = json.loads(decrypted_data.decode('utf-8'))
            logger.info(f"Secrets erfolgreich aus '{self.encrypted_file}' entschlüsselt und geladen.")
            return secrets
        except Exception as e:
            logger.error(f"Fehler beim Entschlüsseln oder Laden der Secrets aus '{self.encrypted_file}': {e}")
            logger.error("Mögliche Ursachen: Falscher Schlüssel, Datei beschädigt, oder Datei nicht mit diesem Schlüssel verschlüsselt.""")
            return {}

# Beispielhafte Verwendung (kann in ein separates Skript oder Tool integriert werden)
if __name__ == '__main__':
    manager = SecretsManager()

    # Schritt 1: Schlüssel generieren (nur einmal ausführen!)
    # manager.generate_key()

    # Schritt 2: secrets.json erstellen (manuell oder per Skript)
    # Beispiel-Inhalt für secrets.json:
    # {
    #   "openai_api_key": "sk-...",
    #   "weather_api_key": "your-key..."
    # }

    # Schritt 3: Secrets verschlüsseln (ausführen, nachdem secrets.json erstellt wurde)
    # manager.encrypt_secrets()

    # Schritt 4: Entschlüsselte Secrets laden (im Hauptprogramm verwenden)
    # decrypted_secrets = manager.load_decrypted_secrets()
    # if decrypted_secrets:
    #     print("Geladene Secrets:", decrypted_secrets)
    #     openai_key = decrypted_secrets.get('openai_api_key')
    #     weather_key = decrypted_secrets.get('weather_api_key')
    #     print(f"OpenAI Key: {openai_key}")
    #     print(f"Weather Key: {weather_key}")

    print("SecretsManager Beispiel beendet.")
    print("Führen Sie die Schritte 1 und 3 über die Kommandozeile oder ein separates Tool aus.") 