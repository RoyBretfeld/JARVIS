import os
from vosk import Model, KaldiRecognizer, SetLogLevel
import wave
import json
import mmap
import numpy as np
import pyaudio
import time
import soundfile as sf
import librosa

class SpeechRecognizer:
    def __init__(self, model_path="data/models/vosk-model-de", progress_callback=None):
        self.model_path = model_path
        self.model = None
        self.recognizer = None  # Initialisiere recognizer mit None
        self.progress_callback = progress_callback
        # Reduziere Log-Level für schnelleres Laden
        SetLogLevel(-1)
        self.initialize()
        
    def _update_progress(self, value, text):
        """Aktualisiert den Ladefortschritt"""
        if self.progress_callback:
            self.progress_callback(value, text)
    
    def initialize(self):
        """Initialisiert das Vosk-Modell und den Recognizer"""
        if not os.path.exists(self.model_path):
            print(f"Fehler: Sprachmodell nicht gefunden in {self.model_path}")
            return False
            
        try:
            if self.model is None:
                print(f"Debug: Lade Sprachmodell aus {self.model_path}")
                self._update_progress(10, "Initialisiere Modell...")
                self.model = Model(self.model_path)
                print("Debug: Sprachmodell erfolgreich geladen")
                
            # Erstelle den Recognizer NACHDEM das Modell geladen wurde
            if self.model and self.recognizer is None:
                target_sr = 16000 # Die Sample Rate, die das Modell erwartet
                print(f"Debug: Erstelle KaldiRecognizer mit Sample Rate {target_sr}")
                self.recognizer = KaldiRecognizer(self.model, target_sr)
                self.recognizer.SetWords(True) # Optional: für Wort-Zeitstempel
                print("Debug: KaldiRecognizer erfolgreich erstellt")
            
            self._update_progress(100, "Modell erfolgreich initialisiert")
            return True
                
        except Exception as e:
            print(f"Fehler beim Initialisieren von Vosk: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            self.model = None
            self.recognizer = None
            return False
    
    def transcribe_wav(self, wav_file):
        """Transkribiert eine WAV-Datei (aus Datei oder BytesIO)"""
        if not self.model or not self.recognizer:
            if not self.initialize():
                return None

        try:
            # Lese die WAV-Daten und die Sample Rate
            # Verwende soundfile, da es flexibler mit BytesIO ist
            audio_data, original_sr = sf.read(wav_file, dtype='float32')
            print(f"Debug: WAV gelesen - Länge: {len(audio_data)}, Original SR: {original_sr}")

            # Stelle sicher, dass die Daten Mono sind
            if audio_data.ndim > 1:
                print("Debug: Konvertiere Stereo zu Mono")
                audio_data = librosa.to_mono(audio_data.T) # Transponieren für librosa

            # === Resample auf 16000 Hz ===
            target_sr = 16000
            if original_sr != target_sr:
                print(f"Debug: Resample von {original_sr} Hz zu {target_sr} Hz")
                audio_data = librosa.resample(audio_data, orig_sr=original_sr, target_sr=target_sr)
                print(f"Debug: Resampled Länge: {len(audio_data)}")
            else:
                print("Debug: Sample Rate ist bereits 16000 Hz, kein Resampling nötig.")

            # Konvertiere zu 16-bit Integer für Vosk
            audio_data_int16 = (audio_data * 32767).astype(np.int16)

            # Transkription
            print("Debug: Starte Vosk AcceptWaveform...")
            self.recognizer.AcceptWaveform(audio_data_int16.tobytes())
            result = json.loads(self.recognizer.FinalResult())
            text = result.get("text", "").strip()
            print(f"Debug: Vosk Ergebnis: {text}")

            if text:
                return text
            else:
                print("Debug: Vosk hat keinen Text zurückgegeben.")
                return None

        except Exception as e:
            print(f"Debug: Fehler in transcribe_wav - {str(e)}")
            import traceback
            print(f"Debug: Traceback - {traceback.format_exc()}")
            return None

    def process_audio(self, audio_data, sample_rate=44100):
        """Verarbeitet Audio-Daten direkt aus dem numpy array"""
        if not self.model or not self.recognizer:
            if not self.initialize():
                return None
                
        try:
            print(f"Debug: process_audio - Länge: {len(audio_data)}, SR: {sample_rate}")

            # Stelle sicher, dass die Daten Float sind für Librosa
            if audio_data.dtype != np.float32:
                # Skaliere Int16 zu Float32
                if audio_data.dtype == np.int16:
                     audio_data = audio_data.astype(np.float32) / 32768.0
                else:
                    # Versuche andere Typen zu konvertieren (kann fehlschlagen)
                    audio_data = audio_data.astype(np.float32)

            # === Resample auf 16000 Hz ===
            target_sr = 16000
            if sample_rate != target_sr:
                print(f"Debug: process_audio - Resample von {sample_rate} Hz zu {target_sr} Hz")
                audio_data = librosa.resample(audio_data, orig_sr=sample_rate, target_sr=target_sr)
                print(f"Debug: process_audio - Resampled Länge: {len(audio_data)}")
            else:
                print("Debug: process_audio - Sample Rate ist bereits 16000 Hz.")

            # Konvertiere zu 16-bit int für Vosk
            audio_data_int16 = (audio_data * 32767).astype(np.int16)
            
            # Sende die kompletten Daten
            print("Debug: process_audio - Starte Vosk AcceptWaveform...")
            self.recognizer.AcceptWaveform(audio_data_int16.tobytes())
            
            # Hole das finale Ergebnis
            result = json.loads(self.recognizer.FinalResult())
            text = result.get("text", "").strip()
            print(f"Debug: process_audio - Vosk Ergebnis: {text}")
            
            if text:
                return text
            else:
                print("Debug: process_audio - Vosk hat keinen Text zurückgegeben.")
                return None
            
        except Exception as e:
            print(f"Debug: Fehler bei der Spracherkennung (process_audio) - {str(e)}")
            import traceback
            print(f"Debug: Traceback - {traceback.format_exc()}")
            return None 