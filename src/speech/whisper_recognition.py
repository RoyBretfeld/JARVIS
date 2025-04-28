import os
import json
import numpy as np
import time
import soundfile as sf
import librosa
from faster_whisper import WhisperModel
import torch
from datetime import datetime
from loguru import logger

class WhisperRecognizer:
    def __init__(self, model_size="base", device="cpu", compute_type="int8"):
        logger.info(f"Initialisiere WhisperRecognizer mit Modell: {model_size}, Gerät: {device}, Typ: {compute_type}")
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
        logger.info("WhisperRecognizer initialisiert.")
        self.language = "de"
        self.beam_size = 5
        self.best_of = 5
        self.temperature = 0
        print("[WhisperRecognizer] Whisper-Modell erfolgreich initialisiert.")

    def detect_silence(self, audio_data, sample_rate, threshold=0.01, min_silence_duration=0.7):
        """Erkennt, ob die Aufnahme hauptsächlich aus Stille besteht."""
        try:
            # Stelle sicher, dass die Daten float32 sind (sollte vom Aufnahmethread kommen)
            if audio_data.dtype != np.float32:
                logger.warning(f"Unerwarteter Audio-Datentyp in detect_silence: {audio_data.dtype}. Konvertiere zu float32.")
                # Konvertiere, falls möglich (Annahme: int16 -> float32)
                if np.issubdtype(audio_data.dtype, np.integer):
                    audio_data = audio_data.astype(np.float32) / np.iinfo(audio_data.dtype).max
                else:
                    # Fallback, wenn Konvertierung unklar
                    audio_data = audio_data.astype(np.float32)

            # Konvertiere zu Mono falls stereo
            if len(audio_data.shape) > 1:
                audio_data = audio_data.mean(axis=1)
            
            # Berechne Energie über kurze Zeitfenster (z.B. 50ms)
            frame_length = int(sample_rate * 0.05) # 50ms
            hop_length = int(sample_rate * 0.025) # 25ms Überlappung
            
            # Verwende librosa für RMS-Energieberechnung
            rms = librosa.feature.rms(y=audio_data, frame_length=frame_length, hop_length=hop_length)[0]
            
            if rms.size == 0: # Wenn Audio zu kurz ist
                logger.warning("Audio zu kurz für Stilleerkennung.")
                return True # Im Zweifel als still betrachten

            # Berechne den Anteil der Frames unterhalb des Schwellenwerts
            silent_frames = np.sum(rms < threshold)
            total_frames = len(rms)
            silence_ratio = silent_frames / total_frames

            # Debug-Ausgabe
            logger.debug(f"Stilleerkennung: Max RMS={np.max(rms):.4f}, Schwellenwert={threshold}, Stille-Anteil={silence_ratio:.2f}")

            # Entscheide basierend auf dem Anteil und der Mindestdauer
            # Wenn mehr als z.B. 90% der Frames still sind
            if silence_ratio > 0.90:
                logger.warning(f"Stille erkannt: {silent_frames}/{total_frames} ({silence_ratio*100:.1f}%) Frames unter Schwellenwert {threshold}")
                return True
                
            return False
        except Exception as e:
            logger.error(f"Fehler in detect_silence: {e}", exc_info=True)
            return False # Im Fehlerfall lieber nicht als still klassifizieren

    def transcribe_wav(self, wav_path):
        logger.info(f"Transkribiere WAV-Datei: {wav_path}")
        start_time = time.time()
        try:
            segments, info = self.model.transcribe(
                wav_path, 
                beam_size=5,
                language="de",  # Sprache auf Deutsch setzen
                vad_filter=True, # Verwende VAD Filter
                vad_parameters=dict(min_silence_duration_ms=500), # VAD Parameter
                suppress_blank=True, # Unterdrücke leere Ausgaben
                no_speech_threshold=0.6 # Schwelle für keine Sprache erkennen
            )
            
            transcription = "".join([segment.text for segment in segments])
            end_time = time.time()
            duration = end_time - start_time
            logger.info(f"Transkription abgeschlossen in {duration:.2f} Sekunden. Ergebnis: {transcription}")
            return transcription.strip()
        except Exception as e:
            logger.error(f"Fehler bei der Transkription von {wav_path}: {e}", exc_info=True)
            return ""

    def process_audio(self, audio_data, sample_rate=16000):
        logger.info("Verarbeite rohe Audiodaten...")
        start_time = time.time()
        try:
            # Umwandlung zu float32, falls nötig (Whisper erwartet float32)
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32) / 32768.0 # Skalierung für float32

            segments, info = self.model.transcribe(
                audio_data,
                beam_size=5,
                language="de",
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
                suppress_blank=True,
                no_speech_threshold=0.6
            )
            
            transcription = "".join([segment.text for segment in segments])
            end_time = time.time()
            duration = end_time - start_time
            logger.info(f"Audioverarbeitung abgeschlossen in {duration:.2f} Sekunden. Ergebnis: {transcription}")
            return transcription.strip()
        except Exception as e:
            logger.error(f"Fehler bei der Verarbeitung von Audiodaten: {e}", exc_info=True)
            return ""

# Beispielhafte Nutzung (kann zum Testen einkommentiert werden)
if __name__ == '__main__':
    # Erstelle ein Dummy-Audiosignal (Stille) und speichere es als WAV
    sample_rate = 16000
    duration = 5  # Sekunden
    silence = np.zeros(int(sample_rate * duration), dtype=np.int16)
    wav_path = "silence_test.wav"
    sf.write(wav_path, silence, sample_rate)
    print(f"Stille-Audiodatei '{wav_path}' erstellt.")

    # Initialisiere den Recognizer
    # Verwende 'cuda' und 'float16' wenn eine NVIDIA GPU verfügbar ist
    # recognizer = WhisperRecognizer(model_size="medium", device="cuda", compute_type="float16")
    recognizer = WhisperRecognizer(model_size="base", device="cpu", compute_type="int8") 

    # Transkribiere die Stille-Datei
    print(f"Transkribiere '{wav_path}'...")
    transcription = recognizer.transcribe_wav(wav_path)
    print(f"Transkription Ergebnis: '{transcription}'")

    # Lösche die Testdatei
    os.remove(wav_path)
    print(f"Testdatei '{wav_path}' gelöscht.")

    # Beispiel für die Verarbeitung von rohen Daten (hier auch Stille)
    print("\nVerarbeite rohe Audiodaten (Stille)...")
    raw_silence = np.zeros(int(sample_rate * duration), dtype=np.float32) # float32 für direkte Verarbeitung
    transcription_raw = recognizer.process_audio(raw_silence)
    print(f"Verarbeitung roher Daten Ergebnis: '{transcription_raw}'") 