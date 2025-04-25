import os
import sys
import soundfile as sf
import numpy as np
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                           QLabel, QPushButton, QFrame, QComboBox, QDialog,
                           QScrollArea, QTextEdit, QMessageBox, QProgressDialog, 
                           QGroupBox, QStatusBar, QFileDialog, QListWidget, QDialogButtonBox, QProgressBar,
                           QApplication, QSplitter, QLineEdit, QStyle, QCheckBox,
                           QInputDialog)
from PyQt6.QtCore import Qt, QDateTime, QTimer, QThread, pyqtSignal, QMetaObject, Q_ARG, QSize, pyqtSlot, QObject
from PyQt6.QtGui import QPalette, QColor, QFont, QPainter, QPen, QIcon, QTextCursor
import threading
import queue
from datetime import datetime
from config import Config
import time
import io
from ..utils.system_monitor import SystemMonitor
from .debug_monitor import DebugMonitor
from ..llm.llm_manager import LLMManager
from ..llm.learning_manager import LearningManager
from ..learning.river_learning_manager import RiverLearningManager
from .mic_selector import MicrophoneSelector
from ..audio.audio_thread import AudioProcessThread
import requests
from .prompt_editor import PromptEditor
from ..audio.audio_processor import AudioProcessor
from .loading_screen import LoadingScreen
# Entferne alten Import
# from ..audio.tts_manager import TTSManager
# Importiere die Factory und die Basisklasse (für Type Hinting, optional)
from ..audio.base_tts_manager import BaseTTSManager, create_tts_manager
import traceback
import shutil
from typing import List, Dict, Optional
import logging
import pyaudio
import math # Import math für Umrechnung
import platform
import psutil
import uuid
# Importiere die Audiobook-Verarbeitungsfunktion
from ..learning.audiobook_learning import find_and_process_audio_in_folder
# Import WhisperRecognizer für Type Hinting im AudiobookImportThread
from ..speech.whisper_recognition import WhisperRecognizer
# Korrigierter Import für StatusWidget
from .widgets.status_widget import StatusWidget
from .audio_settings_widget import AudioSettingsWidget # Import new widget

# Konfiguriere das Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('jarvis.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Re-add logging configuration and logger definition
# Konfiguriere das Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('jarvis.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Füge eine frühe Testmeldung hinzu
logger.info("==== Logging initialisiert ====")

# Konstante für DB Pfad (relativ zum Workspace Root)
# Holen wir uns den Pfad lieber aus der LM-Konstante?
# Vorerst hier hardcoded, aber besser wäre es, ihn zentral zu verwalten.
CHROMA_DB_DISPLAY_PATH = "data/knowledge_base/chroma_db"

# Hilfsfunktion
def get_directory_size(directory):
    """Berechnet die Gesamtgröße eines Verzeichnisses in Kilobyte."""
    total_size = 0
    try:
        if not os.path.exists(directory):
            logger.info(f"Verzeichnis nicht gefunden: {directory}")
            return 0.0
        for dirpath, dirnames, filenames in os.walk(directory):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if not os.path.islink(fp):
                    try:
                        total_size += os.path.getsize(fp)
                    except OSError as e:
                        logger.warning(f"Konnte Größe von {fp} nicht lesen: {e}")
                        pass
    except Exception as e:
        logger.error(f"Fehler beim Berechnen der Verzeichnisgröße '{directory}': {e}")
        return -1.0

    return total_size / 1024 if total_size > 0 else 0.0  # Konvertiere zu KB

class AudioVisualizer(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.audio_data = np.zeros(100)
        self.audio_buffer = None  # Buffer für die Aufnahme
        self.is_recording = False
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update)
        self.update_timer.start(50)  # 20 FPS
        
        # Wiedergabe-Variablen
        self.is_playing = False
        self.playback_thread = None
        self.p = None
        self.stream = None
        self.stop_playback = False
        
    def update_audio_data(self, data):
        """Aktualisiert die Audiodaten für die Visualisierung"""
        self.audio_data = data
        
    def paintEvent(self, event):
        """Zeichnet die Audio-Visualisierung"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Setze die Zeichenfarbe basierend auf dem Status
        if self.is_recording:
            color = QColor("#ff4444")  # Rot während der Aufnahme
        elif self.is_playing:
            color = QColor("#00ff00")  # Grün während der Wiedergabe
        else:
            color = QColor("#00ff00")  # Standard grün
            
        painter.setPen(QPen(color, 2))
        
        # Berechne die Skalierung
        width = self.width()
        height = self.height()
        center_y = height / 2
        
        # Zeichne die Wellenform
        for i in range(len(self.audio_data) - 1):
            x1 = (i / len(self.audio_data)) * width
            x2 = ((i + 1) / len(self.audio_data)) * width
            
            y1 = center_y + (self.audio_data[i] * height / 2)
            y2 = center_y + (self.audio_data[i + 1] * height / 2)
            
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))
    
    def start_recording(self):
        """Startet die Aufnahme"""
        self.is_recording = True
        self.audio_buffer = None
        self.update()
    
    def stop_recording(self):
        """Stoppt die Aufnahme"""
        self.is_recording = False
        self.update()
    
    def play_recording(self):
        """Gibt die Aufnahme wieder"""
        if self.audio_buffer is None or self.is_playing:
            return
            
        self.is_playing = True
        self.update()
        
        # Starte Wiedergabe-Thread
        self.playback_thread = threading.Thread(target=self._play_audio)
        self.playback_thread.daemon = True
        self.playback_thread.start()
    
    def _play_audio(self):
        """Wiedergabe der Audio-Daten in einem separaten Thread"""
        try:
            self.p = pyaudio.PyAudio()
            
            self.stream = self.p.open(format=pyaudio.paInt16,
                                    channels=1,
                                    rate=44100,
                                    output=True,
                                    frames_per_buffer=2048)
            
            if not isinstance(self.audio_buffer, np.ndarray):
                logger.info("Konvertiere Audio-Buffer zu NumPy Array")
                self.audio_buffer = np.array(self.audio_buffer, dtype=np.int16)
            
            chunk_size = 2048
            total_samples = len(self.audio_buffer)
            
            for i in range(0, total_samples, chunk_size):
                if self.stop_playback:
                    logger.info("Wiedergabe wird gestoppt")
                    break
                
                chunk = self.audio_buffer[i:min(i + chunk_size, total_samples)]
                
                if len(chunk) > 0:
                    self.stream.write(chunk.tobytes())
            
            logger.info("Wiedergabe beendet")
            
        except Exception as e:
            logger.error(f"Fehler bei der Wiedergabe: {str(e)}")
        finally:
            if hasattr(self, 'stream') and self.stream is not None:
                try:
                    self.stream.stop_stream()
                    self.stream.close()
                    self.stream = None
                except Exception as e:
                    logger.error(f"Fehler beim Schließen des Streams: {str(e)}")
            
            if hasattr(self, 'p') and self.p is not None:
                try:
                    self.p.terminate()
                    self.p = None
                except Exception as e:
                    logger.error(f"Fehler beim Beenden von PyAudio: {str(e)}")
            
            self.is_playing = False
            self.stop_playback = False
            self.update()
    
    def stop_playing(self):
        """Stoppt die Wiedergabe"""
        try:
            self.stop_playback = True
            if hasattr(self, 'stream') and self.stream is not None:
                self.stream.stop_stream()
                self.stream.close()
                self.stream = None
            self.is_playing = False
            self.update()
        except Exception as e:
            logger.error(f"Fehler beim Stoppen der Wiedergabe: {str(e)}")
            self.is_playing = False
            self.update()

class MicrophoneSelector(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Mikrofon auswählen")
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a1a;
                color: #ffffff;
            }
            QComboBox {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                padding: 5px;
                border-radius: 4px;
            }
            QPushButton {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
            }
        """)
        
        layout = QVBoxLayout(self)
        
        # Mikrofon-Auswahl
        self.mic_combo = QComboBox()
        self.populate_microphones()
        layout.addWidget(QLabel("Verfügbare Mikrofone:"))
        layout.addWidget(self.mic_combo)
        
        # Buttons
        button_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        cancel_button = QPushButton("Abbrechen")
        
        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
        self.setMinimumWidth(300)
    
    def populate_microphones(self):
        """Füllt die ComboBox mit verfügbaren und funktionierenden Mikrofonen"""
        p = pyaudio.PyAudio()
        working_mics = []
        
        for i in range(p.get_device_count()):
            try:
                device_info = p.get_device_info_by_index(i)
                if device_info.get('maxInputChannels') > 0:
                    test_stream = p.open(
                        format=pyaudio.paInt16,
                        channels=1,
                        rate=44100,
                        input=True,
                        input_device_index=i,
                        frames_per_buffer=2048,
                        start=False
                    )
                    test_stream.close()
                    
                    name = device_info.get('name', f"Unbekanntes Gerät {i}")
                    working_mics.append((name, i))
                    logger.info(f"Funktionierendes Mikrofon gefunden - Name: {name}, Index: {i}")
            except Exception as e:
                logger.warning(f"Mikrofon {i} nicht verfügbar: {str(e)}")
                continue
        
        seen_names = set()
        for name, index in working_mics:
            if name not in seen_names:
                seen_names.add(name)
                self.mic_combo.addItem(name, index)
                
        p.terminate()
        
        if self.mic_combo.count() == 0:
            logger.warning("Keine funktionierenden Mikrofone gefunden")
            
    def get_selected_microphone(self):
        """Gibt den Index des ausgewählten Mikrofons zurück"""
        return self.mic_combo.currentData()

class ModelLoaderThread(QThread):
    """Thread zum Laden des Whisper-Modells mit GPU-Optimierung"""
    finished = pyqtSignal(object)  # Sendet das geladene Modell
    error = pyqtSignal(str)        # Sendet Fehlermeldungen
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
    def run(self):
        """Lädt das Whisper-Modell im Hintergrund"""
        try:
            # Add the import statement here
            from ..speech.whisper_recognition import WhisperRecognizer
            
            # Initialisiere WhisperRecognizer mit optimierten Einstellungen
            recognizer = WhisperRecognizer(
                model_size="large-v2",
                device="cuda",
                compute_type="float16",
                cache_dir="data/models/whisper"
            )
            
            # Sende das initialisierte Modell zurück
            self.finished.emit(recognizer)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error.emit(f"Fehler beim Laden des Whisper-Modells: {str(e)}")

