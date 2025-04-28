import os
import sys
import soundfile as sf
import numpy as np
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                           QLabel, QPushButton, QFrame, QComboBox, QDialog,
                           QScrollArea, QTextEdit, QMessageBox, QProgressDialog, 
                           QGroupBox, QStatusBar, QFileDialog, QListWidget, QDialogButtonBox, QProgressBar,
                           QApplication, QSplitter, QLineEdit, QStyle, QCheckBox,
                           QInputDialog, QListWidgetItem)
from PyQt6.QtCore import Qt, QDateTime, QTimer, QThread, pyqtSignal, QMetaObject, Q_ARG, QSize, pyqtSlot, QObject
from PyQt6.QtGui import QPalette, QColor, QFont, QPainter, QPen, QIcon, QTextCursor
import threading
import queue
from datetime import datetime
import time
import io
import uuid
import logging
import glob
import math
import librosa
from pydub import AudioSegment
from ..utils.system_monitor import SystemMonitor
from .debug_monitor import DebugMonitor
from ..llm.llm_manager import LLMManager
from ..llm.learning_manager import LearningManager
from ..learning.river_learning_manager import RiverLearningManager
from .mic_selector import MicrophoneSelector
from ..audio.audio_thread import AudioProcessThread
from .prompt_editor import PromptEditor
from ..audio.audio_processor import AudioProcessor
from .loading_screen import LoadingScreen
from ..audio.base_tts_manager import BaseTTSManager, create_tts_manager
from ..speech.whisper_recognition import WhisperRecognizer
from .widgets.status_widget import StatusWidget
from .audio_settings_widget import AudioSettingsWidget
from ..tasks.task_manager import TaskManager
import requests
import subprocess
import tempfile
import getpass

