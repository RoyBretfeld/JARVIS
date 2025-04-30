# src/audio/piper_tts_manager.py
import os
import logging
import subprocess # Für den Aufruf von piper.exe
import tempfile  # Für temporäre WAV-Dateien
import winsound  # Für die WAV-Wiedergabe unter Windows
import json      # Zum Lesen der Sample Rate aus der Config
import re
import threading
import time
import sounddevice as sd # NEU: Importiere sounddevice für Wiedergabe und Stopp
import soundfile as sf # NEU: Importiere soundfile für WAV-Dateien
# Importiere die Basisklasse
from .base_tts_manager import BaseTTSManager

# Konfiguriere Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Erbe von BaseTTSManager
class PiperTTSManager(BaseTTSManager):
    """
    Verwaltet die Text-to-Speech-Ausgabe mit einer externen piper.exe.
    """
    def __init__(self,
                 piper_executable_path="piper/piper.exe", # Pfad relativ zum Projektstamm
                 model_path="data/models/tts/de_DE-thorsten-high.onnx",
                 config_path=None):
        """
        Initialisiert den PiperTTSManager und prüft die Verfügbarkeit von piper.exe und Modell.

        Args:
            piper_executable_path (str): Relativer Pfad zur piper.exe.
            model_path (str): Pfad zur .onnx Modelldatei.
            config_path (str, optional): Pfad zur .onnx.json Konfigurationsdatei.
                                        Wenn None, wird versucht, sie aus dem model_path abzuleiten.
        """
        # Rufe den Konstruktor der Basisklasse auf
        super().__init__()
        logger.info(f"Initialisiere PiperTTSManager für externe piper.exe: {piper_executable_path}")
        self.piper_exe_path = os.path.abspath(piper_executable_path)
        self.model_path = os.path.abspath(model_path)
        self.config_path = os.path.abspath(config_path) if config_path else os.path.abspath(model_path + ".json")
        self.sample_rate = None # Wird nicht mehr direkt für die Wiedergabe benötigt, aber gut zu haben
        # self.is_ready wird jetzt in der Basisklasse initialisiert
        self.current_playback = None
        self.playback_lock = threading.Lock()

        if not os.path.exists(self.piper_exe_path):
            logger.error(f"FEHLER: piper.exe nicht gefunden unter: {self.piper_exe_path}")
            self.is_ready = False # Setze is_ready explizit auf False
            return

        if not os.path.exists(self.model_path):
            logger.error(f"FEHLER: Modelldatei nicht gefunden: {self.model_path}")
            self.is_ready = False
            return
        if not os.path.exists(self.config_path):
            logger.error(f"FEHLER: Konfigurationsdatei nicht gefunden: {self.config_path}")
            self.is_ready = False
            return

        # Optional: Lese Sample Rate aus JSON für Info-Zwecke
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                self.sample_rate = int(config_data.get('audio', {}).get('sample_rate', 22050))
                logger.info(f"Sample Rate aus {self.config_path} gelesen: {self.sample_rate} Hz")
        except Exception as e:
            logger.warning(f"Konnte Sample Rate nicht aus {self.config_path} lesen: {e}")
            self.sample_rate = 22050 # Fallback
            
        # NEU: Statusvariable für aktive Wiedergabe
        self._is_playing = False

        logger.info(f"PiperTTSManager ist bereit. Verwende piper.exe: {self.piper_exe_path}")
        self.is_ready = True # Setze auf True wenn alles okay ist

    def prepare_mixed_language_text(self, text: str) -> str:
        """Bereitet Text mit gemischten Sprachen für die Synthese vor."""
        # Liste der englischen Wörter und technischen Begriffe
        english_words = {
            "software", "update", "computer", "internet", "browser",
            "email", "password", "username", "database", "server",
            "network", "firewall", "router", "monitor", "keyboard",
            "mouse", "printer", "scanner", "backup", "restore",
            "install", "uninstall", "download", "upload", "stream",
            "buffer", "cache", "proxy", "domain", "host",
            "client", "server", "protocol", "port", "socket",
            "kernel", "shell", "script", "command", "terminal",
            "console", "debug", "compile", "runtime", "framework",
            "library", "module", "package", "dependency", "repository",
            "branch", "commit", "merge", "push", "pull",
            "fork", "clone", "issue", "pull request", "milestone",
            "sprint", "backlog", "scrum", "agile", "waterfall",
            "devops", "ci/cd", "deployment", "container", "docker",
            "kubernetes", "cloud", "aws", "azure", "gcp",
            "api", "rest", "graphql", "soap", "json",
            "xml", "yaml", "toml", "ini", "csv",
            "sql", "nosql", "mongodb", "redis", "postgresql",
            "mysql", "oracle", "sqlite", "elasticsearch", "kibana",
            "logstash", "beats", "prometheus", "grafana", "jaeger",
            "zipkin", "opentelemetry", "jaeger", "zipkin", "opentelemetry",
            "Captain", "JARVIS", "Tony", "Stark", "Iron", "Man",
            "AI", "System", "Master", "Hello", "Greetings",
            "Terminator", "Hasta", "la", "vista", "baby",
            "Assistant", "Intelligent", "Support", "Analysis", "Decision",
            "Human", "Knowledge", "Skills", "Life", "People",
            "World", "Safe", "Simple", "Effective", "Solution",
            "Data", "Information", "Task", "Support", "Help",
            "Service", "Technology", "Digital", "Virtual", "Smart",
            "Automatic", "Machine", "Learning", "Neural", "Network",
            "Algorithm", "Process", "Function", "Feature", "Interface",
            "User", "Admin", "Root", "Access", "Control",
            "Security", "Privacy", "Encryption", "Authentication", "Authorization",
            "Session", "Token", "Cookie", "Cache", "Storage",
            "Memory", "Disk", "Drive", "File", "Folder",
            "Path", "Directory", "Link", "Symbol", "Icon",
            "Window", "Screen", "Display", "Monitor", "Resolution",
            "Pixel", "Color", "Theme", "Style", "Format",
            "Font", "Text", "Image", "Video", "Audio",
            "Sound", "Voice", "Speech", "Language", "Translation",
            "Code", "Program", "Application", "Software", "Hardware",
            "Device", "Peripheral", "Input", "Output", "Interface",
            "Port", "Connection", "Network", "Internet", "Web",
            "Site", "Page", "Content", "Media", "Stream",
            "Download", "Upload", "Transfer", "Share", "Sync",
            "Backup", "Restore", "Recovery", "Archive", "Compress",
            "Extract", "Install", "Uninstall", "Update", "Upgrade",
            "Patch", "Fix", "Bug", "Error", "Exception",
            "Log", "Debug", "Trace", "Profile", "Monitor",
            "Alert", "Notification", "Message", "Mail", "Chat",
            "Call", "Video", "Audio", "Conference", "Meeting",
            "Schedule", "Calendar", "Task", "Todo", "Reminder",
            "Note", "Document", "File", "Folder", "Archive",
            "Search", "Find", "Filter", "Sort", "Order",
            "Group", "Category", "Tag", "Label", "Mark",
            "Bookmark", "Favorite", "Like", "Share", "Comment",
            "Rate", "Review", "Feedback", "Report", "Statistics",
            "Analytics", "Dashboard", "Chart", "Graph", "Table",
            "List", "Grid", "View", "Layout", "Design",
            "Theme", "Style", "Format", "Template", "Pattern",
            "Model", "View", "Controller", "Service", "Repository",
            "Factory", "Singleton", "Observer", "Strategy", "Adapter",
            "Decorator", "Facade", "Proxy", "Command", "Iterator",
            "State", "Visitor", "Template", "Method", "Class",
            "Object", "Instance", "Property", "Method", "Function",
            "Parameter", "Argument", "Return", "Value", "Type",
            "Variable", "Constant", "Enum", "Struct", "Union",
            "Interface", "Abstract", "Virtual", "Override", "Final",
            "Static", "Public", "Private", "Protected", "Internal",
            "Namespace", "Package", "Module", "Import", "Export",
            "Require", "Include", "Use", "Extend", "Implement",
            "Inherit", "Override", "Abstract", "Interface", "Trait",
            "Mixin", "Composition", "Aggregation", "Association", "Dependency",
            "Coupling", "Cohesion", "Encapsulation", "Abstraction", "Polymorphism",
            "Inheritance", "Composition", "Delegation", "Proxy", "Facade",
            "Adapter", "Bridge", "Composite", "Decorator", "Flyweight",
            "Proxy", "Chain", "Command", "Interpreter", "Iterator",
            "Mediator", "Memento", "Observer", "State", "Strategy",
            "Template", "Visitor", "Abstract", "Factory", "Builder",
            "Factory", "Method", "Prototype", "Singleton", "Object",
            "Pool", "Lazy", "Loading", "Eager", "Loading",
            "Proxy", "Virtual", "Proxy", "Protection", "Proxy",
            "Remote", "Proxy", "Smart", "Reference", "Proxy",
            "Cache", "Proxy", "Synchronization", "Proxy", "Firewall",
            "Proxy", "Copy", "On", "Write", "Proxy"
        }

        # Teile den Text in Wörter
        words = text.split()
        result = []

        for word in words:
            # Entferne Satzzeichen für den Vergleich
            clean_word = re.sub(r'[^\w\s]', '', word.lower())

            # Wenn das Wort in der englischen Liste ist
            if clean_word in english_words:
                # Füge SSML-Tags hinzu und behalte die originale Formatierung bei
                result.append(f'<lang xml:lang="en-US">{word}</lang>')
            else:
                result.append(word)

        return ' '.join(result)

    def play_audio_async_sd(self, wav_file: str):
        """Spielt Audio asynchron mit sounddevice ab, um Stoppen zu ermöglichen."""
        def playback_thread():
            temp_file_to_delete = wav_file
            try:
                # Lese die WAV-Datei
                data, fs = sf.read(wav_file, dtype='float32')
                with self.playback_lock:
                    self._is_playing = True
                logger.debug(f"Starte Wiedergabe von: {wav_file} mit sounddevice (Samplerate: {fs})")
                # Spiele die Datei ab (blockierend innerhalb dieses Threads)
                sd.play(data, fs)
                # Warte, bis die Wiedergabe abgeschlossen ist ODER gestoppt wird
                sd.wait()
                logger.debug(f"Wiedergabe von {wav_file} beendet (oder gestoppt).")

            except Exception as e:
                logger.error(f"Fehler bei der Wiedergabe von {wav_file} mit sounddevice: {e}", exc_info=True)
            finally:
                with self.playback_lock:
                    self._is_playing = False
                # Lösche die temporäre Datei
                if temp_file_to_delete:
                    try:
                        os.unlink(temp_file_to_delete)
                        logger.info(f"Temporäre WAV-Datei gelöscht: {temp_file_to_delete}")
                    except Exception as e_del:
                        logger.error(f"Fehler beim Löschen der temporären WAV-Datei {temp_file_to_delete}: {e_del}")

        thread = threading.Thread(target=playback_thread)
        thread.daemon = True
        thread.start()

    def speak(self, text: str):
        """Synthetisiert Text zu Sprache und spielt ihn asynchron ab"""
        if not self.is_ready:
            logger.error("PiperTTSManager ist nicht bereit")
            return

        if not text:
            logger.warning("Leerer Text zum Sprechen übergeben")
            return

        # Bereite den Text mit Sprachmarkierungen vor
        prepared_text = self.prepare_mixed_language_text(text)

        # Füge SSML-Wrapper nur hinzu, wenn englische Wörter vorhanden sind
        # und das 'speak'-Tag nicht schon manuell eingefügt wurde.
        if '<lang xml:lang="en-US">' in prepared_text and not prepared_text.strip().startswith('<speak>'):
            ssml_text = f'<speak>{prepared_text}</speak>'
            logger.debug("SSML <speak>-Tag hinzugefügt.")
        else:
            ssml_text = prepared_text
            logger.debug("Kein <speak>-Tag hinzugefügt (entweder kein Englisch oder schon vorhanden).")


        temp_wav_file = None
        try:
            # Erstelle temporäre Datei sicher
            fd, temp_wav_file = tempfile.mkstemp(suffix=".wav")
            os.close(fd) # Schließe den Dateideskriptor sofort

            logger.debug(f"Erstelle temporäre WAV-Datei: {temp_wav_file}")

            command = [
                self.piper_exe_path,
                "--model", self.model_path,
                "--config", self.config_path,
                "--output_file", temp_wav_file,
                "--ssml" # Annahme, dass Piper SSML über stdin erwartet, wenn --ssml gesetzt ist
            ]

            logger.debug(f"Führe Piper aus: {' '.join(command)}")
            # Übergebe SSML-Text als Input
            process = subprocess.run(
                command,
                input=ssml_text.encode('utf-8'), # Kodiere den Text als UTF-8 Bytes
                capture_output=True,
                check=False, # Wir prüfen den Returncode manuell
                creationflags=subprocess.CREATE_NO_WINDOW # Versteckt das Konsolenfenster unter Windows
            )

            if process.returncode != 0:
                # Dekodiere stdout und stderr für die Fehlermeldung
                stdout_str = process.stdout.decode('utf-8', errors='ignore') if process.stdout else ''
                stderr_str = process.stderr.decode('utf-8', errors='ignore') if process.stderr else ''
                # Einfache Fehlermeldung
                logger.error(f"Fehler bei piper.exe (Return Code {process.returncode})")
                # Logge stdout/stderr separat, falls vorhanden
                if stdout_str:
                    logger.error(f"Piper STDOUT: {stdout_str}")
                if stderr_str:
                    logger.error(f"Piper STDERR: {stderr_str}")
                # Lösche die (möglicherweise leere) temporäre Datei im Fehlerfall
                if temp_wav_file and os.path.exists(temp_wav_file):
                    try:
                        os.unlink(temp_wav_file)
                    except Exception as e_del_err:
                         logger.warning(f"Konnte temporäre Datei nach Fehler nicht löschen: {temp_wav_file} - {e_del_err}")
                return # Beende die Funktion hier

            if not os.path.exists(temp_wav_file) or os.path.getsize(temp_wav_file) < 100: # Mindestgröße für eine gültige WAV
                # Dekodiere stdout und stderr für die Fehlermeldung
                stdout_str = process.stdout.decode('utf-8', errors='ignore') if process.stdout else ''
                stderr_str = process.stderr.decode('utf-8', errors='ignore') if process.stderr else ''
                # Einfache Fehlermeldung
                size_info = os.path.getsize(temp_wav_file) if os.path.exists(temp_wav_file) else 'existiert nicht'
                logger.error(f"Keine gültige WAV-Datei erstellt oder Datei ist zu klein ({size_info}).")
                # Logge stdout/stderr separat, falls vorhanden
                if stdout_str:
                    logger.error(f"Piper STDOUT: {stdout_str}")
                if stderr_str:
                    logger.error(f"Piper STDERR: {stderr_str}")
                # Lösche die (möglicherweise leere) temporäre Datei im Fehlerfall
                if temp_wav_file and os.path.exists(temp_wav_file):
                    try:
                        os.unlink(temp_wav_file)
                    except Exception as e_del_err:
                         logger.warning(f"Konnte kleine/leere temporäre Datei nicht löschen: {temp_wav_file} - {e_del_err}")
                return # Beende die Funktion hier

            logger.info(f"Piper hat WAV-Datei erfolgreich erstellt: {temp_wav_file} (Größe: {os.path.getsize(temp_wav_file)} Bytes)")

            # Starte asynchrone Wiedergabe mit sounddevice
            self.play_audio_async_sd(temp_wav_file)
            
            # Die Temporärdatei wird im play_audio_async_sd Thread gelöscht

        except FileNotFoundError:
             logger.error(f"FEHLER: piper.exe nicht gefunden unter: {self.piper_exe_path}", exc_info=True)
             # Lösche temporäre Datei, falls sie erstellt wurde
             if temp_wav_file and os.path.exists(temp_wav_file):
                 try: os.unlink(temp_wav_file)
                 except Exception: pass
        except Exception as e:
            logger.error(f"Unerwarteter Fehler während der TTS: {e}", exc_info=True)
            # Hier die temporäre Datei löschen, falls sie noch existiert und erstellt wurde
            if temp_wav_file and os.path.exists(temp_wav_file):
                try:
                    os.unlink(temp_wav_file)
                    logger.info(f"Temporäre WAV-Datei nach Fehler gelöscht: {temp_wav_file}")
                except Exception as del_e:
                    logger.error(f"Fehler beim Löschen der temporären WAV-Datei nach Fehler: {del_e}")

    def stop_playback(self):
        """Stoppt die aktuelle Audiowiedergabe über sounddevice."""
        with self.playback_lock:
            if self._is_playing:
                try:
                    sd.stop()
                    self._is_playing = False # Status zurücksetzen
                    logger.info("Audiowiedergabe (sounddevice) gestoppt.")
                except Exception as e:
                    logger.error(f"Fehler beim Stoppen der sounddevice-Wiedergabe: {e}")
            else:
                logger.debug("Keine aktive Audiowiedergabe zum Stoppen gefunden.")

    # Die check_readiness Methode wird von der Basisklasse geerbt
    # def check_readiness(self) -> bool:
    #     return self.is_ready