class AudioProcessThread(QThread):
    """Thread für die Audioaufnahme und -verarbeitung."""
    finished = pyqtSignal(bytes)  # Signal für fertige Audiodaten
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
        self._stop_event = threading.Event()  # Event zum Stoppen des Threads
        self.log_prefix = "[AudioProcessThread]"
        self.response_id = str(uuid.uuid4())  # Generiere eine eindeutige ID für diese Antwort
        
    def stop(self):
        """Stoppt den Thread sicher."""
        logger.info(f"{self.log_prefix} Stoppe Aufnahme...")
        self._stop_event.set()
        self.is_recording = False
    
    def run(self):
        try:
            logger.info(f"{self.log_prefix} Starte Audioaufnahme...")
            p = pyaudio.PyAudio()
            stream = p.open(
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
                    data = stream.read(self.chunk_size, exception_on_overflow=False)
                    self.frames.append(data)
                    
                    # Sende Daten für Visualisierung
                    chunk_data = np.frombuffer(data, dtype=np.int16)
                    normalized_data = chunk_data.astype(np.float32) / 32768.0
                    self.update_visualization.emit(normalized_data)
                except Exception as e:
                    logger.error(f"{self.log_prefix} Fehler beim Lesen des Streams: {str(e)}")
                    break
            
            # Aufnahme beenden
            if stream:
                stream.stop_stream()
                stream.close()
            if p:
                p.terminate()
            
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

class ProcessingThread(QThread):
    """Führt die Audioverarbeitung, Transkription und LLM-Anfrage im Hintergrund aus."""
    update_chat = pyqtSignal(str, str, str)  # Hinzugefügt: response_id als dritter Parameter
    trigger_tts = pyqtSignal(str)
    processing_finished = pyqtSignal(bool, str)
    transcription_result = pyqtSignal(str)

    def __init__(self, audio_data, audio_processor, whisper_recognizer, llm_manager, config, learning_manager, river_learning_manager, parent=None):
        super().__init__(parent)
        self.audio_data = audio_data
        self.audio_processor = audio_processor
        self.whisper_recognizer = whisper_recognizer
        self.llm_manager = llm_manager
        self.config = config
        self.learning_manager = learning_manager
        self.river_learning_manager = river_learning_manager # Store instance
        self.log_prefix = "[ProcessingThread]"
        self.response_id = str(uuid.uuid4())  # Generiere eine eindeutige ID für diese Antwort

    def run(self):
        """Führt die Verarbeitungsschritte aus."""
        success = False
        result_or_error = "Unbekannter Fehler"
        try:
            logger.info(f"{self.log_prefix} Gestartet mit {len(self.audio_data)} Bytes Audio.")

            # --- Schritt 1: Audio verarbeiten --- 
            logger.info(f"{self.log_prefix} Rufe audio_processor.process_audio auf...")
            if not self.audio_processor:
                raise ValueError("AudioProcessor ist nicht initialisiert")
            processed_data, sample_rate = self.audio_processor.process_audio(self.audio_data)
            if processed_data is None or len(processed_data) == 0:
                raise ValueError("AudioProcessor hat keine Daten zurückgegeben.")
            logger.info(f"{self.log_prefix} Audio verarbeitet. Sample Rate: {sample_rate}, Datenlänge: {len(processed_data)}")

            # --- Schritt 2: WAV speichern --- 
            save_dir = os.path.join(self.config.get('AUDIO', 'recordings_path', fallback='data/audio/recordings'))
            os.makedirs(save_dir, exist_ok=True)
            save_path = os.path.join(save_dir, "current_recording.wav")
            logger.info(f"{self.log_prefix} Speichere WAV nach: {save_path}")
            sf.write(save_path, processed_data, sample_rate)
            logger.info(f"{self.log_prefix} WAV-Datei erfolgreich gespeichert.")

            # --- Schritt 3: Whisper Transkription --- 
            if not self.whisper_recognizer:
                 raise RuntimeError("Whisper Recognizer ist nicht initialisiert.")
            logger.info(f"{self.log_prefix} Rufe whisper_recognizer.transcribe_wav auf...")
            transcript = self.whisper_recognizer.transcribe_wav(save_path)
            if transcript is None:
                 raise RuntimeError("Whisper hat kein Transkript zurückgegeben.")
            logger.info(f"{self.log_prefix} Whisper Transkription erfolgreich: '{transcript}'")
            
            # Sende Transkript über das dedizierte Signal
            self.transcription_result.emit(transcript)

            # --- Schritt 3.5: Predict intent with River --- 
            if self.river_learning_manager:
                try:
                    intent_prediction = self.river_learning_manager.predict(transcript)
                    logger.info(f"{self.log_prefix} River Intent Prediction: '{intent_prediction}' for '{transcript}'")
                    # Store context for potential learning
                    if hasattr(self.parent(), 'interaction_context'):
                        self.parent().interaction_context[self.response_id] = {"user_input": transcript, "river_prediction": intent_prediction}
                    # TODO: Use the prediction later (e.g., adapt prompt?)
                except Exception as river_e:
                    logger.warning(f"{self.log_prefix} River prediction failed: {river_e}")
            else:
                logger.warning(f"{self.log_prefix} RiverLearningManager not available for prediction.")

            # --- Schritt 4: LLM Anfrage --- 
            if not self.llm_manager:
                raise RuntimeError("LLM Manager ist nicht initialisiert.")
            logger.info(f"{self.log_prefix} Rufe llm_manager.process_text auf...")
            llm_response = self.llm_manager.process_text(transcript)
            if not llm_response:
                raise RuntimeError("LLM hat keine Antwort zurückgegeben.")
            logger.info(f"{self.log_prefix} LLM Antwort erhalten: '{llm_response[:100]}...'")
            
            # Sende LLM Antwort an GUI mit der Antwort-ID
            self.update_chat.emit("JARVIS", llm_response, self.response_id)
            
            # Trigger TTS für die LLM Antwort
            self.trigger_tts.emit(llm_response)
            
            # Speichere die Antwort-ID im LearningManager
            if self.learning_manager:
                try:
                    self.learning_manager.add_entry(
                        doc_id=self.response_id,
                        content=llm_response,
                        metadata={
                            "entry_type": "response",
                            "timestamp": datetime.now().isoformat(),
                            "question": transcript
                        }
                    )
                    logger.info(f"{self.log_prefix} Antwort mit ID {self.response_id} gespeichert")
                except Exception as e:
                    logger.error(f"{self.log_prefix} Fehler beim Speichern der Antwort-ID: {e}")
            
            success = True
            result_or_error = llm_response

        except Exception as e:
            logger.error(f"{self.log_prefix} Fehler in der Verarbeitung: {e}")
            traceback.print_exc()
            result_or_error = f"Fehler im ProcessingThread: {str(e)}"
            success = False
            try:
                self.update_chat.emit("System", result_or_error, self.response_id)
            except Exception as emit_error:
                logger.error(f"{self.log_prefix} Fehler beim Senden der Fehlermeldung: {emit_error}")
                self.update_chat.emit("System", f"Fehler bei der Verarbeitung: Ein interner Fehler ist aufgetreten")

        finally:
            logger.info(f"{self.log_prefix} Verarbeitung beendet (Success: {success}).")
            self.processing_finished.emit(success, result_or_error)

    def on_update_chat(self, sender: str, message: str, response_id: str = None):
        """Aktualisiert den Chat-Bereich mit einer neuen Nachricht."""
        try:
            if hasattr(self, 'chat_area'):
                # Formatierung der Nachricht
                timestamp = QDateTime.currentDateTime().toString("HH:mm:ss")
                formatted_message = f"[{timestamp}] {sender}: {message}\n"
                
                # Füge die Nachricht zum Chat-Bereich hinzu
                self.chat_area.append(formatted_message)
                
                # Aktiviere Feedback-Buttons nur für JARVIS-Antworten
                if sender == "JARVIS":
                    # Speichere die Antwort-ID
                    self.last_response_id = response_id
                    if response_id:
                        logger.info(f"Antwort-ID {response_id} für Feedback gespeichert")
                        self.thumbs_up_button.setEnabled(True)
                        self.thumbs_down_button.setEnabled(True)
                    else:
                        logger.warning("Keine Antwort-ID für JARVIS-Antwort erhalten")
                        self.thumbs_up_button.setEnabled(False)
                        self.thumbs_down_button.setEnabled(False)
                else:
                    # Deaktiviere Feedback-Buttons für andere Sender
                    self.thumbs_up_button.setEnabled(False)
                    self.thumbs_down_button.setEnabled(False)
                
                # Scrolle zum Ende
                cursor = self.chat_area.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.End)
                self.chat_area.setTextCursor(cursor)
                
                logger.debug(f"Chat aktualisiert: {sender} - {message[:50]}...")
        except Exception as e:
            logger.error(f"Fehler beim Aktualisieren des Chats: {str(e)}")

    def send_feedback(self, is_positive: bool):
        """Sendet Feedback für die letzte Antwort."""
        try:
            if not self.last_response_id:
                logger.warning("Keine Antwort-ID für Feedback verfügbar")
                return
                
            logger.info(f"Sende Feedback für Antwort-ID {self.last_response_id}")
            
            # --- River Learning Integration ---
            if is_positive and self.river_learning_manager:
                if self.last_response_id in self.interaction_context:
                    context = self.interaction_context[self.last_response_id]
                    user_input = context.get("user_input")
                    river_prediction = context.get("river_prediction")
                    
                    # Learn if input exists and prediction was made (even if prediction is None)
                    if user_input is not None and "river_prediction" in context: 
                        try:
                            self.river_learning_manager.learn(user_input, river_prediction)
                            logger.info(f"River Learning: Called learn for ID {self.last_response_id} with input '{user_input[:50]}...' and label '{river_prediction}'")
                        except Exception as learn_e:
                            logger.error(f"River Learning: Error calling learn for ID {self.last_response_id}: {learn_e}")
                    else:
                        logger.warning(f"River Learning: Skipping learn for ID {self.last_response_id} due to missing input or prediction context.")
                        
                    # Optional: Remove context after feedback to prevent re-learning
                    # del self.interaction_context[self.last_response_id]
                else:
                     logger.warning(f"River Learning: Skipping learn for ID {self.last_response_id} - context not found.")
            # --- End River Learning Integration ---
            
            # --- Negative Feedback Handling for River ---
            elif not is_positive and self.river_learning_manager:
                 if self.last_response_id in self.interaction_context:
                    context = self.interaction_context[self.last_response_id]
                    user_input = context.get("user_input")
                    river_prediction = context.get("river_prediction") # Get the prediction that was made
                    
                    if user_input is not None:
                        # Ask user for the correct intent
                        correct_label, ok = QInputDialog.getText(self, 
                                                               'Feedback zur Absicht',
                                                               f'Die Vorhersage war "{river_prediction}". Was war die korrekte Absicht für:\n\"{user_input[:80]}...\"?')
                        
                        if ok and correct_label:
                            # User provided a correct label, learn with it
                            try:
                                self.river_learning_manager.learn(user_input, correct_label)
                                logger.info(f"River Learning (Corrected): Called learn for ID {self.last_response_id} with input '{user_input[:50]}...' and CORRECTED label '{correct_label}'")
                            except Exception as learn_e:
                                logger.error(f"River Learning (Corrected): Error calling learn for ID {self.last_response_id}: {learn_e}")
                        else:
                            logger.info(f"River Learning (Corrected): User cancelled feedback dialog for ID {self.last_response_id}.")
                    else:
                        logger.warning(f"River Learning (Corrected): Skipping feedback for ID {self.last_response_id} due to missing input context.")
                 else:
                     logger.warning(f"River Learning (Corrected): Skipping feedback for ID {self.last_response_id} - context not found.")
            # --- End Negative Feedback Handling ---
                 
            # Original Feedback Processing for LLMManager (if needed)
            if self.llm_manager.process_feedback(is_positive, self.last_response_id):
                # Feedback erfolgreich verarbeitet
                feedback_type = "positiv" if is_positive else "negativ"
                logger.info(f"Feedback ({feedback_type}) für Antwort-ID {self.last_response_id} erfolgreich verarbeitet")
                
                # Deaktiviere die Feedback-Buttons
                self.thumbs_up_button.setEnabled(False)
                self.thumbs_down_button.setEnabled(False)
                
                # Zeige Bestätigung im Chat
                self.on_update_chat("System", f"Danke für dein {feedback_type}es Feedback!")
            else:
                logger.error(f"Fehler beim Verarbeiten des Feedbacks für Antwort-ID {self.last_response_id}")
                self.on_update_chat("System", "Entschuldigung, das Feedback konnte nicht verarbeitet werden.")
                
        except Exception as e:
            error_msg = f"Fehler beim Senden des Feedbacks: {str(e)}"
            logger.error(error_msg)
            self.on_update_chat("System", error_msg)

class KnowledgeImportThread(QThread):
    """Importiert Wissensdateien im Hintergrund."""
    # Signale:
    # update_status(message)
    update_status = pyqtSignal(str)
    # import_finished(success_count, total_count)
    import_finished = pyqtSignal(int, int)

    def __init__(self, file_paths: List[str], learning_manager: LearningManager, import_dir: str = "data/knowledge_import", parent=None):
        super().__init__(parent)
        self.file_paths = file_paths
        self.learning_manager = learning_manager
        self.import_dir = import_dir
        self.log_prefix = "[KnowledgeImportThread]"

    def run(self):
        """Führt den Importprozess für die übergebenen Dateien aus."""
        success_count = 0
        total_count = len(self.file_paths)
        logger.info(f"{self.log_prefix} Starte Import von {total_count} Dateien...")
        self.update_status.emit(f"Starte Import von {total_count} Dateien...")

        try:
            # Stelle sicher, dass das Zielverzeichnis existiert
            os.makedirs(self.import_dir, exist_ok=True)

            for i, source_path in enumerate(self.file_paths):
                filename = os.path.basename(source_path)
                target_path = os.path.join(self.import_dir, filename)
                
                current_status = f"Importiere Datei {i+1}/{total_count}: {filename}..."
                logger.info(f"{self.log_prefix} {current_status}")
                self.update_status.emit(current_status)

                try:
                    # 1. Datei ins Import-Verzeichnis kopieren (optional, aber empfohlen)
                    # Prüfe, ob die Datei (mit gleichem Inhalt) schon existiert? Vorerst einfache Namensprüfung.
                    if os.path.exists(target_path):
                         # Optional: Überspringen oder Überschreiben oder Versionieren?
                         # Fürs Erste: Überspringen, wenn der Name gleich ist.
                         logger.info(f"{self.log_prefix} Datei '{filename}' existiert bereits im Import-Ordner. Überspringe Kopieren.")
                         # Wir versuchen trotzdem, sie zu lernen, falls sie noch nicht in der KB ist
                    else:
                        shutil.copy2(source_path, target_path) # copy2 behält Metadaten bei
                        logger.info(f"{self.log_prefix} Datei nach '{target_path}' kopiert.")

                    # 2. Datei mit LearningManager lernen (verwendet jetzt den Pfad im Import-Ordner)
                    # Optional: Prüfen, ob das *Dokument* (nicht nur die Datei) schon gelernt wurde?
                    # is_already_learned = any(
                    #     item.get('entry_type') == 'document' and item.get('source') == filename 
                    #     for item in self.learning_manager.knowledge_base # <-- Ineffizient! Lädt alles.
                    # )
                    
                    # Effizientere Dublettenprüfung direkt über ChromaDB
                    try:
                        existing_doc = self.learning_manager.collection.get(
                            # Korrigierte where-Klausel mit $and Operator (ohne Backslash-Escaping)
                            where={"$and": [{"entry_type": "document"}, {"source": filename}]},
                            limit=1,
                            include=[] # Wir brauchen nur die Info, OB es existiert
                        )
                        is_already_learned = len(existing_doc['ids']) > 0
                    except Exception as db_check_error:
                        logger.error(f"{self.log_prefix} Fehler bei der Dublettenprüfung für {filename}: {db_check_error}")
                        is_already_learned = False # Im Zweifel lieber versuchen zu lernen

                    if is_already_learned:
                        logger.info(f"{self.log_prefix} Dokument '{filename}' wurde bereits gelernt. Überspringe lernen.")
                        # Zählen wir übersprungene als "Erfolg"? Ja, da das Wissen da ist.
                        success_count += 1
                        continue # Nächste Datei
                        
                    learn_success = self.learning_manager.learn_from_file(target_path)
                    if learn_success:
                        success_count += 1
                    else:
                         logger.info(f"{self.log_prefix} Fehler beim Lernen von Datei: {filename}")
                         # Optional: Kopierte Datei wieder löschen?

                except Exception as copy_learn_error:
                    logger.error(f"{self.log_prefix} Fehler bei Verarbeitung von {filename}: {copy_learn_error}")
                    self.update_status.emit(f"Fehler bei {filename}: {copy_learn_error}")
                    # Nicht abbrechen, nächste Datei versuchen

            # 3. Vektoren aktualisieren nach dem Verarbeiten aller Dateien
            if success_count > 0: # Nur aktualisieren, wenn etwas Neues hinzugefügt wurde
                logger.info(f"{self.log_prefix} Aktualisiere Vektoren nach Import...")
                self.update_status.emit("Aktualisiere Wissens-Vektoren...")
                self.learning_manager.update_vectors()
                logger.info(f"{self.log_prefix} Vektoren aktualisiert.")
                
                # 4. Wissensbasis speichern
                logger.info(f"{self.log_prefix} Speichere aktualisierte Wissensbasis...")
                self.update_status.emit("Speichere Wissensbasis...")
                self.learning_manager.save_knowledge_base()
                logger.info(f"{self.log_prefix} Wissensbasis gespeichert.")

        except Exception as e:
            logger.error(f"{self.log_prefix} Schwerwiegender Fehler während des Imports: {e}")
            traceback.print_exc()
            self.update_status.emit(f"Importfehler: {e}")
        finally:
            # Sende finales Signal
            final_message = f"Import beendet: {success_count} von {total_count} Dateien verarbeitet."
            logger.info(f"{self.log_prefix} {final_message}")
            self.update_status.emit(final_message)
            self.import_finished.emit(success_count, total_count)

