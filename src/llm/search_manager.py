import logging
from typing import List, Dict, Optional
from duckduckgo_search import DDGS # Geändert von duckduckgo_search -> DDGS

logger = logging.getLogger(__name__)

class SearchManager:
    """Verwaltet Websuchen über eine Suchmaschine."""

    def __init__(self, config=None): # Config ist optional, da DDG keine Keys braucht
        # Später für API-Keys anderer Suchmaschinen
        # self.api_key = config.get("search_api_key") if config else None
        # self.search_engine = config.get("search_engine", "duckduckgo") if config else "duckduckgo"
        logger.info("SearchManager initialisiert (verwendet DuckDuckGo).")
        pass # Vorerst keine Konfiguration nötig

    def web_search(self, query: str, max_results: int = 5) -> List[Dict]:
        """
        Führt eine Websuche durch und gibt die Top-Ergebnisse zurück.

        Args:
            query: Der Suchbegriff.
            max_results: Die maximale Anzahl der zurückzugebenden Ergebnisse.

        Returns:
            Eine Liste von Dictionaries, wobei jedes Dict ein Suchergebnis 
            mit den Schlüsseln 'title', 'snippet', 'url' repräsentiert.
            Gibt eine leere Liste bei Fehlern zurück.
        """
        logger.info(f"Führe Websuche für '{query}' durch (max. {max_results} Ergebnisse)...")
        results = []
        try:
            # Verwende DuckDuckGo Search
            # Beachte: Parameter können sich je nach Version der Bibliothek ändern
            # `max_results` wird direkt in der Suche verwendet
            with DDGS() as ddgs:
                 search_results = list(ddgs.text(query, max_results=max_results)) # ddgs.text liefert einen Generator

            if not search_results:
                logger.warning(f"Keine Suchergebnisse für '{query}' gefunden.")
                return []

            # Extrahiere relevante Informationen
            for result in search_results:
                 results.append({
                     'title': result.get('title', 'Kein Titel'),
                     'snippet': result.get('body', ''), # 'body' enthält oft das Snippet
                     'url': result.get('href', '#')
                 })
                 # Debug-Ausgabe für jedes Ergebnis
                 # logger.debug(f"  - Titel: {result.get('title')}")
                 # logger.debug(f"    URL: {result.get('href')}")
                 # logger.debug(f"    Snippet: {result.get('body', '')[:100]}...")

            logger.info(f"{len(results)} Suchergebnisse für '{query}' verarbeitet.")
            return results

        except ImportError:
             logger.error("DuckDuckGo Search Bibliothek nicht installiert. Bitte 'pip install duckduckgo-search' ausführen.")
             return []
        except Exception as e:
            logger.error(f"Fehler bei der Websuche für '{query}': {e}", exc_info=True)
            return [] # Leere Liste bei Fehlern zurückgeben 