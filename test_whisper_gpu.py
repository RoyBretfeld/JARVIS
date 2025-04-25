from faster_whisper import WhisperModel

print("Initialisiere Whisper-Modell mit GPU-Unterstützung...")
model = WhisperModel("small", device="cuda", compute_type="float16")
print("Modell erfolgreich geladen!")
print(f"Gerät: {model.model.device}")
print(f"Compute Type: {model.model.compute_type}") 