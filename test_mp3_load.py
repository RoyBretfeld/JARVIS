# test_mp3_load.py
import sys
import os
from pydub import AudioSegment
import numpy as np

# --- BITTE ANPASSEN: Pfad zur MP3-Datei ---
# Verwenden Sie einen der Pfade aus den Logs, z.B.:
mp3_file_path = r"E:/Hoerbuecher_Global-1.Wahl/Die ganze Welt des Wissens 2 2015/Die ganze Welt des Wissens 2 - 04 - Das Auge/Die Welt des Wissens 2 - 04 - Das Auge - 01.mp3"
# -----------------------------------------

print(f"Versuche, MP3-Datei zu laden: {mp3_file_path}")

# Optional: FFmpeg Pfad-Workaround auch hier anwenden
try:
    ffmpeg_bin_path = r"C:\ffmpeg\bin"
    current_path = os.environ.get("PATH", "")
    if ffmpeg_bin_path not in current_path:
        print(f"INFO: Füge {ffmpeg_bin_path} zu PATH hinzu...")
        os.environ["PATH"] = ffmpeg_bin_path + os.pathsep + current_path
except Exception as path_e:
    print(f"WARNUNG: Fehler beim Setzen des FFmpeg PATH: {path_e}")

try:
    # Versuche, die MP3-Datei mit pydub zu laden
    print("INFO: Rufe AudioSegment.from_mp3(...) auf...")
    audio = AudioSegment.from_mp3(mp3_file_path)
    print("INFO: AudioSegment.from_mp3(...) erfolgreich beendet.")

    # Konvertiere zu Numpy Array (optional, nur zum Test)
    print("INFO: Konvertiere zu Numpy Array...")
    samples = np.array(audio.get_array_of_samples()).astype(np.float32)
    print(f"INFO: Konvertierung erfolgreich. Shape: {samples.shape}, dtype: {samples.dtype}")

    print("\n----\nERFOLG: MP3-Datei konnte geladen und verarbeitet werden.\n----")

except Exception as e:
    print(f"\n----\nFEHLER: Beim Laden/Verarbeiten der MP3-Datei ist ein Fehler aufgetreten.")
    print(f"Fehlertyp: {type(e).__name__}")
    print(f"Fehlermeldung: {e}")
    import traceback
    traceback.print_exc()
    print("----\n")
    sys.exit(1) # Beende mit Fehlercode

sys.exit(0) # Beende erfolgreich 