# Logger für dieses Modul
logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    def __init__(self, config_manager, llm_manager, learning_manager, river_learning_manager, task_manager):
        super().__init__()
        logger.info("Initialisiere MainWindow...")
        
        # Speichere die Manager
        self.config_manager = config_manager
        self.config = config_manager.config
        self.llm_manager = llm_manager
        self.learning_manager = learning_manager
        self.river_learning_manager = river_learning_manager
        self.task_manager = task_manager
        
        # Setze Wetter API Key
        self.config["weather_api_key"] = "91ee2d32a13be6a0c1086c8539f8dcf5"
        self.config["weather_city"] = "Dresden"
        
        # ---> Hole Benutzernamen
        try:
            self.username = getpass.getuser()
            logger.info(f"Benutzername ermittelt: {self.username}")
        except Exception as e:
             logger.warning(f"Konnte Benutzernamen nicht ermitteln: {e}. Verwende 'Benutzer'.")
             self.username = "Benutzer"
        # <--- Ende Benutzernamen holen
        
        # Initialisiere Whisper
        self.whisper_recognizer = WhisperRecognizer()
        
        # Initialisiere System Monitor
        self.system_monitor = SystemMonitor()
        # Entferne den Timer, da SystemMonitor Signale sendet
        # self.system_monitor_timer = QTimer()
        # self.system_monitor_timer.timeout.connect(self.update_system_stats)
        # self.system_monitor_timer.start(2000)  # Alle 2 Sekunden aktualisieren
        
        # Variablen zum Speichern der letzten Statistikwerte
        self.last_cpu = 0.0
        self.last_gpu = 0.0
        self.last_memory = 0.0
        
        # *** TTS aktivieren ***
        self.config["use_tts"] = True
        logger.info(f"Konfiguration 'use_tts' gesetzt auf: {self.config['use_tts']}")
        
        # Verbinde SystemMonitor Signale mit Slots
        self.system_monitor.cpu_update.connect(self.on_cpu_update)
        self.system_monitor.gpu_update.connect(self.on_gpu_update)
        self.system_monitor.memory_update.connect(self.on_memory_update)
        
        # Initialisiere Grundzustand
        self.is_recording = False
        self.audio_thread = None
        self.processing_thread = None
        self.last_response_id = None
        self.interaction_context = {}
        
        # UI initialisieren
        self.init_ui()
        # *** TTS initialisieren ***
        self.init_tts()

    def init_ui(self):
        """Initialisiert die Benutzeroberfläche."""
        try:
            logger.info("UI wird initialisiert...")
            
            # Setze Fenstertitel und Größe
            self.setWindowTitle("JARVIS - Intelligenter Assistent")
            self.setMinimumSize(1200, 800)
            
            # Erstelle zentrales Widget und Layout
            central_widget = QWidget()
            self.setCentralWidget(central_widget)
            main_layout = QHBoxLayout(central_widget)  # Horizontales Layout für die drei Spalten
            
            # Linke Spalte: Aufgabenverwaltung
            left_column = QWidget()
            left_layout = QVBoxLayout(left_column)
            
            # Aufgabenverwaltung Gruppe
            task_group = QGroupBox("Aufgabenverwaltung")
            task_layout = QVBoxLayout()
            
            # Task Liste
            self.task_list = QListWidget()
            self.task_list.addItem("Instagram Post Idee generieren")
            task_layout.addWidget(self.task_list)
            
            # Neue Aufgabe Eingabe
            task_input_layout = QHBoxLayout()
            self.task_input = QLineEdit()
            self.task_input.setPlaceholderText("Neue Aufgabe eingeben...")
            self.add_task_btn = QPushButton("Hinzufügen")
            task_input_layout.addWidget(self.task_input)
            task_input_layout.addWidget(self.add_task_btn)
            task_layout.addLayout(task_input_layout)
            
            # Task Buttons
            task_buttons_layout = QHBoxLayout()
            self.mark_done_btn = QPushButton("Als erledigt markieren")
            self.remove_task_btn = QPushButton("Entfernen")
            task_buttons_layout.addWidget(self.mark_done_btn)
            task_buttons_layout.addWidget(self.remove_task_btn)
            task_layout.addLayout(task_buttons_layout)
            
            task_group.setLayout(task_layout)
            left_layout.addWidget(task_group)
            main_layout.addWidget(left_column, 1)  # Stretch-Faktor 1
            
            # Mittlere Spalte: Hauptbereich
            middle_column = QWidget()
            middle_layout = QVBoxLayout(middle_column)
            
            # Status Gruppe
            status_group = QGroupBox("Status")
            status_layout = QVBoxLayout()
            
            # Whisper Status
            self.whisper_status = QLabel("Whisper: Bereit")
            self.whisper_status.setStyleSheet("color: #00ff00")  # Grün für "Bereit"
            status_layout.addWidget(self.whisper_status)
            
            # LLM Auswahl
            llm_layout = QHBoxLayout()
            llm_label = QLabel("LLM:")
            self.llm_combo = QComboBox()
            self.llm_combo.addItem("Ollama")
            llm_layout.addWidget(llm_label)
            llm_layout.addWidget(self.llm_combo)
            
            # Modell Auswahl
            model_label = QLabel("Modell:")
            self.model_combo = QComboBox()
            self.model_combo.addItem("llama3:8b")
            self.prompt_edit_btn = QPushButton("Prompt bearbeiten")
            llm_layout.addWidget(model_label)
            llm_layout.addWidget(self.model_combo)
            llm_layout.addWidget(self.prompt_edit_btn)
            status_layout.addLayout(llm_layout)
            
            # Mikrofon Auswahl
            mic_layout = QHBoxLayout()
            mic_label = QLabel("Mikrofon:")
            self.mic_status = QLabel("Mikrofon (Moman EMP Microphone)")
            self.mic_status.setStyleSheet("color: #00ff00")  # Grün für aktives Mikrofon
            self.mic_select_btn = QPushButton("Mikrofon auswählen")
            self.record_btn = QPushButton("Aufnahme starten")
            mic_layout.addWidget(mic_label)
            mic_layout.addWidget(self.mic_status)
            mic_layout.addWidget(self.mic_select_btn)
            mic_layout.addWidget(self.record_btn)
            status_layout.addLayout(mic_layout)
            
            status_group.setLayout(status_layout)
            middle_layout.addWidget(status_group)
            
            # Wissensbasis Gruppe
            knowledge_group = QGroupBox("Wissensbasis Lernen")
            knowledge_layout = QVBoxLayout()
            
            # Import Buttons
            self.import_files_btn = QPushButton("📄 Dateien importieren")
            self.import_audio_btn = QPushButton("🔊 Audiobücher lernen (Ordner)")
            knowledge_layout.addWidget(self.import_files_btn)
            knowledge_layout.addWidget(self.import_audio_btn)
            
            # Kompakter Datenbank-Status
            status_layout = QHBoxLayout()
            self.db_status_label = QLabel("📚 Einträge:")
            self.db_status_count = QLabel("0")  # Wird durch update_db_status aktualisiert
            self.db_status_label.setStyleSheet("color: #00ff00")  # Grün für aktiv
            status_layout.addWidget(self.db_status_label)
            status_layout.addWidget(self.db_status_count)
            status_layout.addStretch()
            knowledge_layout.addLayout(status_layout)
            
            knowledge_group.setLayout(knowledge_layout)
            middle_layout.addWidget(knowledge_group)
            
            # Chat Gruppe
            chat_group = QGroupBox("Chat")
            chat_layout = QVBoxLayout()
            
            # Chat Bereich
            self.chat_area = QTextEdit()
            self.chat_area.setReadOnly(True)
            chat_layout.addWidget(self.chat_area)
            
            # War diese Antwort hilfreich?
            feedback_layout = QHBoxLayout()
            feedback_label = QLabel("War diese Antwort hilfreich?")
            self.thumbs_up_btn = QPushButton("👍")
            self.thumbs_down_btn = QPushButton("👎")
            feedback_layout.addWidget(feedback_label)
            feedback_layout.addWidget(self.thumbs_up_btn)
            feedback_layout.addWidget(self.thumbs_down_btn)
            feedback_layout.addStretch()
            chat_layout.addLayout(feedback_layout)
            
            # Chat Eingabe
            input_layout = QHBoxLayout()
            self.chat_input = QLineEdit()
            self.chat_input.setPlaceholderText("Nachricht eingeben...")
            self.send_btn = QPushButton("Senden")
            input_layout.addWidget(self.chat_input)
            input_layout.addWidget(self.send_btn)
            chat_layout.addLayout(input_layout)
            
            chat_group.setLayout(chat_layout)
            middle_layout.addWidget(chat_group)
            
            main_layout.addWidget(middle_column, 2)  # Stretch-Faktor 2
            
            # Rechte Spalte: Wetter & Internet
            right_column = QWidget()
            right_layout = QVBoxLayout(right_column)
            
            # Wetter Gruppe
            weather_group = QGroupBox("Wetter")
            weather_layout = QVBoxLayout()
            
            # Dynamische Wetter-Labels
            self.time_label = QLabel()
            self.location_label = QLabel()
            self.temp_label = QLabel()
            self.feels_label = QLabel()
            self.cloud_label = QLabel()
            self.humidity_label = QLabel()
            self.wind_label = QLabel()
            self.last_update_label = QLabel()
            
            weather_layout.addWidget(self.time_label)
            weather_layout.addWidget(self.location_label)
            weather_layout.addWidget(self.temp_label)
            weather_layout.addWidget(self.feels_label)
            weather_layout.addWidget(self.cloud_label)
            weather_layout.addWidget(self.humidity_label)
            weather_layout.addWidget(self.wind_label)
            weather_layout.addWidget(self.last_update_label)
            
            weather_group.setLayout(weather_layout)
            right_layout.addWidget(weather_group)
            
            # Wetter-Update Timer
            self.weather_timer = QTimer()
            self.weather_timer.timeout.connect(self.update_weather)
            self.weather_timer.start(300000)  # Update alle 5 Minuten
            
            # Initiales Wetter-Update
            self.update_weather()
            
            # Internet Gruppe
            internet_group = QGroupBox("Internet")
            internet_layout = QVBoxLayout()
            
            # Online Status
            self.online_status = QCheckBox("Online-Modus")
            self.online_status.setChecked(True)
            internet_layout.addWidget(self.online_status)
            
            # URL Eingabe
            url_layout = QHBoxLayout()
            self.url_input = QLineEdit()
            self.url_input.setPlaceholderText("URL eingeben...")
            self.search_btn = QPushButton("Suchen")
            url_layout.addWidget(self.url_input)
            url_layout.addWidget(self.search_btn)
            internet_layout.addLayout(url_layout)
            
            # Optionen
            self.extract_links = QCheckBox("Links extrahieren")
            self.capture_images = QCheckBox("Bilder erfassen")
            self.analyze_headings = QCheckBox("Überschriften analysieren")
            self.auto_save = QCheckBox("Automatisch speichern")
            
            internet_layout.addWidget(self.extract_links)
            internet_layout.addWidget(self.capture_images)
            internet_layout.addWidget(self.analyze_headings)
            internet_layout.addWidget(self.auto_save)
            
            # Status und Ergebnis
            self.web_status = QLabel("Bereit")
            self.web_result = QLabel("Ergebnis")
            
            # Aktions-Buttons
            web_buttons_layout = QHBoxLayout()
            self.save_btn = QPushButton("Speichern")
            self.clear_btn = QPushButton("Löschen")
            web_buttons_layout.addWidget(self.save_btn)
            web_buttons_layout.addWidget(self.clear_btn)
            
            internet_layout.addWidget(self.web_status)
            internet_layout.addWidget(self.web_result)
            internet_layout.addLayout(web_buttons_layout)
            
            internet_group.setLayout(internet_layout)
            right_layout.addWidget(internet_group)
            
            main_layout.addWidget(right_column, 1)  # Stretch-Faktor 1
            
            # Statusleiste
            self.statusBar = QStatusBar()
            self.setStatusBar(self.statusBar)
            
            # System-Auslastung in der Statusleiste
            self.system_stats = QLabel("CPU: 2.9% | RAM: 34.7% | GPU: --% | Modell: -- | DB: 36120.5 MB")
            self.statusBar.addPermanentWidget(self.system_stats)
            
            # Signal-Verbindungen
            self.setup_connections()
            
            logger.info("UI erfolgreich initialisiert")
            
        except Exception as e:
            logger.error(f"Fehler beim Initialisieren der UI: {e}", exc_info=True)
            raise

    def setup_connections(self):
        """Verbindet alle Signale mit ihren Slots"""
        try:
            # Aufgabenverwaltung
            self.add_task_btn.clicked.connect(self.add_task)
            self.mark_done_btn.clicked.connect(self.mark_task_done)
            self.remove_task_btn.clicked.connect(self.remove_task)
            
            # Chat
            self.chat_input.returnPressed.connect(self.send_message)
            self.send_btn.clicked.connect(self.send_message)
            self.thumbs_up_btn.clicked.connect(lambda: self.send_feedback(True))
            self.thumbs_down_btn.clicked.connect(lambda: self.send_feedback(False))
            
            # Audio
            self.record_btn.clicked.connect(self.toggle_recording)
            self.mic_select_btn.clicked.connect(self.show_mic_selector)
            
            # Wissensbasis
            self.import_files_btn.clicked.connect(self.show_import_dialog)
            self.import_audio_btn.clicked.connect(self.import_audiobooks)
            
            # LLM
            self.prompt_edit_btn.clicked.connect(self.show_prompt_editor)
            
            # Internet
            self.search_btn.clicked.connect(self.search_url)
            self.save_btn.clicked.connect(self.save_web_result)
            self.clear_btn.clicked.connect(self.clear_web_result)
            
        except Exception as e:
            logger.error(f"Fehler beim Verbinden der Signale: {e}")

    def add_task(self):
        """Fügt eine neue Aufgabe hinzu"""
        try:
            task_text = self.task_input.text().strip()
            if task_text:
                self.task_list.addItem(task_text)
                self.task_input.clear()
        except Exception as e:
            logger.error(f"Fehler beim Hinzufügen der Aufgabe: {e}")

    def mark_task_done(self):
        """Markiert die ausgewählte Aufgabe als erledigt"""
        try:
            current_item = self.task_list.currentItem()
            if current_item:
                current_item.setCheckState(Qt.CheckState.Checked)
        except Exception as e:
            logger.error(f"Fehler beim Markieren der Aufgabe: {e}")

    def remove_task(self):
        """Entfernt die ausgewählte Aufgabe"""
        try:
            current_row = self.task_list.currentRow()
            if current_row >= 0:
                self.task_list.takeItem(current_row)
        except Exception as e:
            logger.error(f"Fehler beim Entfernen der Aufgabe: {e}")

    def send_message(self):
        """Sendet eine Nachricht"""
        try:
            message = self.chat_input.text().strip()
            if message:
                self.chat_input.clear()
                self.send_text_message(message)
        except Exception as e:
            logger.error(f"Fehler beim Senden der Nachricht: {e}")

    def send_feedback(self, is_positive: bool):
        """Sendet Feedback für die letzte Antwort"""
        try:
            feedback_type = "positiv" if is_positive else "negativ"
            logger.info(f"Feedback ({feedback_type}) für Antwort gesendet")
            # Hier das Feedback verarbeiten
        except Exception as e:
            logger.error(f"Fehler beim Senden des Feedbacks: {e}")

    def search_url(self):
        """Führt eine URL-Suche durch"""
        try:
            url = self.url_input.text().strip()
            if url:
                self.web_status.setText("Suche läuft...")
                # Hier die URL-Suche implementieren
        except Exception as e:
            logger.error(f"Fehler bei der URL-Suche: {e}")

    def save_web_result(self):
        """Speichert das Web-Ergebnis"""
        try:
            self.web_status.setText("Speichern...")
            # Hier das Speichern implementieren
        except Exception as e:
            logger.error(f"Fehler beim Speichern des Web-Ergebnisses: {e}")

    def clear_web_result(self):
        """Löscht das Web-Ergebnis"""
        try:
            self.url_input.clear()
            self.web_result.clear()
            self.web_status.setText("Bereit")
        except Exception as e:
            logger.error(f"Fehler beim Löschen des Web-Ergebnisses: {e}")

    def create_menu(self):
        """Erstellt die Menüleiste"""
        try:
            menubar = self.menuBar()
            
            # Datei-Menü
            file_menu = menubar.addMenu('&Datei')
            
            import_action = file_menu.addAction('&Importieren')
            import_action.triggered.connect(self.show_import_dialog)
            
            export_action = file_menu.addAction('&Exportieren')
            export_action.triggered.connect(self.export_conversation)
            
            file_menu.addSeparator()
            
            exit_action = file_menu.addAction('&Beenden')
            exit_action.triggered.connect(self.close)
            
            # Einstellungen-Menü
            settings_menu = menubar.addMenu('&Einstellungen')
            
            audio_action = settings_menu.addAction('&Audio')
            audio_action.triggered.connect(self.show_audio_settings)
            
            model_action = settings_menu.addAction('&KI-Modell')
            model_action.triggered.connect(self.show_model_settings)
            
            # Hilfe-Menü
            help_menu = menubar.addMenu('&Hilfe')
            
            about_action = help_menu.addAction('Ü&ber')
            about_action.triggered.connect(self.show_about)
            
        except Exception as e:
            logger.error(f"Fehler beim Erstellen des Menüs: {e}")

    def show_import_dialog(self):
        """Zeigt Dialog zum Importieren von Wissen"""
        try:
            options = QFileDialog.Option.DontUseNativeDialog
            file_name, _ = QFileDialog.getOpenFileName(
                self,
                "Wissen importieren",
                "",
                "Alle Dateien (*);;Text Dateien (*.txt);;PDF Dateien (*.pdf)",
                options=options
            )
            
            if file_name:
                self.import_knowledge(file_name)

        except Exception as e:
            logger.error(f"Fehler beim Anzeigen des Import-Dialogs: {e}")
            
    def import_knowledge(self, file_path):
        """Importiert Wissen aus einer Datei"""
        try:
            # Erstelle und starte Import-Thread
            self.import_thread = KnowledgeImportThread(
                self.learning_manager,
                file_path,
                parent=self
            )
            
            self.import_thread.progress_updated.connect(
                lambda msg: self.statusBar.showMessage(msg))
            self.import_thread.import_finished.connect(
                lambda: self.statusBar.showMessage("Import abgeschlossen"))
            self.import_thread.import_error.connect(
                lambda msg: QMessageBox.critical(self, "Fehler", msg))
                
            self.import_thread.start()
            
        except Exception as e:
            logger.error(f"Fehler beim Importieren von {file_path}: {e}")
            QMessageBox.critical(self, "Fehler", 
                               f"Fehler beim Importieren: {str(e)}")
            
    def export_conversation(self):
        """Exportiert die aktuelle Konversation"""
        try:
            options = QFileDialog.Option.DontUseNativeDialog
            file_name, _ = QFileDialog.getSaveFileName(
                self,
                "Konversation exportieren",
                f"conversation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                "Text Dateien (*.txt)",
                options=options
            )
            
            if file_name:
                with open(file_name, 'w', encoding='utf-8') as f:
                    f.write(self.chat_area.toPlainText())
                self.statusBar.showMessage("Konversation exportiert")
                
        except Exception as e:
            logger.error(f"Fehler beim Exportieren der Konversation: {e}")
            QMessageBox.critical(self, "Fehler", 
                               f"Fehler beim Exportieren: {str(e)}")
            
    def show_audio_settings(self):
        """Zeigt Audio-Einstellungen"""
        try:
            self.audio_settings.show()
        except Exception as e:
            logger.error(f"Fehler beim Anzeigen der Audio-Einstellungen: {e}")
            
    def show_model_settings(self):
        """Zeigt KI-Modell-Einstellungen"""
        try:
            # TODO: Implementiere Modell-Einstellungen
            QMessageBox.information(self, "Info", 
                                  "Modell-Einstellungen noch nicht implementiert")
        except Exception as e:
            logger.error(f"Fehler beim Anzeigen der Modell-Einstellungen: {e}")
            
    def show_about(self):
        """Zeigt Über-Dialog"""
        try:
            about_text = """
            JARVIS - Ihr KI-Assistent
            Version 1.0
            
            Ein intelligenter Assistent mit Spracherkennung,
            Text-to-Speech und maschinellem Lernen.
            
            © 2024 Alle Rechte vorbehalten
            """
            
            QMessageBox.about(self, "Über JARVIS", about_text.strip())
            
        except Exception as e:
            logger.error(f"Fehler beim Anzeigen des Über-Dialogs: {e}")

    @pyqtSlot()
    def send_text_message(self, text):
        """Verarbeitet die Texteingabe und sendet sie an den LLM."""
        try:
            # Generiere eine eindeutige ID für diese Antwort
            response_id = str(uuid.uuid4())
            
            # Speichere den Kontext für River Learning
            self.interaction_context[response_id] = {"user_input": text}

            # Zeige die Benutzereingabe im Chat
            self.on_update_chat(self.username, text)
            
            # Lösche das Eingabefeld
            self.chat_input.clear()

            # Starte den Verarbeitungs-Thread
            self.processing_thread = TextProcessingThread(
                text=text,
                llm_manager=self.llm_manager,
                config=self.config,
                learning_manager=self.learning_manager,
                river_learning_manager=self.river_learning_manager,
                response_id=response_id,
                parent=self
            )
            
            # Verbinde die Signale
            self.processing_thread.update_chat.connect(self.on_update_chat)
            self.processing_thread.trigger_tts.connect(self.on_trigger_tts)
            self.processing_thread.processing_finished.connect(self.on_processing_finished)
            
            # Starte den Thread
            self.processing_thread.start()
            
        except Exception as e:
            error_msg = f"Fehler bei der Verarbeitung der Texteingabe: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.on_update_chat("System", error_msg)

    @pyqtSlot()
    def toggle_recording(self):
        """Startet/Stoppt die Audioaufnahme"""
        try:
            if not self.is_recording:
                # Starte Aufnahme
                self.record_btn.setText("Aufnahme stoppen")
                self.record_btn.setStyleSheet("background-color: #ff0000")  # Rot für Aufnahme
                self.whisper_status.setText("Whisper: Aufnahme läuft...")
                self.whisper_status.setStyleSheet("color: #ff0000")  # Rot für Aufnahme
                
                # Starte Audio-Thread
                self.audio_thread = AudioRecordingThread(
                    device_index=self.config.get("audio_device_index", 0),
                    sample_rate=16000,
                    chunk_size=1024,
                    parent=self
                )
                
                # Verbinde Signale
                self.audio_thread.audio_data_ready.connect(self.process_audio_data)
                self.audio_thread.error.connect(self.on_recording_error)
                
                # Starte Thread
                self.audio_thread.start()
                self.is_recording = True
                
            else:
                # Stoppe Aufnahme
                self.stop_recording()
                
        except Exception as e:
            logger.error(f"Fehler beim Umschalten der Aufnahme: {e}")
            self.stop_recording()
            QMessageBox.critical(self, "Fehler", f"Fehler bei der Audioaufnahme: {str(e)}")

    def stop_recording(self):
        """Stoppt die Audioaufnahme"""
        try:
            if self.audio_thread and self.audio_thread.isRunning():
                self.audio_thread.stop()
                self.audio_thread.wait()
                
            self.is_recording = False
            self.record_btn.setText("Aufnahme starten")
            self.record_btn.setStyleSheet("")
            self.whisper_status.setText("Whisper: Bereit")
            self.whisper_status.setStyleSheet("color: #00ff00")
            
        except Exception as e:
            logger.error(f"Fehler beim Stoppen der Aufnahme: {e}")

    def process_audio_data(self, audio_data):
        """Verarbeitet die aufgenommenen Audiodaten"""
        try:
            logger.info("Starte Audioverarbeitung...")
            
            # Logge Audio-Daten Statistik VOR der Stilleerkennung
            if audio_data is not None and audio_data.size > 0:
                logger.debug(f"Audiodaten empfangen: Länge={len(audio_data)}, Min={np.min(audio_data):.4f}, Max={np.max(audio_data):.4f}, MeanAbs={np.mean(np.abs(audio_data)):.4f}, dtype={audio_data.dtype}")
            else:
                logger.warning("Keine oder leere Audiodaten empfangen.")
                return # Keine Verarbeitung möglich

            # Stilleerkennung (prüft, ob die Aufnahme hauptsächlich still ist)
            sample_rate = 16000  # Die Sample-Rate, mit der aufgenommen wurde
            # === DEBUG: Stilleerkennung temporär deaktivieren ===
            # if self.whisper_recognizer.detect_silence(audio_data, sample_rate):
            #     logger.warning("Stille erkannt, überspringe Transkription.")
            #     self.whisper_status.setText("Whisper: Stille erkannt")
            #     self.whisper_status.setStyleSheet("color: #ffa500")  # Orange für Warnung
            #     return  # Breche die Verarbeitung ab
            logger.info("DEBUG: Stilleerkennung wird übersprungen!") # Hinzugefügt für Klarheit
            # === Ende DEBUG ===

            # Speichere Audio temporär
            temp_file = "temp_recording.wav"
            logger.info(f"Speichere temporäre Datei: {temp_file}")
            sf.write(temp_file, audio_data, sample_rate)
            
            # Transkribiere mit Whisper
            logger.info("Starte Whisper-Transkription...")
            text = self.whisper_recognizer.transcribe_wav(temp_file)  # Korrigierte Methode
            logger.info(f"Whisper-Ergebnis: {text}")
            
            # Lösche temporäre Datei
            os.remove(temp_file)
            logger.info("Temporäre Datei gelöscht")
            
            if text and text.strip():
                # Zeige erkannten Text NICHT HIER AN (wird in send_text_message gemacht)
                # self.on_update_chat("Benutzer", text)  # ENTFERNT
                
                # Sende an LLM
                self.send_text_message(text)
            else:
                logger.warning("Keine Sprache erkannt")
                self.whisper_status.setText("Whisper: Keine Sprache erkannt")
                self.whisper_status.setStyleSheet("color: #ffa500")  # Orange für Warnung

        except Exception as e:
            logger.error(f"Fehler bei der Audioverarbeitung: {e}", exc_info=True)
            self.whisper_status.setText("Whisper: Fehler")
            self.whisper_status.setStyleSheet("color: #ff0000")  # Rot für Fehler

    def init_audio(self):
        """Initialisiert die Audio-Komponenten"""
        try:
            self.audio_processor = AudioProcessor(self)
            self.audio_processor.recording_started.connect(self.on_recording_started)
            self.audio_processor.recording_stopped.connect(self.on_recording_stopped)
            self.audio_processor.audio_data_ready.connect(self.on_audio_data)
            
        except Exception as e:
            logger.error(f"Fehler beim Initialisieren der Audio-Komponenten: {e}")

    def init_tts(self):
        """Initialisiert die Text-to-Speech-Komponenten"""
        self.tts_manager = None # Explizit initialisieren
        try:
            logger.info(f"Versuche TTS-Manager mit der aktuellen Konfiguration zu initialisieren...")
            # Übergebe das gesamte Konfigurationsobjekt
            manager = create_tts_manager(self.config)
            
            if manager:
                self.tts_manager = manager
                tts_engine_used = self.config.get("tts", {}).get("engine", "unbekannt") # Versuche, die verwendete Engine zu loggen
                logger.info(f"TTS-Manager ({tts_engine_used}) erfolgreich initialisiert.")
                
                # Hauptsignal verbinden
                if hasattr(self.tts_manager, 'tts_finished'):
                    self.tts_manager.tts_finished.connect(self.on_tts_finished)
                else:
                    logger.warning(f"TTS Manager ({tts_engine_used}) hat kein 'tts_finished' Signal.")
                
                # Optionale Signale verbinden
                if hasattr(self.tts_manager, 'tts_error'):
                     self.tts_manager.tts_error.connect(self.on_tts_error)
                if hasattr(self.tts_manager, 'tts_progress'):
                     self.tts_manager.tts_progress.connect(self.on_tts_progress)
                     
                logger.info(f"TTS-Manager ({tts_engine_used}): Signale verbunden.")
            else:
                # create_tts_manager loggt den Fehler bereits
                logger.warning("TTS Manager konnte nicht initialisiert werden (siehe vorherige Logs). TTS nicht verfügbar.")
                self.tts_manager = None # Sicherstellen, dass es None ist

        except Exception as e:
            logger.error(f"Unerwarteter Fehler beim Initialisieren der Text-to-Speech-Komponenten: {e}", exc_info=True)
            self.tts_manager = None # Sicherstellen, dass es None im Fehlerfall ist

    def on_recording_started(self):
        """Handler für Aufnahmestart"""
        self.is_recording = True
        self.record_btn.setChecked(True)
        self.statusBar.showMessage("Aufnahme läuft...")
        
    def on_recording_stopped(self):
        """Handler für Aufnahmestopp"""
        self.is_recording = False
        self.record_btn.setChecked(False)
        self.statusBar.showMessage("Aufnahme gestoppt")
        
    def on_audio_data(self, data):
        """Handler für neue Audiodaten"""
        if hasattr(self, 'audio_visualizer'):
            self.audio_visualizer.update_audio_data(data)

    def on_tts_finished(self, text):
        """Handler für fertige Text-to-Speech-Erstellung"""
        self.on_update_chat("System", text)

    def on_tts_error(self, error_msg):
        """Handler für Fehler bei der Text-to-Speech-Erstellung"""
        self.on_update_chat("System", error_msg)
        self.last_response_id = None

    def on_tts_progress(self, progress):
        """Handler für Text-to-Speech-Fortschritt"""
        self.status_widget.set_tts_progress(progress)

    def on_recording_error(self, error_msg):
        """Handler für Fehler bei der Audioaufnahme"""
        self.on_update_chat("System", error_msg)
        self.is_recording = False
        self.record_btn.setChecked(False)
        QMessageBox.critical(self, "Fehler", 
                           f"Fehler bei der Audioaufnahme: {str(error_msg)}")

    def on_recording_progress(self, progress):
        """Handler für Audioaufnahme-Fortschritt"""
        self.status_widget.set_recording_progress(progress)

    def on_update_chat(self, sender, message):
        """Handler für neue Nachrichten im Chat"""
        try:
            # Formatiere Nachricht
            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted_message = f"[{timestamp}] {sender}: {message}\n"
            
            # Füge Nachricht hinzu
            self.chat_area.moveCursor(QTextCursor.MoveOperation.End)
            self.chat_area.insertPlainText(formatted_message)
            self.chat_area.moveCursor(QTextCursor.MoveOperation.End)
            
        except Exception as e:
            logger.error(f"Fehler beim Aktualisieren des Chats: {e}")

    def on_trigger_tts(self, text):
        """Triggert die Text-to-Speech-Erstellung"""
        use_tts_config = self.config.get("use_tts", False)
        logger.debug(f"on_trigger_tts aufgerufen. use_tts={use_tts_config}, tts_manager vorhanden={self.tts_manager is not None}")
        
        if use_tts_config and self.tts_manager:
            try:
                logger.info(f"Starte TTS für Text: '{text[:50]}...'")
                self.tts_manager.speak(text)
            except AttributeError as ae:
                 # Fange speziell den Fehler ab, falls speak fehlt
                 logger.error(f"TTS Manager hat keine Methode 'speak': {ae}", exc_info=True)
                 self.on_update_chat("System", "Fehler: Sprachausgabe-Funktion nicht gefunden.")
            except Exception as e:
                logger.error(f"Fehler während TTS speak() Aufruf: {e}", exc_info=True)
                self.on_update_chat("System", f"Fehler bei der Sprachausgabe: {e}")
        elif use_tts_config and not self.tts_manager:
            logger.warning("TTS ist aktiviert, aber der TTS-Manager ist nicht initialisiert. Sprachausgabe übersprungen.")
            # Optional: Inform user in chat?
            # self.on_update_chat("System", "Hinweis: Sprachausgabe ist aktiviert, aber nicht funktionsfähig.")
        else:
             logger.debug("TTS ist nicht aktiviert oder Manager nicht vorhanden, überspringe Sprachausgabe.")

    def on_processing_finished(self, response_id, result):
        """Handler für abgeschlossene Verarbeitung"""
        self.last_response_id = response_id

    def on_processing_error(self, error_msg):
        """Handler für Fehler bei der Verarbeitung"""
        self.on_update_chat("System", error_msg)
        self.last_response_id = None

    def show_mic_selector(self):
        """Zeigt den Mikrofon-Auswahl-Dialog"""
        try:
            selector = MicrophoneSelector(self)
            if selector.exec() == QDialog.DialogCode.Accepted:
                device_index = selector.get_selected_device_index()
                self.mic_combo.setCurrentText(f"Mikrofon: {device_index}")
        except Exception as e:
            logger.error(f"Fehler beim Anzeigen der Mikrofon-Auswahl: {e}")

    def show_prompt_editor(self):
        """Zeigt den Prompt-Editor"""
        try:
            # Pfad zur Prompt-Datei definieren
            prompts_file_path = os.path.join("data", "config", "prompts.json")
            
            # Editor mit dem Pfad initialisieren
            editor = PromptEditor(prompts_file=prompts_file_path, parent=self)
            
            if editor.exec() == QDialog.DialogCode.Accepted:
                # Wenn gespeichert wurde (editor.accept() wurde in save_prompts aufgerufen)
                logger.info("Änderungen im PromptEditor gespeichert. Informiere LLMManager...")
                
                # Annahme: LLMManager bemerkt die Dateiänderung nicht von selbst.
                # Wir müssen ihm sagen, die Datei neu zu laden UND den Provider zu aktualisieren.
                
                # 1. LLMManager soll prompts.json neu laden
                #    (Dafür braucht der LLMManager eine Methode, z.B. reload_prompts())
                # TODO: Implementiere reload_prompts() im LLMManager
                if hasattr(self.llm_manager, 'reload_prompts'):
                     self.llm_manager.reload_prompts()
                     logger.info("LLMManager: Prompts neu geladen.")
                else:
                     # Fallback: Wir holen den formatierten Prompt direkt nach dem Speichern,
                     # basierend auf der Annahme, dass der LLMManager beim nächsten get_system_prompt
                     # die Daten korrekt formatiert.
                     logger.warning("LLMManager hat keine reload_prompts Methode. Aktualisiere Provider direkt.")
                
                # 2. Hole den NEU formatierten System-Prompt vom LLMManager
                #    (get_system_prompt formattiert die intern geladenen Daten)
                formatted_prompt = self.llm_manager.get_system_prompt()
                                
                if formatted_prompt:
                     # 3. Aktualisiere den Provider über den LLMManager
                     self.llm_manager.update_system_prompt(formatted_prompt)
                else:
                     logger.error("Konnte den formatierten Prompt nach dem Speichern nicht erstellen.")

        except Exception as e:
            logger.error(f"Fehler beim Anzeigen des Prompt-Editors: {e}", exc_info=True) # Logge mit Traceback
            QMessageBox.critical(self, "Fehler", f"Fehler beim Öffnen des Prompt-Editors: {str(e)}")

    def import_audiobooks(self):
        """Importiert Audiobücher aus einem Ordner"""
        try:
            folder = QFileDialog.getExistingDirectory(
                self,
                "Audiobuch-Ordner auswählen",
                "",
                QFileDialog.Option.ShowDirsOnly
            )
            
            if not folder:
                return
                
            # Progress Dialog
            progress = QProgressDialog("Verarbeite Audiodateien...", "Abbrechen", 0, 100, self)
            # ---> Setze Fenstertitel
            progress.setWindowTitle("Fortschritt")
            # <--- Ende Fenstertitel
            # Mache den Dialog nicht-modal, um den Hauptthread weniger zu blockieren
            progress.setWindowModality(Qt.WindowModality.NonModal) 
            progress.setAutoClose(True)
            progress.setMinimumDuration(0)
            
            # ---> Speichere Referenz auf ProgressDialog
            self.audio_progress_dialog = progress 
            # <--- Ende ÄNDERUNG

            # Starte Verarbeitung in separatem Thread
            self.audio_processing_thread = AudioProcessingThread(
                folder_path=folder,
                chunk_size=60,  # 60 Sekunden Chunks
                learning_manager=self.learning_manager,
                whisper_recognizer=self.whisper_recognizer,
                parent=self
            )
            
            # ---> VERBINDE NEUES SIGNAL MIT NEUEM SLOT
            self.audio_processing_thread.progress_update.connect(self.update_audio_progress_dialog)
            # <--- Ende ÄNDERUNG
            self.audio_processing_thread.finished.connect(self.on_audio_processing_finished)
            self.audio_processing_thread.error.connect(self.on_audio_processing_error)
            
            self.audio_processing_thread.start()
            # Zeige den Dialog an, aber blockiere nicht den Hauptthread
            progress.show() 
            
        except Exception as e:
            logger.error(f"Fehler beim Importieren von Audiobüchern: {e}")
            QMessageBox.critical(self, "Fehler", f"Fehler beim Importieren: {str(e)}")

    @pyqtSlot(int, int, str)
    def update_audio_progress_dialog(self, current, total, message):
        """Aktualisiert den Fortschrittsdialog sicher aus dem Hauptthread."""
        # Finde den QProgressDialog (wir speichern ihn temporär in einer Instanzvariable)
        if hasattr(self, 'audio_progress_dialog') and self.audio_progress_dialog:
            progress = self.audio_progress_dialog
            if progress.wasCanceled():
                # Signalisiere dem Thread, dass er stoppen soll (falls er noch läuft)
                if hasattr(self, 'audio_processing_thread') and self.audio_processing_thread.isRunning():
                    self.audio_processing_thread.stop()
                # Schließe den Dialog, falls nicht automatisch
                # progress.close() # AutoClose ist True, also wahrscheinlich nicht nötig
                self.audio_progress_dialog = None # Referenz entfernen
                return
                
            progress.setMaximum(total)
            progress.setValue(current)
            progress.setLabelText(message)
        else:
             logger.warning("update_audio_progress_dialog aufgerufen, aber kein gültiger Dialog gefunden.")

    def on_audio_processing_finished(self):
        """Callback wenn Audio-Verarbeitung abgeschlossen"""
        # ---> Dialog-Referenz entfernen
        if hasattr(self, 'audio_progress_dialog'):
            self.audio_progress_dialog = None 
        # <--- Ende ÄNDERUNG
        try:
            QMessageBox.information(self, "Erfolg", "Audiobücher wurden erfolgreich importiert!")
            self.update_db_status()  # Aktualisiere Datenbank-Status
        except Exception as e:
            logger.error(f"Fehler nach Audio-Verarbeitung: {e}")

    def on_audio_processing_error(self, message):
        """Callback bei Fehler während der Audio-Verarbeitung"""
        # ---> Dialog-Referenz entfernen
        if hasattr(self, 'audio_progress_dialog'):
            self.audio_progress_dialog = None
        # <--- Ende ÄNDERUNG
        QMessageBox.critical(self, "Fehler", f"Fehler bei der Verarbeitung: {message}")

    def update_weather(self):
        """Aktualisiert die Wetterdaten über die API"""
        try:
            # API-Key und Stadt aus Config
            api_key = self.config.get("weather_api_key")
            city = self.config.get("weather_city", "Dresden")
            
            if not api_key:
                logger.warning("Kein Wetter-API-Key konfiguriert")
                self.show_weather_error("API-Key nicht konfiguriert")
                return
                
            # API-Anfrage senden
            url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric&lang=de"
            response = requests.get(url)
            
            if response.status_code != 200:
                logger.error(f"Wetter-API Fehler: {response.status_code}")
                self.show_weather_error("API-Fehler")
                return
                
            data = response.json()
            
            # Daten aktualisieren
            self.time_label.setText(f"Zeit: {datetime.now().strftime('%H:%M')}")
            self.location_label.setText(f"📍 {city}")
            self.temp_label.setText(f"🌡️ Temperatur: {data['main']['temp']}°C")
            self.feels_label.setText(f"🌡️ Gefühlt: {data['main']['feels_like']}°C")
            self.cloud_label.setText(f"☁️ {data['weather'][0]['description']}")
            self.humidity_label.setText(f"💧 Luftfeuchtigkeit: {data['main']['humidity']}%")
            self.wind_label.setText(f"💨 Wind: {data['wind']['speed']} km/h")
            self.last_update_label.setText(f"Letzte Aktualisierung: {datetime.now().strftime('%H:%M')}")
            
        except Exception as e:
            logger.error(f"Fehler beim Aktualisieren der Wetterdaten: {e}")
            self.show_weather_error("Verbindungsfehler")
            
    def show_weather_error(self, message):
        """Zeigt Wetterfehler in der UI an"""
        self.time_label.setText("Zeit: --:--")
        self.location_label.setText("📍 --")
        self.temp_label.setText("🌡️ --°C")
        self.feels_label.setText("🌡️ Gefühlt: --°C")
        self.cloud_label.setText(f"☁️ Fehler: {message}")
        self.humidity_label.setText("💧 --%")
        self.wind_label.setText("💨 -- km/h")
        self.last_update_label.setText("Keine Verbindung zur Wetter-API")

    def update_db_status(self, count=None):
        """Aktualisiert die Anzeige der Datenbankeinträge"""
        try:
            entry_count = "N/A" # Standardwert
            if hasattr(self.learning_manager, 'get_statistics'):
                stats = self.learning_manager.get_statistics()
                if "entry_count" in stats and "error" not in stats: # Prüfe ob Zählung erfolgreich war
                    entry_count = stats["entry_count"]
                elif "error" in stats:
                    logger.error(f"Fehler beim Abrufen der DB-Statistiken: {stats['error']}")
                else:
                    logger.warning("'entry_count' nicht in Statistiken gefunden.")
            else:
                logger.warning("'LearningManager' hat keine Methode 'get_statistics'. DB-Status kann nicht ermittelt werden.")
            
            self.db_status_count.setText(str(entry_count))
            if entry_count != "N/A":
                self.db_status_label.setStyleSheet("color: #00ff00")  # Grün für aktiv
            else:
                 self.db_status_label.setStyleSheet("color: #ffa500")  # Orange für unbekannt/Fehler
            
        except Exception as e:
            logger.error(f"Fehler beim Aktualisieren des Datenbank-Status: {e}", exc_info=True) # Füge Traceback hinzu
            self.db_status_count.setText("Fehler")
            self.db_status_label.setStyleSheet("color: #ff0000")  # Rot für Fehler

    @pyqtSlot(float)
    def on_cpu_update(self, value):
        self.last_cpu = value
        self._update_status_bar()

    @pyqtSlot(float)
    def on_gpu_update(self, value):
        self.last_gpu = value
        self._update_status_bar()

    @pyqtSlot(float)
    def on_memory_update(self, value):
        self.last_memory = value
        self._update_status_bar()
        
    def _update_status_bar(self):
        """Aktualisiert den Text in der Statusleiste mit den neuesten Werten."""
        try:
            model_name = self.llm_manager.get_current_model() if self.llm_manager else "--"
            
            # Hole DB Größe in MB
            db_status_text = "DB: -- MB" # Standardwert
            if hasattr(self.learning_manager, 'chroma_db_path'): 
                db_path = self.learning_manager.chroma_db_path
                if db_path and os.path.exists(db_path):
                    try:
                        total_size = 0
                        for dirpath, dirnames, filenames in os.walk(db_path):
                            for f in filenames:
                                fp = os.path.join(dirpath, f)
                                # skip if it is symbolic link
                                if not os.path.islink(fp):
                                    total_size += os.path.getsize(fp)
                        
                        # Umrechnung in MB
                        if total_size > 0:
                            size_mb = total_size / (1024 * 1024)
                            db_status_text = f"DB: {size_mb:.1f} MB"
                        else:
                            db_status_text = "DB: 0.0 MB"
                            
                    except Exception as size_e:
                        logger.warning(f"Fehler beim Berechnen der DB-Größe für Pfad {db_path}: {size_e}")
                        db_status_text = "DB: Fehler MB"
                else:
                     logger.warning(f"DB-Pfad '{db_path}' vom LearningManager existiert nicht. Kann Größe nicht bestimmen.")
            else:
                logger.warning("LearningManager hat kein Attribut 'chroma_db_path'. Kann DB-Größe nicht bestimmen.")

            stats_text = (f"CPU: {self.last_cpu:.1f}% | "
                         f"RAM: {self.last_memory:.1f}% | "
                         f"GPU: {self.last_gpu:.1f}% | "
                         f"Modell: {model_name} | "
                         f"{db_status_text}") # Angepasster DB Status (Größe)
            
            self.system_stats.setText(stats_text)
            
        except Exception as e:
            logger.error(f"Fehler beim Aktualisieren der Statusleiste: {e}")

