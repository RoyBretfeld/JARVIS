import pyaudio
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QListWidget, 
                           QPushButton, QLabel, QListWidgetItem)
from PyQt6.QtCore import Qt

class MicrophoneSelector(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Mikrofon auswählen")
        self.setMinimumWidth(400)
        self.selected_device = None
        
        # Layout erstellen
        layout = QVBoxLayout()
        
        # Label hinzufügen
        label = QLabel("Verfügbare Mikrofone:")
        layout.addWidget(label)
        
        # Liste für Mikrofone
        self.device_list = QListWidget()
        layout.addWidget(self.device_list)
        
        # Buttons
        select_button = QPushButton("Auswählen")
        select_button.clicked.connect(self.accept)
        select_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        
        cancel_button = QPushButton("Abbrechen")
        cancel_button.clicked.connect(self.reject)
        cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        
        # Buttons zum Layout hinzufügen
        button_layout = QVBoxLayout()
        button_layout.addWidget(select_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # Geräteliste laden
        self.load_devices()
        
    def load_devices(self):
        """Lädt alle verfügbaren Audiogeräte"""
        p = pyaudio.PyAudio()
        
        for i in range(p.get_device_count()):
            device_info = p.get_device_info_by_index(i)
            
            # Nur Eingabegeräte anzeigen
            if device_info['maxInputChannels'] > 0:
                item = QListWidgetItem(f"{device_info['name']}")
                # Speichere Device-Index (PyQt6 Syntax)
                item.setData(Qt.ItemDataRole.UserRole, i)  
                self.device_list.addItem(item)
                
        p.terminate()
        
    def get_selected_device_index(self): # Umbenannt für Klarheit
        """Gibt den Index des ausgewählten Mikrofons zurück"""
        current_item = self.device_list.currentItem()
        if current_item:
            # Hole Daten mit neuer PyQt6 Syntax
            return current_item.data(Qt.ItemDataRole.UserRole)
        return None
        
    def get_selected_device_name(self):
        """Gibt den Namen des ausgewählten Mikrofons zurück"""
        current_item = self.device_list.currentItem()
        if current_item:
            return current_item.text()
        return None 