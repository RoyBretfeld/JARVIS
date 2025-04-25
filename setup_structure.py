import os
import yaml

def create_directory_structure(base_path):
    print(f"Erstelle Verzeichnisstruktur in: {base_path}")
    
    # Hauptverzeichnisse
    directories = [
        'docs/api',
        'docs/user',
        'docs/developer',
        'src/core',
        'src/speech',
        'src/nlp',
        'src/ml',
        'src/gui/widgets',
        'src/gui/screens',
        'src/api',
        'src/utils',
        'data/models/speech',
        'data/models/nlp',
        'data/models/ml',
        'data/user/preferences',
        'data/user/history',
        'data/system/logs',
        'data/system/cache',
        'tests/unit',
        'tests/integration',
        'tests/e2e',
        'config'
    ]

    # Erstelle alle Verzeichnisse
    for dir_path in directories:
        full_path = os.path.join(base_path, dir_path)
        os.makedirs(full_path, exist_ok=True)
        print(f"Verzeichnis erstellt: {full_path}")

    # Erstelle __init__.py Dateien
    init_paths = [
        'src',
        'src/core',
        'src/speech',
        'src/nlp',
        'src/ml',
        'src/gui',
        'src/api',
        'src/utils',
        'tests'
    ]

    for init_path in init_paths:
        init_file = os.path.join(base_path, init_path, '__init__.py')
        open(init_file, 'a').close()
        print(f"Datei erstellt: {init_file}")

    # Erstelle config.yaml
    config = {
        'speech': {
            'wake_word': 'Jarvis',
            'language': 'de-DE',
            'voice_id': 'default'
        },
        'nlp': {
            'model': 'spacy_de_core_news_lg',
            'context_memory_size': 5
        },
        'gui': {
            'theme': 'dark',
            'dashboard_widgets': ['weather', 'calendar', 'system_status']
        }
    }

    config_path = os.path.join(base_path, 'config', 'config.yaml')
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    print(f"Datei erstellt: {config_path}")

    # Erstelle logging.yaml
    logging_config = {
        'version': 1,
        'formatters': {
            'standard': {
                'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
            }
        },
        'handlers': {
            'file': {
                'class': 'logging.FileHandler',
                'filename': 'data/system/logs/jarvis.log',
                'formatter': 'standard'
            }
        },
        'root': {
            'level': 'INFO',
            'handlers': ['file']
        }
    }

    logging_path = os.path.join(base_path, 'config', 'logging.yaml')
    with open(logging_path, 'w', encoding='utf-8') as f:
        yaml.dump(logging_config, f, default_flow_style=False)
    print(f"Datei erstellt: {logging_path}")

    # Erstelle README.md
    readme_content = """# J.A.R.V.I.S. Assistenzsystem

Ein intelligentes persönliches Assistenzsystem im Stil von J.A.R.V.I.S.

## Funktionen

- Spracherkennung und -verarbeitung
- Dialogfähigkeit
- Lernfähigkeit
- Informationsverarbeitung
- Persönliche Assistenz
- Systemsteuerung

## Installation

1. Python 3.8 oder höher installieren
2. Abhängigkeiten installieren: `pip install -r requirements.txt`
3. Konfiguration in `config/config.yaml` anpassen
4. System starten: `python jarvis.py`

## Entwicklung

- Dokumentation: siehe `docs/`
- Tests ausführen: `python -m pytest tests/`
"""
    readme_path = os.path.join(base_path, 'README.md')
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    print(f"Datei erstellt: {readme_path}")

    # Erstelle requirements.txt
    requirements = """pyttsx3>=2.90
SpeechRecognition>=3.8.1
PyAudio>=0.2.11
spacy>=3.0.0
PyYAML>=5.4.1
PyQt5>=5.15.0
python-dotenv>=0.19.0
requests>=2.26.0
numpy>=1.19.0
pandas>=1.3.0
scikit-learn>=0.24.0
pytest>=6.2.5
"""
    requirements_path = os.path.join(base_path, 'requirements.txt')
    with open(requirements_path, 'w', encoding='utf-8') as f:
        f.write(requirements)
    print(f"Datei erstellt: {requirements_path}")

if __name__ == "__main__":
    base_path = os.path.dirname(os.path.abspath(__file__))
    try:
        create_directory_structure(base_path)
        print("\nVerzeichnisstruktur wurde erfolgreich erstellt!")
    except Exception as e:
        print(f"\nFehler beim Erstellen der Verzeichnisstruktur: {e}")