class TextProcessingThread(QThread):
    """Thread für die Textverarbeitung"""
    update_chat = pyqtSignal(str, str)  # sender, message
    trigger_tts = pyqtSignal(str)  # text
    processing_finished = pyqtSignal(str, str)  # response_id, result
    
    def __init__(self, text, llm_manager, config, learning_manager, river_learning_manager, response_id, parent=None):
        super().__init__(parent)
        self.text = text
        self.llm_manager = llm_manager
        self.config = config
        self.learning_manager = learning_manager
        self.river_learning_manager = river_learning_manager
        self.response_id = response_id
        
    def run(self):
        try:
            # Verarbeite Text mit LLM
            response = self.llm_manager.process_text(self.text)
            
            # Speichere Interaktion (Korrigierter Methodenname)
            if hasattr(self.learning_manager, 'add_interaction'):
                self.learning_manager.add_interaction(
                    self.text, 
                    response,
                    # Passe den Kontext an, falls die Methode ihn erwartet
                    # Ggf. nur response_id oder ein leeres Dict übergeben?
                    # Hängt von der Definition von add_interaction ab.
                    # Aktuell: Übergebe response_id als Teil eines dicts
                    context={"response_id": self.response_id} 
                )
            else:
                logger.warning("LearningManager hat keine Methode 'add_interaction'. Interaktion kann nicht gespeichert werden.")
            
            # Aktualisiere River Learning
            if self.river_learning_manager:
                # Versuche, das Modell mit der neuen Interaktion zu aktualisieren
                try:
                    self.river_learning_manager.learn(self.text, response)
                    logger.info("River-Modell erfolgreich aktualisiert.")
                except Exception as e:
                    logger.error(f"Fehler beim Aktualisieren des River-Modells: {e}")
            
            # Sende Ergebnis
            self.update_chat.emit("JARVIS", response)
            self.processing_finished.emit(self.response_id, response)
            
            # Trigger TTS wenn aktiviert
            if self.config.get("use_tts", False):
                self.trigger_tts.emit(response)
            
        except Exception as e:
            error_msg = f"Fehler bei der Textverarbeitung: {str(e)}"
            logger.error(error_msg)
            self.update_chat.emit("System", error_msg)

