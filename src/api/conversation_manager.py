from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class Message:
    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)

class ConversationManager:
    def __init__(self, max_context_length: int = 10):
        """Initialisiert den Konversationsmanager."""
        self.conversation_history: List[Message] = []
        self.max_context_length = max_context_length
        
    def add_message(self, role: str, content: str):
        """Fügt eine neue Nachricht zur Konversationshistorie hinzu."""
        message = Message(role=role, content=content)
        self.conversation_history.append(message)
        
        # Begrenzt die Historie auf die maximale Kontextlänge
        if len(self.conversation_history) > self.max_context_length:
            self.conversation_history = self.conversation_history[-self.max_context_length:]
            
    def get_context(self) -> List[Dict[str, str]]:
        """Gibt den aktuellen Konversationskontext im OpenAI-Format zurück."""
        return [
            {"role": msg.role, "content": msg.content}
            for msg in self.conversation_history
        ]
        
    def clear_history(self):
        """Löscht die Konversationshistorie."""
        self.conversation_history.clear()
        
    @property
    def last_message(self) -> Optional[Message]:
        """Gibt die letzte Nachricht zurück, falls vorhanden."""
        return self.conversation_history[-1] if self.conversation_history else None
        
    def get_summary(self) -> str:
        """Gibt eine Zusammenfassung der Konversation zurück."""
        if not self.conversation_history:
            return "Keine Konversationshistorie vorhanden."
            
        num_messages = len(self.conversation_history)
        last_message = self.last_message
        return f"{num_messages} Nachrichten im Kontext. Letzte Nachricht von {last_message.role} um {last_message.timestamp.strftime('%H:%M:%S')}" 