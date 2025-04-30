import requests
from parsel import Selector
import logging
from urllib.parse import urljoin

# Logging einrichten
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Ziel-URL für ComputerBase
URL = "https://www.computerbase.de/"

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

    # --- Schritt 3: CSS-Selektoren für Artikellinks definieren und testen ---
    logging.info("Teste CSS-Selektoren für Artikellinks...")

    # Liste von Selektoren, die wir ausprobieren wollen
    # (MÜSSEN FÜR COMPUTERBASE.DE ANGEPASST WERDEN!)
    link_selectors_to_try = [
        # Beispiele - Wahrscheinlich falsch für ComputerBase
        'a[href*="/artikel/"]::attr(href)',
        'a[href*="/news/"]::attr(href)',
        '.news-list-item a::attr(href)',
        'article > a::attr(href)',
        'h2 > a::attr(href)',
        'h3 > a::attr(href)',
        'a.teaser__link::attr(href)', # Häufige Klasse
        'a.cb-teaser-link::attr(href)', # ComputerBase spezifisch?
        # Fügen Sie hier weitere Selektoren hinzu, die Sie im Browser identifizieren
    ]

    found_links = set()

    for css_selector in link_selectors_to_try:
        try:
            extracted_links = selector.css(css_selector).getall()
            logging.info(f"  Selektor '{css_selector}' -> {len(extracted_links)} Links gefunden.")
            for link in extracted_links:
                # Bereinigen und absolute URL erstellen
                absolute_link = urljoin(URL, link.split('?')[0])
                # Filtern: Nur Links von computerbase.de und keine generischen Pfade
                if "computerbase.de" in absolute_link and absolute_link != URL and not absolute_link.endswith(".de") and not absolute_link.endswith(".de/"):
                     # Evtl. weitere Filter hinzufügen (z.B. Ausschluss von /forum/, /preisvergleich/)
                     if "/forum/" not in absolute_link and "/preisvergleich/" not in absolute_link:
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