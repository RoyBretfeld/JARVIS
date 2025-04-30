import requests
from parsel import Selector
import logging
from urllib.parse import urljoin

# Logging einrichten (optional, aber hilfreich)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Ziel-URL
URL = "https://www.heise.de/ct/"

# --- Schritt 1: HTML-Inhalt abrufen ---
try:
    logging.info(f"Rufe Inhalt von {URL} ab...")
    # User-Agent setzen, um Blockierung zu vermeiden
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    response = requests.get(URL, headers=headers, timeout=10)
    response.raise_for_status() # Fehler bei Statuscodes != 2xx auslösen
    html_content = response.text
    logging.info(f"Inhalt erfolgreich abgerufen ({len(html_content)} Bytes).")

    # --- Schritt 2: Parsel Selector erstellen ---
    selector = Selector(text=html_content)

    # --- Schritt 3: CSS-Selektoren für Artikellinks definieren und testen ---
    logging.info("Teste CSS-Selektoren für Artikellinks...")

    # Liste von Selektoren, die wir ausprobieren wollen
    # (Basierend auf der Struktur von heise.de/ct - ANPASSEN!)
    link_selectors_to_try = [
        # Alte Selektoren (zum Vergleich)
        'article a[href*="/meldung/"]::attr(href)',
        'a.a-article-teaser__link::attr(href)',
        'h2 > a::attr(href)',
        'h3 > a::attr(href)',
        # === NEUE IDEEN (Beispiele - MÜSSEN ÜBERPRÜFT WERDEN!) ===
        'a[href*="/news/"]::attr(href)', # Oft für News-Artikel verwendet
        'a[href*="/artikel/"]::attr(href)', # Genereller Artikel-Link?
        'article[data-article-id] a::attr(href)', # Wenn Artikel durch data-Attribut markiert sind
        '.teaser a::attr(href)', # Wenn Artikel in einem 'teaser'-Element sind
        'a.article-link::attr(href)', # Wenn Links eine spezifische Klasse haben
        'div.beitrag a::attr(href)' # Struktur auf heise.de/ct
        # Fügen Sie hier weitere Selektoren hinzu, die Sie im Browser identifizieren
    ]

    found_links = set()

    for css_selector in link_selectors_to_try:
        try:
            extracted_links = selector.css(css_selector).getall()
            logging.info(f"  Selektor '{css_selector}' -> {len(extracted_links)} Links gefunden.")
            for link in extracted_links:
                # Bereinigen und absolute URL erstellen
                absolute_link = urljoin(URL, link.split('?')[0]) # Parameter entfernen
                # Nur Links hinzufügen, die auf heise.de verweisen und nicht nur "/" sind
                if "heise.de" in absolute_link and absolute_link != URL:
                    found_links.add(absolute_link)
        except Exception as e:
            logging.error(f"Fehler bei Selektor '{css_selector}': {e}")

    # --- Schritt 4: Ergebnisse ausgeben ---
    logging.info("-" * 30)
    logging.info(f"Insgesamt {len(found_links)} einzigartige potenzielle Artikel-Links gefunden:")
    if found_links:
        for i, link in enumerate(sorted(list(found_links))):
            logging.info(f"  {i+1}. {link}")
    else:
        logging.warning("Keine Links mit den aktuellen Selektoren gefunden. Bitte die Selektoren in der Liste `link_selectors_to_try` anpassen!")
    logging.info("-" * 30)

except requests.exceptions.RequestException as e:
    logging.error(f"Fehler beim Abrufen der URL {URL}: {e}")
except Exception as e:
    logging.error(f"Ein unerwarteter Fehler ist aufgetreten: {e}", exc_info=True) 