import sys
import pkg_resources
import importlib
import subprocess
from typing import Dict, List, Tuple

def check_python_version() -> Tuple[bool, str]:
    """Überprüft die Python-Version"""
    required_version = (3, 8)
    current_version = sys.version_info[:2]
    is_compatible = current_version >= required_version
    return is_compatible, f"Python {'.'.join(map(str, current_version))}"

def check_package(package_name: str) -> Tuple[bool, str]:
    """Überprüft, ob ein Paket installiert ist und importiert werden kann"""
    try:
        if package_name == "PyAudio":
            import pyaudio
            version = pyaudio.__version__
            return True, f"PyAudio {version}"
        else:
            # Versuche das Paket zu importieren
            importlib.import_module(package_name)
            # Hole die installierte Version
            version = pkg_resources.get_distribution(package_name).version
            return True, f"{package_name} {version}"
    except ImportError as e:
        return False, f"{package_name} nicht gefunden: {str(e)}"
    except Exception as e:
        return False, f"Fehler bei {package_name}: {str(e)}"

def check_system_dependencies() -> List[Tuple[str, bool, str]]:
    """Überprüft System-Abhängigkeiten"""
    results = []
    
    # Überprüfe Python-Version
    is_compatible, version = check_python_version()
    results.append(("Python", is_compatible, version))
    
    # Überprüfe wichtige Pakete
    packages = [
        "PyQt5",
        "PyAudio",
        "vosk",
        "numpy",
        "soundfile",
        "requests",
        "tqdm"
    ]
    
    for package in packages:
        is_installed, version = check_package(package)
        results.append((package, is_installed, version))
    
    return results

def print_results(results: List[Tuple[str, bool, str]]):
    """Gibt die Testergebnisse formatiert aus"""
    print("\n=== Abhängigkeits-Check ===")
    print("-" * 50)
    print(f"{'Paket':<20} {'Status':<10} {'Version/Info'}")
    print("-" * 50)
    
    all_passed = True
    for package, is_installed, version in results:
        status = "✓" if is_installed else "✗"
        print(f"{package:<20} {status:<10} {version}")
        if not is_installed:
            all_passed = False
    
    print("-" * 50)
    if all_passed:
        print("\n✓ Alle Abhängigkeiten sind korrekt installiert!")
    else:
        print("\n✗ Einige Abhängigkeiten fehlen oder sind nicht korrekt installiert.")
        print("Bitte installieren Sie die fehlenden Pakete mit:")
        print("pip install -r requirements.txt")

def main():
    """Hauptfunktion"""
    print("Starte Abhängigkeits-Check...")
    results = check_system_dependencies()
    print_results(results)

if __name__ == "__main__":
    main() 