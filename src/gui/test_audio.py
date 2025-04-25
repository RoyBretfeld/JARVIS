import pyaudio
import wave
import numpy as np
import time
import os
from datetime import datetime
import matplotlib.pyplot as plt

def analyze_audio_data(audio_array, sample_rate):
    """Analysiert die Audio-Daten detailliert"""
    # Berechne Frequenzspektrum
    fft_data = np.fft.fft(audio_array)
    freqs = np.fft.fftfreq(len(audio_array), 1/sample_rate)
    
    # Berechne Signalstärke
    signal_strength = np.abs(audio_array).mean()
    signal_peak = np.abs(audio_array).max()
    
    # Berechne Signal-Rausch-Verhältnis (SNR)
    noise_floor = np.percentile(np.abs(audio_array), 10)
    signal_peak = np.percentile(np.abs(audio_array), 90)
    snr = 20 * np.log10(signal_peak / noise_floor) if noise_floor > 0 else 0
    
    return {
        'samples': len(audio_array),
        'duration': len(audio_array) / sample_rate,
        'mean': np.mean(audio_array),
        'std': np.std(audio_array),
        'max': np.max(audio_array),
        'min': np.min(audio_array),
        'signal_strength': signal_strength,
        'signal_peak': signal_peak,
        'snr': snr,
        'freqs': freqs,
        'fft_data': fft_data
    }

def plot_audio_analysis(audio_array, analysis, save_path):
    """Erstellt Visualisierungen der Audio-Analyse"""
    plt.figure(figsize=(15, 10))
    
    # Zeitverlauf
    plt.subplot(3, 1, 1)
    time = np.arange(len(audio_array)) / 44100
    plt.plot(time, audio_array)
    plt.title('Zeitverlauf')
    plt.xlabel('Zeit (s)')
    plt.ylabel('Amplitude')
    
    # Frequenzspektrum
    plt.subplot(3, 1, 2)
    plt.plot(analysis['freqs'][:len(analysis['freqs'])//2], 
             np.abs(analysis['fft_data'])[:len(analysis['freqs'])//2])
    plt.title('Frequenzspektrum')
    plt.xlabel('Frequenz (Hz)')
    plt.ylabel('Amplitude')
    
    # Histogramm
    plt.subplot(3, 1, 3)
    plt.hist(audio_array, bins=100, density=True)
    plt.title('Amplitudenverteilung')
    plt.xlabel('Amplitude')
    plt.ylabel('Häufigkeit')
    
    plt.tight_layout()
    plt.savefig(save_path)
    plt.close()

def test_audio_recording():
    """Testet die Audioaufnahme mit verschiedenen Einstellungen"""
    # Audio-Parameter
    CHUNK = 2048
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 44100
    RECORD_SECONDS = 5
    
    # Erstelle Test-Ordner
    test_dir = os.path.join("data", "audio", "tests")
    os.makedirs(test_dir, exist_ok=True)
    
    try:
        # Initialisiere PyAudio
        p = pyaudio.PyAudio()
        
        # Liste alle verfügbaren Geräte
        print("\nVerfügbare Audio-Geräte:")
        for i in range(p.get_device_count()):
            device_info = p.get_device_info_by_index(i)
            print(f"Index {i}: {device_info['name']}")
            print(f"  Max Input Channels: {device_info['maxInputChannels']}")
            print(f"  Default Sample Rate: {device_info['defaultSampleRate']}")
            print(f"  Default Low Input Latency: {device_info['defaultLowInputLatency']}")
            print(f"  Default High Input Latency: {device_info['defaultHighInputLatency']}")
            print()
        
        # Wähle das Standard-Eingabegerät
        default_device = p.get_default_input_device_info()
        print(f"\nStandard-Eingabegerät: {default_device['name']} (Index: {default_device['index']})")
        
        # Öffne den Stream
        stream = p.open(format=FORMAT,
                       channels=CHANNELS,
                       rate=RATE,
                       input=True,
                       frames_per_buffer=CHUNK)
        
        print(f"\nStarte Aufnahmetest mit {RATE} Hz...")
        print("Sprechen Sie bitte für 5 Sekunden...")
        
        # Buffer für die Audio-Daten
        frames = []
        audio_data = []
        
        # Aufnahme mit DC-Offset-Korrektur und sanfter Normalisierung
        max_amplitude = 0
        min_amplitude = 0
        sum_samples = 0
        sample_count = 0
        
        # Erste Phase: DC-Offset berechnen
        for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
            data = stream.read(CHUNK, exception_on_overflow=False)
            chunk_data = np.frombuffer(data, dtype=np.int16)
            sum_samples += np.sum(chunk_data)
            sample_count += len(chunk_data)
            frames.append(data)
            audio_data.extend(chunk_data)
        
        print("Aufnahme beendet")
        
        # DC-Offset berechnen und korrigieren
        dc_offset = int(sum_samples / sample_count)
        print(f"DC-Offset: {dc_offset}")
        
        # Konvertiere zu numpy array
        audio_array = np.array(audio_data)
        
        # DC-Offset korrigieren
        audio_array = audio_array - dc_offset
        
        # Sanfte Normalisierung (nur wenn nötig)
        max_amplitude = np.max(np.abs(audio_array))
        if max_amplitude > 32767 * 0.9:  # Nur normalisieren wenn über 90% des Dynamikbereichs
            scale_factor = 32767 * 0.9 / max_amplitude
            audio_array = np.int16(audio_array * scale_factor)
            print(f"Normalisierung angewendet (Faktor: {scale_factor:.3f})")
        
        # Detaillierte Analyse
        analysis = analyze_audio_data(audio_array, RATE)
        
        # Ausgabe der Analyse
        print(f"\nDetaillierte Audio-Analyse:")
        print(f"Anzahl Samples: {analysis['samples']}")
        print(f"Aufnahmedauer: {analysis['duration']:.2f} Sekunden")
        print(f"Sample-Rate: {RATE} Hz")
        print(f"Maximaler Wert: {analysis['max']}")
        print(f"Minimaler Wert: {analysis['min']}")
        print(f"Durchschnittlicher Wert: {analysis['mean']:.2f}")
        print(f"Standardabweichung: {analysis['std']:.2f}")
        print(f"Signalstärke: {analysis['signal_strength']:.2f}")
        print(f"Signal-Peak: {analysis['signal_peak']:.2f}")
        print(f"Signal-Rausch-Verhältnis (SNR): {analysis['snr']:.2f} dB")
        
        # Speichere die Aufnahme
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"test_recording_{timestamp}.wav"
        filepath = os.path.join(test_dir, filename)
        
        with wave.open(filepath, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(p.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(audio_array.tobytes())
        
        print(f"\nAufnahme gespeichert: {filepath}")
        
        # Erstelle und speichere Visualisierung
        plot_filename = f"test_recording_{timestamp}_analysis.png"
        plot_filepath = os.path.join(test_dir, plot_filename)
        plot_audio_analysis(audio_array, analysis, plot_filepath)
        print(f"Analyse-Visualisierung gespeichert: {plot_filepath}")
        
        # Cleanup
        stream.stop_stream()
        stream.close()
        p.terminate()
        
        return True
        
    except Exception as e:
        print(f"\nFehler beim Audio-Test: {str(e)}")
        return False

if __name__ == "__main__":
    print("Starte Audio-Test...")
    success = test_audio_recording()
    if success:
        print("\nAudio-Test erfolgreich abgeschlossen!")
    else:
        print("\nAudio-Test fehlgeschlagen!") 