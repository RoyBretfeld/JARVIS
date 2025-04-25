import pytest
import os
import sys

# Füge das Hauptverzeichnis zum Python-Pfad hinzu
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

@pytest.fixture
def test_data_dir():
    """Gibt den Pfad zum Testdatenverzeichnis zurück"""
    return os.path.join(os.path.dirname(__file__), 'test_data')

@pytest.fixture
def mock_config():
    """Gibt eine Test-Konfiguration zurück"""
    return {
        'speech': {
            'wake_word': 'Jarvis',
            'language': 'de-DE'
        },
        'nlp': {
            'model': 'test_model'
        }
    }

@pytest.fixture
def temp_dir(tmp_path):
    """Gibt ein temporäres Verzeichnis für Tests zurück"""
    return tmp_path 