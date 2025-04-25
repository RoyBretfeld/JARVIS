import os
import sys
import subprocess
from pathlib import Path

def install_local_packages():
    """Installiert alle lokalen Python-Pakete"""
    # Pfad zu den lokalen Paketen
    packages_dir = Path("lib/packages")
    
    if not packages_dir.exists():
        print("Fehler: Pakete-Verzeichnis nicht gefunden!")
        return False
    
    # Liste alle .whl und .tar.gz Dateien
    package_files = list(packages_dir.glob("*.whl")) + list(packages_dir.glob("*.tar.gz"))
    
    if not package_files:
        print("Fehler: Keine Pakete gefunden!")
        return False
    
    print(f"Gefundene Pakete: {len(package_files)}")
    
    # Installiere jedes Paket
    for package in package_files:
        print(f"\nInstalliere {package.name}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--no-index", "--find-links", str(packages_dir), str(package)])
            print(f"✓ {package.name} erfolgreich installiert")
        except subprocess.CalledProcessError as e:
            print(f"✗ Fehler beim Installieren von {package.name}: {str(e)}")
            return False
    
    print("\nAlle Pakete wurden erfolgreich installiert!")
    return True

if __name__ == "__main__":
    install_local_packages() 