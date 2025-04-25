import os
import openai
from typing import Generator, Optional
from dataclasses import dataclass
from dotenv import load_dotenv

@dataclass
class LLMConfig:
    model: str = "gpt-4"
    temperature: float = 0.7
    max_tokens: int = 1000
    stream: bool = True

class LLMClient:
    def __init__(self, config: Optional[LLMConfig] = None):
        """Initialisiert den LLM Client mit der angegebenen Konfiguration."""
        load_dotenv()  # Lädt API Keys aus .env Datei
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API Key nicht gefunden. Bitte in .env Datei definieren.")
        
        openai.api_key = self.api_key
        self.config = config or LLMConfig()
        
    def generate_response(self, prompt: str) -> Generator[str, None, None]:
        """Generiert eine Antwort vom LLM mit Streaming-Unterstützung."""
        try:
            response = openai.ChatCompletion.create(
                model=self.config.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                stream=self.config.stream
            )
            
            if self.config.stream:
                for chunk in response:
                    if chunk and chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
            else:
                yield response.choices[0].message.content
                
        except Exception as e:
            yield f"Fehler bei der API-Anfrage: {str(e)}"
            
    def update_config(self, **kwargs):
        """Aktualisiert die Konfiguration des LLM Clients."""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                
    @property
    def model_info(self) -> str:
        """Gibt Informationen über das aktuelle Modell zurück."""
        return f"Modell: {self.config.model} (T={self.config.temperature})" 