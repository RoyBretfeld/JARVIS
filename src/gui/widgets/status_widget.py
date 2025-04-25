from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox
from PyQt6.QtCore import Qt
import logging

logger = logging.getLogger(__name__)

class StatusWidget(QWidget):
    """
    Widget zur Anzeige verschiedener Statusinformationen (System, LLM, etc.).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("StatusWidget") # Für Styling/Referenz

        # Hauptlayout (vertikal, um Gruppen untereinander anzuordnen, falls nötig)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(5)

        # Layout für die Status-Labels (horizontal)
        status_layout = QHBoxLayout()

        # --- Labels für verschiedene Status ---
        # Beispiel-Labels, passe sie an die tatsächlich benötigten Infos an
        self.cpu_label = QLabel("CPU: --%")
        self.ram_label = QLabel("RAM: --%")
        self.gpu_label = QLabel("GPU: --%")
        self.llm_provider_label = QLabel("LLM: --")
        self.llm_model_label = QLabel("Modell: --")
        self.db_info_label = QLabel("DB: --") # Für DB Größe/Einträge

        # Füge Labels zum Layout hinzu
        status_layout.addWidget(self.cpu_label)
        status_layout.addWidget(self.ram_label)
        status_layout.addWidget(self.gpu_label)
        status_layout.addSpacing(15) # Abstand
        status_layout.addWidget(self.llm_provider_label)
        status_layout.addWidget(self.llm_model_label)
        status_layout.addSpacing(15) # Abstand
        status_layout.addWidget(self.db_info_label)
        status_layout.addStretch(1) # Schiebt alles nach links

        # Füge das horizontale Layout zum Hauptlayout hinzu
        main_layout.addLayout(status_layout)

        # Optional: Style anwenden
        # self.setStyleSheet("QLabel { color: #cccccc; font-size: 10pt; }")

        self.setLayout(main_layout)

    # --- Methoden zum Aktualisieren der Labels ---
    def update_system_stats(self, cpu: float, ram: float, gpu: str):
        self.cpu_label.setText(f"CPU: {cpu:.1f}%")
        self.ram_label.setText(f"RAM: {ram:.1f}%")
        self.gpu_label.setText(f"GPU: {gpu}%") # GPU Info könnte String sein (z.B. "N/A")

    def update_llm_status(self, provider: str, model: str):
        self.llm_provider_label.setText(f"LLM: {provider}")
        self.llm_model_label.setText(f"Modell: {model}")

    def update_db_status(self, info: str):
        # Info könnte z.B. sein "12.34 KB | 150 Einträge"
        self.db_info_label.setText(f"DB: {info}")

    def update_general_status(self, message: str):
        # Möglicherweise ein separates Label für allgemeine Nachrichten
        # oder wir verwenden eines der vorhandenen. Vorerst nicht implementiert.
        logger.debug(f"StatusWidget received general status: {message}")
        pass 