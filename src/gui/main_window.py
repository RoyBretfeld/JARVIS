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
from ..audio.audio_thread import AudioProcessThread, AudioRecordingThread
from .prompt_editor import PromptEditor
from ..audio.audio_processor import AudioProcessor
from .loading_screen import LoadingScreen
from ..audio.base_tts_manager import BaseTTSManager
from ..speech.whisper_recognition import WhisperRecognizer
from .widgets.status_widget import StatusWidget
from .audio_settings_widget import AudioSettingsWidget
from ..tasks.task_manager import TaskManager
import requests
import subprocess
import tempfile
import getpass
from bs4 import BeautifulSoup
from scrapy.crawler import CrawlerProcess
from scrapy.settings import Settings
from scrapy import signals
from itemadapter import ItemAdapter
import crochet

# Logger für dieses Modul
logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    # Signal für Feedback an den Benutzer (z.B. bei erfolgreichem scheduled run)
    scheduled_crawl_feedback = pyqtSignal(str)
    # ---> Neue Signale für AllSpidersRunThread
    all_spiders_starting = pyqtSignal(str) # spider_name
    all_spiders_finished_one = pyqtSignal(str, int) # spider_name, exit_code
    all_spiders_sequence_finished = pyqtSignal()
    all_spiders_error = pyqtSignal(str) # error_message
    # <--- Ende Neue Signale

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
        
        # ---> Hole Benutzernamen (priorisiert aus Config)
        try:
            # Versuche, den Namen aus der Config zu lesen
            configured_name = self.config_manager.get('user_profile', 'display_name')
            if configured_name and configured_name.strip():
                self.username = configured_name.strip()
                logger.info(f"Benutzername aus config.json geladen: {self.username}")
            else:
                # Fallback: Windows-Benutzername
                self.username = getpass.getuser()
                logger.info(f"Kein display_name in config.json, verwende Windows-Benutzername: {self.username}")
        except Exception as e:
             # Fallback bei jeglichem Fehler
             logger.warning(f"Konnte Benutzernamen nicht ermitteln (weder Config noch System): {e}. Verwende 'Benutzer'.")
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
        
        # In __init__ hinzufügen:
        self.crawler_thread = None
        self.all_spiders_thread = None # Variable für den neuen Thread
        
        # --- Scheduler für Crawls ---
        self.scheduled_spiders = [
            "heise_spider",
            "golem_spider",
            "t3n_spider",
            "ct_spider",
            "computerbase_spider",
            "chip_spider"
        ]
        self.current_scheduled_spider_index = -1 # -1 bedeutet: keine aktive Sequenz
        self.is_scheduled_crawl_active = False   # Flag, ob eine Sequenz gerade läuft
        self.crawl_scheduler_timer = QTimer(self)
        self.crawl_scheduler_timer.timeout.connect(self.start_scheduled_crawl_sequence)
        # Starte den Timer, alle 1 Stunde (3600000 ms)
        schedule_interval_ms = 3600 * 1000
        self.crawl_scheduler_timer.start(schedule_interval_ms)
        logger.info(f"Crawl-Scheduler initialisiert. Intervall: {schedule_interval_ms / 1000 / 60} Minuten.")
        # --- Ende Scheduler ---
        
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
            # self.setMinimumSize(1200, 800) # Alte Größe
            self.resize(1800, 1000) # Neue Größe
            
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

            # ---> NEUE Gruppe: Autonomes Lernen Status <---
            learning_status_group = QGroupBox("Autonomes Lernen Status")
            learning_status_layout = QVBoxLayout()

            # Hauptstatus (Idle, Running, Finished, Error)
            self.crawler_main_status_label = QLabel("Status: Idle") 
            # Detail-Status (z.B. aktuelle URL, Anzahl gefundener Items)
            self.crawler_activity_label = QLabel("Aktivität: -") 
            self.crawler_activity_label.setWordWrap(True) # Zeilenumbruch erlauben
            
            learning_status_layout.addWidget(self.crawler_main_status_label)
            learning_status_layout.addWidget(self.crawler_activity_label)

            # Buttons zum Starten der Crawls hinzufügen
            # === Buttons erstellen (bleibt gleich) ===
            self.start_heise_crawl_btn = QPushButton("Heise Crawl starten")
            self.start_golem_crawl_btn = QPushButton("Golem Crawl starten")
            self.start_t3n_crawl_btn = QPushButton("t3n Crawl starten")
            self.start_ct_crawl_btn = QPushButton("c't Crawl starten")
            self.start_cb_crawl_btn = QPushButton("CB Crawl starten") # CB = ComputerBase
            self.start_chip_crawl_btn = QPushButton("Chip Crawl starten")

            # === Buttons direkt zum vertikalen Layout hinzufügen ===
            learning_status_layout.addWidget(self.start_heise_crawl_btn)
            learning_status_layout.addWidget(self.start_golem_crawl_btn)
            learning_status_layout.addWidget(self.start_t3n_crawl_btn)
            learning_status_layout.addWidget(self.start_ct_crawl_btn)
            learning_status_layout.addWidget(self.start_cb_crawl_btn)
            learning_status_layout.addWidget(self.start_chip_crawl_btn)
            # === Ende direkte Buttons ===

            # ---> NEUER Button hinzufügen
            self.start_all_spiders_btn = QPushButton("Alle Spider starten")
            learning_status_layout.addWidget(self.start_all_spiders_btn)
            # <--- ENDE NEUER Button

            learning_status_layout.addStretch(1) # Fügt Platz am Ende hinzu

            learning_status_group.setLayout(learning_status_layout)
            left_layout.addWidget(learning_status_group)
            # ---> ENDE NEUE Gruppe <---

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
            # self.llm_combo.addItem("Ollama") # Alt: Statisch
            llm_layout.addWidget(llm_label)
            llm_layout.addWidget(self.llm_combo)

            # Modell Auswahl
            model_label = QLabel("Modell:")
            self.model_combo = QComboBox()
            # self.model_combo.addItem("llama3:8b") # Alt: Statisch
            self.prompt_edit_btn = QPushButton("Prompt bearbeiten")
            llm_layout.addWidget(model_label)
            llm_layout.addWidget(self.model_combo)
            llm_layout.addWidget(self.prompt_edit_btn)
            status_layout.addLayout(llm_layout)

            # --- Dynamische Befüllung der LLM/Modell-Combos ---
            self.populate_llm_combos()

            # --- Mikrofon Auswahl wird aus Status entfernt ---
            # mic_layout = QHBoxLayout()
            # mic_label = QLabel("Mikrofon:")
            # self.mic_status = QLabel("Mikrofon (Moman EMP Microphone)")
            # self.mic_status.setStyleSheet("color: #00ff00")  # Grün für aktives Mikrofon
            # self.mic_select_btn = QPushButton("Mikrofon auswählen")
            # self.mic_select_btn.setVisible(True) # Explizit sichtbar machen
            # logger.debug(f"[UI Debug] mic_select_btn erstellt. Sichtbar: {self.mic_select_btn.isVisible()}, Größe: {self.mic_select_btn.sizeHint()}")
            # mic_layout.addWidget(mic_label)
            # mic_layout.addWidget(self.mic_status)
            # mic_layout.addWidget(self.mic_select_btn)
            # mic_layout.addStretch() # Füge Stretch hinzu
            # status_layout.addLayout(mic_layout) # <- Wird entfernt
            
            status_group.setLayout(status_layout)
            middle_layout.addWidget(status_group) # Status Gruppe zuerst hinzufügen

            # ---> NEUE Gruppe: Audio-Einstellungen <---
            audio_group = QGroupBox("Audio-Einstellungen")
            audio_layout = QVBoxLayout() # Vertikales Layout für diese Gruppe

            # Mikrofon Auswahl (Hier neu erstellen und hinzufügen)
            mic_layout = QHBoxLayout()
            mic_label = QLabel("Mikrofon:")
            self.mic_status = QLabel("Mikrofon (Moman EMP Microphone)") # Annahme: Init-Wert okay?
            self.mic_status.setStyleSheet("color: #00ff00")
            self.mic_select_btn = QPushButton("Mikrofon auswählen")
            self.mic_select_btn.setVisible(True)
            # Optional: Debug Logging hier wiederholen, falls gewünscht
            mic_layout.addWidget(mic_label)
            mic_layout.addWidget(self.mic_status)
            mic_layout.addWidget(self.mic_select_btn)
            mic_layout.addStretch()
            
            audio_layout.addLayout(mic_layout) # Füge mic_layout zur neuen Gruppe hinzu
            audio_group.setLayout(audio_layout)
            middle_layout.addWidget(audio_group) # Füge neue Gruppe zum Hauptlayout hinzu
            # ---> ENDE NEUE Gruppe <---

            # ---> WIEDER EINGEFÜGT: Wissensbasis Gruppe <---
            knowledge_group = QGroupBox("Wissensbasis Lernen")
            knowledge_layout = QVBoxLayout()
            
            # Import Buttons
            self.import_files_btn = QPushButton("📄 Dateien importieren")
            self.import_audio_btn = QPushButton("🔊 Audiobücher lernen (Ordner)")
            knowledge_layout.addWidget(self.import_files_btn)
            knowledge_layout.addWidget(self.import_audio_btn)
            
            # Kompakter Datenbank-Status
            db_status_layout = QHBoxLayout() # Renamed layout variable
            self.db_status_label = QLabel("📚 Einträge:")
            self.db_status_count = QLabel("0")  # Wird durch update_db_status aktualisiert
            self.db_status_label.setStyleSheet("color: #00ff00")  # Grün für aktiv
            db_status_layout.addWidget(self.db_status_label)
            db_status_layout.addWidget(self.db_status_count)
            db_status_layout.addStretch()
            knowledge_layout.addLayout(db_status_layout)
            
            knowledge_group.setLayout(knowledge_layout)
            middle_layout.addWidget(knowledge_group)
            # ---> ENDE WIEDER EINGEFÜGT <---

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
            self.record_btn = QPushButton("Aufnahme starten") # Definition hier hinzugefügt
            self.stop_tts_btn = QPushButton("Stop ⏹️") # NEUER Stop-Button
            feedback_layout.addWidget(feedback_label)
            feedback_layout.addWidget(self.thumbs_up_btn)
            feedback_layout.addWidget(self.thumbs_down_btn)
            feedback_layout.addWidget(self.record_btn)
            feedback_layout.addWidget(self.stop_tts_btn) # Stop-Button hinzufügen
            feedback_layout.addStretch()
            chat_layout.addLayout(feedback_layout)
            
            # Chat Eingabe
            input_layout = QHBoxLayout()
            self.chat_input = QLineEdit()
            self.chat_input.setPlaceholderText("Nachricht eingeben...")
            # Setze die Höhe für ca. 3 Zeilen (Annahme: ca. 25px pro Zeile)
            self.chat_input.setFixedHeight(75)
            self.send_btn = QPushButton("Senden")
            input_layout.addWidget(self.chat_input)
            input_layout.addWidget(self.send_btn)
            chat_layout.addLayout(input_layout)
            
            # --- NEU: Layout für Aktions-Buttons UNTER dem Input ---
            action_button_layout = QHBoxLayout()
            # Erstelle die Buttons (falls sie oben komplett entfernt wurden)
            self.create_image_btn = QPushButton("🖼️ Bild")
            self.create_video_btn = QPushButton("🎬 Video")
            self.voice_agent_btn = QPushButton("🗣️ Voice Agent")
            self.create_image_btn.setToolTip("Neues Bild generieren")
            self.create_video_btn.setToolTip("Neues Video generieren")
            self.voice_agent_btn.setToolTip("Voice Agent starten/konfigurieren")
            # Füge Buttons zum neuen Layout hinzu
            action_button_layout.addWidget(self.create_image_btn)
            action_button_layout.addWidget(self.create_video_btn)
            action_button_layout.addWidget(self.voice_agent_btn)
            action_button_layout.addStretch() # Füge Platz rechts hinzu
            chat_layout.addLayout(action_button_layout) # Füge das neue Layout zum Chat-Layout hinzu
            # --- Ende Aktions-Buttons Layout ---
            
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
            self.web_result = QTextEdit()
            self.web_result.setReadOnly(True)
            self.web_result.setPlaceholderText("Webseiten-Inhalt wird hier angezeigt...")
            
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

            # --- NEU: Aktions-Buttons zur Statusleiste hinzufügen (links) ---
            # self.create_image_btn = QPushButton("🖼️ Bild")
            # self.create_video_btn = QPushButton("🎬 Video")
            # self.voice_agent_btn = QPushButton("🗣️ Voice Agent")
            # self.create_image_btn.setToolTip("Neues Bild generieren")
            # self.create_video_btn.setToolTip("Neues Video generieren")
            # self.voice_agent_btn.setToolTip("Voice Agent starten/konfigurieren")
            # self.statusBar.addWidget(self.create_image_btn)
            # self.statusBar.addWidget(self.create_video_btn)
            # self.statusBar.addWidget(self.voice_agent_btn)
            # --- Ende Aktions-Buttons ---

            # System-Auslastung in der Statusleiste (rechts)
            self.system_stats = QLabel("CPU: --% | RAM: --% | GPU: --% | Modell: -- | DB: -- MB") # Initiale Werte
            self.statusBar.addPermanentWidget(self.system_stats)

            # Signal-Verbindungen
            self.setup_connections()
            
            logger.info("UI erfolgreich initialisiert")
            
        except Exception as e:
            logger.error(f"Fehler beim Initialisieren der UI: {e}", exc_info=True)
            raise

    def populate_llm_combos(self):
        """Befüllt die LLM- und Modell-Dropdowns dynamisch."""
        try:
            # Lösche alte Einträge
            self.llm_combo.clear()
            self.model_combo.clear()

            if self.llm_manager:
                # Befülle LLM Provider Combo
                available_providers = self.llm_manager.get_available_providers()
                current_provider_name = self.llm_manager.get_provider()
                
                if available_providers:
                    self.llm_combo.addItems(available_providers)
                    if current_provider_name in available_providers:
                         self.llm_combo.setCurrentText(current_provider_name)
                    else:
                         logger.warning(f"Aktiver Provider '{current_provider_name}' nicht in der Liste der verfügbaren Provider?")
                         if available_providers: # Setze den ersten als Fallback
                             self.llm_combo.setCurrentIndex(0)
                else:
                     self.llm_combo.addItem("Keine Provider")
                     self.llm_combo.setEnabled(False)
                
                # Befülle Modell Combo basierend auf aktivem Provider
                available_models = self.llm_manager.get_available_models()
                current_model_name = self.llm_manager.get_current_model()
                
                if available_models:
                    self.model_combo.addItems(available_models)
                    if current_model_name in available_models:
                        self.model_combo.setCurrentText(current_model_name)
                    else:
                        logger.warning(f"Aktives Modell '{current_model_name}' nicht in der Liste der verfügbaren Modelle?")
                        if available_models: # Setze das erste als Fallback
                             self.model_combo.setCurrentIndex(0)
                else:
                     self.model_combo.addItem("Keine Modelle")
                     self.model_combo.setEnabled(False)
            else:
                 # Fallback, wenn LLM Manager nicht initialisiert ist
                 self.llm_combo.addItem("Fehler")
                 self.model_combo.addItem("Fehler")
                 self.llm_combo.setEnabled(False)
                 self.model_combo.setEnabled(False)
                 logger.error("LLMManager nicht verfügbar zum Befüllen der Comboboxen.")
                 
        except Exception as e:
            logger.error(f"Fehler beim Befüllen der LLM/Modell-Comboboxen: {e}", exc_info=True)
            # Setze Fehlerstatus in Comboboxen
            self.llm_combo.clear()
            self.model_combo.clear()
            self.llm_combo.addItem("Fehler")
            self.model_combo.addItem("Fehler")
            self.llm_combo.setEnabled(False)
            self.model_combo.setEnabled(False)

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
            
            # Autonomes Lernen
            self.start_heise_crawl_btn.clicked.connect(self.trigger_heise_crawl)
            self.start_golem_crawl_btn.clicked.connect(self.trigger_golem_crawl)
            # === NEUE Verbindungen ===
            self.start_t3n_crawl_btn.clicked.connect(self.trigger_t3n_crawl)
            self.start_ct_crawl_btn.clicked.connect(self.trigger_ct_crawl)
            self.start_cb_crawl_btn.clicked.connect(self.trigger_cb_crawl)
            self.start_chip_crawl_btn.clicked.connect(self.trigger_chip_crawl)
            # === ENDE NEUE Verbindungen ===

            # ---> Verbindung für neuen Button
            self.start_all_spiders_btn.clicked.connect(self.trigger_all_spiders_sequentially)
            # <--- ENDE Verbindung

            # Verbinde das neue Feedback-Signal
            self.scheduled_crawl_feedback.connect(self.show_scheduled_crawl_feedback)
            
            # Verbinde die neuen Button-Signale
            self.create_image_btn.clicked.connect(self.on_create_image_clicked)
            self.create_video_btn.clicked.connect(self.on_create_video_clicked)
            self.voice_agent_btn.clicked.connect(self.on_voice_agent_clicked) # Geändert
            
            # NEU: Verbindung für Stop TTS Button
            self.stop_tts_btn.clicked.connect(self.on_stop_tts_clicked)
            
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
        """Startet den Thread zum Abrufen einer URL."""
        url = self.url_input.text().strip()
        if not url:
            self.web_status.setText("Bitte URL eingeben.")
            return
            
        # Füge http:// hinzu, falls es fehlt (einfache Prüfung)
        if not url.startswith('http://') and not url.startswith('https://'):
            url = 'http://' + url
            self.url_input.setText(url) # Aktualisiere das Feld
            
        self.web_status.setText(f"Suche {url}...")
        self.web_result.clear() # Altes Ergebnis löschen
        QApplication.processEvents() # UI kurz aktualisieren
        
        # Prüfen ob bereits ein Thread läuft
        if hasattr(self, 'url_fetch_thread') and self.url_fetch_thread and self.url_fetch_thread.isRunning():
             logger.warning("Ein URL-Abruf läuft bereits.")
             self.web_status.setText("Ein anderer Abruf läuft bereits...")
             return
             
        # ---> Starte den Thread
        self.url_fetch_thread = UrlFetchThread(url, parent=self)
        self.url_fetch_thread.content_ready.connect(self.on_url_content_ready)
        self.url_fetch_thread.error_occurred.connect(self.on_url_fetch_error)
        # Optional: Thread automatisch löschen, wenn er fertig ist
        self.url_fetch_thread.finished.connect(self.url_fetch_thread.deleteLater) 
        self.url_fetch_thread.start()
        # <--- Ende Thread-Start

    def save_web_result(self):
        """Startet den Thread zum Speichern des Webinhalts aus self.web_result."""
        # ---> Code zum direkten Speichern ENTFERNT <--- 
        try:
            html_content = self.web_result.toPlainText()
            current_url = self.url_input.text().strip() # Hole die URL für Metadaten

            if not html_content or html_content.startswith("Fehler:") or html_content.startswith("Unerwarteter Fehler:"):
                self.web_status.setText("Kein gültiger Inhalt zum Speichern.")
                logger.warning("Versuch, ungültigen Webinhalt zu speichern.")
                return

            # Prüfen ob bereits ein Speicher-Thread läuft
            if hasattr(self, 'web_save_thread') and self.web_save_thread and self.web_save_thread.isRunning():
                logger.warning("Ein Web-Speicherprozess läuft bereits.")
                self.web_status.setText("Ein anderer Speicherprozess läuft bereits...")
                return
                
            self.web_status.setText("Starte Speichervorgang...")
            QApplication.processEvents() # UI kurz aktualisieren

            # ---> Starte den Speicher-Thread
            self.web_save_thread = WebSaveThread(
                html_content=html_content,
                source_url=current_url,
                learning_manager=self.learning_manager,
                parent=self
            )
            self.web_save_thread.save_success.connect(self.on_web_save_success)
            self.web_save_thread.save_error.connect(self.on_web_save_error)
            self.web_save_thread.finished.connect(self.web_save_thread.deleteLater)
            self.web_save_thread.start()
            # <--- Ende Thread-Start

        except Exception as e:
            logger.error(f"Fehler beim Starten des Web-Speicher-Threads: {e}", exc_info=True)
            self.web_status.setText("Fehler beim Starten des Speicherns.")

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
                
            # Korrigierter Aufruf
            # self.statusBar().showMessage("Starte Wissensimport...")
            self.statusBar.showMessage("Starte Wissensimport...")
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
                # Korrigierter Aufruf
                # self.statusBar().showMessage("Konversation exportiert")
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
        """Initialisiert das TTS System."""
        # Stelle sicher, dass die Konfiguration existiert
        # ... (Fehlerbehandlung für Config fehlt hier, aber ok für jetzt)

        use_tts = self.config_manager.get('tts.use_tts', True) # Lese TTS-Flag

        if use_tts:
            logger.info("Initialisiere TTS Manager...")
            # TTS Manager erstellen
            # Verwende die korrekte Config-Instanz
            # self.tts_manager = create_tts_manager(self.config_manager) # Alt
            self.tts_manager = BaseTTSManager.create(self.config_manager) # Neu

            if self.tts_manager:
                if self.tts_manager.check_readiness():
                    # Hauptsignal verbinden
                    if hasattr(self.tts_manager, 'tts_finished'):
                        self.tts_manager.tts_finished.connect(self.on_tts_finished)
                    else:
                        logger.warning(f"TTS Manager hat kein 'tts_finished' Signal.")
                    
                    # Optionale Signale verbinden
                    if hasattr(self.tts_manager, 'tts_error'):
                         self.tts_manager.tts_error.connect(self.on_tts_error)
                    if hasattr(self.tts_manager, 'tts_progress'):
                         self.tts_manager.tts_progress.connect(self.on_tts_progress)
                         
                    logger.info(f"TTS-Manager ({self.tts_manager.__class__.__name__}): Signale verbunden.")
                else:
                    logger.warning("TTS Manager ist nicht bereit. Überprüfen Sie die Konfiguration.")
        else:
            logger.warning("TTS ist deaktiviert. Sprachausgabe wird übersprungen.")
            self.tts_manager = None

    def on_recording_started(self):
        """Handler für Aufnahmestart"""
        self.is_recording = True
        self.record_btn.setChecked(True)
        # Korrigierter Aufruf
        # self.statusBar().showMessage("Aufnahme läuft...")
        self.statusBar.showMessage("Aufnahme läuft...")
        
    def on_recording_stopped(self):
        """Handler für Aufnahmestopp"""
        self.is_recording = False
        self.record_btn.setChecked(False)
        # Korrigierter Aufruf
        # self.statusBar().showMessage("Aufnahme gestoppt")
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
                device_name = selector.get_selected_device_name() # Annahme: Methode existiert oder wird hinzugefügt
                
                if device_index is not None and device_name is not None:
                    logger.info(f"Mikrofon ausgewählt: Index={device_index}, Name='{device_name}'")
                    # Aktualisiere das Status-Label
                    self.mic_status.setText(f"Mikrofon: {device_name}")
                    self.mic_status.setStyleSheet("color: #00ff00") # Grün setzen
                    
                    # Aktualisiere die Konfiguration
                    try:
                        self.config_manager.set_microphone(device_index, device_name)
                        # Optional: Neustart des Audio-Threads erzwingen, falls er läuft?
                        # if self.is_recording:
                        #     self.stop_recording()
                        #     self.toggle_recording() # Oder eine spezifischere Update-Methode
                    except Exception as config_e:
                        logger.error(f"Fehler beim Speichern der Mikrofon-Konfiguration: {config_e}")
                        QMessageBox.warning(self, "Fehler", "Mikrofon-Einstellung konnte nicht gespeichert werden.")
                else:
                     logger.warning("Kein gültiges Mikrofon im Dialog ausgewählt.")
                     self.mic_status.setStyleSheet("color: #ffa500") # Orange für unklaren Status

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
                     # Fallback: Wir holen den NEU formatierten System-Prompt direkt nach dem Speichern,
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
            self.audio_processing_thread = AudiobookImportThread(
                folder_path=folder,
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

    # ---> Slots für URL Fetch Thread
    @pyqtSlot(str)
    def on_url_content_ready(self, content):
        """Wird aufgerufen, wenn der UrlFetchThread den Inhalt erfolgreich abgerufen hat."""
        self.web_result.setText(content)
        self.web_status.setText(f"Inhalt geladen.")
        self.url_fetch_thread = None # Thread-Referenz löschen
        
        # Optional: Automatisch speichern, wenn Checkbox aktiviert ist
        if self.auto_save.isChecked():
             self.save_web_result() # Rufe die Speicherfunktion auf
             
    @pyqtSlot(str)
    def on_url_fetch_error(self, error_message):
        """Wird aufgerufen, wenn beim URL-Abruf ein Fehler aufgetreten ist."""
        self.web_result.setText(error_message)
        self.web_status.setText("Fehler beim Laden.")
        self.url_fetch_thread = None # Thread-Referenz löschen
    # <--- Ende Slots

    # ---> Slots für Web Save Thread
    @pyqtSlot(str)
    def on_web_save_success(self, url):
        """Wird aufgerufen, wenn der WebSaveThread erfolgreich gespeichert hat."""
        logger.info(f"Web-Inhalt von {url} erfolgreich hinzugefügt (via Thread).")
        self.web_status.setText("Inhalt erfolgreich gespeichert.")
        self.update_db_status() # DB-Status aktualisieren
        self.web_save_thread = None # Thread-Referenz löschen

    @pyqtSlot(str)
    def on_web_save_error(self, error_message):
        """Wird aufgerufen, wenn beim Speichern des Webinhalts ein Fehler aufgetreten ist."""
        logger.error(f"Fehler beim Speichern des Web-Inhalts (via Thread): {error_message}")
        self.web_status.setText(f"Fehler: {error_message}")
        self.web_save_thread = None # Thread-Referenz löschen
    # <--- Ende Slots

    # === Methoden für Scrapy Crawler ===

    def _start_crawl(self, spider_name):
        """Interne Methode zum Starten eines Crawl-Threads."""
        if self.crawler_thread and self.crawler_thread.isRunning():
            QMessageBox.warning(self, "Crawl läuft bereits", "Es läuft bereits ein Crawl-Prozess. Bitte warten Sie.")
            return

        # Status basierend darauf setzen, ob es ein geplanter oder manueller Lauf ist
        if self.is_scheduled_crawl_active:
            status_text = f"Scheduler: Starte {spider_name}..."
            # Buttons sind bereits deaktiviert durch run_next_scheduled_spider
        else:
            status_text = f"Starte {spider_name} Crawl..."
            self.set_crawl_buttons_enabled(False) # Manuelle Buttons deaktivieren
            
        # Korrigierter Aufruf: Zeige temporäre Nachricht in der Statusleiste
        self.statusBar.showMessage(status_text, 5000) # Korrekt: ohne () nach statusBar
        self.crawler_main_status_label.setText("Status: Running...")
        self.crawler_activity_label.setText(f"Spider: {spider_name}")

        logger.info(f"Starte {spider_name} Crawl-Thread...")
        self.crawler_thread = ScrapyCrawlerThread(spider_name, self.learning_manager, self.config)

        # Verbinde die Signale des Threads mit den Slots der MainWindow
        self.crawler_thread.crawl_started.connect(self.on_crawl_started)
        self.crawler_thread.status_update.connect(self.on_crawl_status_update)
        self.crawler_thread.item_processed.connect(self.on_crawl_item_processed)
        # Wichtig: _crawl_finished ist jetzt der zentrale Punkt!
        self.crawler_thread.crawl_finished.connect(self._crawl_finished)
        self.crawler_thread.crawl_error.connect(self.on_crawl_error)
        # Signal hinzufügen, wenn der Thread tatsächlich beendet ist
        self.crawler_thread.finished.connect(self.on_thread_actually_finished)

        self.crawler_thread.start()

    # --- Trigger für manuelle Crawls ---
    def trigger_heise_crawl(self):
        """Startet den Heise-Crawl manuell."""
        if not self.is_scheduled_crawl_active: # Nur starten, wenn kein Scheduler läuft
            self._start_crawl("heise_spider")
        else:
            self.statusBar().showMessage("Geplanter Crawl aktiv, manueller Start nicht möglich.", 3000)

    def trigger_golem_crawl(self):
        """Startet den Golem-Crawl manuell."""
        if not self.is_scheduled_crawl_active:
            self._start_crawl("golem_spider")
        else:
            self.statusBar().showMessage("Geplanter Crawl aktiv, manueller Start nicht möglich.", 3000)

    # === NEUE Trigger-Methoden ===
    def trigger_t3n_crawl(self):
        """Startet den t3n-Crawl manuell."""
        if not self.is_scheduled_crawl_active:
            self._start_crawl("t3n_spider")
        else:
            self.statusBar().showMessage("Geplanter Crawl aktiv, manueller Start nicht möglich.", 3000)

    def trigger_ct_crawl(self):
        """Startet den c't-Crawl manuell."""
        if not self.is_scheduled_crawl_active:
            self._start_crawl("ct_spider")
        else:
            self.statusBar().showMessage("Geplanter Crawl aktiv, manueller Start nicht möglich.", 3000)

    def trigger_cb_crawl(self):
        """Startet den ComputerBase-Crawl manuell."""
        if not self.is_scheduled_crawl_active:
            self._start_crawl("computerbase_spider")
        else:
            self.statusBar().showMessage("Geplanter Crawl aktiv, manueller Start nicht möglich.", 3000)

    def trigger_chip_crawl(self):
        """Startet den Chip-Crawl manuell."""
        if not self.is_scheduled_crawl_active:
            self._start_crawl("chip_spider")
        else:
            self.statusBar().showMessage("Geplanter Crawl aktiv, manueller Start nicht möglich.", 3000)
    # === ENDE NEUE Trigger-Methoden ===

    def set_crawl_buttons_enabled(self, enabled):
        """Aktiviert oder deaktiviert die manuellen Crawl-Startbuttons."""
        self.start_heise_crawl_btn.setEnabled(enabled)
        self.start_golem_crawl_btn.setEnabled(enabled)
        self.start_t3n_crawl_btn.setEnabled(enabled)
        self.start_ct_crawl_btn.setEnabled(enabled)
        self.start_cb_crawl_btn.setEnabled(enabled)
        self.start_chip_crawl_btn.setEnabled(enabled)
        # ---> Neuen Button hinzufügen
        if hasattr(self, 'start_all_spiders_btn'): # Sicherstellen, dass der Button existiert
            self.start_all_spiders_btn.setEnabled(enabled)
        # <--- ENDE Neuer Button

    # --- Slots für Crawl-Thread-Signale ---
    @pyqtSlot()
    def on_crawl_started(self):
        """Slot, der aufgerufen wird, wenn der Scrapy-Prozess im Thread gestartet wurde."""
        logger.info("Crawl-Prozess gestartet (Signal empfangen).")
        # Status wurde bereits in _start_crawl gesetzt

    @pyqtSlot(str)
    def on_crawl_status_update(self, message):
        """Aktualisiert die Detail-Statusanzeige."""
        self.crawler_activity_label.setText(f"Aktivität: {message}")

    @pyqtSlot(str)
    def on_crawl_item_processed(self, url):
        """Aktualisiert die Anzeige, wenn ein Item verarbeitet wurde."""
        # Zeige nur die letzten paar Zeichen der URL, um Platz zu sparen
        display_url = url if len(url) < 50 else "..." + url[-47:]
        self.crawler_activity_label.setText(f"Gefunden: {display_url}")
        # Optional: Zähler für gefundene Items hinzufügen

    # ANGEPASST: Dieser Slot behandelt das Ende und triggert ggf. den nächsten geplanten Crawl
    @pyqtSlot(str, str)
    def _crawl_finished(self, spider_name, reason):
        """Slot, der aufgerufen wird, wenn ein Spider (im Thread) beendet wurde."""
        logger.info(f"Crawl für {spider_name} beendet. Grund: {reason}")
        final_status = f"Status: Finished ({spider_name})"
        self.crawler_main_status_label.setText(final_status)
        self.crawler_activity_label.setText(f"Grund: {reason}")

        # Prüfe, ob dies Teil einer aktiven, geplanten Sequenz war
        if self.is_scheduled_crawl_active and self.current_scheduled_spider_index != -1:
            expected_spider = self.scheduled_spiders[self.current_scheduled_spider_index]
            if spider_name == expected_spider:
                self.logger.info(f"Scheduler: {spider_name} erfolgreich beendet. Starte nächsten...")
                self.current_scheduled_spider_index += 1
                # Starte den nächsten Spider mit kurzer Verzögerung
                QTimer.singleShot(500, self.run_next_scheduled_spider) # 500ms Pause
            else:
                # Unerwarteter Spider beendet während der Sequenz - Sequenz abbrechen
                self.logger.warning(f"Scheduler: Unerwarteter Crawl ({spider_name}) beendet. Erwartet: {expected_spider}. Breche Sequenz ab.")
                self.is_scheduled_crawl_active = False
                self.current_scheduled_spider_index = -1
                self.set_crawl_buttons_enabled(True) # Buttons wieder freigeben
                # Korrigierter Aufruf
                # self.statusBar().showMessage("Scheduler: Crawl-Sequenz abgebrochen (Fehler).", 5000)
                self.statusBar.showMessage("Scheduler: Crawl-Sequenz abgebrochen (Unerwarteter Crawl).", 5000)
        else:
            # Ende eines manuellen Crawls oder die Sequenz war nicht aktiv/schon beendet
            logger.debug("Manueller Crawl beendet. Rufe set_crawl_buttons_enabled(True) auf...") # DEBUG LOGGING
            self.set_crawl_buttons_enabled(True)

    @pyqtSlot()
    def on_thread_actually_finished(self):
        """Slot der aufgerufen wird, wenn der QThread selbst beendet ist."""
        # Wird aufgerufen *nachdem* der Thread run() beendet hat.
        # Kann für Aufräumarbeiten genutzt werden, falls nötig.
        logger.debug("ScrapyCrawlerThread tatsächlich beendet.")
        # Hier keine Buttons aktivieren, das passiert in _crawl_finished oder on_crawl_error

    @pyqtSlot(str, str)
    def on_crawl_error(self, spider_name, error_message):
        """Slot, der bei einem Fehler im Crawl-Prozess aufgerufen wird."""
        logger.error(f"Fehler im Crawl-Prozess ({spider_name}): {error_message}")
        self.crawler_main_status_label.setText(f"Status: Error ({spider_name})")
        self.crawler_activity_label.setText(f"Fehler: {error_message[:100]}...") # Begrenze Fehlermeldung
        QMessageBox.critical(self, "Crawl Fehler", f"Fehler beim Crawlen mit {spider_name}:\n{error_message}")

        # Wenn ein Fehler während einer geplanten Sequenz auftritt -> Sequenz abbrechen
        if self.is_scheduled_crawl_active:
            self.logger.warning(f"Scheduler: Fehler bei {spider_name}. Breche Crawl-Sequenz ab.")
            self.is_scheduled_crawl_active = False
            self.current_scheduled_spider_index = -1
            # Korrigierter Aufruf
            # self.statusBar().showMessage("Scheduler: Crawl-Sequenz abgebrochen (Fehler).", 5000)
            self.statusBar.showMessage("Scheduler: Crawl-Sequenz abgebrochen (Fehler).", 5000)

        # Buttons immer wieder aktivieren bei Fehler
        self.set_crawl_buttons_enabled(True)
    # --- Ende Slots für Crawl-Thread-Signale ---

    # --- Scheduler-Methoden ---
    @pyqtSlot()
    def start_scheduled_crawl_sequence(self):
        """Wird vom Timer aufgerufen, um eine neue Crawl-Sequenz zu starten."""
        if self.is_scheduled_crawl_active:
            self.logger.info("Ein geplanter Crawl-Lauf ist bereits aktiv. Überspringe diesen Zyklus.")
            return
        
        # Prüfe, ob ein manueller Crawl läuft (optional, aber sinnvoll)
        if self.crawler_thread and self.crawler_thread.isRunning():
             self.logger.info("Ein manueller Crawl-Lauf ist aktiv. Überspringe geplanten Start.")
             return

        self.logger.info(f"Starte geplanter Crawl-Lauf für {len(self.scheduled_spiders)} Spider.")
        self.is_scheduled_crawl_active = True
        self.current_scheduled_spider_index = 0
        # Korrigierter Aufruf: Zeige temporäre Nachricht in der Statusleiste
        # self.statusBar().showMessage("Scheduler: Starte Crawl-Sequenz...", 5000) # 5 Sek anzeigen
        self.statusBar.showMessage("Scheduler: Starte Crawl-Sequenz...", 5000) # Korrekt: ohne () nach statusBar
        self.run_next_scheduled_spider() # Starte den ersten Spider

    def run_next_scheduled_spider(self):
        """Startet den nächsten Spider in der geplanten Sequenz."""
        if not self.is_scheduled_crawl_active or self.current_scheduled_spider_index >= len(self.scheduled_spiders):
            if self.is_scheduled_crawl_active: # Nur loggen/Feedback geben, wenn die Sequenz aktiv war
                 self.logger.info("Geplanter Crawl-Lauf erfolgreich beendet.")
                 self.scheduled_crawl_feedback.emit("Geplanter Crawl-Lauf für alle Spider beendet.")
            self.is_scheduled_crawl_active = False
            self.current_scheduled_spider_index = -1
            # Buttons wieder aktivieren, falls sie deaktiviert wurden
            self.set_crawl_buttons_enabled(True)
            return

        spider_name = self.scheduled_spiders[self.current_scheduled_spider_index]
        self.logger.info(f"Scheduler: Starte Crawl für Spider {spider_name} ({self.current_scheduled_spider_index + 1}/{len(self.scheduled_spiders)})...")
        
        # Deaktiviere manuelle Startbuttons während der Sequenz
        self.set_crawl_buttons_enabled(False)
        
        # Starte den Crawl-Thread für diesen Spider
        # Das `scheduled=True` ist hier implizit durch `is_scheduled_crawl_active`
        self._start_crawl(spider_name) # Verwende die interne Startmethode

    @pyqtSlot(str)
    def show_scheduled_crawl_feedback(self, message):
        """Zeigt eine kurze Info-Nachricht zum Scheduler-Status an."""
        # Optional: Zeige dies in der Statusleiste oder als kleine Popup-Nachricht
        # Korrigierter Aufruf
        # self.statusBar().showMessage(message, 5000) # 5 Sekunden anzeigen
        self.statusBar.showMessage(message, 5000) # Korrekt: ohne () nach statusBar
        logger.info(message) # Auch im Log ausgeben
    # --- Ende Scheduler-Methoden ---

    # --- NEUER Slot zum Stoppen der TTS --- 
    @pyqtSlot()
    def on_stop_tts_clicked(self):
        """Wird aufgerufen, wenn der Stop-TTS-Button geklickt wird."""
        if hasattr(self, 'tts_manager') and self.tts_manager and hasattr(self.tts_manager, 'stop_playback'):
            logger.info("Stop TTS Button geklickt. Versuche Wiedergabe zu stoppen...")
            try:
                self.tts_manager.stop_playback()
            except Exception as e:
                logger.error(f"Fehler beim Aufrufen von tts_manager.stop_playback(): {e}", exc_info=True)
        else:
            logger.warning("Stop TTS Button geklickt, aber kein gültiger TTS-Manager oder keine stop_playback Methode gefunden.")
    # --- Ende Neuer Slot --- 

    # ---> Trigger-Methode für den neuen Button
    def trigger_all_spiders_sequentially(self):
        """Startet den Thread zum sequenziellen Ausführen aller Spider."""
        if self.all_spiders_thread and self.all_spiders_thread.isRunning():
            QMessageBox.warning(self, "Prozess läuft bereits", "Es läuft bereits ein Prozess zum Starten aller Spider.")
            return

        # Prüfe auch, ob ein normaler Crawl oder ein Scheduler aktiv ist
        if (self.crawler_thread and self.crawler_thread.isRunning()) or self.is_scheduled_crawl_active:
            QMessageBox.warning(self, "Anderer Prozess aktiv", "Ein einzelner Crawl oder der Scheduler ist bereits aktiv.")
            return

        logger.info("Starte Thread zum sequenziellen Ausführen aller Spider...")
        self.statusBar.showMessage("Starte Prozess: Alle Spider nacheinander...", 3000)
        self.set_crawl_buttons_enabled(False) # Alle Crawl-Buttons deaktivieren
        self.crawler_main_status_label.setText("Status: Starting All...")
        self.crawler_activity_label.setText("Finding spiders...")

        self.all_spiders_thread = AllSpidersRunThread(project_root="D:\\_____RH-IT\\JARVIS") # Pfad anpassen bei Bedarf

        # Signale des Threads verbinden
        self.all_spiders_thread.spider_starting.connect(self.on_all_spiders_starting)
        self.all_spiders_thread.spider_finished.connect(self.on_all_spiders_finished_one)
        self.all_spiders_thread.all_spiders_finished.connect(self.on_all_spiders_sequence_finished)
        self.all_spiders_thread.error_occurred.connect(self.on_all_spiders_error)
        # Aufräumen, wenn der Thread beendet ist (wichtig!)
        self.all_spiders_thread.finished.connect(self.on_all_spiders_thread_actually_finished)

        self.all_spiders_thread.start()
    # <--- Ende Trigger-Methode

    # ---> Slots für den AllSpidersRunThread
    @pyqtSlot(str)
    def on_all_spiders_starting(self, spider_name):
        """Aktualisiert die UI, wenn der nächste Spider gestartet wird."""
        self.crawler_main_status_label.setText(f"Status: Running All...")
        self.crawler_activity_label.setText(f"Running: {spider_name}")
        logger.info(f"[All Spiders] Starting: {spider_name}")

    @pyqtSlot(str, int)
    def on_all_spiders_finished_one(self, spider_name, exit_code):
        """Wird aufgerufen, wenn ein einzelner Spider beendet wurde."""
        if exit_code == 0:
            logger.info(f"[All Spiders] Finished successfully: {spider_name}")
            self.crawler_activity_label.setText(f"Finished: {spider_name}, starting next...")
        else:
            logger.error(f"[All Spiders] Failed: {spider_name} with exit code {exit_code}")
            self.crawler_activity_label.setText(f"Failed: {spider_name} (Code: {exit_code})")
            # Optional: Hier könnte man die Sequenz abbrechen

    @pyqtSlot()
    def on_all_spiders_sequence_finished(self):
        """Wird aufgerufen, wenn alle Spider erfolgreich durchgelaufen sind."""
        logger.info("[All Spiders] Sequence finished successfully.")
        self.statusBar.showMessage("Alle Spider erfolgreich ausgeführt.", 5000)
        self.crawler_main_status_label.setText("Status: Idle")
        self.crawler_activity_label.setText("All spiders finished.")
        # Buttons wieder aktivieren, wenn der Thread tatsächlich beendet ist (siehe on_all_spiders_thread_actually_finished)

    @pyqtSlot(str)
    def on_all_spiders_error(self, error_message):
        """Wird aufgerufen, wenn im AllSpidersRunThread ein Fehler auftritt."""
        logger.error(f"[All Spiders] Error during sequence: {error_message}")
        QMessageBox.critical(self, "Fehler beim Ausführen aller Spider", error_message)
        self.crawler_main_status_label.setText("Status: Error (All Spiders)")
        self.crawler_activity_label.setText(f"Error: {error_message[:100]}...")
        # Buttons wieder aktivieren, wenn der Thread tatsächlich beendet ist (siehe on_all_spiders_thread_actually_finished)

    @pyqtSlot()
    def on_all_spiders_thread_actually_finished(self):
        """Slot der aufgerufen wird, wenn der QThread selbst beendet ist (nach run())."""
        logger.debug("AllSpidersRunThread tatsächlich beendet. Aktiviere Buttons.")
        self.set_crawl_buttons_enabled(True) # Buttons hier sicher wieder aktivieren
        self.all_spiders_thread = None # Referenz löschen
    # <--- Ende Slots für AllSpidersRunThread

    # --- Placeholder für neue Aktions-Buttons ---
    def on_create_image_clicked(self):
        logger.info("Button 'Bild erstellen' geklickt (Funktion noch nicht implementiert).")
        QMessageBox.information(self, "Info", "Funktion 'Bild erstellen' ist noch nicht implementiert.")

    def on_create_video_clicked(self):
        logger.info("Button 'Video erstellen' geklickt (Funktion noch nicht implementiert).")
        QMessageBox.information(self, "Info", "Funktion 'Video erstellen' ist noch nicht implementiert.")

    def on_voice_agent_clicked(self): # Geändert
        logger.info("Button 'Voice Agent' geklickt (Funktion noch nicht implementiert).")
        QMessageBox.information(self, "Info", "Funktion 'Voice Agent' ist noch nicht implementiert.")
    # --- Ende Placeholder ---

@crochet.wait_for(timeout=None) # Erlaubt das Starten von Twisted-Prozessen im Thread
def run_spider_in_thread(process, spider_name, **kwargs):
    """ Hilfsfunktion, um den CrawlerProcess im Crochet-Kontext zu starten """
    # Diese Funktion startet den Crawl und gibt ein Deferred zurück.
    # crochet.wait_for kümmert sich darum, dass der Thread wartet,
    # bis das Deferred abgeschlossen ist, ohne die GUI zu blockieren.
    # Übergibt zusätzliche kwargs an process.crawl
    return process.crawl(spider_name, **kwargs)

# === Neue Klasse für ScrapyCrawlerThread ===
class ScrapyCrawlerThread(QThread):
    # Signale für die Kommunikation mit dem Hauptthread (BLEIBEN GLEICH)
    crawl_started = pyqtSignal()
    status_update = pyqtSignal(str)
    item_processed = pyqtSignal(str) # Sendet z.B. die URL des verarbeiteten Items
    crawl_finished = pyqtSignal(str, str) # spider_name, reason
    crawl_error = pyqtSignal(str, str) # spider_name, error_message

    def __init__(self, spider_name, learning_manager, config, parent=None):
        super().__init__(parent)
        self.spider_name = spider_name
        self.learning_manager = learning_manager
        self.config = config
        # self.pipeline_instance = None # Nicht mehr benötigt?
        self.result_queue = queue.Queue() # *** NEUE Queue erstellen ***
        logger.info(f"ScrapyCrawlerThread für Spider '{self.spider_name}' initialisiert (mit Queue).")

    def run(self):
        spider_finished = False # Flag um die Queue-Schleife zu beenden
        try:
            self.crawl_started.emit()
            self.status_update.emit(f"Initialisiere Scrapy Settings für {self.spider_name}...")
            logger.info(f"Initialisiere Scrapy Settings für CrawlerThread ({self.spider_name})...")

            settings_obj = Settings()
            settings_obj['ITEM_PIPELINES'] = {
                'src.scraping.knowledge_crawler.pipelines.LearningManagerPipeline': 1,
            }
            settings_obj['LOG_LEVEL'] = 'INFO'
            settings_obj['SPIDER_MODULES'] = ['src.scraping.knowledge_crawler.spiders']
            # Optional: Eigene User-Agent Einstellung, falls blockiert wird
            # settings_obj['USER_AGENT'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

            self.status_update.emit("Erstelle CrawlerProcess...")
            logger.info("Erstelle CrawlerProcess...")
            process = CrawlerProcess(settings_obj)

            self.status_update.emit(f"Starte {self.spider_name} Spider...")
            logger.info(f"Starte {self.spider_name} über CrawlerProcess und übergebe LearningManager und Thread-Instanz...")

            # Starte den spezifischen Spider im Crochet-Kontext
            run_spider_in_thread(process, self.spider_name,
                               learning_manager=self.learning_manager,
                               thread_instance=self)

            logger.info(f"Scrapy-Prozess für {self.spider_name} (via crochet) beendet.")

        except Exception as e:
            error_msg = f"Fehler im ScrapyCrawlerThread run ({self.spider_name}): {e}"
            logger.error(error_msg, exc_info=True)
            self.crawl_error.emit(self.spider_name, error_msg)
        finally:
            logger.info(f"ScrapyCrawlerThread run-Methode für {self.spider_name} beendet.")

    # --- Implementierte Signal Handler ---
    # Diese Methoden werden von Scrapy-Signalen aufgerufen (im Twisted Reactor Thread)
    # Sie müssen sicherstellen, dass GUI-Updates über Signale an den Hauptthread gesendet werden.

    def _item_scraped_handler(self, item, response, spider):
        # Wird für jedes gecrawlte Item aufgerufen
        adapter = ItemAdapter(item)
        url = adapter.get('url', 'Unbekannte URL') # Hole URL vom Item
        # Sende Signal an Hauptthread
        self.item_processed.emit(url) # Direktes Emit sollte Thread-sicher sein für Qt Signale
        logger.debug(f"Item scraped: {url}")

    def _spider_closed_handler(self, spider, reason):
        # Wird aufgerufen, wenn der Spider schließt
        # Sende spider_name mit
        logger.debug(f"Thread {self.objectName()}: Spider '{spider.name}' geschlossen. Sende crawl_finished Signal...") # NEUES DEBUG LOGGING
        self.crawl_finished.emit(spider.name, reason)
        logger.info(f"Spider geschlossen: {spider.name}, Grund: {reason}")

    def _spider_error_handler(self, failure, response, spider):
        # Wird bei Fehlern während des Crawlens aufgerufen
        error_msg = f"Spider Error in {spider.name}: {failure.getErrorMessage()}"
        logger.error(error_msg, exc_info=failure.value) # Logge den Traceback
        # Sende auch den spider_name mit
        self.crawl_error.emit(spider.name, error_msg)

# --- Ende ScrapyCrawlerThread ---

# === Klasse für den Audiobook-Import (aus Backup wiederhergestellt) ===
def find_and_process_audio_in_folder(file_path: str, learning_manager, whisper_recognizer) -> bool:
    """
    Verarbeitet eine einzelne Audiodatei und fügt sie zur Wissensbasis hinzu.

    Args:
        file_path: Pfad zur Audiodatei
        learning_manager: Instance des LearningManager
        whisper_recognizer: Instance des WhisperRecognizer

    Returns:
        bool: True wenn erfolgreich, False wenn ein Fehler auftrat
    """
    try:
        # Transkribiere die Audio-Datei
        transcript = whisper_recognizer.transcribe_wav(file_path)

        if not transcript:
            logger.warning(f"Keine Transkription für: {file_path}")
            return False

        # Speichere das Transkript in der Wissensbasis
        learning_manager.add_entry(
            doc_id=str(uuid.uuid4()),
            content=transcript,
            metadata={
                "entry_type": "audiobook_chunk",
                "source": os.path.basename(file_path),
                "timestamp": datetime.now().isoformat()
            }
        )

        return True

    except Exception as e:
        logger.error(f"Fehler bei der Verarbeitung von {file_path}: {e}")
        return False

class AudiobookImportThread(QThread):
    """Thread für den Import von Audiobüchern."""
    # VERWENDE NEUE SIGNALNAMEN (wie in import_audiobooks verbunden)
    progress_update = pyqtSignal(int, int, str) # (current, total, message)
    finished = pyqtSignal() # Signal ohne Argumente für Erfolg
    error = pyqtSignal(str) # Signal für Fehlermeldung

    def __init__(self, folder_path: str, whisper_recognizer: WhisperRecognizer, learning_manager: LearningManager, parent=None):
        super().__init__(parent)
        self.folder_path = folder_path
        self.whisper_recognizer = whisper_recognizer
        self.learning_manager = learning_manager
        self.log_prefix = "[AudiobookImportThread]"
        self._is_stopped = False # Flag zum Stoppen
        self.processed_log_file = os.path.join("data", "temp", "audiobook_processing", "processed_files.log")
        # ---> Sicherstellen, dass das Log-Verzeichnis existiert
        try:
            os.makedirs(os.path.dirname(self.processed_log_file), exist_ok=True)
        except Exception as e:
            logger.error(f"{self.log_prefix} Konnte Log-Verzeichnis nicht erstellen: {e}")
            # Optional: Thread hier beenden oder weitermachen und hoffen?

    def stop(self):
        """Setzt das Stop-Flag."""
        self._is_stopped = True
        logger.info(f"{self.log_prefix} Stop-Anforderung erhalten.")

    def run(self):
        """Führt den Import-Prozess aus und hängt jede erfolgreiche Datei an die Logdatei an."""
        success_count = 0
        total_files_to_process = 0
        processed_files = 0
        # last_successful_file wird nicht mehr benötigt
        try:
            logger.info(f"{self.log_prefix} Starte Import von Audiobüchern aus: {self.folder_path}")
            # Zuerst alle relevanten Dateien zählen
            audio_files = []
            for root, _, files in os.walk(self.folder_path):
                for file in files:
                    if self._is_stopped:
                        logger.info(f"{self.log_prefix} Import während Dateisuche abgebrochen.")
                        self.error.emit("Import abgebrochen")
                        return
                    if file.lower().endswith(('.mp3', '.wav', '.m4a', '.flac')):
                        audio_files.append(os.path.join(root, file))
            total_files_to_process = len(audio_files)
            logger.info(f"{self.log_prefix} {total_files_to_process} Audiodateien gefunden.")

            if not self.whisper_recognizer:
                error_msg = "Whisper Recognizer ist nicht initialisiert."
                logger.error(f"{self.log_prefix} {error_msg}")
                self.error.emit(error_msg)
                return

            # Verarbeite die gefundenen Dateien
            for file_path in audio_files:
                if self._is_stopped:
                    logger.info(f"{self.log_prefix} Import während Verarbeitung abgebrochen.")
                    break # Verlasse die Schleife
                processed_files += 1
                try:
                    file_name = os.path.basename(file_path)
                    status_msg = f"Verarbeite ({processed_files}/{total_files_to_process}): {file_name}..."
                    self.progress_update.emit(processed_files, total_files_to_process, status_msg)
                    logger.debug(f"{self.log_prefix} {status_msg}")

                    success = find_and_process_audio_in_folder(
                        file_path,
                        self.learning_manager,
                        self.whisper_recognizer
                    )

                    if success:
                        success_count += 1
                        logger.info(f"{self.log_prefix} Erfolgreich importiert: {file_name}")
                        # ---> Logge die erfolgreiche Datei sofort im Append-Modus
                        try:
                            with open(self.processed_log_file, 'a', encoding='utf-8') as f:
                                f.write(file_path + '\n') # Schreibe Pfad und Zeilenumbruch
                            # Optional: Loggen, dass geschrieben wurde (kann viel werden)
                            # logger.debug(f"{self.log_prefix} '{file_path}' an Logdatei angehängt.")
                        except Exception as log_e:
                            logger.error(f"{self.log_prefix} Fehler beim Anhängen an Logdatei '{self.processed_log_file}': {log_e}")
                        # <--- Ende Loggen
                    else:
                        logger.warning(f"{self.log_prefix} Fehler beim Import von: {file_name}")

                except Exception as e:
                    logger.error(f"{self.log_prefix} Fehler bei der Verarbeitung von {file_name}: {e}", exc_info=True)
                    self.progress_update.emit(processed_files, total_files_to_process, f"Fehler bei {file_name}")

            logger.info(f"{self.log_prefix} Import-Schleife beendet. {success_count} von {processed_files} verarbeiteten Dateien erfolgreich.")
            # ---> Kein separates Loggen mehr am Ende nötig
            self.finished.emit() # Erfolgssignal

        except Exception as e:
            error_msg = f"Schwerwiegender Fehler im Import-Prozess: {e}"
            logger.error(f"{self.log_prefix} {error_msg}", exc_info=True)
            # ---> Kein separates Loggen mehr am Ende nötig
            self.error.emit(error_msg)

# === Ende AudiobookImportThread ===

# === HIER die TextProcessingThread Klasse aus dem Backup einfügen ===
class TextProcessingThread(QThread):
    """Thread für die Verarbeitung von Texteingaben."""
    # Passe die Signale an die aktuellen Slots in MainWindow an, falls nötig
    # Annahme: update_chat sendet nur sender und message
    update_chat = pyqtSignal(str, str)
    trigger_tts = pyqtSignal(str)
    # Passe das Signal an, um response_id und result zurückzugeben (wie in on_processing_finished erwartet)
    processing_finished = pyqtSignal(str, str) # response_id, result
    processing_error = pyqtSignal(str) # Fehlermeldung

    def __init__(self, text: str, llm_manager, config, learning_manager, river_learning_manager, response_id: str, parent=None):
        super().__init__(parent)
        self.text = text
        self.llm_manager = llm_manager
        self.config = config
        self.learning_manager = learning_manager
        self.river_learning_manager = river_learning_manager
        self.response_id = response_id
        self.log_prefix = "[TextProcessingThread]"

    def run(self):
        """Verarbeitet die Texteingabe und erhält eine Antwort vom LLM."""
        try:
            logger.info(f"{self.log_prefix} Verarbeite Text: '{self.text}'")

            # --- Schritt 0.5: Predict intent with River (falls vorhanden) --- 
            if self.river_learning_manager:
                try:
                    intent_prediction = self.river_learning_manager.predict(self.text)
                    logger.info(f"{self.log_prefix} River Intent Prediction: '{intent_prediction}' for '{self.text}'")
                    # TODO: Kontext speichern? (interaction_context ist in MainWindow)
                except Exception as river_e:
                    logger.warning(f"{self.log_prefix} River prediction failed: {river_e}")
            else:
                logger.debug(f"{self.log_prefix} RiverLearningManager not available for prediction.") # Debug statt Warning

            # --- Schritt 1: Sende Text direkt an LLM --- 
            if not self.llm_manager:
                raise RuntimeError("LLM Manager ist nicht initialisiert")

            logger.info(f"{self.log_prefix} Rufe llm_manager.process_text auf...")
            llm_response = self.llm_manager.process_text(self.text)

            if not llm_response:
                # raise RuntimeError("LLM hat keine Antwort zurückgegeben") # Alt: Absturz
                # Neu: Fehlermeldung an GUI senden
                error_msg = "Das KI-Modell hat leider keine Antwort generiert."
                logger.warning(f"{self.log_prefix} {error_msg}")
                self.update_chat.emit("System", f"[Fehler: {error_msg}]")
                self.processing_finished.emit(self.response_id, "") # Signalisiere Ende ohne gültige Antwort
                return # Beende den Thread hier

            logger.info(f"{self.log_prefix} LLM Antwort erhalten: '{llm_response[:100]}...'")

            # Speichere die Konversation in der Wissensbasis (falls vorhanden)
            if self.learning_manager:
                try:
                    metadata = {
                        "entry_type": "conversation",
                        "timestamp": datetime.now().isoformat(),
                        "input": self.text,
                        "response": llm_response
                    }
                    self.learning_manager.add_entry(
                        doc_id=str(uuid.uuid4()), # Verwende uuid hier
                        content=f"Frage: {self.text}\nAntwort: {llm_response}",
                        metadata=metadata
                    )
                    logger.info(f"{self.log_prefix} Konversation in Wissensbasis gespeichert")
                except Exception as e:
                    logger.error(f"{self.log_prefix} Fehler beim Speichern der Konversation: {str(e)}")

            # Sende LLM Antwort an GUI
            self.update_chat.emit("JARVIS", llm_response)

            # Trigger TTS wenn aktiviert
            try:
                # Prüfe die Konfiguration direkt über self.config
                if self.config and self.config.get("use_tts", False):
                    self.trigger_tts.emit(llm_response)
                    logger.debug(f"{self.log_prefix} TTS Signal gesendet für Antwort.")
                else:
                    logger.debug(f"{self.log_prefix} TTS ist deaktiviert oder Config fehlt.")
            except Exception as e:
                logger.error(f"{self.log_prefix} Fehler beim Prüfen der TTS-Konfiguration oder Senden des Signals: {e}", exc_info=True)

            # Sende das Ergebnis zurück an MainWindow
            self.processing_finished.emit(self.response_id, llm_response)

        except Exception as e:
            error_msg = f"{self.log_prefix} Fehler in der Verarbeitung: {str(e)}"
            logger.error(error_msg, exc_info=True) # Logge Traceback
            # Sende Fehler an GUI
            self.processing_error.emit(error_msg)
            # Signalisiere auch das Ende (mit Fehlermarker)
            self.processing_finished.emit(self.response_id, f"FEHLER: {e}") # Sende Fehler auch hier

# === Ende TextProcessingThread ===

# === NEUE Klasse AllSpidersRunThread HIER definieren (am Ende der Datei) ===
class AllSpidersRunThread(QThread):
    """Thread zum sequenziellen Ausführen aller Scrapy Spiders."""
    spider_starting = pyqtSignal(str) # spider_name
    spider_finished = pyqtSignal(str, int) # spider_name, exit_code
    all_spiders_finished = pyqtSignal()
    error_occurred = pyqtSignal(str) # error_message

    def __init__(self, project_root, parent=None):
        super().__init__(parent)
        self.project_root = project_root
        self.log_prefix = "[AllSpidersRunThread]"
        self._is_stopped = False # Für zukünftige Abbruch-Funktionalität

    def stop(self):
        self._is_stopped = True
        logger.info(f"{self.log_prefix} Stop request received (not fully implemented for subprocesses yet).")

    def run(self):
        """Führt 'scrapy list' aus und dann 'scrapy crawl' für jeden Spider."""
        spider_names = []
        crawl_cmd = [] # Für Fehlermeldung
        try:
            scraping_dir = os.path.join(self.project_root, "src", "scraping")
            venv_python = os.path.join(self.project_root, "venv", "Scripts", "python.exe")

            if not os.path.exists(venv_python):
                # Versuch, den globalen Python-Interpreter zu verwenden, falls kein venv da ist
                # Dies ist riskant, wenn Abhängigkeiten nicht global installiert sind.
                logger.warning(f"{self.log_prefix} Venv Python not found at {venv_python}. Trying system Python.")
                venv_python = sys.executable # Verwende den Interpreter, der dieses Skript ausführt

            if not os.path.isdir(scraping_dir):
                 raise FileNotFoundError(f"Scraping directory not found: {scraping_dir}")

            # 1. Scrapy list
            logger.info(f"{self.log_prefix} Finding spiders in {scraping_dir} using {venv_python}...")
            list_cmd = [venv_python, "-m", "scrapy", "list"]
            result = subprocess.run(list_cmd, cwd=scraping_dir, capture_output=True, text=True, check=True, shell=False)
            spider_names = [name.strip() for name in result.stdout.splitlines() if name.strip()]
            logger.info(f"{self.log_prefix} Found spiders: {spider_names}")

            if not spider_names:
                logger.warning(f"{self.log_prefix} No spiders found.")
                self.error_occurred.emit("Keine Spider gefunden.")
                return

            # 2. Scrapy crawl für jeden Spider
            for spider_name in spider_names:
                if self._is_stopped:
                    logger.info(f"{self.log_prefix} Stopping sequence before running {spider_name}.")
                    self.error_occurred.emit("Prozess abgebrochen.")
                    return

                self.spider_starting.emit(spider_name)
                crawl_cmd = [venv_python, "-m", "scrapy", "crawl", spider_name]
                logger.info(f"{self.log_prefix} Running command: {' '.join(crawl_cmd)}")

                # Verwende run, um auf die Beendigung zu warten
                process_result = subprocess.run(crawl_cmd, cwd=scraping_dir, capture_output=True, text=True, shell=False)
                exit_code = process_result.returncode

                if exit_code != 0:
                    logger.error(f"{self.log_prefix} Spider {spider_name} failed with exit code {exit_code}.")
                    logger.error(f"{self.log_prefix} Stdout:\n{process_result.stdout}")
                    logger.error(f"{self.log_prefix} Stderr:\n{process_result.stderr}")
                    # Optional: Hier abbrechen oder weitermachen? Aktuell: Weitermachen
                else:
                     logger.info(f"{self.log_prefix} Spider {spider_name} finished successfully.")

                self.spider_finished.emit(spider_name, exit_code)

            # Wenn die Schleife durchläuft, sind alle fertig
            self.all_spiders_finished.emit()

        except FileNotFoundError as e:
             error_msg = f"Fehler: Datei oder Verzeichnis nicht gefunden: {e}. Ist der Projektpfad korrekt und Scrapy im venv?"
             logger.error(f"{self.log_prefix} {error_msg}")
             self.error_occurred.emit(error_msg)
        except subprocess.CalledProcessError as e:
            command_str = ' '.join(e.cmd)
            error_msg = f"Fehler beim Ausführen von Scrapy ({command_str}): {e.stderr or e.stdout or 'Keine Ausgabe'}"
            logger.error(f"{self.log_prefix} {error_msg}", exc_info=True)
            self.error_occurred.emit(error_msg)
        except Exception as e:
            error_msg = f"Unerwarteter Fehler im AllSpidersRunThread: {e}"
            logger.error(f"{self.log_prefix} {error_msg}", exc_info=True)
            self.error_occurred.emit(error_msg)

# === Ende AllSpidersRunThread ===