import os
import json
import base64
from datetime import datetime
from typing import Dict, Any
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import logging # Logger importieren

class EncryptionManager:
    def __init__(self, key_file: str = "config/encryption_key.key"):
        """Initialisiert den EncryptionManager"""
        self.key_file = key_file
        self.key_dir = os.path.dirname(key_file)
        self.fernet = None
        self.init_encryption()
        
    def init_encryption(self):
        """Initialisiert die Verschlüsselung"""
        try:
            # Stelle sicher, dass Verzeichnis existiert
            os.makedirs(self.key_dir, exist_ok=True)
            
            # Lade oder generiere Schlüssel
            if os.path.exists(self.key_file):
                with open(self.key_file, 'rb') as f:
                    key = f.read()
            else:
                # Generiere neuen Schlüssel
                key = self.generate_key()
                # Speichere Schlüssel
                with open(self.key_file, 'wb') as f:
                    f.write(key)
                    
            self.fernet = Fernet(key)
            
        except Exception as e:
            print(f"Fehler bei der Initialisierung der Verschlüsselung: {str(e)}")
            
    def generate_key(self) -> bytes:
        """Generiert einen neuen Verschlüsselungsschlüssel"""
        try:
            # Generiere Salt
            salt = os.urandom(16)
            
            # Nutze PBKDF2 für Key Derivation
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
                backend=default_backend()
            )
            
            # Generiere Key
            key = base64.urlsafe_b64encode(kdf.derive(os.urandom(32)))
            return key
            
        except Exception as e:
            print(f"Fehler bei der Schlüsselgenerierung: {str(e)}")
            return None
            
    def encrypt_data(self, data: Dict[str, Any]) -> bytes:
        """Verschlüsselt Daten"""
        try:
            if not self.fernet:
                raise Exception("Verschlüsselung nicht initialisiert")
                
            # Konvertiere zu JSON und verschlüssele
            json_data = json.dumps(data)
            encrypted_data = self.fernet.encrypt(json_data.encode())
            return encrypted_data
            
        except Exception as e:
            print(f"Fehler bei der Verschlüsselung: {str(e)}")
            return None
            
    def decrypt_data(self, encrypted_data: bytes) -> Dict[str, Any]:
        """Entschlüsselt Daten (mit verbessertem Error-Logging)"""
        try:
            if not self.fernet:
                # Sollte durch init_encryption behandelt werden, aber sicher ist sicher
                print("[EncryptionManager] FEHLER: Verschlüsselung nicht initialisiert in decrypt_data!")
                raise Exception("Verschlüsselung nicht initialisiert")

            if not encrypted_data:
                 print("[EncryptionManager] Warnung: Leere Daten zum Entschlüsseln erhalten.")
                 return None # Leere Daten können nicht entschlüsselt werden

            # Entschlüssele und parse JSON
            print("[EncryptionManager] Versuche Fernet.decrypt...") # Log vor decrypt
            decrypted_bytes = self.fernet.decrypt(encrypted_data)
            print("[EncryptionManager] Fernet.decrypt erfolgreich. Versuche decode...") # Log nach decrypt
            decrypted_string = decrypted_bytes.decode('utf-8')
            print("[EncryptionManager] Decode erfolgreich. Versuche json.loads...") # Log vor json.loads
            data = json.loads(decrypted_string)
            print("[EncryptionManager] json.loads erfolgreich.") # Log nach json.loads
            return data

        except InvalidToken:
             # Spezifischer Fehler für ungültigen Schlüssel oder beschädigte Daten
             print(f"[EncryptionManager] FEHLER bei der Entschlüsselung: InvalidToken - Schlüssel ungültig oder Daten korrumpiert.")
             return None
        except json.JSONDecodeError as json_e:
             print(f"[EncryptionManager] FEHLER bei der Entschlüsselung: JSONDecodeError - Entschlüsselte Daten sind kein gültiges JSON: {json_e}")
             # Logge die ersten paar entschlüsselten Bytes (falls möglich)
             try:
                 print(f"[EncryptionManager] Anfang der entschlüsselten (aber ungültigen) Daten: {decrypted_bytes[:100]}...")
             except NameError:
                 pass # Falls decrypted_bytes noch nicht zugewiesen wurde
             return None
        except Exception as e:
            # Allgemeiner Fehler
            print(f"[EncryptionManager] Allgemeiner FEHLER bei der Entschlüsselung: {type(e).__name__} - {str(e)}")
            import traceback
            traceback.print_exc() # Zeige vollen Traceback für unerwartete Fehler
            return None
            
    def rotate_key(self):
        """Rotiert den Verschlüsselungsschlüssel"""
        try:
            # Generiere neuen Schlüssel
            new_key = self.generate_key()
            if not new_key:
                return False
                
            # Erstelle Backup vom alten Schlüssel
            backup_file = f"{self.key_file}.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
            with open(self.key_file, 'rb') as f:
                old_key = f.read()
            with open(backup_file, 'wb') as f:
                f.write(old_key)
                
            # Speichere neuen Schlüssel
            with open(self.key_file, 'wb') as f:
                f.write(new_key)
                
            # Aktualisiere Fernet
            self.fernet = Fernet(new_key)
            return True
            
        except Exception as e:
            print(f"Fehler bei der Schlüsselrotation: {str(e)}")
            return False
            
    def secure_delete(self, file_path: str):
        """Sicheres Löschen einer Datei"""
        try:
            if os.path.exists(file_path):
                # Überschreibe mit Zufallsdaten
                size = os.path.getsize(file_path)
                with open(file_path, 'wb') as f:
                    f.write(os.urandom(size))
                # Lösche Datei
                os.remove(file_path)
                
        except Exception as e:
            print(f"Fehler beim sicheren Löschen: {str(e)}")
            
    def verify_integrity(self, data: bytes, signature: bytes) -> bool:
        """Verifiziert die Integrität der Daten"""
        try:
            if not self.fernet:
                raise Exception("Verschlüsselung nicht initialisiert")
                
            # Berechne Hash der Daten
            hasher = hashes.Hash(hashes.SHA256(), backend=default_backend())
            hasher.update(data)
            calculated_hash = hasher.finalize()
            
            # Vergleiche mit Signatur
            return calculated_hash == signature
            
        except Exception as e:
            print(f"Fehler bei der Integritätsprüfung: {str(e)}")
            return False 