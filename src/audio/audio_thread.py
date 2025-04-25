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