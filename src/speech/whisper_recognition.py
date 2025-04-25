import os
import json
import numpy as np
import time
import soundfile as sf
import librosa
from faster_whisper import WhisperModel
import torch
from datetime import datetime

class WhisperRecognizer:
    def __init__(self, model_size="large-v2", device="cuda", compute_type="float16", cache_dir="data/models/whisper"):
        """Initialisiert das Whisper-Modell"""
        print(f"[WhisperRecognizer] Initialisiere Modell '{model_size}' mit Cache-Verzeichnis '{cache_dir}'...")
        print("[WhisperRecognizer] Rufe WhisperModel(...) Konstruktor auf...")
        self.model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
            download_root=cache_dir
        )
        print("[WhisperRecognizer] WhisperModel(...) Konstruktor beendet.")
        self.language = "de"
        self.beam_size = 5
        self.best_of = 5
        self.temperature = 0
        print("[WhisperRecognizer] Whisper-Modell erfolgreich initialisiert.")

    def detect_silence(self, audio_data, sample_rate, threshold=0.005, min_silence_duration=0.7):
        """Erkennt, ob die Aufnahme hauptsächlich aus Stille besteht."""
        # Konvertiere zu Mono falls stereo
        if len(audio_data.shape) > 1:
            audio_data = audio_data.mean(axis=1)
        
        # Berechne RMS-Amplitude in Zeitfenstern
        window_size = int(sample_rate * 0.1)  # 100ms Fenster
        windows = np.array_split(audio_data, len(audio_data) // window_size)
        
        # Berechne RMS für jedes Fenster
        rms_values = [np.sqrt(np.mean(window**2)) for window in windows if len(window) == window_size]
        
        if not rms_values:  # Keine vollständigen Fenster
            return True
            
        # Zähle Fenster unter dem Schwellenwert
        silent_windows = sum(1 for rms in rms_values if rms < threshold)
        total_windows = len(rms_values)
        
        # Wenn mehr als 90% der Fenster still sind
        if total_windows > 0 and silent_windows / total_windows > 0.9:
            print(f"[WhisperRecognizer] Stille erkannt: {silent_windows}/{total_windows} Fenster unter Schwellenwert")
            return True
            
        return False

    def transcribe_wav(self, audio_path):
        """Transkribiert eine WAV-Datei mit Stilledetektion"""
        print(f"[WhisperRecognizer] Transkribiere WAV: {audio_path}") # DEBUG
        try:
            # Lade Audio-Datei
            # audio_data, sample_rate = sf.read(audio_path)
            
            # Prüfe auf Stille (VORÜBERGEHEND DEAKTIVIERT)
            # if self.detect_silence(audio_data, sample_rate):
            #     print("[WhisperRecognizer] Aufnahme enthält hauptsächlich Stille.")
            #     return None
            
            # Transkribiere nur wenn keine Stille erkannt wurde
            # (Jetzt wird immer transkribiert)
            segments, info = self.model.transcribe(
                audio_path,
                language=self.language,
                beam_size=self.beam_size,
                best_of=self.best_of,
                temperature=self.temperature,
                word_timestamps=True,
                condition_on_previous_text=False,
                compression_ratio_threshold=2.4,
                vad_filter=False, # VAD wieder deaktivieren
                # vad_parameters=dict(min_silence_duration_ms=500) # Auskommentiert, da VAD aus
            )
            
            # Sammle den transkribierten Text
            segment_texts = [segment.text for segment in segments]
            
            if not segment_texts:
                print("[WhisperRecognizer] Keine Sprachsegmente gefunden.") # DEBUG
                return None
                
            text = " ".join(segment_texts)
            text = text.strip()
            
            if text:
                print(f"[WhisperRecognizer] Transkription: '{text}'") # DEBUG
                return text
            else:
                print("[WhisperRecognizer] Leerer Text nach dem Zusammenfügen der Segmente.") # DEBUG
                return None
            
        except Exception as e:
            print(f"[WhisperRecognizer] Fehler bei der Transkription: {str(e)}") # DEBUG
            import traceback
            traceback.print_exc()
            return None
            
    def process_audio(self, audio_data, sample_rate=44100):
        """Verarbeitet Audio-Daten direkt"""
        try:
            # Stelle sicher, dass die Daten Float sind
            if audio_data.dtype != np.float32:
                # Skaliere Int16 zu Float32
                if audio_data.dtype == np.int16:
                     audio_data = audio_data.astype(np.float32) / 32768.0
                else:
                    # Versuche andere Typen zu konvertieren
                    audio_data = audio_data.astype(np.float32)
            
            # Transkription mit Whisper - optimierte Parameter
            segments, info = self.model.transcribe(
                audio_data, 
                sample_rate=sample_rate,
                language=self.language,
                beam_size=5,
                word_timestamps=True,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500)
            )
            
            # Sammle den transkribierten Text
            text = " ".join([segment.text for segment in segments])
            text = text.strip()
            
            if text:
                return text
            else:
                print("Debug: Whisper hat keinen Text zurückgegeben.")
                return None
            
        except Exception as e:
            print(f"Debug: Fehler bei der Spracherkennung (process_audio) - {str(e)}")
            return None 