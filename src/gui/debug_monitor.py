import logging
from PyQt6.QtWidgets import QTextEdit, QWidget, QVBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QTextCursor
from datetime import datetime

class DebugMonitor(QTextEdit, logging.Handler):
    """Ein Widget, das Debug-Nachrichten anzeigt und als Logging-Handler fungiert."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Konfiguriere das Widget
        self.setReadOnly(True)
        self.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 5px;
                font-family: 'Consolas', 'Monospace';
            }
        """)
        
        # Konfiguriere den Logging-Handler
        self.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        self.level = logging.DEBUG  # Setze das Level auf DEBUG
        
    def emit(self, record):
        """Wird aufgerufen, wenn eine neue Log-Nachricht empfangen wird."""
        try:
            msg = self.format(record)
            self.append(msg)
            # Scrolle zum Ende
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.setTextCursor(cursor)
        except Exception:
            self.handleError(record)
            
    def add_message(self, message: str):
        """Fügt eine Nachricht direkt zum Monitor hinzu."""
        self.append(message)
        # Scrolle zum Ende
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor)

    def log(self, message: str, level: str = "INFO"):
        """Fügt eine Nachricht zum Debug-Monitor hinzu"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        color = {
            "INFO": "#00ff00",
            "WARNING": "#ffff00",
            "ERROR": "#ff0000",
            "DEBUG": "#00ffff"
        }.get(level, "#00ff00")
        
        formatted_message = f'<span style="color: {color}">[{timestamp}] {level}: {message}</span><br>'
        self.append(formatted_message)
        # Scrolle automatisch nach unten
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor) 