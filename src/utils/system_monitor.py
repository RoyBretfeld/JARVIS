import psutil
import GPUtil
from PyQt6.QtCore import QTimer, QObject, pyqtSignal
from typing import Dict, List

class SystemMonitor(QObject):
    """Überwacht CPU und GPU Auslastung"""
    
    # Signale für Updates
    cpu_update = pyqtSignal(float)  # CPU Auslastung in Prozent
    gpu_update = pyqtSignal(float)  # GPU Auslastung in Prozent
    memory_update = pyqtSignal(float)  # Speicherauslastung in Prozent
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_stats)
        self.timer.start(1000)  # Update jede Sekunde
        
        # Initialisiere GPU-Monitoring
        self.gpus = []
        try:
            self.gpus = GPUtil.getGPUs()
        except:
            print("Keine NVIDIA GPU gefunden")
    
    def update_stats(self):
        """Aktualisiert die System-Statistiken"""
        # CPU Auslastung
        cpu_percent = psutil.cpu_percent(interval=1)
        self.cpu_update.emit(cpu_percent)
        
        # GPU Auslastung
        if self.gpus:
            try:
                gpu_percent = self.gpus[0].load * 100
                self.gpu_update.emit(gpu_percent)
            except:
                self.gpu_update.emit(0.0)
        else:
            self.gpu_update.emit(0.0)
        
        # Speicherauslastung
        memory_percent = psutil.virtual_memory().percent
        self.memory_update.emit(memory_percent)
    
    def get_gpu_info(self) -> Dict:
        """Gibt Informationen über die GPU zurück"""
        if not self.gpus:
            return {"name": "Keine GPU", "memory_total": 0, "memory_used": 0}
        
        gpu = self.gpus[0]
        return {
            "name": gpu.name,
            "memory_total": gpu.memoryTotal,
            "memory_used": gpu.memoryUsed
        } 