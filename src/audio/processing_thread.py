import os
import logging
from PyQt6.QtCore import QThread, pyqtSignal
from typing import Optional
import traceback
import time
import soundfile as sf
from datetime import datetime

logger = logging.getLogger(__name__)

class ProcessingThread(QThread):
    """Führt die Audioverarbeitung, Transkription und LLM-Anfrage im Hintergrund aus."""
    update_chat = pyqtSignal(str, str)
    trigger_tts = pyqtSignal(str)
    processing_finished = pyqtSignal(bool, str)
    transcription_result = pyqtSignal(str)

    def __init__(self, audio_data, audio_processor, whisper_recognizer, llm_manager, config, parent=None):
        super().__init__(parent)
        self.audio_data = audio_data
        self.audio_processor = audio_processor
        self.whisper_recognizer = whisper_recognizer
        self.llm_manager = llm_manager
        self.config = config
        self.log_prefix = "[ProcessingThread]"

    def run(self):
        """Führt die Verarbeitungsschritte aus."""
        try:
            logger.info(f"{self.log_prefix} Starte Verarbeitung mit {len(self.audio_data)} Bytes Audio")
            
            # 1. Audio verarbeiten
            if not self.audio_processor:
                raise ValueError("AudioProcessor nicht initialisiert")
                
            logger.info(f"{self.log_prefix} Verarbeite Audio mit AudioProcessor...")
            processed_data, sample_rate = self.audio_processor.process_audio(self.audio_data)
            if processed_data is None or len(processed_data) == 0:
                raise ValueError("Keine verarbeiteten Audiodaten erhalten")
                
            logger.info(f"{self.log_prefix} Audio erfolgreich verarbeitet: {len(processed_data)} Samples, {sample_rate} Hz")
            
            # 2. WAV-Datei speichern
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            wav_path = os.path.join(self.audio_processor.recordings_dir, f"recording_{timestamp}.wav")
            logger.info(f"{self.log_prefix} Speichere WAV-Datei: {wav_path}")
            sf.write(wav_path, processed_data, sample_rate)
            logger.info(f"{self.log_prefix} WAV-Datei erfolgreich gespeichert")
            
            # 3. Transkription
            if not self.whisper_recognizer:
                raise ValueError("WhisperRecognizer nicht initialisiert")
                
            logger.info(f"{self.log_prefix} Starte Transkription...")
            transcript = self.whisper_recognizer.transcribe_wav(wav_path)
            if not transcript:
                raise ValueError("Keine Transkription erhalten")
                
            logger.info(f"{self.log_prefix} Transkription erhalten: {transcript}")
            self.transcription_result.emit(transcript)
            self.update_chat.emit("Transkript", transcript)
            
            # 4. LLM-Verarbeitung
            if not self.llm_manager:
                raise ValueError("LLM Manager nicht initialisiert")
                
            logger.info(f"{self.log_prefix} Starte LLM-Verarbeitung...")
            response = self.llm_manager.process_text(transcript)
            if not response:
                raise ValueError("Keine LLM-Antwort erhalten")
                
            logger.info(f"{self.log_prefix} LLM-Antwort erhalten: {response[:100]}...")
            self.update_chat.emit("JARVIS", response)
            self.trigger_tts.emit(response)
            
            self.processing_finished.emit(True, response)
            logger.info(f"{self.log_prefix} Verarbeitung erfolgreich abgeschlossen")
            
        except Exception as e:
            error_msg = f"{self.log_prefix} Fehler: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())  # Füge Stack Trace hinzu
            self.update_chat.emit("System", error_msg)
            self.processing_finished.emit(False, str(e))
            
        finally:
            # Cleanup
            if 'wav_path' in locals() and os.path.exists(wav_path):
                try:
                    os.remove(wav_path)
                    logger.debug(f"{self.log_prefix} Temporäre WAV-Datei gelöscht: {wav_path}")
                except Exception as e:
                    logger.warning(f"{self.log_prefix} Konnte temporäre WAV-Datei nicht löschen: {str(e)}") 