class AudioRecordingThread(QThread):
    """Thread für kontinuierliche Audioaufnahme"""
    audio_data_ready = pyqtSignal(object)  # Sendet numpy array
    error = pyqtSignal(str)
    
    def __init__(self, device_index, sample_rate, chunk_size, parent=None):
        super().__init__(parent)
        self.device_index = device_index
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.running = False
        # === DEBUGGING: Logge Initialisierungsparameter ===
        logger.debug(f"AudioRecordingThread initialisiert mit device_index={self.device_index}, sample_rate={self.sample_rate}, chunk_size={self.chunk_size}")
        
    def run(self):
        # === DEBUGGING: Logge Thread-Start ===
        logger.info(f"AudioRecordingThread gestartet (ID: {self.currentThreadId()})")
        try:
            import sounddevice as sd
            logger.debug("Sounddevice-Modul erfolgreich importiert.")
            
            self.running = True
            # === DEBUGGING: Logge vor dem Öffnen des Streams ===
            logger.info(f"Versuche, InputStream zu öffnen: device={self.device_index}, samplerate={self.sample_rate}, channels=1")
            
            with sd.InputStream(device=self.device_index,
                              samplerate=self.sample_rate,
                              channels=1,
                              dtype=np.float32,
                              blocksize=self.chunk_size) as stream:
                
                # === DEBUGGING: Logge erfolgreiches Öffnen des Streams ===
                logger.info("InputStream erfolgreich geöffnet.")
                
                # Buffer für die gesamte Aufnahme
                buffer = []
                
                while self.running:
                    # === DEBUGGING: Logge vor stream.read() ===
                    # logger.debug("Warte auf Audiodaten von stream.read()...") # Deaktiviert, da es zu viel loggt
                    audio_chunk, overflowed = stream.read(self.chunk_size)
                    # === DEBUGGING: Logge nach stream.read() ===
                    if overflowed:
                        logger.warning("Input overflowed!")
                    # logger.debug(f"Audio-Chunk gelesen, Größe: {audio_chunk.shape}") # Deaktiviert, da es zu viel loggt
                    
                    buffer.append(audio_chunk.copy())
                    
                    # Entferne die Puffer-Prüfung und das Senden hier
                    # buffer_duration = len(buffer) * self.chunk_size / self.sample_rate
                    # logger.debug(f"Aktueller Puffer: {len(buffer)} Chunks, Berechnete Dauer: {buffer_duration:.4f}s")
                    # if len(buffer) >= 32: # Geändert von 79 -> ENTFERNT
                    #     ... Sende Logik entfernt ...
                    #     buffer = [] # Leere den Buffer -> ENTFERNT
                
                # === Nach der Schleife: Sende die gesamte Aufnahme ===
                if buffer: # Prüfe, ob überhaupt etwas aufgenommen wurde
                    audio_data = np.concatenate(buffer)
                    buffer_duration = len(audio_data) / self.sample_rate
                    logger.info(f"Aufnahme gestoppt. Sende gesamte Audioaufnahme ({buffer_duration:.2f}s, Datenform: {audio_data.shape})")
                    self.audio_data_ready.emit(audio_data)
                else:
                    logger.info("Aufnahme gestoppt, aber kein Audio im Puffer.")
                        
        except sd.PortAudioError as pae:
             logger.error(f"PortAudio Fehler im Aufnahme-Thread: {pae}", exc_info=True)
        except Exception as e:
            # === DEBUGGING: Logge unerwarteten Fehler detaillierter ===
            logger.error(f"Unerwarteter Fehler im Aufnahme-Thread: {e}", exc_info=True)
            self.error.emit(str(e))
        finally:
            # === DEBUGGING: Logge Thread-Ende ===
            logger.info(f"AudioRecordingThread beendet (ID: {self.currentThreadId()}). Running-Status: {self.running}")
            
    def stop(self):
        """Stoppt die Aufnahme"""
        # === DEBUGGING: Logge Stopp-Anforderung ===
        logger.info(f"AudioRecordingThread stop() aufgerufen (ID: {self.currentThreadId()})")
        self.running = False

