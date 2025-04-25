from faster_whisper import WhisperModel
import time
import torch
import os
from tqdm import tqdm
import numpy as np

def create_test_audio(duration=10, sample_rate=16000):
    """Erstellt eine Test-Audiodatei mit weißem Rauschen"""
    # Weißes Rauschen generieren (10 Sekunden)
    samples = np.random.normal(0, 1, size=(duration * sample_rate,)).astype(np.float32)
    # Normalisieren
    samples = samples / np.max(np.abs(samples))
    return samples

def load_model(device, compute_type):
    print(f"\nLade Modell auf {device.upper()}...")
    return WhisperModel("small", device=device, compute_type=compute_type)

def run_benchmark(model, name, audio):
    print(f"\nStarte Benchmark auf {name}...")
    times = []
    
    # Mehrere Durchläufe für stabilere Ergebnisse
    for _ in tqdm(range(5), desc=f"{name} Durchläufe"):
        start_time = time.time()
        segments, _ = model.transcribe(audio)
        # Liste durchlaufen um sicherzustellen, dass alles verarbeitet wurde
        list(segments)
        end_time = time.time()
        times.append(end_time - start_time)
    
    avg_time = sum(times) / len(times)
    return avg_time

def print_results(cpu_time, gpu_time):
    print("\n" + "="*50)
    print("BENCHMARK ERGEBNISSE")
    print("="*50)
    print(f"CPU Durchschnittszeit: {cpu_time:.2f} Sekunden")
    print(f"GPU Durchschnittszeit: {gpu_time:.2f} Sekunden")
    print(f"Geschwindigkeitsvorteil GPU: {cpu_time/gpu_time:.1f}x schneller")
    print("="*50)

def main():
    # Test-Audio erstellen
    print("Erstelle Test-Audio...")
    audio = create_test_audio(duration=30)  # 30 Sekunden Audio
    
    # GPU Benchmark
    gpu_model = load_model("cuda", "float16")
    gpu_time = run_benchmark(gpu_model, "GPU", audio)
    
    # CPU Benchmark
    cpu_model = load_model("cpu", "float32")
    cpu_time = run_benchmark(cpu_model, "CPU", audio)
    
    print_results(cpu_time, gpu_time)

if __name__ == "__main__":
    main() 