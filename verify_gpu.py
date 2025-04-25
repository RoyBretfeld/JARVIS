import torch

is_available = torch.cuda.is_available()

print(f"CUDA verfügbar: {is_available}")

if is_available:
    try:
        device_name = torch.cuda.get_device_name(0)
        print(f"Gerätename: {device_name}")
    except Exception as e:
        print(f"Fehler beim Abrufen des Gerätenamens: {e}")
else:
    print("Keine CUDA-fähige GPU gefunden.") 