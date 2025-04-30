# src/audio/coqui_tts_manager.py
import logging
import os
import torch
import tempfile
import winsound
import threading
import time
from .base_tts_manager import BaseTTSManager

# Versuche Coqui TTS zu importieren
try:
    from TTS.api import TTS
    COQUI_AVAILABLE = True
except ImportError:
    TTS = None
    COQUI_AVAILABLE = False
    logging.warning("Coqui TTS Modul (TTS.api) nicht gefunden. CoquiTTSManager wird nicht verfügbar sein.")

# Versuche pydub zu importieren (für MP3-Konvertierung)
try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    AudioSegment = None
    PYDUB_AVAILABLE = False
    logging.warning("pydub nicht gefunden. MP3-Konvertierung für Coqui speaker_wav nicht möglich.")

logger = logging.getLogger(__name__)

class CoquiTTSManager(BaseTTSManager):
    """
    Verwaltet Text-to-Speech mit Coqui TTS, insbesondere XTTS v2.
    """
    def __init__(self, config):
        super().__init__(config)
        self.model_name = config.get("tts.model_name", fallback="tts_models/multilingual/multi-dataset/xtts_v2")
        self.speaker_wav_path_config = config.get("tts.speaker_wav_path", fallback="")
        self.current_speaker_wav_path = self.speaker_wav_path_config

        self.tts = None
        self.device = None
        self.playback_lock = threading.Lock() # Lock für die Wiedergabe
        self.current_playback = None
        self._current_temp_file = None

        if not COQUI_AVAILABLE:
            logger.error("Coqui TTS ist nicht installiert. Initialisierung fehlgeschlagen.")
            self.is_ready = False
            return

        try:
            # Gerät bestimmen (GPU bevorzugt)
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Coqui TTS wird auf Gerät '{self.device}' ausgeführt.")

            # TTS initialisieren und Modell laden
            logger.info(f"Lade Coqui TTS Modell: {self.model_name}...")
            self.tts = TTS(self.model_name).to(self.device)
            logger.info(f"Coqui TTS Modell '{self.model_name}' erfolgreich geladen.")

            if self.tts is None:
                 raise RuntimeError("TTS-Objekt konnte nicht initialisiert werden.")

            # Prüfe, ob ein gültiger Pfad für speaker_wav konfiguriert ist
            if not self.speaker_wav_path_config or not os.path.exists(self.speaker_wav_path_config):
                 logger.warning(f"Kein gültiger Pfad für 'speaker_wav_path' in der Konfiguration gefunden oder Datei existiert nicht: '{self.speaker_wav_path_config}'. Voice Cloning wird nicht funktionieren.")
                 # Setze is_ready nicht auf True, wenn keine Referenzstimme da ist, da XTTS sie braucht.
                 # Alternativ: Nur warnen und is_ready trotzdem setzen, wenn man hofft, dass ein Default-Speaker geht?
                 # Wir entscheiden uns erstmal für strikt: Keine Stimme -> nicht bereit.
                 self.is_ready = False
                 logger.error("CoquiTTSManager nicht bereit, da keine gültige Referenzstimme konfiguriert ist.")
                 return
            else:
                 logger.info(f"Referenzstimme für Voice Cloning konfiguriert: {self.speaker_wav_path_config}")
                 self.is_ready = True # Jetzt bereit, da Modell geladen UND Stimme konfiguriert
                 logger.info("CoquiTTSManager ist bereit.")

        except Exception as e:
            logger.error(f"Fehler beim Initialisieren von Coqui TTS ({self.model_name}): {e}", exc_info=True)
            self.tts = None
            self.is_ready = False

    def _convert_to_wav_if_needed(self, audio_path: str) -> tuple[str | None, bool]:
        """Konvertiert eine Audiodatei zu WAV, falls nötig. Gibt Pfad zur WAV und Flag zurück, ob es eine temporäre Datei ist."""
        if not os.path.exists(audio_path):
            logger.error(f"Audiodatei für Konvertierung nicht gefunden: {audio_path}")
            return None, False

        _, ext = os.path.splitext(audio_path)
        if ext.lower() == ".wav":
            logger.debug("Referenzdatei ist bereits WAV.")
            return audio_path, False # Keine temporäre Datei

        if ext.lower() in [".mp3", ".ogg", ".flac"]: # Unterstützte Typen für pydub
            if not PYDUB_AVAILABLE:
                logger.error("pydub ist nicht verfügbar. Konvertierung von {ext} zu WAV nicht möglich.")
                return None, False
            try:
                logger.info(f"Konvertiere Referenzdatei {audio_path} zu temporärem WAV...")
                audio = AudioSegment.from_file(audio_path)
                # Erstelle temporäre WAV-Datei
                fd, temp_wav = tempfile.mkstemp(suffix=".wav")
                os.close(fd)
                # Exportiere als WAV (Standard-Parameter sollten ok sein)
                audio.export(temp_wav, format="wav")
                logger.info(f"Temporäre WAV-Datei erstellt: {temp_wav}")
                return temp_wav, True # Es ist eine temporäre Datei
            except Exception as e:
                logger.error(f"Fehler bei der Konvertierung von {audio_path} zu WAV: {e}", exc_info=True)
                return None, False
        else:
            logger.warning(f"Nicht unterstützter Dateityp für Konvertierung: {audio_path}. Versuche trotzdem, es als WAV zu verwenden.")
            return audio_path, False

    def speak(self, text: str):
        if not self.is_ready or not self.tts:
            logger.error("CoquiTTSManager ist nicht bereit oder TTS-Objekt fehlt.")
            return

        if not text:
            logger.warning("Leerer Text zum Sprechen übergeben")
            return

        # Prüfe erneut den Pfad zur Referenzstimme (falls er zur Laufzeit geändert wurde? Eher unwahrscheinlich)
        if not self.speaker_wav_path_config or not os.path.exists(self.speaker_wav_path_config):
            logger.error("Keine gültige Referenzstimme beim Aufruf von speak() gefunden.")
            return

        temp_synth_wav_file = None
        temp_speaker_wav_file = None
        is_speaker_temp = False

        try:
            # Schritt 1: Referenzstimme vorbereiten (konvertieren wenn nötig)
            speaker_wav_to_use, is_speaker_temp = self._convert_to_wav_if_needed(self.speaker_wav_path_config)

            if not speaker_wav_to_use:
                logger.error("Konnte Referenzstimme nicht vorbereiten.")
                return

            temp_speaker_wav_file = speaker_wav_to_use if is_speaker_temp else None

            # Schritt 2: Temporäre Datei für die Synthese erstellen
            fd, temp_synth_wav_file = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            logger.debug(f"Erstelle temporäre WAV-Datei für Coqui TTS Synthese: {temp_synth_wav_file}")

            # Schritt 3: Sprache für XTTS bestimmen (TODO: Dynamisch machen)
            language_to_use = "de"
            logger.info(f"Synthetisiere Sprache mit Coqui TTS [{language_to_use}]: '{text[:50]}...' mit Stimme von {speaker_wav_to_use}")

            # Schritt 4: Synthese durchführen
            self.tts.tts_to_file(
                text=text,
                speaker_wav=speaker_wav_to_use, # Pfad zur (ggf. temporären) WAV
                language=language_to_use,
                file_path=temp_synth_wav_file
            )

            # Schritt 5: Temporäre Referenz-WAV löschen (falls erstellt)
            if temp_speaker_wav_file and os.path.exists(temp_speaker_wav_file):
                try:
                    os.unlink(temp_speaker_wav_file)
                    logger.info(f"Temporäre Referenz-WAV gelöscht: {temp_speaker_wav_file}")
                except Exception as e_del_ref:
                    logger.warning(f"Konnte temporäre Referenz-WAV nicht löschen: {temp_speaker_wav_file} - {e_del_ref}")
                temp_speaker_wav_file = None # Zur Sicherheit zurücksetzen

            # Schritt 6: Prüfen, ob Synthese-Datei erstellt wurde
            if not os.path.exists(temp_synth_wav_file) or os.path.getsize(temp_synth_wav_file) == 0:
                logger.error("Coqui TTS hat keine gültige WAV-Datei für die Synthese erstellt.")
                if os.path.exists(temp_synth_wav_file):
                    try: os.unlink(temp_synth_wav_file)
                    except Exception: pass
                return

            logger.info(f"Coqui TTS hat Synthese-WAV-Datei erfolgreich erstellt: {temp_synth_wav_file}")

            # Schritt 7: Audio asynchron abspielen (kümmert sich ums Löschen der Synthese-Datei)
            self.play_audio_async(temp_synth_wav_file)
            temp_synth_wav_file = None # Wird von play_audio_async gehandhabt

        except Exception as e:
            logger.error(f"Fehler während der Coqui TTS Sprachsynthese: {e}", exc_info=True)
            # Aufräumen im Fehlerfall
            if temp_synth_wav_file and os.path.exists(temp_synth_wav_file):
                try: os.unlink(temp_synth_wav_file)
                except Exception: pass
            if temp_speaker_wav_file and os.path.exists(temp_speaker_wav_file):
                 try: os.unlink(temp_speaker_wav_file)
                 except Exception: pass

    def play_audio_async(self, wav_file: str):
        """Spielt die generierte WAV-Datei asynchron ab und löscht sie danach."""
        def playback_thread():
            temp_file_to_delete = wav_file # Merken zum Löschen
            try:
                with self.playback_lock:
                    if self.current_playback:
                        try:
                            # Stoppe aktuelle Wiedergabe und lösche alte Datei
                            winsound.PlaySound(None, winsound.SND_PURGE)
                            if self._current_temp_file and os.path.exists(self._current_temp_file):
                                time.sleep(0.1)
                                os.unlink(self._current_temp_file)
                                logger.debug(f"Alte Coqui-Temp-Datei gelöscht: {self._current_temp_file}")
                        except Exception as stop_e:
                            logger.warning(f"Fehler beim Stoppen/Löschen der vorherigen Coqui-Wiedergabe: {stop_e}")

                    self.current_playback = wav_file
                    self._current_temp_file = wav_file

                    logger.debug(f"Starte Wiedergabe (Coqui): {wav_file}")
                    winsound.PlaySound(wav_file, winsound.SND_FILENAME | winsound.SND_NODEFAULT)
                    logger.debug(f"Wiedergabe (Coqui) beendet: {wav_file}")

            except Exception as e:
                logger.error(f"Fehler bei der Coqui-Wiedergabe von {wav_file}: {e}", exc_info=True)
            finally:
                with self.playback_lock:
                    self.current_playback = None
                    self._current_temp_file = None
                # Lösche die aktuelle temporäre Datei
                if temp_file_to_delete and os.path.exists(temp_file_to_delete):
                    time.sleep(0.1)
                    try:
                        os.unlink(temp_file_to_delete)
                        logger.info(f"Temporäre Coqui WAV-Datei gelöscht: {temp_file_to_delete}")
                    except Exception as e_del:
                        logger.error(f"Fehler beim Löschen der temporären Coqui WAV-Datei {temp_file_to_delete}: {e_del}")

        thread = threading.Thread(target=playback_thread)
        thread.daemon = True
        thread.start() 