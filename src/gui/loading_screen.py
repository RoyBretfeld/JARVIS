from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar
from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

class LoadingScreen(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("JARVIS wird initialisiert...")
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.CustomizeWindowHint)
        self.setFixedSize(400, 200)
        
        # Layout
        layout = QVBoxLayout()
        
        # Status Label
        self.status_label = QLabel("Initialisiere JARVIS...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        
        # Progress Bar
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        
        # Details Label
        self.details_label = QLabel("")
        self.details_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.details_label)
        
        self.setLayout(layout)
        
    def set_status(self, status_text):
        self.status_label.setText(status_text)
        QApplication.processEvents()
        
    def update_status(self, status: str, progress: int, details: str = ""):
        """Aktualisiert den Ladestatus (Legacy-Methode)"""
        self.status_label.setText(status)
        self.progress.setValue(progress)
        self.details_label.setText(details)
        self.repaint() 