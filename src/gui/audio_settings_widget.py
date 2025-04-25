from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QComboBox
from PyQt6.QtCore import pyqtSignal, Qt
import logging

logger = logging.getLogger(__name__)

class AudioSettingsWidget(QWidget):
    """
    Widget zur Anzeige und Änderung von Audio-Einstellungen (z.B. TTS-Engine).
    """
    # Signal, das die neu ausgewählte Engine als String sendet
    tts_engine_changed = pyqtSignal(str)

    def __init__(self, available_engines=None, current_engine=None, parent=None):
        super().__init__(parent)
        if available_engines is None:
            available_engines = ["piper", "coqui"] # Standard-Engines

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0) # Keine inneren Ränder

        label = QLabel("TTS Engine:")
        self.tts_combo_box = QComboBox()
        self.tts_combo_box.addItems(available_engines)

        if current_engine and current_engine in available_engines:
            self.tts_combo_box.setCurrentText(current_engine)
        elif available_engines:
            # Fallback auf die erste verfügbare Engine, falls die aktuelle ungültig ist
            self.tts_combo_box.setCurrentIndex(0)
            # Signal senden, falls wir auf einen Fallback wechseln mussten
            # Deaktiviert, um nicht beim Start ungewollt zu feuern
            # self.tts_engine_changed.emit(self.tts_combo_box.currentText())


        # Signal verbinden, um Änderungen weiterzuleiten
        self.tts_combo_box.currentTextChanged.connect(self.on_engine_selected)

        layout.addWidget(label)
        layout.addWidget(self.tts_combo_box)
        layout.addStretch(1) # Schiebt die Elemente nach links

        self.setLayout(layout)

    def on_engine_selected(self, engine: str):
        """
        Wird aufgerufen, wenn eine neue Engine in der ComboBox ausgewählt wird.
        Sendet das tts_engine_changed Signal.
        """
        logger.info(f"TTS Engine Auswahl geändert auf: {engine}")
        self.tts_engine_changed.emit(engine)

    def set_current_engine(self, engine_name: str):
        """
        Aktualisiert die Auswahl in der ComboBox, ohne ein Signal zu senden.
        """
        if engine_name == self.tts_combo_box.currentText():
            return # Nichts zu tun

        index = self.tts_combo_box.findText(engine_name, Qt.MatchFlag.MatchFixedString)
        if index >= 0:
            # Blockiere Signale, um eine Schleife zu verhindern, wenn dies programmatisch gesetzt wird
            self.tts_combo_box.blockSignals(True)
            self.tts_combo_box.setCurrentIndex(index)
            self.tts_combo_box.blockSignals(False)
            logger.debug(f"AudioSettingsWidget: Engine programmatisch auf {engine_name} gesetzt.")
        else:
            logger.warning(f"Versuch, ungültige TTS Engine '{engine_name}' im AudioSettingsWidget zu setzen.") 