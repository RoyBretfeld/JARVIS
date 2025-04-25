from typing import List, Dict
from .llama_client import LlamaClient

class ConversationManager:
    def __init__(self, config: dict):
        """
        Initialisiert den ConversationManager.
        
        Args:
            config: Die Konfiguration mit server_url
        """
        self.llm_client = LlamaClient(server_url=config["llm"]["server_url"])
        self.conversation_history: List[Dict[str, str]] = []
        self.max_history = 10  # Maximale Anzahl der gespeicherten Nachrichten
        
    def process_message(self, user_message: str) -> str:
        """
        Verarbeitet eine Benutzernachricht und gibt die Antwort zurück.
        
        Args:
            user_message: Die Nachricht des Benutzers
            
        Returns:
            Die Antwort des Modells
        """
        # Prüfe Server-Status
        if not self.llm_client.is_server_running():
            return "Der LLaMA-Server ist nicht erreichbar. Bitte starten Sie den Server."
            
        # Hole Antwort vom Server
        response = self.llm_client.chat(user_message, self.conversation_history)
        
        # Füge Nachricht und Antwort zur Historie hinzu
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })
        self.conversation_history.append({
            "role": "assistant",
            "content": response
        })
        
        # Begrenze die Historie auf die letzten N Nachrichten
        if len(self.conversation_history) > self.max_history * 2:  # *2 weil jede Interaktion aus 2 Nachrichten besteht
            self.conversation_history = self.conversation_history[-self.max_history * 2:]
            
        return response
        
    def clear_history(self):
        """Löscht die Konversationshistorie."""
        self.conversation_history = [] 