class TextProcessingThread(QThread):
    """Thread für die Verarbeitung von Texteingaben."""
    update_chat = pyqtSignal(str, str, str) # sender, message, response_id
    trigger_tts = pyqtSignal(str)
    processing_finished = pyqtSignal(bool, str)

    # Add river_learning_manager and response_id to constructor
    def __init__(self, text: str, llm_manager, config, learning_manager, river_learning_manager, response_id: str, parent=None):
        super().__init__(parent)
        self.text = text
        self.llm_manager = llm_manager
        self.config = config
        self.learning_manager = learning_manager
        self.river_learning_manager = river_learning_manager # Store instance
        self.response_id = response_id # Store response_id
        self.log_prefix = "[TextProcessingThread]"

    def run(self):
        """Verarbeitet die Texteingabe und erhält eine Antwort vom LLM."""
        try:
            logger.info(f"{self.log_prefix} Verarbeite Text: '{self.text}'")
            
            # --- Schritt 0.5: Predict intent with River --- 
            if self.river_learning_manager:
                try:
                    intent_prediction = self.river_learning_manager.predict(self.text)
                    logger.info(f"{self.log_prefix} River Intent Prediction: '{intent_prediction}' for '{self.text}'")
                    # Store prediction in context
                    if hasattr(self.parent(), 'interaction_context') and self.response_id in self.parent().interaction_context:
                         self.parent().interaction_context[self.response_id]["river_prediction"] = intent_prediction
                    # TODO: Use the prediction later (e.g., adapt prompt?)
                except Exception as river_e:
                    logger.warning(f"{self.log_prefix} River prediction failed: {river_e}")
            else:
                logger.warning(f"{self.log_prefix} RiverLearningManager not available for prediction.")
            
            # --- Schritt 1: Sende Text direkt an LLM --- 
            if not self.llm_manager:
                raise RuntimeError("LLM Manager ist nicht initialisiert")
                
            logger.info(f"{self.log_prefix} Rufe llm_manager.process_text auf...")
            llm_response = self.llm_manager.process_text(self.text)
            
            if not llm_response:
                raise RuntimeError("LLM hat keine Antwort zurückgegeben")
                
            logger.info(f"{self.log_prefix} LLM Antwort erhalten: '{llm_response[:100]}...'")
            
            # Speichere die Konversation in der Wissensbasis
            if self.learning_manager:
                try:
                    # Erstelle Metadaten für die Konversation
                    metadata = {
                        "entry_type": "conversation",
                        "timestamp": datetime.now().isoformat(),
                        "input": self.text,
                        "response": llm_response
                    }
                    
                    # Füge die Konversation zur Wissensbasis hinzu
                    self.learning_manager.add_entry(
                        doc_id=str(uuid.uuid4()),
                        content=f"Frage: {self.text}\nAntwort: {llm_response}",
                        metadata=metadata
                    )
                    
                    logger.info(f"{self.log_prefix} Konversation in Wissensbasis gespeichert")
                except Exception as e:
                    logger.error(f"{self.log_prefix} Fehler beim Speichern der Konversation: {str(e)}")
            
            # Sende LLM Antwort an GUI mit response_id
            self.update_chat.emit("JARVIS", llm_response, self.response_id)
            
            # Trigger TTS wenn aktiviert
            try:
                if isinstance(self.config, dict) and "tts" in self.config:
                    tts_config = self.config["tts"]
                    if isinstance(tts_config, dict) and tts_config.get("enable_tts", False):
                        self.trigger_tts.emit(llm_response)
            except Exception as e:
                logger.error(f"{self.log_prefix} Fehler beim TTS-Trigger: {str(e)}")
            
            self.processing_finished.emit(True, llm_response)
            
        except Exception as e:
            error_msg = f"{self.log_prefix} Fehler in der Verarbeitung: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            self.update_chat.emit("System", error_msg)
            self.processing_finished.emit(False, str(e))

    def send_user_input(self):
        """Verarbeitet die Benutzereingabe aus dem Textfeld."""
        try:
            # Hole den Text aus dem Eingabefeld
            user_text = self.input_field.toPlainText().strip()
            if not user_text:
                return
                
            # Zeige die Nachricht im Chat an (ohne response_id hier)
            self.on_update_chat("Roy", user_text)
            
            # Leere das Eingabefeld
            self.input_field.clear()
            
            # Sende die Nachricht an den LLM-Manager
            if not hasattr(self, 'llm_manager') or not self.llm_manager:
                logger.error("LLM-Manager nicht verfügbar")
                self.on_update_chat("System", "Fehler: LLM-Manager ist nicht initialisiert")
                return
                
            # Generate response_id for this interaction
            response_id = str(uuid.uuid4())
            
            # Store initial context (user input, prediction is None initially)
            self.interaction_context[response_id] = {"user_input": user_text, "river_prediction": None}
            
            # Starte die Verarbeitung in einem separaten Thread
            self.processing_thread = TextProcessingThread(
                text=user_text,
                llm_manager=self.llm_manager,
                config=self.config,
                learning_manager=self.learning_manager,
                river_learning_manager=self.river_learning_manager, # Pass the manager
                response_id=response_id, # Pass the id
                parent=self
            )
            
            # Verbinde die Signale
            self.processing_thread.update_chat.connect(self.on_update_chat)
            self.processing_thread.trigger_tts.connect(self.on_trigger_tts)
            self.processing_thread.processing_finished.connect(self.on_processing_finished)
            
            # Starte die Verarbeitung
            self.processing_thread.start()
            
        except Exception as e:
            error_msg = f"Fehler bei der Textverarbeitung: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.on_update_chat("System", error_msg)

