import json
import requests
from typing import List, Dict, Any

class LlamaClient:
    def __init__(self, server_url: str = "http://localhost:8080"):
        self.server_url = server_url
        self.headers = {"Content-Type": "application/json"}
        self.system_prompt = "Du bist JARVIS, ein hilfreicher KI-Assistent. Antworte immer auf Deutsch."
        
    def chat(self, user_message: str, conversation_history: List[Dict[str, str]] = None) -> str:
        """
        Sendet eine Nachricht an den LLaMA-Server und gibt die Antwort zurück.
        
        Args:
            user_message: Die Nachricht des Benutzers
            conversation_history: Optional, frühere Nachrichten für Kontext
            
        Returns:
            Die Antwort des Modells als String
        """
        if conversation_history is None:
            conversation_history = []
            
        # Füge System-Prompt hinzu, wenn noch nicht vorhanden
        if not any(msg.get("role") == "system" for msg in conversation_history):
            conversation_history.insert(0, {
                "role": "system",
                "content": self.system_prompt
            })
            
        # Füge aktuelle Nachricht hinzu
        messages = conversation_history + [{
            "role": "user",
            "content": user_message
        }]
        
        try:
            response = requests.post(
                f"{self.server_url}/v1/chat/completions",
                headers=self.headers,
                json={"messages": messages},
                timeout=30  # 30 Sekunden Timeout
            )
            response.raise_for_status()
            
            result = response.json()
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"].strip()
            else:
                return "Entschuldigung, ich konnte keine passende Antwort generieren."
                
        except requests.exceptions.RequestException as e:
            print(f"Fehler bei der Kommunikation mit dem LLaMA-Server: {e}")
            return "Entschuldigung, es gab ein Problem bei der Kommunikation mit dem Server."
            
    def is_server_running(self) -> bool:
        """
        Überprüft, ob der LLaMA-Server erreichbar ist.
        
        Returns:
            True wenn der Server läuft, False sonst
        """
        try:
            response = requests.get(f"{self.server_url}/health", timeout=5)
            return response.status_code == 200
        except:
            return False 