# === Neue Klasse für Audiobuch-Verarbeitung ===
class AudioProcessingThread(QThread):
    """Thread zur Verarbeitung von Audiodateien (z.B. Hörbücher) im Hintergrund."""
    finished = pyqtSignal()
    error = pyqtSignal(str)
    progress_update = pyqtSignal(int, int, str) # current, total, message

    def __init__(self, folder_path, chunk_size, learning_manager, whisper_recognizer, parent=None):
        super().__init__(parent)
        self.folder_path = folder_path
        self.chunk_size_seconds = chunk_size
        self.learning_manager = learning_manager
        self.whisper_recognizer = whisper_recognizer
        self.running = True
        self.sample_rate = 16000 # Whisper benötigt 16kHz
        
    def run(self):
        try:
            # === Finde ffmpeg.exe Pfad ===
            # Versuche zuerst einen bekannten Pfad, dann den System-PATH
            ffmpeg_path = "C:\\ffmpeg\\bin\\ffmpeg.exe" # Annahme basierend auf früheren Logs
            if not os.path.exists(ffmpeg_path):
                 # Versuche, ffmpeg im PATH zu finden (Windows)
                 try:
                      where_output = subprocess.check_output(["where", "ffmpeg"], text=True, startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.CREATE_NO_WINDOW | subprocess.STARTF_USESHOWWINDOW))
                      ffmpeg_path = where_output.strip().split('\n')[0] # Nimm den ersten Treffer
                      logger.info(f"FFmpeg im PATH gefunden: {ffmpeg_path}")
                 except (subprocess.CalledProcessError, FileNotFoundError):
                      logger.error("ffmpeg.exe konnte weder am Standardort noch im PATH gefunden werden! Konvertierung nicht möglich.")
                      self.error.emit("ffmpeg nicht gefunden")
                      return # Thread beenden
            else:
                 logger.info(f"Verwende ffmpeg von: {ffmpeg_path}")

            logger.info(f"Starte Audiobuch-Verarbeitung für Ordner: {self.folder_path}")
            
            # === Dateisuche bleibt gleich ===
            audio_files = []
            supported_extensions = {".wav", ".mp3", ".flac", ".m4a"} 
            for root, dirs, files in os.walk(self.folder_path):
                for filename in files:
                    _, ext = os.path.splitext(filename)
                    if ext.lower() in supported_extensions:
                        filepath = os.path.join(root, filename)
                        audio_files.append(filepath)
                        logger.debug(f"Gefunden: {filepath}")

            if not audio_files:
                logger.warning(f"Keine unterstützten Audiodateien ({supported_extensions}) in {self.folder_path} mit os.walk gefunden.")
                self.error.emit(f"Keine Audiodateien gefunden in {self.folder_path}")
                return

            total_files = len(audio_files)
            logger.info(f"Gefunden: {total_files} Audiodateien.")

            for idx, original_filepath in enumerate(audio_files):
                if not self.running: break

                temp_wav_file = None # Reset
                processing_filepath = original_filepath # Pfad zur Datei, die verarbeitet wird
                try:
                    current_file_num = idx + 1
                    filename = os.path.basename(original_filepath)
                    
                    # ---> CALLBACK-AUFRUF ERSETZT DURCH SIGNAL
                    self.progress_update.emit(current_file_num, total_files, f"Verarbeite {filename} ({current_file_num}/{total_files})")
                    # Kurze Pause, um der GUI Zeit zum Aktualisieren zu geben (optional, aber kann helfen)
                    QThread.msleep(10) 
                    # <--- Ende ÄNDERUNG

                    # === Konvertiere zu WAV mit subprocess ===
                    if not original_filepath.lower().endswith('.wav'):
                        logger.info(f"Konvertiere {original_filepath} zu WAV mit ffmpeg...")
                        temp_wav_file = os.path.join(
                            tempfile.gettempdir(), # Temporäres Verzeichnis verwenden
                            f"jarvis_temp_{uuid.uuid4()}.wav"
                        )
                        
                        # ffmpeg Kommando
                        # -i: Input, -vn: Video deaktivieren, -acodec pcm_s16le: WAV Codec,
                        # -ar 16000: Samplerate, -ac 1: Mono, -y: Überschreiben
                        command = [
                            ffmpeg_path,
                            "-i", original_filepath,
                            "-vn", "-acodec", "pcm_s16le",
                            "-ar", str(self.sample_rate), "-ac", "1",
                            "-y", # Überschreibe Zieldatei, falls vorhanden
                            temp_wav_file
                        ]
                        
                        logger.debug(f"Führe FFmpeg Kommando aus: {' '.join(command)}")
                        logger.info(f"Starte subprocess.run für ffmpeg für Datei: {original_filepath}")
                        startupinfo = None
                        if os.name == 'nt': # Nur für Windows
                            startupinfo = subprocess.STARTUPINFO()
                            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                            startupinfo.wShowWindow = subprocess.SW_HIDE
                            # CREATE_NO_WINDOW Flag, um Konsolenfenster zu verhindern
                            creationflags = subprocess.CREATE_NO_WINDOW 
                        else:
                             creationflags = 0
                        
                        process = subprocess.run(
                            command, 
                            capture_output=True, # stdout/stderr abfangen
                            text=True, 
                            check=False, # Fehler manuell prüfen
                            startupinfo=startupinfo,
                            creationflags=creationflags
                        )
                        
                        logger.info(f"subprocess.run für ffmpeg beendet. Return Code: {process.returncode}")
                        
                        if process.returncode != 0:
                            logger.error(f"FFmpeg Konvertierung fehlgeschlagen für {original_filepath}. Return Code: {process.returncode}")
                            logger.error(f"FFmpeg stderr: {process.stderr}")
                            # Temporäre Datei versuchen zu löschen, falls erstellt
                            if os.path.exists(temp_wav_file):
                                try: os.remove(temp_wav_file)
                                except Exception as del_e: logger.warning(f"Konnte fehlerhafte temp WAV nicht löschen: {del_e}")
                            continue # Nächste Datei
                        else:
                            logger.info(f"Konvertierung nach {temp_wav_file} erfolgreich.")
                            processing_filepath = temp_wav_file # Verarbeite die neue WAV
                    
                    # === Ende Konvertierung ===

                    # Verarbeite die WAV-Datei (Original oder temporär konvertiert)
                    self.process_audio_file(processing_filepath)
                    
                except Exception as e:
                    logger.error(f"Fehler bei der Verarbeitung der Datei {original_filepath}: {e}", exc_info=True)
                    continue 
                finally:
                    # Aufräumen der temporären WAV-Datei (falls erstellt)
                    if temp_wav_file and os.path.exists(temp_wav_file):
                        try:
                            os.remove(temp_wav_file)
                            logger.info(f"Temporäre Konvertierungsdatei {temp_wav_file} gelöscht.")
                        except Exception as e:
                            logger.error(f"Fehler beim Löschen der temporären Konvertierungsdatei {temp_wav_file}: {e}")
            
            if self.running: self.finished.emit()
            
        except Exception as e:
            logger.error(f"Allgemeiner Fehler in der Audiobuch-Verarbeitung: {e}", exc_info=True)
            self.error.emit(f"Allgemeiner Fehler: {str(e)}")
            self.finished.emit() 

    def process_audio_file(self, filepath):
        """Verarbeitet eine einzelne WAV-Audiodatei: Lädt, chunkt, transkribiert und speichert."""
        logger.info(f"Beginne Verarbeitung von: {filepath}")
        original_filename = os.path.basename(filepath) # Für Metadaten

        try:
            # 1. Lade Audiodatei mit librosa
            # Verwende sr=None, um die ursprüngliche Sample-Rate zu erhalten, resample später falls nötig
            logger.info(f"Starte librosa.load für Datei: {filepath}")
            audio, sr = librosa.load(filepath, sr=None, mono=True) # Lade als Mono
            logger.info(f"librosa.load abgeschlossen. SampleRate={sr}, Samples={len(audio)}")
            logger.debug(f"Audiodatei geladen: Länge={len(audio)} Samples, SampleRate={sr} Hz")

            # Resample zu 16kHz falls notwendig (Whisper erwartet 16kHz)
            target_sr = 16000
            if sr != target_sr:
                logger.info(f"Resample von {sr}Hz zu {target_sr}Hz...")
                audio = librosa.resample(audio, orig_sr=sr, target_sr=target_sr)
                sr = target_sr # Update Sample Rate
                logger.info("Resampling abgeschlossen.")

            # Berechne Chunk-Größe in Samples
            chunk_length_samples = self.chunk_size_seconds * sr
            num_chunks = math.ceil(len(audio) / chunk_length_samples)
            logger.info(f"Datei wird in {num_chunks} Chunks von ca. {self.chunk_size_seconds}s aufgeteilt.")

            # 2. Iteriere durch Chunks
            for i in range(num_chunks):
                if not self.running: # Prüfe Abbruchbedingung
                    logger.info("Audiobuch-Verarbeitung (in process_audio_file) durch Benutzer abgebrochen.")
                    break 

                start_sample = i * chunk_length_samples
                end_sample = start_sample + chunk_length_samples
                audio_chunk = audio[start_sample:end_sample]
                
                chunk_start_time_sec = start_sample / sr
                chunk_end_time_sec = end_sample / sr

                # ---> DEBUG-Log auskommentieren
                # logger.debug(f"Verarbeite Chunk {i+1}/{num_chunks} (Samples {start_sample}-{end_sample}, Zeit {chunk_start_time_sec:.2f}s-{chunk_end_time_sec:.2f}s)")
                # <--- Ende Änderung

                # --- Workaround: Chunk temporär speichern für Whisper ---
                # Erstelle eine temporäre WAV-Datei für den Chunk
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_chunk_file:
                    temp_chunk_path = temp_chunk_file.name
                    # Schreibe den Chunk in die temporäre Datei
                    sf.write(temp_chunk_path, audio_chunk, sr) 
                    # ---> DEBUG-Log auskommentieren
                    # logger.debug(f"Chunk temporär gespeichert unter: {temp_chunk_path}")
                    # <--- Ende Änderung

                # 3. Transkribiere den Chunk
                try:
                    # Stelle sicher, dass whisper_recognizer initialisiert ist
                    if not self.whisper_recognizer:
                         logger.error("Whisper Recognizer ist nicht initialisiert!")
                         # Optional: Hier abbrechen oder Fehler werfen
                         os.remove(temp_chunk_path) # Temporäre Datei trotzdem löschen
                         continue # Nächsten Chunk versuchen

                    transcript = self.whisper_recognizer.transcribe_wav(temp_chunk_path)
                    
                    # Lösche die temporäre Chunk-Datei direkt nach der Transkription
                    try:
                        os.remove(temp_chunk_path)
                        # ---> DEBUG-Log auskommentieren
                        # logger.debug(f"Temporäre Chunk-Datei {temp_chunk_path} gelöscht.")
                        # <--- Ende Änderung
                    except Exception as del_e:
                         logger.warning(f"Konnte temporäre Chunk-Datei {temp_chunk_path} nicht löschen: {del_e}")

                    if transcript and transcript.strip():
                        logger.info(f"Chunk {i+1} transkribiert: '{transcript[:80]}...'")
                        
                        # 4. Bereite Metadaten vor und speichere im LearningManager
                        doc_id = f"audiobook_{original_filename}_chunk_{i+1}"
                        metadata = {
                            "entry_type": "audiobook_chunk",
                            "source_file": original_filename,
                            "chunk_index": i + 1,
                            "total_chunks": num_chunks,
                            "start_time_seconds": round(chunk_start_time_sec, 2),
                            "end_time_seconds": round(chunk_end_time_sec, 2),
                            "timestamp": datetime.now().isoformat()
                        }
                        
                        # Stelle sicher, dass learning_manager initialisiert ist
                        if not self.learning_manager:
                             logger.error("Learning Manager ist nicht initialisiert!")
                             # Optional: Hier abbrechen
                             continue

                        self.learning_manager.add_entry(
                            doc_id=doc_id,
                            content=transcript.strip(),
                            metadata=metadata
                        )
                        # Kurze Pause, um UI nicht komplett zu blockieren
                        time.sleep(0.05) 

                    else:
                        logger.info(f"Chunk {i+1}: Keine Sprache erkannt oder leerer Transcript.")

                except Exception as transcribe_e:
                    logger.error(f"Fehler beim Transkribieren von Chunk {i+1} aus {filepath}: {transcribe_e}", exc_info=True)
                    # Versuche trotzdem, die temporäre Datei zu löschen, falls sie noch existiert
                    if 'temp_chunk_path' in locals() and os.path.exists(temp_chunk_path):
                         try:
                             os.remove(temp_chunk_path)
                             # ---> DEBUG-Log auskommentieren
                             # logger.debug(f"Temporäre Chunk-Datei {temp_chunk_path} nach Fehler gelöscht.")
                             # <--- Ende Änderung
                         except Exception as del_e:
                              logger.warning(f"Konnte temporäre Chunk-Datei {temp_chunk_path} nach Fehler nicht löschen: {del_e}")
                    continue # Mit nächstem Chunk fortfahren
                # --- Ende Workaround ---

            logger.info(f"Verarbeitung von {filepath} abgeschlossen.")

        except librosa.LibrosaError as load_error:
             logger.error(f"Librosa Fehler beim Laden von {filepath}: {load_error}", exc_info=True)
             # Hier könnte man this.error signalisieren
        except Exception as e:
            logger.error(f"Allgemeiner Fehler bei der Verarbeitung der Datei {filepath}: {e}", exc_info=True)
            # Hier könnte man this.error signalisieren
        
    def stop(self):
        """Signalisiert dem Thread, die Verarbeitung zu stoppen."""
        logger.info("Stopp-Signal für AudioProcessingThread empfangen.")
        self.running = False