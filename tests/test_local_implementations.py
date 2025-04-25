import sys
import os
from typing import Dict, List, Tuple

# Füge das src-Verzeichnis zum Python-Pfad hinzu
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from local_packages.speech_recognition import LocalSpeechRecognition
from local_packages.speech_synthesis import LocalSpeechSynthesis
from local_packages.nlp_processor import LocalNLPProcessor

def test_speech_recognition():
    """Test der Spracherkennung"""
    print("\n=== Test Spracherkennung ===")
    try:
        recognizer = LocalSpeechRecognition()
        print("✓ Spracherkennung initialisiert")
        
        # Test der Audioaufnahme
        print("Teste Audioaufnahme (5 Sekunden)...")
        audio_data = recognizer.record_audio(duration=5.0)
        print(f"✓ Audioaufnahme erfolgreich (Datenform: {audio_data.shape})")
        
        # Test der Stilleerkennung
        is_silent = recognizer.detect_silence(audio_data)
        print(f"✓ Stilleerkennung: {'Stille' if is_silent else 'Geräusch'} erkannt")
        
        # Test der Wake-Word-Erkennung
        wake_word_detected = recognizer.detect_wake_word(audio_data)
        print(f"✓ Wake-Word-Erkennung: {'Wake-Word erkannt' if wake_word_detected else 'Kein Wake-Word'}")
        
        return True
    except Exception as e:
        print(f"✗ Fehler bei der Spracherkennung: {str(e)}")
        return False

def test_speech_synthesis():
    """Test der Sprachausgabe"""
    print("\n=== Test Sprachausgabe ===")
    try:
        synthesizer = LocalSpeechSynthesis()
        print("✓ Sprachausgabe initialisiert")
        
        # Test der Sprachsynthese
        print("Teste Sprachausgabe...")
        synthesizer.speak("Test Nachricht")
        print("✓ Sprachausgabe erfolgreich")
        
        return True
    except Exception as e:
        print(f"✗ Fehler bei der Sprachausgabe: {str(e)}")
        return False

def test_nlp_processor():
    """Test der NLP-Verarbeitung"""
    print("\n=== Test NLP-Verarbeitung ===")
    try:
        processor = LocalNLPProcessor()
        print("✓ NLP-Prozessor initialisiert")
        
        # Test verschiedener Befehle
        test_commands = [
            "Wie ist das Wetter heute?",
            "Suche nach Python Tutorial",
            "Erinnerung: Meeting um 14:00 Uhr",
            "Wie spät ist es?"
        ]
        
        for command in test_commands:
            result = processor.process_text(command)
            print(f"\nBefehl: {command}")
            print(f"Intent: {result['intent']}")
            print(f"Konfidenz: {result['confidence']:.2f}")
            print(f"Entitäten: {result['entities']}")
        
        return True
    except Exception as e:
        print(f"✗ Fehler bei der NLP-Verarbeitung: {str(e)}")
        return False

def main():
    """Hauptfunktion"""
    print("Starte Tests der lokalen Implementierungen...")
    
    # Führe alle Tests durch
    speech_recognition_success = test_speech_recognition()
    speech_synthesis_success = test_speech_synthesis()
    nlp_processor_success = test_nlp_processor()
    
    # Zusammenfassung
    print("\n=== Test Zusammenfassung ===")
    print(f"Spracherkennung: {'✓' if speech_recognition_success else '✗'}")
    print(f"Sprachausgabe: {'✓' if speech_synthesis_success else '✗'}")
    print(f"NLP-Verarbeitung: {'✓' if nlp_processor_success else '✗'}")
    
    # Gesamtergebnis
    all_success = all([speech_recognition_success, speech_synthesis_success, nlp_processor_success])
    print(f"\nGesamtergebnis: {'✓ Alle Tests erfolgreich!' if all_success else '✗ Einige Tests fehlgeschlagen.'}")

if __name__ == "__main__":
    main() 