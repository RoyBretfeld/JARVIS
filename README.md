# J.A.R.V.I.S. - Sprachassistent

Ein Python-basierter Sprachassistent mit grafischer Benutzeroberfläche.

## Installation

### Voraussetzungen
- Python 3.8 oder höher
- Windows 10/11

### Lokale Installation

1. Klonen Sie das Repository:
```bash
git clone https://github.com/IhrUsername/JARVIS.git
cd JARVIS
```

2. Erstellen Sie eine virtuelle Umgebung:
```bash
python -m venv venv
.\venv\Scripts\activate
```

3. Installieren Sie die lokalen Pakete:
```bash
python install_local.py
```

4. Starten Sie die Anwendung:
```bash
python src/gui/app.py
```

## Funktionen
- Spracherkennung (offline)
- Grafische Benutzeroberfläche
- Audio-Aufnahme und -Wiedergabe
- Konversationshistorie

## Projektstruktur
```
JARVIS/
├── data/
│   ├── audio/
│   └── models/
├── lib/
│   └── packages/     # Lokale Python-Pakete
├── src/
│   ├── gui/
│   └── speech/
├── requirements.txt
└── install_local.py
```

## Lizenz
MIT License