class MainWindow(QMainWindow):
    def __init__(self, config_manager, llm_manager, learning_manager, river_learning_manager):
        super().__init__()
        logger.info("Initialisiere MainWindow...")
        
        # Setze Fenstergröße und Titel
        self.setWindowTitle("Status") # Geänderter Titel
        self.setMinimumSize(1200, 800)  # Minimale Größe
        self.resize(1200, 800)  # Standardgröße
        
        # Manager speichern
        self.config = config_manager
        self.llm_manager = llm_manager
        self.learning_manager = learning_manager
        self.river_learning_manager = river_learning_manager # Store the instance
        
        # Initialisiere AudioProcessor
        self.audio_processor = AudioProcessor()
        logger.info("AudioProcessor initialisiert")
        
        # Initialisiere Whisper Recognizer auf None
        self.whisper_recognizer = None
        
        # Initialisiere TTS-Manager mit der Factory-Funktion
        self.tts_manager: Optional[BaseTTSManager] = None # Type Hinting mit Basisklasse
        try:
            # Erstelle TTS Manager über die Factory
            self.tts_manager = create_tts_manager(self.config)
            if self.tts_manager and self.tts_manager.check_readiness():
                 logger.info("TTS-Manager erfolgreich initialisiert und bereit.")
            elif self.tts_manager:
                 logger.warning("TTS-Manager initialisiert, aber nicht bereit.")
            else:
                 logger.error("TTS-Manager konnte nicht erstellt werden (siehe vorherige Logs).")

        except Exception as e:
            logger.error(f"Schwerwiegender Fehler bei der TTS-Initialisierung via Factory: {e}", exc_info=True)
            self.tts_manager = None # Sicherstellen, dass es None ist im Fehlerfall
        
        # Initialisiere Grundzustand
        self.is_recording = False
        self.audio_thread = None
        self.processing_thread = None
        self.last_response_id = None  # Speichert die ID der letzten Antwort
        self.interaction_context = {} # Store user input and river prediction per interaction
        
        # Initialisiere main_layout als None
        self.main_layout = None
        
        # Initialisiere Audio-Visualizer
        self.audio_visualizer = AudioVisualizer()
        self.audio_visualizer.setMinimumHeight(50)
        self.audio_visualizer.setMaximumHeight(100)
        
        # UI initialisieren
        self.init_ui()
        logger.debug("UI erfolgreich initialisiert")
        
        # Whisper initialisieren
        self.init_whisper()
        logger.debug("Whisper initialisiert")
        
        # LLaMA initialisieren
        self.init_llama()
        logger.debug("LLaMA initialisiert")
        
        # Gespeichertes Mikrofon laden
        self.load_saved_microphone()
        logger.debug("Mikrofon-Konfiguration geladen")
        
        # Timer und initiale Updates NACH init_ui
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(2000)  # Update alle 2 Sekunden
        logger.debug("Status-Timer initialisiert")
        
        self.db_size_timer = QTimer(self)
        self.db_size_timer.timeout.connect(self.update_db_size_display)
        self.db_size_timer.start(10000) # Update alle 10 Sekunden
        logger.debug("DB-Größen-Timer initialisiert")

        # Wetter-Timer initialisieren
        self.weather_timer = QTimer(self)
        self.weather_timer.timeout.connect(self.update_weather)
        self.weather_timer.start(300000)  # Update alle 5 Minuten (300000 ms)
        logger.debug("Wetter-Timer initialisiert")
        
        self.update_status() # Initiales Update für CPU/RAM/GPU
        self.update_db_size_display() # Initiales Update für DB Größe
        self.update_weather() # Initiales Update für Wetter
        
        # Beispiel für eine anfängliche Nachricht
        self.on_update_chat("JARVIS", "Guten Tag! Wie kann ich Ihnen behilflich sein?")
        logger.info("MainWindow Initialisierung abgeschlossen")

    def init_ui(self):
        """Initialisiert die Benutzeroberfläche."""
        try:
            # Zentrales Widget erstellen
            central_widget = QWidget()
            self.setCentralWidget(central_widget)

            # StatusWidget früh instanziieren (ENTFERNT, da nicht mehr benötigt)
            # self.status_widget = StatusWidget(self)

            # Haupt-Layout erstellen (wird später durch root_layout ersetzt, aber für left/right benötigt)
            self.main_layout_placeholder = QHBoxLayout() # Platzhalter

            # Linke Seite vorbereiten
            left_layout = QVBoxLayout()
            left_layout.setContentsMargins(0, 0, 0, 0)
            # Nicht mehr zum Platzhalter hinzufügen: self.main_layout_placeholder.addLayout(left_layout, stretch=75)

            # Statusleiste erstellen
            self.status_bar = QStatusBar()
            self.setStatusBar(self.status_bar)
            self.status_bar.showMessage("Bereit")

            # TTS Engine Selector erstellen und zur Statusleiste hinzufügen
            tts_label = QLabel(" TTS Engine:") # Kleiner Abstandhalter
            self.status_bar.addPermanentWidget(tts_label)
            self.tts_engine_selector = QComboBox()
            available_engines = ["piper", "coqui"] # Holen wir uns das besser dynamisch?
            self.tts_engine_selector.addItems(available_engines)
            # Setze den aktuellen Wert aus der Config
            try:
                tts_config_section = self.config.get_config().get("tts", {})
                current_engine_config = tts_config_section.get("engine", "piper")
                index = self.tts_engine_selector.findText(current_engine_config, Qt.MatchFlag.MatchFixedString)
                if index >= 0:
                    self.tts_engine_selector.setCurrentIndex(index)
            except Exception as e:
                logger.warning(f"Konnte TTS Engine nicht aus Config laden: {e}")
            self.tts_engine_selector.currentTextChanged.connect(self.on_tts_engine_changed)
            self.tts_engine_selector.setStyleSheet("background-color: #2d2d2d; color: white; border: 1px solid #3d3d3d; padding: 1px 5px;")
            self.status_bar.addPermanentWidget(self.tts_engine_selector)

            # DB-Größen-Label erstellen (wird nicht mehr zur Statusleiste hinzugefügt)
            # # self.db_size_label = QLabel("Datenbankgröße: Wird berechnet...")
            # # self.status_bar.addPermanentWidget(self.db_size_label)

            # --- Alte Status Gruppe Entfernen ---
            # status_group = QGroupBox("Status")
            # ... (rest des alten status_group codes)
            # left_layout.addWidget(status_group)

            # LLM Status Gruppe (Bleibt)
            llm_status_group = QGroupBox("LLM Status")
            llm_status_layout = QHBoxLayout()
            
            # Erstelle den Edit-Prompt-Button
            self.edit_prompt_button = QPushButton("Prompt bearbeiten")
            self.edit_prompt_button.clicked.connect(self.show_prompt_editor)
            llm_status_layout.addWidget(self.edit_prompt_button)
            llm_status_layout.addStretch(1)

            # Whisper Status Label erstellen
            self.whisper_model_label = QLabel("Whisper: Nicht initialisiert")
            llm_status_layout.addWidget(self.whisper_model_label)

            # LLM Selector und Status Label erstellen
            self.llm_selector = QComboBox()
            self.llm_selector.addItems(["ollama", "openai", "anthropic"])  # Verfügbare LLM-Provider
            self.llm_selector.currentTextChanged.connect(self.on_llm_changed)
            llm_status_layout.addWidget(self.llm_selector)

            # Model Combo erstellen
            self.model_combo = QComboBox()
            self.model_combo.currentTextChanged.connect(self.on_model_changed)
            llm_status_layout.addWidget(self.model_combo)

            # LLM Model Label erstellen
            self.llm_model_label = QLabel("Modell: --")
            llm_status_layout.addWidget(self.llm_model_label)

            self.llama_status_label = QLabel("LLaMA: Nicht initialisiert")
            llm_status_layout.addWidget(self.llama_status_label)

            llm_status_group.setLayout(llm_status_layout)
            left_layout.addWidget(llm_status_group)

            # Rechte Seite vorbereiten (Container und Layout)
            right_container = QWidget()
            right_container.setFixedWidth(280)
            right_layout = QVBoxLayout(right_container)
            right_layout.setContentsMargins(0, 0, 0, 0)
            right_layout.setSpacing(8)

            # --- Rechten Container NICHT zum alten Layout hinzufügen ---
            # # self.main_layout_placeholder.addWidget(right_container, stretch=0, alignment=Qt.AlignmentFlag.AlignRight)

            # Gemeinsames StyleSheet (Bleibt)
            widget_style = """
                QGroupBox {
                    background-color: #1a1a1a;
                    border: 1px solid #3d3d3d;
                    border-radius: 4px;
                    margin-top: 0.5em;
                    padding: 8px;
                    color: white;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 3px 0 3px;
                }
                QLabel, QCheckBox {
                    color: #ffffff;
                    background-color: transparent;
                    border: none;
                    padding: 4px;
                    margin: 2px;
                    font-size: 12pt;
                }
                QCheckBox::indicator {
                    width: 18px;
                    height: 18px;
                }
                QCheckBox::indicator:unchecked {
                    background-color: #2d2d2d;
                    border: 1px solid #3d3d3d;
                    border-radius: 3px;
                }
                QCheckBox::indicator:checked {
                    background-color: #4CAF50;
                    border: 1px solid #3d3d3d;
                    border-radius: 3px;
                }
            """

            # Wetter Widget (Zum rechten Layout hinzufügen)
            weather_group = QGroupBox("Wetter")
            weather_group.setStyleSheet(widget_style)
            weather_layout = QVBoxLayout()
            weather_layout.setContentsMargins(8, 12, 8, 8)
            self.weather_label = QLabel("Wetter wird geladen...")
            self.weather_label.setWordWrap(True)
            self.weather_label.setMinimumWidth(260)
            # Reduce minimum height
            self.weather_label.setMinimumHeight(180)  
            weather_layout.addWidget(self.weather_label)
            weather_group.setLayout(weather_layout)
            right_layout.addWidget(weather_group)

            # Internetverbindung Widget (Zum rechten Layout hinzufügen)
            internet_group = QGroupBox("Internet")
            internet_group.setStyleSheet(widget_style)
            internet_layout = QVBoxLayout()
            internet_layout.setContentsMargins(8, 12, 8, 8)
            self.internet_toggle = QCheckBox("Online-Modus")
            self.internet_toggle.setChecked(True)
            self.internet_toggle.stateChanged.connect(self.on_internet_toggle_changed)
            internet_layout.addWidget(self.internet_toggle)
            internet_group.setLayout(internet_layout)
            right_layout.addWidget(internet_group)

            # Web-Scraping Widget (Zum rechten Layout hinzufügen)
            scraping_widget = QWidget()
            scraping_layout = QVBoxLayout()
            scraping_widget.setLayout(scraping_layout)
            scraping_widget.setMinimumWidth(210)
            scraping_widget.setStyleSheet(widget_style)

            # URL Eingabefeld
            url_layout = QHBoxLayout()
            self.url_input = QLineEdit()
            self.url_input.setPlaceholderText("URL eingeben...")
            url_layout.addWidget(self.url_input)
            
            # Scrape Button
            scrape_button = QPushButton("Analysieren")
            scrape_button.clicked.connect(self.scrape_url)
            url_layout.addWidget(scrape_button)
            scraping_layout.addLayout(url_layout)

            # Optionen
            options_group = QGroupBox("Optionen")
            options_layout = QVBoxLayout()
            
            # Checkboxen für Scraping-Optionen
            # Apply specific style to ensure text visibility
            checkbox_style = "QCheckBox { color: #ffffff; } QCheckBox::indicator { /* Keep existing indicator style */ }"
            
            self.scrape_links = QCheckBox("Links extrahieren")
            self.scrape_links.setStyleSheet(checkbox_style)
            self.scrape_images = QCheckBox("Bilder erfassen")
            self.scrape_images.setStyleSheet(checkbox_style)
            self.scrape_headings = QCheckBox("Überschriften analysieren")
            self.scrape_headings.setStyleSheet(checkbox_style)
            self.auto_save = QCheckBox("Automatisch speichern")
            self.auto_save.setStyleSheet(checkbox_style)
            
            options_layout.addWidget(self.scrape_links)
            options_layout.addWidget(self.scrape_images)
            options_layout.addWidget(self.scrape_headings)
            options_layout.addWidget(self.auto_save)
            options_group.setLayout(options_layout)
            scraping_layout.addWidget(options_group)

            # Status und Fortschritt
            self.scraping_progress = QProgressBar()
            self.scraping_progress.setVisible(False)
            scraping_layout.addWidget(self.scraping_progress)
            
            self.scraping_status = QLabel("Bereit")
            scraping_layout.addWidget(self.scraping_status)

            # Ergebnis-Anzeige
            result_group = QGroupBox("Ergebnis")
            result_layout = QVBoxLayout()
            self.result_text = QTextEdit()
            self.result_text.setReadOnly(True)
            self.result_text.setMaximumHeight(150)
            result_layout.addWidget(self.result_text)
            result_group.setLayout(result_layout)
            scraping_layout.addWidget(result_group)

            # Aktions-Buttons
            action_layout = QHBoxLayout()
            save_button = QPushButton("Speichern")
            save_button.clicked.connect(self.save_scraping_result)
            clear_button = QPushButton("Löschen")
            clear_button.clicked.connect(self.clear_scraping_result)
            action_layout.addWidget(save_button)
            action_layout.addWidget(clear_button)
            scraping_layout.addLayout(action_layout)

            right_layout.addWidget(scraping_widget)

            # Stretch am Ende des rechten Layouts (Bleibt)
            right_layout.addStretch()

            # Steuerungs Gruppe (Bleibt im linken Layout)
            control_group = QGroupBox("Steuerung")
            control_layout = QHBoxLayout()
            self.mic_label = QLabel("Mikrofon: Nicht ausgewählt")
            self.mic_label.setStyleSheet("color: #ffcc00;")
            self.mic_button = QPushButton("Mikrofon auswählen")
            self.mic_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
            self.mic_button.clicked.connect(self.show_mic_selector)
            self.record_button = QPushButton("Aufnahme starten")
            self.record_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
            self.record_button.clicked.connect(self.toggle_recording)
            control_layout.addWidget(self.mic_label)
            control_layout.addWidget(self.mic_button)
            control_layout.addWidget(self.record_button)
            control_layout.addWidget(self.audio_visualizer)
            control_layout.addStretch(1)
            control_group.setLayout(control_layout)
            left_layout.addWidget(control_group)

            # --- Alte Audio Einstellungen Gruppe Entfernen ---
            # audio_settings_group = QGroupBox("Audio Einstellungen")
            # ... (rest des alten audio_settings_group codes) ...
            # left_layout.addWidget(audio_settings_group)

            # Wissensbasis & Lernen Gruppe (Angepasst im linken Layout)
            knowledge_group = QGroupBox("Wissensbasis & Lernen")
            knowledge_layout = QVBoxLayout() # Vertikales Layout

            # Button zum Importieren von Dateien
            self.import_knowledge_button = QPushButton("Dateien importieren")
            self.import_knowledge_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
            self.import_knowledge_button.setToolTip("Textdateien, PDFs etc. auswählen und in die Wissensbasis importieren.")
            self.import_knowledge_button.clicked.connect(self.select_and_import_knowledge_files)
            knowledge_layout.addWidget(self.import_knowledge_button)

            # Button zum Importieren von Audiobüchern
            self.import_audiobook_button = QPushButton("Audiobücher lernen (Ordner)")
            self.import_audiobook_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolume))
            self.import_audiobook_button.setToolTip("Ordner mit MP3-Hörbüchern auswählen und zur Wissensbasis hinzufügen.")
            self.import_audiobook_button.clicked.connect(self.import_audiobook_folder)
            knowledge_layout.addWidget(self.import_audiobook_button)

            # DB-Größen-Label HIER hinzufügen
            self.db_size_label = QLabel("DB Größe: wird geladen...")
            knowledge_layout.addWidget(self.db_size_label)

            knowledge_group.setLayout(knowledge_layout)
            left_layout.addWidget(knowledge_group)

            # Chat Gruppe (Bleibt im linken Layout)
            chat_group = QGroupBox("Chat")
            chat_layout = QVBoxLayout()

            # Chat-Textbereich (Anzeige) erstellen
            self.chat_area = QTextEdit()
            self.chat_area.setReadOnly(True)
            self.chat_area.setStyleSheet("background-color: #222; color: #eee; border: 1px solid #444;")
            chat_layout.addWidget(self.chat_area, 1) # Nimmt verfügbaren Platz ein

            # Eingabebereich mit Feld und Button
            input_layout = QHBoxLayout()
            self.input_field = QTextEdit()
            self.input_field.setFixedHeight(75) # Höhe für ca. 3 Zeilen
            self.input_field.setPlaceholderText("Nachricht eingeben (Enter zum Senden)...")
            self.input_field.setStyleSheet("background-color: #333; color: #eee; border: 1px solid #555;")
            # Wir verbinden das keyPressEvent für Enter-Handling
            self.input_field.keyPressEvent = self.handle_input_keypress
            input_layout.addWidget(self.input_field, 1) # Stretch factor 1

            # Feedback Buttons direkt hier einfügen
            self.thumbs_up_button = QPushButton("👍")
            self.thumbs_up_button.setToolTip("Positives Feedback geben")
            self.thumbs_up_button.setEnabled(False)
            self.thumbs_up_button.clicked.connect(lambda: self.send_feedback(True))
            self.thumbs_up_button.setStyleSheet("background-color: transparent; border: none; font-size: 18pt;")
            input_layout.addWidget(self.thumbs_up_button)

            self.thumbs_down_button = QPushButton("👎")
            self.thumbs_down_button.setToolTip("Negatives Feedback geben")
            self.thumbs_down_button.setEnabled(False)
            self.thumbs_down_button.clicked.connect(lambda: self.send_feedback(False))
            self.thumbs_down_button.setStyleSheet("background-color: transparent; border: none; font-size: 18pt;")
            input_layout.addWidget(self.thumbs_down_button)

            self.send_button = QPushButton("Senden")
            self.send_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOkButton))
            self.send_button.clicked.connect(self.send_user_input)
            self.send_button.setStyleSheet("background-color: #444; color: white; padding: 5px;")
            input_layout.addWidget(self.send_button)

            chat_layout.addLayout(input_layout) # Füge das horizontale Layout hinzu
            chat_group.setLayout(chat_layout) # Setze das Layout für die Gruppe
            left_layout.addWidget(chat_group, 1) # Stretch factor 1, damit Chatbereich wächst

            # --- HIER BEGINNT DIE NEUE LAYOUT-STRUKTUR AM ENDE ---

            # --- Top Bar Setup --- (ENTFERNT)
            # self.top_bar_widget = QWidget()
            # self.top_bar_layout = QHBoxLayout(self.top_bar_widget)
            # self.top_bar_layout.setContentsMargins(5, 5, 5, 5)
            # self.top_bar_layout.setSpacing(10)

            # Audio Settings Widget erstellen (ENTFERNT)
            # available_engines = ["piper", "coqui"]
            # try:
            #     tts_config_section = self.config.get_config().get("tts", {})
            #     current_engine = tts_config_section.get("engine", "piper")
            # except Exception:
            #     current_engine = "piper"
            # self.audio_settings_widget = AudioSettingsWidget(available_engines, current_engine, self)
            # self.audio_settings_widget.tts_engine_changed.connect(self.on_tts_engine_changed)

            # Widgets zur Top Bar hinzufügen (StatusWidget wurde oben instanziiert) (ENTFERNT)
            # if hasattr(self, 'status_widget'):
            #      self.top_bar_layout.addWidget(self.status_widget, 30) # 30% Stretch
            # else:
            #      logger.error("StatusWidget nicht gefunden beim Hinzufügen zur Top-Bar!")
            # self.top_bar_layout.addWidget(self.audio_settings_widget, 45) # 45% Stretch
            # self.top_bar_layout.addStretch(25) # 25% Leerraum rechts

            # --- Hauptlayout-Struktur mit Splitter ---
            root_layout = QVBoxLayout() # Vertikales Hauptlayout

            # Top Bar oben hinzufügen (ENTFERNT)
            # root_layout.addWidget(self.top_bar_widget)

            # Splitter für den Rest
            content_splitter = QSplitter(Qt.Orientation.Horizontal)

            # Linker Container vorbereiten (left_layout wurde bereits befüllt)
            left_container = QWidget()
            left_container.setLayout(left_layout)
            content_splitter.addWidget(left_container)

            # Rechter Container vorbereiten (right_container wurde bereits befüllt)
            content_splitter.addWidget(right_container) # Füge es zum Splitter hinzu

            # Initiale Größe des Splitters
            # Verwende eine Standardgröße, falls self.width() noch nicht zuverlässig ist
            initial_width = 1180 # Annahme einer typischen Breite
            content_splitter.setSizes([int(initial_width * 0.75), int(initial_width * 0.25)])

            # Splitter zum Root-Layout hinzufügen
            root_layout.addWidget(content_splitter, 1) # Nimmt restlichen Platz ein

            # Root-Layout auf das zentrale Widget anwenden
            central_widget.setLayout(root_layout)

        except Exception as e:
            logger.error(f"Fehler beim Initialisieren der UI: {str(e)}", exc_info=True)
            raise

    def init_whisper(self):
        """Initialisiert das Whisper-Modell im Hintergrund"""
        self.whisper_model_label.setText("Whisper: Lade Modell...")
        self.whisper_model_label.setStyleSheet("color: #ffa500;") # Orange
        
        # Erstelle und starte den ModelLoaderThread
        self.model_loader = ModelLoaderThread(self)
        self.model_loader.finished.connect(self.on_whisper_loaded)
        self.model_loader.error.connect(self.on_whisper_error)
        self.model_loader.start()
        
    def on_whisper_loaded(self, recognizer):
        """Wird aufgerufen, wenn das Whisper-Modell erfolgreich geladen wurde"""
        self.whisper_recognizer = recognizer
        self.whisper_model_label.setText("Whisper: Bereit")
        self.whisper_model_label.setStyleSheet("color: #00ff00;") # Grün
        logger.info("Whisper-Modell erfolgreich geladen")
        
    def on_whisper_error(self, error_msg):
        """Wird aufgerufen, wenn ein Fehler beim Laden des Whisper-Modells auftritt"""
        self.whisper_model_label.setText("Whisper: Fehler")
        self.whisper_model_label.setStyleSheet("color: #ff0000;") # Rot
        logger.error(f"Fehler beim Laden des Whisper-Modells: {error_msg}")
        self.on_update_chat("System", f"Fehler beim Laden der Spracherkennung: {error_msg}")

    def init_llama(self):
        """Initialisiert die LLM-Verbindung."""
        try:
            # Lade den gespeicherten Provider
            saved_provider = self.config.get("llm", "provider", fallback="ollama")
            provider_index = self.llm_selector.findText(saved_provider)
            if provider_index >= 0:
                self.llm_selector.setCurrentIndex(provider_index)
            
            if saved_provider == "hermes":
                # Für Hermes: Einfache Initialisierung
                self.model_combo.clear()
                self.model_combo.addItem("openhermes-2-mistral-7b")
                self.model_combo.setEnabled(False)
                self.llm_model_label.setText("Modell: Hermes (Lokal)")
                self.llm_model_label.setStyleSheet("color: #4CAF50;")
                self.llama_status_label.setText("LLM: Hermes (Lokal)")
                self.llama_status_label.setStyleSheet("color: #4CAF50;")
                logger.info("Hermes LLM initialisiert")
                return
                
            # Für Ollama: Normale Initialisierung
            if self.llm_manager.check_connection():
                available_models = self.llm_manager.get_available_models()
                logger.debug(f"Verfügbare Modelle: {available_models}")
                
                if available_models:
                    self.model_combo.clear()
                    self.model_combo.addItems(available_models)
                    
                    # Hole das gespeicherte Modell aus der Konfiguration
                    saved_model = self.config.get("ollama", "model", fallback="llama2")
                    logger.info(f"Gespeichertes Modell aus Konfiguration: {saved_model}")
                    
                    # Setze das Modell im LLM Manager
                    if self.llm_manager.set_model(saved_model):
                        # Aktualisiere ComboBox-Auswahl
                        index = self.model_combo.findText(saved_model)
                        if index >= 0:
                            self.model_combo.setCurrentIndex(index)
                            
                        # Aktualisiere Modell-Label
                        model_info = self.llm_manager.get_current_model()
                        self.llm_model_label.setText(f"Modell: {model_info}")
                        self.llm_model_label.setStyleSheet("color: #4CAF50;")
                        logger.info(f"LLaMA erfolgreich initialisiert mit Modell: {saved_model}")
                    else:
                        # Fallback auf erstes verfügbares Modell wenn gespeichertes nicht verfügbar
                        fallback_model = available_models[0]
                        logger.warning(f"Gespeichertes Modell {saved_model} nicht verfügbar, verwende {fallback_model}")
                        
                        if self.llm_manager.set_model(fallback_model):
                            self.model_combo.setCurrentIndex(0)
                            self.config.set("ollama", "model", fallback_model)
                            self.config.save()
                            
                            model_info = self.llm_manager.get_current_model()
                            self.llm_model_label.setText(f"Modell: {model_info}")
                            self.llm_model_label.setStyleSheet("color: #4CAF50;")
                        else:
                            self.llm_model_label.setText("Modell nicht verfügbar")
                            self.llm_model_label.setStyleSheet("color: #f44336;")
                            logger.error("Kein Modell konnte geladen werden")
                else:
                    self.llm_model_label.setText("Keine Modelle verfügbar")
                    self.llm_model_label.setStyleSheet("color: #f44336;")
                    logger.error("Keine Modelle von Ollama verfügbar")
                
                # Status aktualisieren
                self.llama_status_label.setText("LLaMA: Verbunden")
                self.llama_status_label.setStyleSheet("color: #4CAF50;")
            else:
                self.llama_status_label.setText("LLaMA: Verbindungsfehler")
                self.llama_status_label.setStyleSheet("color: #f44336;")
                logger.error("Konnte keine Verbindung zu LLaMA herstellen")
        except Exception as e:
            logger.error(f"Fehler bei LLaMA-Initialisierung: {e}", exc_info=True)
            self.llama_status_label.setText("LLaMA: Fehler")
            self.llama_status_label.setStyleSheet("color: #f44336;")

    def on_model_changed(self, model_name: str):
        """Wird aufgerufen, wenn das Modell gewechselt wird."""
        try:
            if self.llm_manager:
                if self.llm_manager.set_model(model_name):
                    # Speichere die Auswahl in der Konfiguration
                    self.config.set("ollama", "model", model_name)
                    self.config.save()
                    
                    # Aktualisiere das Modell-Label
                    model_info = self.llm_manager.get_current_model()
                    self.llm_model_label.setText(f"Modell: {model_info}")
                    self.llm_model_label.setStyleSheet("color: #4CAF50;")  # Grün für aktiv
                    
                    logger.info(f"Modell erfolgreich gewechselt zu: {model_name}")
                else:
                    self.llm_model_label.setText("Modell nicht verfügbar")
                    self.llm_model_label.setStyleSheet("color: #f44336;")  # Rot für Fehler
                    logger.error(f"Modell {model_name} konnte nicht gesetzt werden")
                    
                self.update_status()  # Aktualisiere die Statusleiste
        except Exception as e:
            error_msg = f"Fehler beim Wechseln des Modells: {str(e)}"
            logger.error(error_msg)
            self.llm_model_label.setText("Modell-Wechsel fehlgeschlagen")
            self.llm_model_label.setStyleSheet("color: #f44336;")  # Rot für Fehler

    def on_llm_changed(self, provider_name: str):
        """Wird aufgerufen, wenn der LLM-Provider geändert wird."""
        try:
            logger.debug(f"LLM Provider Wechsel zu: {provider_name}")
            
            if provider_name == "Ollama":
                # Hole verfügbare Modelle von Ollama
                available_models = self.llm_manager.get_available_models()
                if available_models:
                    self.model_combo.clear()
                    self.model_combo.addItems(available_models)
                    # Setze das aktuelle Modell aus der Konfiguration
                    current_model = self.config.get("ollama", "model", fallback="llama2")
                    index = self.model_combo.findText(current_model)
                    if index >= 0:
                        self.model_combo.setCurrentIndex(index)
                        
                self.model_combo.setEnabled(True)
                
            elif provider_name == "Hermes":
                # Für Hermes gibt es nur ein lokales Modell
                self.model_combo.clear()
                self.model_combo.addItem("openhermes-2-mistral-7b")
                self.model_combo.setEnabled(False)  # Deaktiviere Modellauswahl für Hermes
                
                # Aktualisiere das Label
                self.llm_model_label.setText("Modell: Hermes (Lokal)")
                self.llm_model_label.setStyleSheet("color: #4CAF50;")
                
                # Speichere die Auswahl
                self.config.set("llm", "provider", "hermes")
                self.config.save()
                
                logger.info("Auf lokales Hermes-Modell gewechselt")
                
            else:
                self.model_combo.clear()
                self.model_combo.setEnabled(False)
                self.llm_model_label.setText(f"Provider {provider_name} nicht verfügbar")
                self.llm_model_label.setStyleSheet("color: #f44336;")
                logger.warning(f"Provider {provider_name} ist noch nicht implementiert")
                
        except Exception as e:
            error_msg = f"Fehler beim Wechsel des LLM Providers: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.llm_model_label.setText("Provider-Wechsel fehlgeschlagen")
            self.llm_model_label.setStyleSheet("color: #f44336;")

    def show_prompt_editor(self):
        """Öffnet den Prompt-Editor Dialog."""
        try:
            # Erstelle und zeige den Prompt-Editor
            editor = PromptEditor(self)
            
            # Lade den aktuellen Prompt aus der Konfiguration
            current_prompt = self.config.get("prompt", "system_prompt", fallback="")
            editor.set_prompt(current_prompt)
            
            # Zeige den Dialog
            if editor.exec() == QDialog.DialogCode.Accepted:
                # Speichere den neuen Prompt
                new_prompt = editor.get_prompt()
                self.config.set("prompt", "system_prompt", new_prompt)
                self.config.save()  # Verwende save() statt write()
                
                logger.info("Prompt erfolgreich aktualisiert")
            else:
                logger.debug("Prompt-Editor abgebrochen")
                
        except Exception as e:
            error_msg = f"Fehler beim Öffnen des Prompt-Editors: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.on_update_chat("System", f"Fehler beim Öffnen des Prompt-Editors: {str(e)}")

    def show_mic_selector(self):
        """Öffnet den Mikrofon-Auswahldialog und aktualisiert die Auswahl."""
        try:
            # Erstelle und zeige den Mikrofon-Auswahldialog
            selector = MicrophoneSelector(self)
            if selector.exec() == QDialog.DialogCode.Accepted:
                selected_index = selector.get_selected_microphone()
                if selected_index is not None:
                    # Speichere die Auswahl in der Konfiguration
                    self.config.set("audio", "microphone_index", str(selected_index))
                    self.config.save()  # Verwende save() statt write()
                    
                    # Aktualisiere das Mikrofon-Label
                    device_name = selector.mic_combo.currentText()
                    self.mic_label.setText(f"🔊 Mikrofon: {device_name}")
                    self.mic_label.setStyleSheet("color: #4CAF50;")  # Grün für aktives Mikrofon
                    
                    logger.info(f"Mikrofon ausgewählt: {device_name} (Index: {selected_index})")
                else:
                    logger.warning("Kein Mikrofon ausgewählt")
                    self.mic_label.setText("🔊 Mikrofon: Keine Auswahl")
                    self.mic_label.setStyleSheet("color: #ffcc00;")  # Gelb für keine Auswahl
            else:
                logger.debug("Mikrofon-Auswahl abgebrochen")
                
        except Exception as e:
            error_msg = f"Fehler bei der Mikrofon-Auswahl: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.mic_label.setText("🔊 Mikrofon: Fehler")
            self.mic_label.setStyleSheet("color: #f44336;")  # Rot für Fehler
            self.on_update_chat("System", f"Fehler bei der Mikrofon-Auswahl: {str(e)}")

    def load_saved_microphone(self):
        """Lädt das gespeicherte Mikrofon aus der Konfiguration."""
        try:
            # Prüfe, ob ein Mikrofon in der Konfiguration gespeichert ist
            if self.config.has_option("audio", "microphone_index") and self.config.has_option("audio", "microphone_name"):
                mic_index = int(self.config.get("audio", "microphone_index"))
                mic_name = self.config.get("audio", "microphone_name")
                
                # Prüfe, ob das Mikrofon noch verfügbar ist
                p = pyaudio.PyAudio()
                if mic_index < p.get_device_count():
                    device_info = p.get_device_info_by_index(mic_index)
                    self.mic_label.setText(f"🔊 Mikrofon: {mic_name}")
                    self.mic_label.setStyleSheet("color: #4CAF50;")  # Grün für aktives Mikrofon
                    logger.info(f"Gespeichertes Mikrofon geladen: {mic_name} (Index: {mic_index})")
                else:
                    self.mic_label.setText("🔊 Mikrofon: Nicht verfügbar")
                    self.mic_label.setStyleSheet("color: #ff9800;")  # Orange für nicht verfügbar
                p.terminate()
            else:
                self.mic_label.setText("🔊 Mikrofon: Nicht ausgewählt")
                self.mic_label.setStyleSheet("color: #ffcc00;")  # Gelb für keine Auswahl
                logger.debug("Kein Mikrofon in der Konfiguration gespeichert")
        except Exception as e:
            logger.error(f"Fehler beim Laden des gespeicherten Mikrofons: {str(e)}")
            self.mic_label.setText("🔊 Mikrofon: Fehler beim Laden")
            self.mic_label.setStyleSheet("color: #f44336;")  # Rot für Fehler
            self.on_update_chat("System", f"Fehler beim Laden des gespeicherten Mikrofons: {str(e)}")

    @pyqtSlot(bytes)
    def on_audio_finished(self, audio_data):
        """Wird aufgerufen, wenn die Audioaufnahme beendet ist"""
        try:
            logger.info("=== DEBUG: on_audio_finished aufgerufen ===")
            
            # Prüfe ob Audio-Daten vorhanden und nicht leer sind
            if not audio_data or len(audio_data) < 1024:  # Mindestgröße für sinnvolle Audio-Daten
                logger.warning("Keine oder zu wenig Audiodaten empfangen")
                self.on_update_chat("System", "Keine Audiodaten aufgenommen. Bitte versuchen Sie es erneut.")
                return
                
            logger.info(f"Empfangene Audiodaten: {len(audio_data)} Bytes")
                
            # Prüfe AudioProcessor
            if not self.audio_processor:
                logger.error("AudioProcessor ist nicht initialisiert")
                self.on_update_chat("System", "Fehler: AudioProcessor ist nicht initialisiert")
                return
                
            # Initialisiere Whisper Recognizer wenn nötig
            if self.whisper_recognizer is None:
                logger.info("Initialisiere Whisper Recognizer...")
                self.whisper_recognizer = WhisperRecognizer()
                logger.info("Whisper Recognizer initialisiert")
            
            # Prüfe LLM Manager
            if not self.llm_manager:
                logger.error("LLM Manager ist nicht initialisiert")
                self.on_update_chat("System", "Fehler: LLM Manager ist nicht initialisiert")
                return
                
            # Starte Processing Thread
            logger.info("Erstelle Processing Thread...")
            self.processing_thread = ProcessingThread(
                audio_data=audio_data,
                audio_processor=self.audio_processor,
                whisper_recognizer=self.whisper_recognizer,
                llm_manager=self.llm_manager,
                config=self.config,
                learning_manager=self.learning_manager,
                river_learning_manager=self.river_learning_manager, # Pass the manager
                parent=self
            )
            
            # Verbinde Signale
            logger.info("Verbinde Processing Thread Signale...")
            self.processing_thread.update_chat.connect(self.on_update_chat)
            self.processing_thread.processing_finished.connect(self.on_processing_finished)
            self.processing_thread.trigger_tts.connect(self.on_trigger_tts)
            self.processing_thread.transcription_result.connect(self.on_transcription_result)
            
            # Starte Thread
            logger.info("Starte Processing Thread...")
            self.processing_thread.start()
            logger.info("Processing Thread gestartet")
            
        except Exception as e:
            error_msg = f"Fehler bei der Audioverarbeitung: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            self.on_update_chat("System", error_msg)

    def on_processing_finished(self, success: bool, result: str):
        """Wird aufgerufen, wenn die Verarbeitung abgeschlossen ist"""
        try:
            logger.info(f"Verarbeitung abgeschlossen. Erfolg: {success}, Ergebnis: {result}")
            if not success:
                self.on_update_chat("System", f"Fehler bei der Verarbeitung: {result}")
        except Exception as e:
            logger.error(f"Fehler in on_processing_finished: {str(e)}")
            
    def on_transcription_result(self, transcription: str):
        """Wird aufgerufen, wenn die Transkription fertig ist"""
        try:
            logger.info(f"Transkription erhalten: {transcription}")
            self.on_update_chat("Roy", transcription)
        except Exception as e:
            logger.error(f"Fehler in on_transcription_result: {str(e)}")

    def on_trigger_tts(self, text: str):
        """Wird aufgerufen, wenn Text per TTS ausgegeben werden soll."""
        # Prüfe, ob der TTS Manager erfolgreich initialisiert wurde und bereit ist
        if not self.tts_manager or not self.tts_manager.check_readiness():
            logger.warning("TTS-Manager ist nicht initialisiert oder nicht bereit. Überspringe Sprachausgabe.")
            # Optional: Zeige eine Meldung im Chat an
            # self.on_update_chat("System", "Sprachausgabe nicht verfügbar.")
            return

        try:
            # Starte TTS in separatem Thread (Manager-Implementierung sollte dies idealerweise intern tun)
            # Aber zur Sicherheit hier nochmal in einem Thread, falls die speak()-Methode blockiert
            def tts_thread():
                try:
                    # Rufe die speak Methode des initialisierten Managers auf
                    self.tts_manager.speak(text)
                except Exception as e:
                    logger.error(f"Fehler bei TTS speak(): {str(e)}", exc_info=True)

            # Starte Thread
            tts_exec_thread = threading.Thread(target=tts_thread)
            tts_exec_thread.daemon = True  # Thread wird beendet wenn Hauptprogramm endet
            tts_exec_thread.start()

            logger.debug("TTS speak() Aufruf gestartet.")

        except Exception as e:
            error_msg = f"Fehler beim Starten des TTS-Threads: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.on_update_chat("System", "Fehler bei der Sprachausgabe.")

    def send_user_input(self):
        """Verarbeitet die Benutzereingabe aus dem Textfeld."""
        try:
            # Hole den Text aus dem Eingabefeld
            user_text = self.input_field.toPlainText().strip()
            if not user_text:
                return
                
            # Zeige die Nachricht im Chat an (ohne response_id hier)
            self.on_update_chat("Roy", user_text)
            
            # Leere das Eingabefeld
            self.input_field.clear()
            
            # Sende die Nachricht an den LLM-Manager
            if not hasattr(self, 'llm_manager') or not self.llm_manager:
                logger.error("LLM-Manager nicht verfügbar")
                self.on_update_chat("System", "Fehler: LLM-Manager ist nicht initialisiert")
                return
                
            # Generate response_id for this interaction
            response_id = str(uuid.uuid4())
            
            # Store initial context (user input, prediction is None initially)
            self.interaction_context[response_id] = {"user_input": user_text, "river_prediction": None}
            
            # Starte die Verarbeitung in einem separaten Thread
            self.processing_thread = TextProcessingThread(
                text=user_text,
                llm_manager=self.llm_manager,
                config=self.config,
                learning_manager=self.learning_manager,
                river_learning_manager=self.river_learning_manager, # Pass the manager
                response_id=response_id, # Pass the id
                parent=self
            )
            
            # Verbinde die Signale
            self.processing_thread.update_chat.connect(self.on_update_chat)
            self.processing_thread.trigger_tts.connect(self.on_trigger_tts)
            self.processing_thread.processing_finished.connect(self.on_processing_finished)
            
            # Starte die Verarbeitung
            self.processing_thread.start()
            
        except Exception as e:
            error_msg = f"Fehler bei der Textverarbeitung: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.on_update_chat("System", error_msg)

    def update_status(self, message=None):
        """Aktualisiert die Statusleiste mit aktuellen System- und LLM-Informationen."""
        try:
            logger.debug("Aktualisiere Status...")
            
            if hasattr(self, 'status_bar'):
                # System-Informationen abrufen
                cpu_percent = psutil.cpu_percent()
                ram = psutil.virtual_memory()
                ram_percent = ram.percent
                
                # GPU-Informationen (falls verfügbar)
                gpu_info = "N/A"
                try:
                    import pynvml
                    pynvml.nvmlInit()
                    handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                    info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    gpu_percent = (info.used / info.total) * 100
                    gpu_info = f"{gpu_percent:.1f}"
                    logger.debug(f"GPU-Auslastung: {gpu_percent:.1f}%")
                except Exception as e:
                    logger.warning(f"GPU-Informationen nicht verfügbar: {str(e)}")
                
                # LLM-Informationen dynamisch abrufen
                current_provider = self.llm_selector.currentText() if hasattr(self, 'llm_selector') else "N/A"
                
                if current_provider == "Hermes":
                    current_model = "openhermes-2-mistral-7b"
                else:
                    current_model = self.model_combo.currentText() if hasattr(self, 'model_combo') else "N/A"
                
                # Status-Text zusammenbauen
                status_components = [
                    f"CPU: {cpu_percent:.1f}%",
                    f"RAM: {ram_percent:.1f}%", 
                    f"GPU: {gpu_info}%",
                    f"Modell: {current_model}",
                    f"Provider: {current_provider}"
                ]
                
                if message:
                    status_components.append(message)
                
                status = " | ".join(status_components)
                logger.debug(f"Status aktualisiert: {status}")
                
                # Statusleiste aktualisieren
                self.status_bar.showMessage(status)
                
        except Exception as e:
            logger.error(f"Fehler beim Aktualisieren des Status: {str(e)}", exc_info=True)
            if hasattr(self, 'status_bar'):
                self.status_bar.showMessage("Fehler beim Aktualisieren des Status")

    def update_db_size_display(self):
        """Aktualisiert die Anzeige der Datenbankgröße und Einträge."""
        try:
            if hasattr(self, 'db_size_label'):
                db_path = os.path.join("data", "knowledge_base", "chroma_db")
                if os.path.exists(db_path):
                    # Berechne Größe
                    size_kb = get_directory_size(db_path)
                    
                    # Hole Statistiken vom LearningManager
                    try:
                        stats = self.learning_manager.get_statistics()
                        entry_count = stats.get("entry_count", 0)
                        entry_types = stats.get("entry_types", {})
                        
                        # Erstelle detaillierte Anzeige
                        type_details = []
                        for entry_type, count in entry_types.items():
                            type_details.append(f"{entry_type}: {count}")
                        
                        details = " | ".join(type_details) if type_details else ""
                        self.db_size_label.setText(f"Datenbank: {size_kb:.2f} KB | {entry_count} Einträge | {details}")
                    except Exception as e:
                        logger.warning(f"Konnte Statistiken nicht ermitteln: {e}")
                        self.db_size_label.setText(f"Datenbank: {size_kb:.2f} KB")
                else:
                    self.db_size_label.setText("Datenbank: Nicht verfügbar")
        except Exception as e:
            logger.error(f"Fehler beim Aktualisieren der DB-Anzeige: {str(e)}")
            if hasattr(self, 'db_size_label'):
                self.db_size_label.setText("Datenbank: Fehler")

    def on_update_chat(self, sender: str, message: str, response_id: str = None):
        """Aktualisiert den Chat-Bereich mit einer neuen Nachricht."""
        try:
            if hasattr(self, 'chat_area'):
                # Formatierung der Nachricht
                timestamp = QDateTime.currentDateTime().toString("HH:mm:ss")
                formatted_message = f"[{timestamp}] {sender}: {message}\n"
                
                # Füge die Nachricht zum Chat-Bereich hinzu
                self.chat_area.append(formatted_message)
                
                # Aktiviere Feedback-Buttons nur für JARVIS-Antworten
                if sender == "JARVIS":
                    # Speichere die Antwort-ID
                    self.last_response_id = response_id
                    if response_id:
                        logger.info(f"Antwort-ID {response_id} für Feedback gespeichert")
                        self.thumbs_up_button.setEnabled(True)
                        self.thumbs_down_button.setEnabled(True)
                    else:
                        logger.warning("Keine Antwort-ID für JARVIS-Antwort erhalten")
                        self.thumbs_up_button.setEnabled(False)
                        self.thumbs_down_button.setEnabled(False)
                else:
                    # Deaktiviere Feedback-Buttons für andere Sender
                    self.thumbs_up_button.setEnabled(False)
                    self.thumbs_down_button.setEnabled(False)
                
                # Scrolle zum Ende
                cursor = self.chat_area.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.End)
                self.chat_area.setTextCursor(cursor)
                
                logger.debug(f"Chat aktualisiert: {sender} - {message[:50]}...")
        except Exception as e:
            logger.error(f"Fehler beim Aktualisieren des Chats: {str(e)}")
            
    def handle_input_keypress(self, event):
        """Behandelt Tastatureingaben im Eingabefeld."""
        try:
            # Prüfe auf Enter ohne Shift
            if event.key() == Qt.Key.Key_Return and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                # Verhindere Standard-Enter-Verhalten
                event.accept()
                # Sende Nachricht
                self.send_user_input()
            else:
                # Für alle anderen Tasten (inkl. Shift+Enter): Standard-Verhalten
                QTextEdit.keyPressEvent(self.input_field, event)
        except Exception as e:
            logger.error(f"Fehler bei Tastatureingabe: {str(e)}")
            # Fallback zum Standard-Verhalten
            QTextEdit.keyPressEvent(self.input_field, event)

    def toggle_recording(self):
        """Startet oder stoppt die Audioaufnahme."""
        try:
            logger.info("=== DEBUG: toggle_recording aufgerufen ===")
            
            if not self.is_recording:
                # Starte Aufnahme
                logger.info("Starte Aufnahme...")
                self.is_recording = True
                
                # Erstelle neuen AudioThread
                try:
                    device_index = int(self.config.get("audio", "microphone_index"))
                    logger.info(f"Verwende Mikrofon-Index: {device_index}")
                    
                    self.audio_thread = AudioProcessThread(
                        chunk_size=1024,
                        format=pyaudio.paInt16,
                        channels=1,
                        rate=44100,
                        device_index=device_index,
                        parent=self
                    )
                    
                    # Verbinde Signale
                    logger.info("Verbinde AudioThread Signale...")
                    self.audio_thread.update_visualization.connect(self.audio_visualizer.update_audio_data)
                    self.audio_thread.finished.connect(self.on_audio_finished)
                    logger.info("AudioThread Signale verbunden")
                    
                    # Starte Thread
                    self.audio_thread.is_recording = True
                    self.audio_thread.start()
                    
                    # Aktualisiere UI
                    self.record_button.setText("🔴 Aufnahme stoppen")
                    self.record_button.setStyleSheet("""
                        QPushButton {
                            background-color: #ff4444;
                            color: white;
                            border: 1px solid #ff6666;
                            border-radius: 4px;
                            padding: 5px 15px;
                        }
                        QPushButton:hover {
                            background-color: #ff6666;
                        }
                        QPushButton:pressed {
                            background-color: #ff3333;
                        }
                    """)
                    
                    logger.info("AudioThread gestartet")
                    
                except Exception as e:
                    error_msg = f"Fehler beim Erstellen des AudioThreads: {str(e)}"
                    logger.error(error_msg)
                    self.on_update_chat("System", error_msg)
                    self.is_recording = False
                    
            else:
                # Stoppe Aufnahme
                logger.info("Stoppe Aufnahme...")
                self.is_recording = False
                
                if self.audio_thread:
                    # Stoppe Thread
                    self.audio_thread.stop()
                    
                    # Warte auf Thread-Ende
                    if self.audio_thread.isRunning():
                        self.audio_thread.wait()
                    
                    # Trenne Signale
                    logger.info("Trenne AudioThread Signale...")
                    try:
                        self.audio_thread.update_visualization.disconnect(self.audio_visualizer.update_audio_data)
                        self.audio_thread.finished.disconnect(self.on_audio_finished)
                    except Exception as e:
                        logger.warning(f"Fehler beim Trennen der Signale: {str(e)}")
                    logger.info("AudioThread Signale getrennt")
                    
                    # Reset Thread
                    self.audio_thread = None
                    
                    # Aktualisiere UI
                    self.record_button.setText("🎤 Aufnahme starten")
                    self.record_button.setStyleSheet("""
                        QPushButton {
                            background-color: #2d2d2d;
                            color: white;
                            border: 1px solid #3d3d3d;
                            border-radius: 4px;
                            padding: 5px 15px;
                        }
                        QPushButton:hover {
                            background-color: #3d3d3d;
                        }
                        QPushButton:pressed {
                            background-color: #1d1d1d;
                        }
                    """)
                    
                    logger.info("AudioThread beendet")
                    
        except Exception as e:
            error_msg = f"Fehler beim Aufnahme-Toggle: {str(e)}"
            logger.error(error_msg)
            self.on_update_chat("System", error_msg)
            self.is_recording = False
            self.audio_thread = None

    def import_images(self):
        """Importiert Bilder in die Wissensbasis."""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Bilder auswählen",
            "",
            "Bilddateien (*.png *.jpg *.jpeg *.gif *.bmp)"
        )
        if file_paths:
            self.import_knowledge_files(file_paths)

    def import_text(self):
        """Importiert Textdateien in die Wissensbasis."""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Textdateien auswählen",
            "",
            "Textdateien (*.txt *.md *.docx *.pdf)"
        )
        if file_paths:
            self.import_knowledge_files(file_paths)

    def import_audio(self):
        """Importiert Audiodateien in die Wissensbasis."""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Audiodateien auswählen",
            "",
            "Audiodateien (*.wav *.mp3 *.ogg *.flac)"
        )
        if file_paths:
            self.import_knowledge_files(file_paths)

    def import_video(self):
        """Importiert Videodateien in die Wissensbasis."""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Videodateien auswählen",
            "",
            "Videodateien (*.mp4 *.avi *.mkv *.mov)"
        )
        if file_paths:
            self.import_knowledge_files(file_paths)

    def import_knowledge_files(self, file_paths):
        """Importiert Dateien in die Wissensbasis."""
        if not file_paths:
            return

        # Erstelle Import-Thread
        import_thread = KnowledgeImportThread(
            file_paths,
            self.learning_manager,
            "data/knowledge_import"
        )

        # Verbinde Signale
        import_thread.update_status.connect(self.update_status)
        import_thread.import_finished.connect(self.on_import_finished)

        # Starte Import
        import_thread.start()
        self.update_status("Importiere Dateien...")

    def on_import_finished(self, success_count: int, total_count: int):
        """Wird aufgerufen, wenn der Import abgeschlossen ist"""
        try:
            logger.info(f"Import beendet: {success_count} von {total_count} Dateien verarbeitet.")
            self.on_update_chat("System", f"Import beendet: {success_count} von {total_count} Dateien verarbeitet.")
        except Exception as e:
            logger.error(f"Fehler in on_import_finished: {str(e)}")
            self.on_update_chat("System", "Fehler beim Importieren der Dateien")

    def send_feedback(self, is_positive: bool):
        """Sendet Feedback für die letzte Antwort."""
        try:
            if not self.last_response_id:
                logger.warning("Keine Antwort-ID für Feedback verfügbar")
                return
                
            logger.info(f"Sende Feedback für Antwort-ID {self.last_response_id}")
            
            # --- River Learning Integration ---
            if is_positive and self.river_learning_manager:
                if self.last_response_id in self.interaction_context:
                    context = self.interaction_context[self.last_response_id]
                    user_input = context.get("user_input")
                    river_prediction = context.get("river_prediction")
                    
                    # Learn if input exists and prediction was made (even if prediction is None)
                    if user_input is not None and "river_prediction" in context: 
                        try:
                            self.river_learning_manager.learn(user_input, river_prediction)
                            logger.info(f"River Learning: Called learn for ID {self.last_response_id} with input '{user_input[:50]}...' and label '{river_prediction}'")
                        except Exception as learn_e:
                            logger.error(f"River Learning: Error calling learn for ID {self.last_response_id}: {learn_e}")
                    else:
                        logger.warning(f"River Learning: Skipping learn for ID {self.last_response_id} due to missing input or prediction context.")
                        
                    # Optional: Remove context after feedback to prevent re-learning
                    # del self.interaction_context[self.last_response_id]
                else:
                     logger.warning(f"River Learning: Skipping learn for ID {self.last_response_id} - context not found.")
            # --- End River Learning Integration ---
            
            # --- Negative Feedback Handling for River ---
            elif not is_positive and self.river_learning_manager:
                 if self.last_response_id in self.interaction_context:
                    context = self.interaction_context[self.last_response_id]
                    user_input = context.get("user_input")
                    river_prediction = context.get("river_prediction") # Get the prediction that was made
                    
                    if user_input is not None:
                        # Ask user for the correct intent
                        correct_label, ok = QInputDialog.getText(self, 
                                                               'Feedback zur Absicht',
                                                               f'Die Vorhersage war "{river_prediction}". Was war die korrekte Absicht für:\n\"{user_input[:80]}...\"?')
                        
                        if ok and correct_label:
                            # User provided a correct label, learn with it
                            try:
                                self.river_learning_manager.learn(user_input, correct_label)
                                logger.info(f"River Learning (Corrected): Called learn for ID {self.last_response_id} with input '{user_input[:50]}...' and CORRECTED label '{correct_label}'")
                            except Exception as learn_e:
                                logger.error(f"River Learning (Corrected): Error calling learn for ID {self.last_response_id}: {learn_e}")
                        else:
                            logger.info(f"River Learning (Corrected): User cancelled feedback dialog for ID {self.last_response_id}.")
                    else:
                        logger.warning(f"River Learning (Corrected): Skipping feedback for ID {self.last_response_id} due to missing input context.")
                 else:
                     logger.warning(f"River Learning (Corrected): Skipping feedback for ID {self.last_response_id} - context not found.")
            # --- End Negative Feedback Handling ---
                 
            # Original Feedback Processing for LLMManager (if needed)
            if self.llm_manager.process_feedback(is_positive, self.last_response_id):
                # Feedback erfolgreich verarbeitet
                feedback_type = "positiv" if is_positive else "negativ"
                logger.info(f"Feedback ({feedback_type}) für Antwort-ID {self.last_response_id} erfolgreich verarbeitet")
                
                # Deaktiviere die Feedback-Buttons
                self.thumbs_up_button.setEnabled(False)
                self.thumbs_down_button.setEnabled(False)
                
                # Zeige Bestätigung im Chat
                self.on_update_chat("System", f"Danke für dein {feedback_type}es Feedback!")
            else:
                logger.error(f"Fehler beim Verarbeiten des Feedbacks für Antwort-ID {self.last_response_id}")
                self.on_update_chat("System", "Entschuldigung, das Feedback konnte nicht verarbeitet werden.")
                
        except Exception as e:
            error_msg = f"Fehler beim Senden des Feedbacks: {str(e)}"
            logger.error(error_msg)
            self.on_update_chat("System", error_msg)

    def update_weather(self):
        """Aktualisiert die Wetterinformationen."""
        try:
            logger.info("Aktualisiere Wetterdaten...")
            # Hole Wetterdaten vom LLM Manager
            weather_data = self.llm_manager.get_weather_data()
            
            if weather_data:
                # Formatiere die Wetterdaten
                current_time = datetime.now().strftime("%H:%M")
                weather_text = (
                    f"🕒 Zeit: {current_time}\n"
                    f"📍 {weather_data['city']}\n"
                    f"🌡️ Temperatur: {weather_data['temp']}°C\n"
                    f"🌡️ Gefühlt: {weather_data['feels_like']}°C\n"
                    f"☁️ {weather_data['description']}\n"
                    f"💧 Luftfeuchtigkeit: {weather_data['humidity']}%\n"
                    f"💨 Wind: {weather_data['wind_speed']} km/h\n"
                    f"\nLetzte Aktualisierung: {current_time}"
                )
                self.weather_label.setText(weather_text)
                logger.info(f"Wetterdaten erfolgreich aktualisiert für {weather_data['city']}")
            else:
                error_msg = "⚠️ Wetter nicht verfügbar\nPrüfe API-Schlüssel und Internetverbindung"
                self.weather_label.setText(error_msg)
                logger.error("Keine Wetterdaten verfügbar")
                
        except Exception as e:
            error_msg = f"⚠️ Fehler beim Abrufen der Wetterdaten:\n{str(e)}"
            logger.error(f"Fehler beim Aktualisieren des Wetters: {str(e)}")
            self.weather_label.setText(error_msg)

    def update_usage_stats(self):
        """Aktualisiert die Nutzungsstatistiken."""
        try:
            stats = self.learning_manager.get_statistics()
            entry_count = stats.get("entry_count", 0)
            response_count = stats.get("entry_types", {}).get("response", 0)
            self.usage_label.setText(f"Einträge: {entry_count}\nAntworten: {response_count}")
        except Exception as e:
            logger.error(f"Fehler beim Aktualisieren der Statistiken: {str(e)}")
            self.usage_label.setText("Statistiken nicht verfügbar")

    def on_internet_toggle_changed(self, state):
        """Wird aufgerufen, wenn der Internet-Modus geändert wird."""
        try:
            is_online = state == Qt.CheckState.Checked.value
            self.llm_manager.set_online_mode(is_online)
            status = "aktiviert" if is_online else "deaktiviert"
            self.internet_toggle.setText(f"Online-Modus\n({status})")
            logger.info(f"Online-Modus {status}")
        except Exception as e:
            logger.error(f"Fehler beim Ändern des Online-Modus: {str(e)}")

    def update_system_stats(self):
        """Aktualisiert die System-Ressourcen-Anzeige."""
        try:
            # CPU-Auslastung
            cpu_percent = psutil.cpu_percent()
            
            # RAM-Auslastung
            ram = psutil.virtual_memory()
            ram_percent = ram.percent
            ram_used = ram.used / (1024**3)  # GB
            ram_total = ram.total / (1024**3)  # GB
            
            # GPU-Auslastung (falls verfügbar)
            gpu_info = "N/A"
            try:
                import pynvml
                pynvml.nvmlInit()
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                gpu_percent = (info.used / info.total) * 100
                gpu_used = info.used / (1024**3)  # GB
                gpu_total = info.total / (1024**3)  # GB
                gpu_info = f"{gpu_percent:.1f}% ({gpu_used:.1f}/{gpu_total:.1f} GB)"
            except:
                gpu_info = "Nicht verfügbar"
            
            # Formatiere die Systemdaten
            system_text = (
                f"CPU: {cpu_percent}%\n"
                f"RAM: {ram_percent}%\n"
                f"({ram_used:.1f}/{ram_total:.1f} GB)\n"
                f"GPU: {gpu_info}"
            )
            self.system_label.setText(system_text)
            
        except Exception as e:
            logger.error(f"Fehler beim Aktualisieren der Systemdaten: {str(e)}")
            self.system_label.setText("Systemdaten nicht verfügbar")

    def scrape_url(self):
        """Führt erweitertes Web-Scraping durch."""
        url = self.url_input.text().strip()
        if not url:
            self.scraping_status.setText("Bitte URL eingeben")
            return
            
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        self.scraping_status.setText("Analysiere Webseite...")
        self.scraping_progress.setVisible(True)
        self.scraping_progress.setRange(0, 0)  # Unbestimmter Fortschritt
        
        try:
            # Hole Scraping-Optionen
            options = {
                'extract_links': self.scrape_links.isChecked(),
                'extract_images': self.scrape_images.isChecked(),
                'extract_headings': self.scrape_headings.isChecked()
            }
            
            # Starte Scraping in separatem Thread
            self.scraping_thread = QThread()
            self.scraping_worker = ScrapingWorker(url, options, self.llm_manager)  # llm_manager hinzugefügt
            self.scraping_worker.moveToThread(self.scraping_thread)
            
            # Verbinde Signale
            self.scraping_thread.started.connect(self.scraping_worker.run)
            self.scraping_worker.finished.connect(self.on_scraping_finished)
            self.scraping_worker.error.connect(self.on_scraping_error)
            
            # Starte Thread
            self.scraping_thread.start()
            
        except Exception as e:
            self.scraping_status.setText(f"Fehler: {str(e)}")
            self.scraping_progress.setVisible(False)

    def on_scraping_finished(self, result):
        """Verarbeitet die Scraping-Ergebnisse."""
        self.scraping_progress.setVisible(False)
        
        if not result:
            self.scraping_status.setText("Keine Daten gefunden")
            return
            
        # Formatiere Ergebnis
        formatted_result = []
        formatted_result.append(f"Titel: {result['title']}")
        
        if result.get('meta_description'):
            formatted_result.append(f"\nBeschreibung: {result['meta_description']}")
            
        if result.get('headings'):
            formatted_result.append("\nÜberschriften:")
            for h in result['headings']:
                formatted_result.append(f"{h['level']}: {h['text']}")
                
        if result.get('main_content'):
            formatted_result.append(f"\nHauptinhalt:\n{result['main_content'][:500]}...")
            
        if result.get('links') and self.scrape_links.isChecked():
            formatted_result.append("\nGefundene Links:")
            for link in result['links'][:5]:  # Zeige nur die ersten 5 Links
                formatted_result.append(f"- {link['text']}: {link['href']}")
                
        if result.get('images') and self.scrape_images.isChecked():
            formatted_result.append("\nGefundene Bilder:")
            for img in result['images'][:5]:  # Zeige nur die ersten 5 Bilder
                formatted_result.append(f"- {img['alt']}: {img['src']}")
                
        # Zeige Ergebnis
        self.result_text.setText("\n".join(formatted_result))
        self.scraping_status.setText("Analyse abgeschlossen")
        
        # Automatisch speichern wenn aktiviert
        if self.auto_save.isChecked():
            self.save_scraping_result()

    def on_scraping_error(self, error_msg):
        """Behandelt Scraping-Fehler."""
        self.scraping_progress.setVisible(False)
        self.scraping_status.setText(f"Fehler: {error_msg}")

    def save_scraping_result(self):
        """Speichert das Scraping-Ergebnis."""
        if not self.result_text.toPlainText():
            return
            
        try:
            # Öffne Speichern-Dialog
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Ergebnis speichern",
                "",
                "Text Dateien (*.txt);;HTML Dateien (*.html);;Alle Dateien (*.*)"
            )
            
            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.result_text.toPlainText())
                self.scraping_status.setText("Ergebnis gespeichert")
                
        except Exception as e:
            self.scraping_status.setText(f"Fehler beim Speichern: {str(e)}")

    def clear_scraping_result(self):
        """Löscht das aktuelle Scraping-Ergebnis."""
        self.result_text.clear()
        self.scraping_status.setText("Bereit")
        self.url_input.clear()
        self.scraping_progress.setVisible(False)

    # NEU: Methode zum Starten des Audiobook-Imports aus einem Ordner
    def import_audiobook_folder(self):
        """Öffnet einen Dialog zur Auswahl eines Ordners und startet die Verarbeitung."""
        # Prüfen, ob Whisper bereit ist
        if not self.whisper_recognizer:
            QMessageBox.warning(self, "Whisper nicht bereit", "Die Spracherkennung ist noch nicht initialisiert. Bitte warten Sie einen Moment.")
            logger.warning("Audiobook-Import abgebrochen: Whisper nicht bereit.")
            return

        # Prüfen, ob bereits ein Import läuft
        if (hasattr(self, 'import_thread') and self.import_thread and self.import_thread.isRunning()) or \
           (hasattr(self, 'import_audiobook_thread') and self.import_audiobook_thread and self.import_audiobook_thread.isRunning()):
            QMessageBox.warning(self, "Import läuft", "Ein anderer Importvorgang (Wissen oder Audiobuch) läuft bereits. Bitte warten Sie.")
            logger.warning("Audiobook-Import abgebrochen: Anderer Import läuft.")
            return

        folder_path = QFileDialog.getExistingDirectory(self, "Ordner mit Hörbüchern auswählen", "")
        
        if folder_path:
            logger.info(f"Ausgewählter Ordner für Audiobook-Import: {folder_path}")
            self.update_status(f"Starte Audiobook-Import für Ordner: {os.path.basename(folder_path)}...") 
            
            # Erstelle und starte den Audiobook-Import-Thread
            self.import_audiobook_thread = AudiobookImportThread(
                folder_path=folder_path,
                learning_manager=self.learning_manager,
                whisper_recognizer=self.whisper_recognizer,
                parent=self # Optional: parent setzen
            )
            
            # Verbinde Signale
            self.import_audiobook_thread.update_status.connect(self.update_status)
            self.import_audiobook_thread.import_finished.connect(self.on_audiobook_import_finished)
            
            # Starte den Thread
            self.import_audiobook_thread.start()
            logger.info("AudiobookImportThread gestartet.")
        else:
            logger.info("Audiobook-Ordner-Import abgebrochen.")

    # NEU: Slot für das Ende des Audiobook-Imports
    def on_audiobook_import_finished(self, final_message: str):
        """Wird aufgerufen, wenn der AudiobookImportThread beendet ist."""
        QMessageBox.information(self, "Audiobook-Import abgeschlossen", final_message)
        self.update_status(f"Audiobook-Import: {final_message}")
        self.update_db_size_display() # DB-Größe aktualisieren
        self.import_audiobook_thread = None # Thread-Referenz entfernen
        logger.info("AudiobookImportThread beendet und Referenz entfernt.")

    # --- Bestehende Import-Funktionen ---
    def select_and_import_knowledge_files(self):
        """Öffnet einen Dateidialog zur Auswahl von Wissensdateien und startet den Import.""" 
        # Öffne Dateidialog
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Wissensdateien auswählen",
            "", # Startverzeichnis
            "Unterstützte Dateien (*.txt *.md *.pdf *.docx *.csv *.json *.html *.wav *.mp3 *.ogg *.flac);;Alle Dateien (*.*)"
        )
        self.import_knowledge_files(file_paths)

    def import_knowledge_files(self, file_paths: List[str]):
        """Startet den Import von Wissensdateien in einem separaten Thread."""
        if not file_paths:
            return

        # Prüfen, ob bereits ein Import läuft
        if (hasattr(self, 'import_thread') and self.import_thread and self.import_thread.isRunning()) or \
           (hasattr(self, 'import_audiobook_thread') and self.import_audiobook_thread and self.import_audiobook_thread.isRunning()):
            QMessageBox.warning(self, "Import läuft", "Ein anderer Importvorgang läuft bereits. Bitte warten Sie.")
            logger.warning("Wissensimport abgebrochen: Anderer Import läuft.")
            return

        # Erstelle Import-Thread
        self.import_thread = KnowledgeImportThread(
            file_paths,
            self.learning_manager,
            "data/knowledge_import",
            parent=self # Parent setzen
        )

        # Verbinde Signale
        self.import_thread.update_status.connect(self.update_status)
        self.import_thread.import_finished.connect(self.on_import_finished)

        # Starte Import
        self.import_thread.start()
        self.update_status("Importiere Dateien...")

    def on_import_finished(self, success_count: int, total_count: int):
        """Wird aufgerufen, wenn der Wissensimport-Thread beendet ist."""
        QMessageBox.information(self, "Import abgeschlossen", f"{success_count} von {total_count} Dateien erfolgreich verarbeitet.")
        self.update_status(f"Import beendet: {success_count}/{total_count} Dateien.")
        self.update_db_size_display() # DB-Größe aktualisieren
        self.import_thread = None # Thread-Referenz entfernen
        logger.info("KnowledgeImportThread beendet und Referenz entfernt.")
        
    # NEUE METHODE ZUM UMSCHALTEN DER TTS ENGINE (JETZT INNERHALB DER KLASSE)
    def on_tts_engine_changed(self, selected_engine: str):
        """Wird aufgerufen, wenn die TTS Engine in der ComboBox geändert wird."""
        logger.info(f"Versuche, TTS Engine zu wechseln zu: {selected_engine}")

        current_engine = "Unbekannt"
        if self.tts_manager:
            # Versuche, den Namen direkt vom Manager zu bekommen (best practice)
            if hasattr(self.tts_manager, 'engine_name') and self.tts_manager.engine_name:
                 current_engine = self.tts_manager.engine_name
            # Fallback: Versuche es aus der Konfiguration des Managers zu lesen
            elif hasattr(self.tts_manager, 'config') and isinstance(self.tts_manager.config, dict):
                current_engine = self.tts_manager.config.get('tts', {}).get('engine', current_engine)
            # Fallback: Versuche es aus der Hauptkonfiguration zu lesen
            elif isinstance(self.config, Config):
                 tts_config_section = self.config.get_config().get("tts", {})
                 current_engine = tts_config_section.get("engine", current_engine)
            elif isinstance(self.config, dict):
                 tts_config_section = self.config.get("tts", {})
                 current_engine = tts_config_section.get("engine", current_engine)


        if selected_engine.lower() == current_engine.lower():
            logger.debug(f"Ausgewählte Engine ({selected_engine}) ist bereits aktiv.")
            return

        # Erstelle eine temporäre Konfiguration für den neuen Manager
        # Wichtig: Ändere NICHT self.config direkt, um die config.json nicht zu überschreiben
        temp_config_dict = {}
        if isinstance(self.config, Config):
            temp_config_dict = self.config.get_config().copy() # Hole das interne dict und kopiere es
        elif isinstance(self.config, dict):
            temp_config_dict = self.config.copy()

        # Stelle sicher, dass der 'tts' Abschnitt existiert
        if 'tts' not in temp_config_dict:
            temp_config_dict['tts'] = {}
        temp_config_dict['tts']['engine'] = selected_engine.lower()

        try:
            # Versuche, den neuen Manager mit der temporären Konfiguration zu erstellen
            logger.info(f"Erstelle neuen TTS Manager für Engine '{selected_engine}' mit temp config: {temp_config_dict.get('tts')}")
            new_tts_manager = create_tts_manager(temp_config_dict)

            if new_tts_manager and new_tts_manager.check_readiness():
                self.tts_manager = new_tts_manager # Aktualisiere den aktiven Manager
                # Setze engine_name Attribut, falls nicht vorhanden (für nächsten Wechsel)
                if not hasattr(self.tts_manager, 'engine_name') or not self.tts_manager.engine_name:
                    self.tts_manager.engine_name = selected_engine.lower()
                logger.info(f"TTS Engine erfolgreich zu '{selected_engine}' gewechselt.")
                self.on_update_chat("System", f"TTS Engine auf {selected_engine} umgeschaltet.")
            else:
                error_detail = "Manager nicht erstellt" if not new_tts_manager else "Manager nicht bereit (check_readiness fehlgeschlagen)"
                raise RuntimeError(f"Manager für '{selected_engine}' konnte nicht initialisiert werden oder ist nicht bereit. Detail: {error_detail}")

        except Exception as e:
            logger.error(f"Fehler beim Wechsel zu TTS Engine '{selected_engine}': {e}", exc_info=True)
            QMessageBox.warning(self,
                                "TTS Wechsel fehlgeschlagen",
                                f"Konnte nicht zu TTS Engine '{selected_engine}' wechseln.\nFehler: {e}\n\nBleibe bei Engine '{current_engine}'.")

            # Setze ComboBox zurück auf den alten Wert
            self.tts_engine_selector.blockSignals(True)
            index = self.tts_engine_selector.findText(current_engine, Qt.MatchFlag.MatchFixedString)
            if index >= 0:
                self.tts_engine_selector.setCurrentIndex(index)
            else: # Fallback falls alter Engine Name nicht gefunden wird
                 index = self.tts_engine_selector.findText("piper", Qt.MatchFlag.MatchFixedString)
                 if index >= 0:
                    self.tts_engine_selector.setCurrentIndex(index)
            self.tts_engine_selector.blockSignals(False)

    # ... rest of the class ...

