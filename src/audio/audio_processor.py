import os
import numpy as np
from scipy import signal
from scipy.io import wavfile
import noisereduce as nr
import soundfile as sf
from typing import Tuple
import traceback
import logging

logger = logging.getLogger(__name__)

class AudioProcessor:
    def __init__(self):
        """Initialisiert den AudioProcessor"""
        logger.info("Initialisiere AudioProcessor...")
        self.sample_rate = 44100
        self.chunk_size = 2048
        self.channels = 1
        
        # Audio-Parameter
        self.noise_reduction_strength = 0.25
        self.gain = 1.0
        self.threshold = -30  # dB
        self.attack_time = 0.005
        self.release_time = 0.1
        
        # Stelle sicher, dass die Verzeichnisstruktur existiert
        self.recordings_dir = "data/audio/recordings"
        os.makedirs(self.recordings_dir, exist_ok=True)
        logger.info(f"Recordings Verzeichnis initialisiert: {self.recordings_dir}")
        
    def process_audio(self, audio_data: bytes) -> Tuple[np.ndarray, int]:
        """Verarbeitet Audiodaten"""
        try:
            logger.info("[AudioProcessor] Starte Audioverarbeitung...")
            
            # Konvertiere zu NumPy Array
            logger.debug("[AudioProcessor] Konvertiere zu NumPy Array...")
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            logger.debug(f"[AudioProcessor] Audio Array Shape: {audio_array.shape}, Dtype: {audio_array.dtype}")
            
            if len(audio_array) == 0:
                raise ValueError("Leere Audiodaten empfangen")
            
            # Normalisiere auf [-1, 1]
            logger.debug("[AudioProcessor] Normalisiere Audio...")
            audio_float = audio_array.astype(np.float32) / 32767.0
            
            # Rauschunterdrückung
            logger.debug("[AudioProcessor] Wende Rauschunterdrückung an...")
            audio_reduced = nr.reduce_noise(
                y=audio_float,
                sr=self.sample_rate,
                prop_decrease=self.noise_reduction_strength,
                n_fft=2048
            )
            
            # Hochpassfilter (entfernt tieffrequentes Rauschen)
            logger.debug("[AudioProcessor] Wende Hochpassfilter an...")
            sos = signal.butter(10, 80, 'hp', fs=self.sample_rate, output='sos')
            audio_filtered = signal.sosfilt(sos, audio_reduced)
            
            # Kompressor/Limiter
            logger.debug("[AudioProcessor] Wende Kompressor an...")
            audio_compressed = self.apply_compressor(audio_filtered)
            
            # Normalisiere Lautstärke
            logger.debug("[AudioProcessor] Normalisiere Lautstärke...")
            max_val = np.max(np.abs(audio_compressed))
            if max_val > 0:
                audio_compressed = audio_compressed / max_val * 0.95
                
            # Konvertiere zurück zu int16
            logger.debug("[AudioProcessor] Konvertiere zurück zu int16...")
            audio_processed = (audio_compressed * 32767).astype(np.int16)
            
            logger.info("[AudioProcessor] Audioverarbeitung erfolgreich abgeschlossen.")
            return audio_processed, self.sample_rate
            
        except Exception as e:
            logger.error(f"[AudioProcessor] Fehler bei der Audioverarbeitung: {str(e)}")
            logger.error(traceback.format_exc())
            return None, None
            
    def apply_compressor(self, audio: np.ndarray) -> np.ndarray:
        """Wendet einen dynamischen Kompressor an"""
        try:
            # Konvertiere Threshold von dB zu linear
            threshold_linear = 10 ** (self.threshold / 20)
            
            # Berechne Envelope
            attack_samples = int(self.attack_time * self.sample_rate)
            release_samples = int(self.release_time * self.sample_rate)
            
            # RMS-Level
            rms = np.sqrt(np.convolve(audio**2, np.ones(2048)/2048, mode='same'))
            
            # Kompressionsrate
            ratio = 4  # 4:1 Kompression
            
            # Berechne Gain Reduction
            gain_db = np.zeros_like(audio)
            mask = rms > threshold_linear
            gain_db[mask] = (self.threshold + ((20 * np.log10(rms[mask])) - self.threshold) / ratio) - 20 * np.log10(rms[mask])
            
            # Smoothing
            gain_linear = 10 ** (gain_db / 20)
            smoothed_gain = signal.lfilter([1], [1, -0.99], gain_linear)
            
            # Wende Kompression an
            compressed = audio * smoothed_gain
            
            # Make-up Gain
            makeup_gain = 1 / (10 ** (self.threshold * (1 - 1/ratio) / 20))
            compressed *= makeup_gain
            
            return compressed
            
        except Exception as e:
            print(f"Fehler beim Anwenden des Kompressors: {str(e)}")
            return audio
            
    def save_wav(self, audio_data: np.ndarray, filename: str):
        """Speichert Audiodaten als WAV"""
        try:
            sf.write(
                filename,
                audio_data,
                self.sample_rate,
                format='WAV',
                subtype='PCM_16'
            )
            return True
        except Exception as e:
            print(f"Fehler beim Speichern der WAV-Datei: {str(e)}")
            return False
            
    def analyze_audio(self, audio_data: np.ndarray) -> dict:
        """Analysiert Audiodaten"""
        try:
            # RMS Level
            rms = np.sqrt(np.mean(audio_data**2))
            
            # Peak Level
            peak = np.max(np.abs(audio_data))
            
            # Crest Factor (Peak to RMS ratio)
            crest_factor = 20 * np.log10(peak/rms) if rms > 0 else 0
            
            # Spektralanalyse
            frequencies, times, spectrogram = signal.spectrogram(
                audio_data,
                fs=self.sample_rate,
                nperseg=2048,
                noverlap=1024
            )
            
            # Durchschnittliches Spektrum
            avg_spectrum = np.mean(spectrogram, axis=1)
            
            return {
                "rms_level_db": 20 * np.log10(rms) if rms > 0 else -100,
                "peak_level_db": 20 * np.log10(peak) if peak > 0 else -100,
                "crest_factor_db": crest_factor,
                "spectral_centroid": np.average(frequencies, weights=avg_spectrum)
            }
            
        except Exception as e:
            print(f"Fehler bei der Audioanalyse: {str(e)}")
            return {} 