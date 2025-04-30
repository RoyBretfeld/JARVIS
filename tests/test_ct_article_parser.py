import requests
from parsel import Selector
import logging
from urllib.parse import urljoin

# Logging einrichten
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Beispiel-Artikel-URL von heise.de/ct
URL = "https://www.heise.de/news/So-macht-man-einen-Homeserver-von-aussen-erreichbar-10363206.html"

# --- Schritt 1: HTML-Inhalt abrufen ---
try:
    logging.info(f"Rufe Inhalt von {URL} ab...")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    response = requests.get(URL, headers=headers, timeout=10)
    response.raise_for_status()
    html_content = response.text
    logging.info(f"Inhalt erfolgreich abgerufen ({len(html_content)} Bytes).")

    # --- Schritt 2: Parsel Selector erstellen ---
    selector = Selector(text=html_content)

    # --- Schritt 3: CSS-Selektoren für Titel und Text testen ---
    logging.info("Teste CSS-Selektoren für Titel und Text...")

    # === PLATZHALTER / VERMUTUNGEN für heise.de/ct - MÜSSEN ÜBERPRÜFT WERDEN! ===
    # Heise/c't verwendet oft <article> Tags und spezifische Klassen
    title_selector = 'header h1::text' # Dieser funktionierte
    
    # Versuche einen spezifischeren Selektor für die Absätze
    paragraph_selector = 'div.article-layout__content.article-content p::text' 
    # Alter, breiterer Selektor: paragraph_selector = 'article p::text' 
    # === Ende Anpassung ===

    # Titel extrahieren
    title = selector.css(title_selector).get()
    if title:
        title = title.strip()
        logging.info(f"Gefundener Titel: '{title}'")
    else:
        logging.warning(f"Konnte Titel mit Selektor '{title_selector}' nicht finden.")

    # Absätze extrahieren
    paragraphs = selector.css(paragraph_selector).getall()
    if paragraphs:
        # Bereinigten Text erstellen
        article_text = '\n'.join(p.strip() for p in paragraphs if p.strip())
        logging.info(f"Gefundener Text (erste 300 Zeichen):\n'''{article_text[:300]}...'''")
        logging.info(f"(Insgesamt {len(paragraphs)} Absätze gefunden, Textlänge: {len(article_text)} Zeichen)")
    else:
        logging.warning(f"Konnte keine Absätze mit Selektor '{paragraph_selector}' finden.")

    logging.info("-" * 30)
    logging.info("Test abgeschlossen.")
    logging.info("-" * 30)

except requests.exceptions.RequestException as e:
    logging.error(f"Fehler beim Abrufen der URL {URL}: {e}")
except Exception as e:
    logging.error(f"Ein unerwarteter Fehler ist aufgetreten: {e}", exc_info=True) 