class ScrapingWorker(QObject):
    """Worker-Klasse für asynchrones Web-Scraping."""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, url, options, llm_manager):
        super().__init__()
        self.url = url
        self.options = options
        self.llm_manager = llm_manager
        
    def run(self):
        """Führt das Scraping im Hintergrund aus."""
        try:
            result = self.llm_manager.scrape_webpage(self.url)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))

# NEU: Thread für Audiobook-Import
class AudiobookImportThread(QThread):
    """Importiert Hörbücher aus einem Ordner im Hintergrund."""
    # Signale:
    update_status = pyqtSignal(str)  # Sendet Fortschrittsmeldungen
    import_finished = pyqtSignal(str) # Sendet die finale Statusmeldung

    def __init__(self, folder_path: str, learning_manager: LearningManager, whisper_recognizer: WhisperRecognizer, parent=None):
        super().__init__(parent)
        self.folder_path = folder_path
        self.learning_manager = learning_manager
        self.whisper_recognizer = whisper_recognizer
        self.log_prefix = "[AudiobookImportThread]"

    def run(self):
        """Führt den Importprozess für den Ordner aus."""
        final_message = "Audiobook-Import gestartet..."
        try:
            logger.info(f"{self.log_prefix} Starte Import für Ordner: {self.folder_path}")
            if not self.whisper_recognizer:
                raise RuntimeError("Whisper Recognizer ist nicht initialisiert im Thread.")
            if not self.learning_manager:
                 raise RuntimeError("Learning Manager ist nicht initialisiert im Thread.")

            # Rufe die Verarbeitungsfunktion auf und iteriere durch die Statusmeldungen
            for status in find_and_process_audio_in_folder(self.folder_path, self.learning_manager, self.whisper_recognizer):
                logger.info(f"{self.log_prefix} Status-Update: {status}")
                self.update_status.emit(status) # Sende jeden Status an die GUI
                final_message = status # Speichere die letzte Meldung als finale Meldung

        except Exception as e:
            logger.error(f"{self.log_prefix} Fehler während des Audiobook-Imports: {e}", exc_info=True)
            final_message = f"Fehler beim Audiobook-Import: {e}"
            self.update_status.emit(final_message) # Sende Fehlermeldung als Status
        finally:
            # Sende das finale Signal mit der letzten Statusmeldung (Erfolg oder Fehler)
            logger.info(f"{self.log_prefix} {final_message}")
            self.import_finished.emit(final_message)

    # NEUE METHODE ZUM UMSCHALTEN DER TTS ENGINE
    def on_tts_engine_changed(self, selected_engine: str):
        """Wird aufgerufen, wenn die TTS Engine in der ComboBox geändert wird."""
        logger.info(f"Versuche, TTS Engine zu wechseln zu: {selected_engine}")

        current_engine = "Unbekannt"
        if self.tts_manager:
            current_engine = self.tts_manager.engine_name # Annahme: Manager hat Attribut engine_name
            # Fallback, falls Attribut fehlt
            if hasattr(self.tts_manager, 'config') and isinstance(self.tts_manager.config, dict):
                current_engine = self.tts_manager.config.get('tts', {}).get('engine', current_engine)
            elif isinstance(self.config, Config):
                 current_engine = self.config.get("tts", {}).get("engine", current_engine)
            elif isinstance(self.config, dict):
                 current_engine = self.config.get("tts", {}).get("engine", current_engine)


        if selected_engine.lower() == current_engine.lower():
            logger.debug(f"Ausgewählte Engine ({selected_engine}) ist bereits aktiv.")
            return

        # Erstelle eine temporäre Konfiguration für den neuen Manager
        # Wichtig: Ändere NICHT self.config direkt, um die config.json nicht zu überschreiben
        temp_config_dict = {}
        if isinstance(self.config, Config):
            temp_config_dict = self.config.config.copy() # Kopiere das interne dict
        elif isinstance(self.config, dict):
            temp_config_dict = self.config.copy()

        # Stelle sicher, dass der 'tts' Abschnitt existiert
        if 'tts' not in temp_config_dict:
            temp_config_dict['tts'] = {}
        temp_config_dict['tts']['engine'] = selected_engine.lower()

        try:
            # Versuche, den neuen Manager mit der temporären Konfiguration zu erstellen
            new_tts_manager = create_tts_manager(temp_config_dict)

            if new_tts_manager and new_tts_manager.check_readiness():
                self.tts_manager = new_tts_manager # Aktualisiere den aktiven Manager
                logger.info(f"TTS Engine erfolgreich zu '{selected_engine}' gewechselt.")
                self.on_update_chat("System", f"TTS Engine auf {selected_engine} umgeschaltet.")
                # Optional: Statusleiste aktualisieren?
                # self.update_status(f"TTS: {selected_engine}")
            else:
                raise RuntimeError(f"Manager für '{selected_engine}' konnte nicht initialisiert werden oder ist nicht bereit.")

        except Exception as e:
            logger.error(f"Fehler beim Wechsel zu TTS Engine '{selected_engine}': {e}", exc_info=True)
            QMessageBox.warning(self,
                                "TTS Wechsel fehlgeschlagen",
                                f"Konnte nicht zu TTS Engine '{selected_engine}' wechseln.\nFehler: {e}\n\nBleibe bei Engine '{current_engine}'.")

            # Setze ComboBox zurück auf den alten Wert
            # Blockiere vorübergehend Signale, um rekursive Aufrufe zu vermeiden
            self.tts_engine_selector.blockSignals(True)
            index = self.tts_engine_selector.findText(current_engine, Qt.MatchFlag.MatchFixedString)
            if index >= 0:
                self.tts_engine_selector.setCurrentIndex(index)
            self.tts_engine_selector.blockSignals(False)