import sys
import os

# Füge den src Ordner zum Python-Pfad hinzu
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if src_path not in sys.path:
    sys.path.append(src_path)

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from gui.main_window import MainWindow

def main():
    try:
        print("Debug: Starte Anwendung...")
        app = QApplication(sys.argv)
        
        # Setze den Anwendungsstil
        app.setStyle('Fusion')
        
        print("Debug: Erstelle Hauptfenster...")
        window = MainWindow()
        
        # Stelle sicher, dass das Fenster im Vordergrund und aktiviert erscheint
        window.show()
        window.setWindowState(window.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        window.activateWindow()  # Aktiviere das Fenster
        window.raise_()  # Bringe es in den Vordergrund
        
        print("Debug: Initialisierung abgeschlossen, starte GUI Event Loop...")
        
        print("Debug: Anwendung läuft...")
        return app.exec_()
        
    except Exception as e:
        print(f"Kritischer Fehler beim Starten der Anwendung: {str(e)}")
        import traceback
        print(f"Traceback:\n{traceback.format_exc()}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 