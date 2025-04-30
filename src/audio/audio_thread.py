import os
import logging
import threading
import time
import numpy as np
import pyaudio
from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)

class AudioProcessThread(QThread):
    """Thread für die Audioaufnahme und -verarbeitung."""
    finished = pyqtSignal(object)  # Signal für fertige Audiodaten
    update_visualization = pyqtSignal(np.ndarray)  # Signal für Audio-Visualisierung
    
    def __init__(self, chunk_size, format, channels, rate, device_index, parent=None):
        super().__init__(parent)
        self.chunk_size = chunk_size
        self.format = format
        self.channels = channels
        self.rate = rate
        self.device_index = device_index
        self.is_recording = False
        self.frames = []
        self._stop_event = threading.Event()
        self.log_prefix = "[AudioProcessThread]"
        self.p = None
        self.stream = None
        
    def stop(self):
        """Stoppt den Thread sicher."""
        logger.info(f"{self.log_prefix} Stoppe Aufnahme...")
        self._stop_event.set()
        self.is_recording = False
        
    def run(self):
        """Hauptverarbeitungsschleife für die Audioaufnahme."""
        try:
            logger.info(f"{self.log_prefix} Starte Audioaufnahme...")
            self.p = pyaudio.PyAudio()
            
            self.stream = self.p.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                input_device_index=self.device_index,
                frames_per_buffer=self.chunk_size
            )
            
            logger.info(f"{self.log_prefix} Stream erfolgreich geöffnet")
            
            start_time = time.time()
            MAX_RECORDING_TIME = 20  # Maximale Aufnahmezeit in Sekunden
            
            while self.is_recording and not self._stop_event.is_set():
                if time.time() - start_time >= MAX_RECORDING_TIME:
                    logger.info(f"{self.log_prefix} Maximale Aufnahmezeit erreicht")
                    self.is_recording = False
                    break
                    
                try:
                    data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                    self.frames.append(data)
                    
                    # Sende Daten für Visualisierung
                    chunk_data = np.frombuffer(data, dtype=np.int16)
                    normalized_data = chunk_data.astype(np.float32) / 32768.0
                    self.update_visualization.emit(normalized_data)
                except Exception as e:
                    logger.error(f"{self.log_prefix} Fehler beim Lesen des Streams: {str(e)}")
                    break
            
            # Aufnahme beenden
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
            if self.p:
                self.p.terminate()
            
            # Sende fertige Aufnahme
            if self.frames:
                audio_data = b''.join(self.frames)
                logger.info(f"{self.log_prefix} Aufnahme beendet, {len(audio_data)} Bytes aufgenommen")
                self.finished.emit(audio_data)
            else:
                logger.warning(f"{self.log_prefix} Keine Audiodaten aufgenommen")
                self.finished.emit(None)
            
        except Exception as e:
            error_msg = f"{self.log_prefix} Fehler bei der Audioaufnahme: {str(e)}"
            logger.error(error_msg)
            self.finished.emit(None)
            
        finally:
            # Cleanup
            if self.stream:
                try:
                    self.stream.stop_stream()
                    self.stream.close()
                except:
                    pass
            if self.p:
                try:
                    self.p.terminate()
                except:
                    pass

# === Neue Klasse für die Live-Audioaufnahme ===
class AudioRecordingThread(QThread):
    """Thread spezifisch für die kontinuierliche Audioaufnahme."""
    audio_data_ready = pyqtSignal(np.ndarray) # Sendet Audio-Chunks als NumPy-Array
    error = pyqtSignal(str)                   # Sendet Fehlermeldungen

    def __init__(self, device_index, sample_rate=16000, chunk_size=1024, parent=None):
        super().__init__(parent)
        self.device_index = device_index
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.format = pyaudio.paInt16 # Standardformat
        self.channels = 1            # Mono
        self._is_running = False
        self.log_prefix = "[AudioRecordingThread]"
        self.p = None
        self.stream = None

    def stop(self):
        """Stoppt den Thread sicher."""
        logger.info(f"{self.log_prefix} Stop-Anforderung erhalten.")
        self._is_running = False

    def run(self):
        """Hauptschleife für die Audioaufnahme."""
        self._is_running = True
        self.p = pyaudio.PyAudio()
        stream = None
        all_frames = [] # Liste zum Sammeln aller Chunks für die Ausgabe

        try:
            logger.info(f"{self.log_prefix} Öffne Stream mit Rate={self.sample_rate}, Chunk={self.chunk_size}, Device={self.device_index}")
            stream = self.p.open(format=self.format,
                               channels=self.channels,
                               rate=self.sample_rate,
                               input=True,
                               input_device_index=self.device_index,
                               frames_per_buffer=self.chunk_size)

            logger.info(f"{self.log_prefix} Stream geöffnet. Starte Aufnahme...")

            while self._is_running:
                try:
                    data = stream.read(self.chunk_size, exception_on_overflow=False)
                    # Konvertiere Rohdaten in NumPy Array (int16)
                    chunk_data = np.frombuffer(data, dtype=np.int16)
                    all_frames.append(chunk_data)
                    # Sende den einzelnen Chunk für die Visualisierung (optional)
                    # self.visualization_signal.emit(chunk_data.astype(np.float32) / 32768.0)

                except IOError as e:
                    if e.errno == pyaudio.paInputOverflowed:
                        logger.warning(f"{self.log_prefix} Input Buffer Overflowed! Daten könnten verloren gegangen sein.")
                        # Optional: Hier überlegen, wie man damit umgeht (z.B. Pause)
                        continue
                    else:
                        raise # Anderen IOError weiterleiten
                except Exception as e:
                     logger.error(f"{self.log_prefix} Unerwarteter Fehler beim Lesen des Streams: {e}", exc_info=True)
                     self.error.emit(f"Fehler beim Lesen: {e}")
                     self._is_running = False # Bei Fehler anhalten

            logger.info(f"{self.log_prefix} Aufnahmeschleife beendet.")

        except Exception as e:
            error_msg = f"Fehler beim Initialisieren oder während der Aufnahme: {e}"
            logger.error(f"{self.log_prefix} {error_msg}", exc_info=True)
            self.error.emit(error_msg)

        finally:
            if stream is not None:
                try:
                    stream.stop_stream()
                    stream.close()
                    logger.info(f"{self.log_prefix} Stream geschlossen.")
                except Exception as e:
                    logger.error(f"{self.log_prefix} Fehler beim Schließen des Streams: {e}")
            if self.p is not None:
                try:
                    self.p.terminate()
                    logger.info(f"{self.log_prefix} PyAudio terminiert.")
                except Exception as e:
                    logger.error(f"{self.log_prefix} Fehler beim Terminieren von PyAudio: {e}")

            # Nachdem die Schleife beendet ist, kombiniere alle Chunks und sende sie
            if all_frames:
                final_audio_data = np.concatenate(all_frames)
                logger.info(f"{self.log_prefix} Sende finale Audiodaten ({final_audio_data.shape[0]} Samples).")
                self.audio_data_ready.emit(final_audio_data)
            else:
                 logger.warning(f"{self.log_prefix} Keine Audiodaten aufgenommen zum Senden.")
# === Ende neue Klasse === 