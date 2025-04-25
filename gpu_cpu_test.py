from faster_whisper import WhisperModel
import time
import wave
import numpy as np
import os
from tqdm import tqdm

def create_test_wav(filename="test.wav", duration=10, sample_rate=16000):
    """Erstellt eine Test-WAV-Datei mit einem Sinuston"""
    # Sinuston generieren (440 Hz = Kammerton A)
    t = np.linspace(0, duration, int(sample_rate * duration))
    samples = np.sin(2 * np.pi * 440 * t)
    samples = (samples * 32767).astype(np.int16)
    
    # Als WAV-Datei speichern
    with wave.open(filename, 'wb') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(samples.tobytes())
    
    return filename

def run_transcription_test(model_type, audio_file):
    """Führt den Transkriptionstest durch"""
    print(f"\nStarte Test mit {model_type.upper()}...")
    
    # Modell laden
    if model_type == "gpu":
        model = WhisperModel("small", device="cuda", compute_type="float16")
    else:
        model = WhisperModel("small", device="cpu", compute_type="float32")
    
    # Zeitmessung für 3 Durchläufe
    times = []
    for i in tqdm(range(3), desc=f"{model_type.upper()} Durchläufe"):
        start_time = time.time()
        segments, _ = model.transcribe(audio_file)
        list(segments)  # Durchlaufen der Segmente
        end_time = time.time()
        times.append(end_time - start_time)
    
    return sum(times) / len(times)

def main():
    # Test-Audiodatei erstellen
    print("Erstelle Test-Audiodatei...")
    audio_file = create_test_wav(duration=30)  # 30 Sekunden Testton
    
    try:
        # GPU-Test
        gpu_time = run_transcription_test("gpu", audio_file)
        
        # CPU-Test
        cpu_time = run_transcription_test("cpu", audio_file)
        
        # Ergebnisse ausgeben
        print("\n" + "="*50)
        print("BENCHMARK ERGEBNISSE")
        print("="*50)
        print(f"CPU Durchschnittszeit: {cpu_time:.2f} Sekunden")
        print(f"GPU Durchschnittszeit: {gpu_time:.2f} Sekunden")
        print(f"Geschwindigkeitsvorteil GPU: {cpu_time/gpu_time:.1f}x schneller")
        print("="*50)
        
    finally:
        # Aufräumen
        if os.path.exists(audio_file):
            os.remove(audio_file)

if __name__ == "__main__":
    main() 