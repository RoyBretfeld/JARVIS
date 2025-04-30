import requests
from parsel import Selector
import logging
from urllib.parse import urljoin

# Logging einrichten
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Beispiel-Artikel-URL von ComputerBase
URL = "https://www.computerbase.de/news/monitore/neues-samsung-logo-qd-oled-in-ueber-170-produkten-und-das-soll-man-auch-sehen.92405/"

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

    # Vermutete Selektoren (basierend auf dem HTML-Snippet)
    title_selector = 'h1.article-view__h1::text'
    paragraph_selector = 'div.article-view__content p.text-p::text'

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