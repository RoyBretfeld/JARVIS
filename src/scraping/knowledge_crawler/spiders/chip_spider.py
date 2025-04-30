import scrapy
import datetime
from ..items import ArticleItem
from scrapy import signals
import logging
from urllib.parse import urlparse
import queue # Queue importieren
from itemadapter import ItemAdapter # ItemAdapter importieren
from scrapy.selector import Selector # *** Selector importieren ***

# Logger spezifisch für den Spider
spider_logger = logging.getLogger("ChipSpider")

class ChipSpider(scrapy.Spider):
    name = "chip_spider"
    allowed_domains = ["chip.de"]
    start_urls = ['https://www.chip.de/rss/rss_downloads.xml'] # Use the downloads RSS feed
    custom_settings = {
        'LOG_LEVEL': 'INFO',
        'FEEDS': {
            # Add FEEDS settings here if needed, e.g., output format
            # 'output/articles.json': {'format': 'json', 'encoding': 'utf8', 'indent': 4},
        },
        # Add other custom settings if needed
        # 'USER_AGENT': 'MyCoolBot/1.0 (+http://www.mywebsite.com)',
    }

    # Definiere hier robuste Selektoren, um Links zu Artikeln zu finden
    # article_link_selectors = [
    #     'article.Teaser a.ArticleLink[href*="/news/"]::attr(href)', # Nicht mehr benötigt bei RSS
    # ]

    # Hinweis: Consent-Management beachten. (Chip hat oft Overlays)

    # Angepasster __init__ - Erwartet jetzt result_queue
    def __init__(self, learning_manager=None, result_queue=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.learning_manager = learning_manager
        self.result_queue = result_queue # *** Queue speichern ***
        self.logger.info(f"ChipSpider initialisiert {'mit' if learning_manager else 'ohne'} LearningManager und {'mit' if result_queue else 'ohne'} Result Queue.")

    # Implementiere from_crawler - Verbindet jetzt lokale Handler
    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)

        if spider.result_queue and hasattr(spider.crawler, 'signals'):
            try:
                spider.logger.info("Verbinde Scrapy-Signale mit lokalen Handlern...")
                # *** Verbinde mit LOKALEN Methoden ***
                crawler.signals.connect(spider._handle_item_scraped, signal=signals.item_scraped)
                crawler.signals.connect(spider._handle_spider_closed, signal=signals.spider_closed)
                crawler.signals.connect(spider._handle_spider_error, signal=signals.spider_error)
                spider.logger.info("Lokale Signal-Handler erfolgreich verbunden.")
            except Exception as e:
                spider.logger.error(f"Fehler beim Verbinden der lokalen Signal-Handler: {e}", exc_info=True)
        else:
            reason = []
            if not spider.result_queue: reason.append("result_queue nicht verfügbar")
            if not hasattr(spider.crawler, 'signals'): reason.append("crawler.signals nicht verfügbar")
            spider.logger.warning(f"Konnte lokale Signal-Handler nicht verbinden: {', '.join(reason)}.")

        return spider

    # --- NEUE Lokale Signal-Handler ---
    def _handle_item_scraped(self, item, response, spider):
        if self.result_queue:
            try:
                adapter = ItemAdapter(item)
                url = adapter.get('url', 'Unbekannte URL')
                self.result_queue.put(('item', url)) # Nachricht in Queue
            except Exception as e:
                self.logger.error(f"Fehler im _handle_item_scraped: {e}", exc_info=True)

    def _handle_spider_closed(self, spider, reason):
        if self.result_queue:
             try:
                 self.logger.info(f"Spider geschlossen (lokaler Handler). Grund: {reason}. Sende Nachricht an Queue...")
                 self.result_queue.put(('closed', spider.name, reason)) # Nachricht in Queue
             except Exception as e:
                 self.logger.error(f"Fehler im _handle_spider_closed: {e}", exc_info=True)
        self.logger.info(f"ChipSpider ({self.name}) geschlossen (lokaler Handler). Grund: {reason}")

    def _handle_spider_error(self, failure, response, spider):
        if self.result_queue:
            try:
                error_msg = f"Spider Error in {spider.name}: {failure.getErrorMessage()}"
                self.logger.error(f"Spider-Fehler (lokaler Handler): {error_msg}", exc_info=failure.value)
                self.result_queue.put(('error', spider.name, error_msg)) # Nachricht in Queue
            except Exception as e:
                self.logger.error(f"Fehler im _handle_spider_error: {e}", exc_info=True)

    # --- Ende NEUE Handler ---

    # Alte `closed`-Methode entfernen (falls vorhanden)
    # def closed(self, reason):
    #    ...

    # Ggf. start_requests für Cookies überschreiben (falls nötig)

    def parse(self, response):
        """Parse den RSS-Feed, um Artikellinks zu extrahieren."""
        self.logger.info(f"Parsing RSS Feed: {response.url} (Type: {response.text[:50]}...)") # Logge Typ und Anfang des Textes

        # === Explizit einen XML-Selector erstellen ===
        try:
            # Erstelle einen Selector aus dem Text der Antwort, erzwinge Typ XML
            xml_selector = Selector(text=response.text, type='xml')
            # Namespace für RSS entfernen, falls vorhanden (vereinfacht XPath)
            xml_selector.remove_namespaces()
        except Exception as e:
            self.logger.error(f"Konnte keinen XML-Selector aus der Antwort erstellen: {e}", exc_info=True)
            return # Beende die Parse-Methode, wenn XML nicht erstellt werden kann

        # === Schritt 1: Links aus <item>/<link> extrahieren (verwende xml_selector) ===
        # Verwende XPath, um den Inhalt des <link>-Tags innerhalb jedes <item>-Tags zu finden
        article_links_raw = xml_selector.xpath('//item/link/text()').getall()

        self.logger.info(f"Insgesamt {len(article_links_raw)} Links im RSS-Feed gefunden.")
        if article_links_raw:
             self.logger.debug(f"Beispiel-Links aus RSS: {article_links_raw[:5]}...")

        # === Schritt 2: URLs bereinigen und filtern (ähnlich wie vorher) ===
        final_article_links = set()
        # Filter für Pfade, die keine reinen Artikel sind (Anpassung evtl. nötig)
        filtered_out_paths = ['/video/', '/bilderstrecke/', '/gutscheine/', '/tests/', '/bestenlisten/', '/deals/', '/preisvergleich/']

        for link in article_links_raw:
            try:
                # RSS-Links sollten bereits absolut sein, aber sicherheitshalber urljoin
                full_url = response.urljoin(link.split('?')[0]) # Query-Parameter entfernen
                parsed_link = urlparse(full_url)

                # Domain-Check (Testweise auskommentiert)
                # if parsed_link.netloc != self.allowed_domains[0]:
                #     self.logger.debug(f"[Filter] Link übersprungen (falsche Domain): {full_url}")
                #     continue

                # Inhalts-Check (Ausschluss von Kategorien)
                path_lower = parsed_link.path.lower()
                if any(x in path_lower for x in filtered_out_paths):
                    filter_reason = [x for x in filtered_out_paths if x in path_lower]
                    self.logger.debug(f"[Filter] Link übersprungen (Path enthält '{filter_reason}'): {full_url}")
                    continue

                # Mindestlänge Pfad-Check (optional, bei RSS oft weniger nötig)
                # if len(path_lower) <= 6:
                #      self.logger.debug(f"[Filter] Link übersprungen (Pfad zu kurz): {full_url}")
                #      continue

                # Wenn alle Checks bestanden, Link hinzufügen
                final_article_links.add(full_url)

            except Exception as e:
                 self.logger.warning(f"Fehler beim Verarbeiten des Links '{link}' aus RSS-Feed: {e}")

        self.logger.info(f"Gefundene Artikel-Links nach Bereinigung und Filterung (gesamt, unique): {len(final_article_links)}")

        if not final_article_links:
             self.logger.warning(f"Keine gültigen Artikel-Links im Feed {response.url} nach Filterung übrig geblieben.")
             self.logger.debug(f"Ursprünglich gefundene Links (vor Filterung): {article_links_raw}")

        # === Schritt 3: Den gültigen Links folgen ===
        for article_url in final_article_links:
             self.logger.debug(f"Folge gefiltertem Artikel-Link aus RSS: {article_url}")
             yield scrapy.Request(article_url, callback=self.parse_article)

    def parse_article(self, response):
        """Parse eine einzelne Chip.de Artikelseite."""
        self.logger.info(f"Parsing Artikelseite: {response.url}")

        # === Selektoren basierend auf Tests mit chip_kabel_router_article.html ===

        # Titel-Extraktion: Priorität auf Meta-Tag, dann Fallbacks
        title_selector_meta = 'meta[property="og:title"]::attr(content)'
        title_selector_h1 = 'h1.article-title::text' # Alter Selektor als Fallback
        title_selector_h2 = 'h2.Article-Title::text' # Anderer möglicher Fallback
        # title_selector_span = 'span[itemprop="headline"]::text' # Veraltet?

        title = response.css(title_selector_meta).get()
        if not title:
            self.logger.debug(f"Kein Titel mit '{title_selector_meta}' gefunden, versuche {title_selector_h1}...")
            title = response.css(title_selector_h1).get()
        if not title:
             self.logger.debug(f"Kein Titel mit '{title_selector_h1}' gefunden, versuche {title_selector_h2}...")
             title = response.css(title_selector_h2).get()
        # if not title:
        #     self.logger.debug(f"Kein Titel mit '{title_selector_h2}' gefunden, versuche {title_selector_span}...")
        #     title = response.css(title_selector_span).get()


        # Text-Extraktion: Allgemeinerer Selektor, der im Test funktionierte
        text_selector = 'div.article-content p::text, div.copytext p::text, article p::text'
        # Alter, spezifischerer Selektor (hat nicht funktioniert):
        # text_selector_specific = 'div.Article-Content div.Html-Block[data-qa-article-content-text] p::text'
        paragraphs = response.css(text_selector).getall()

        # Bereinigen und Zusammenfügen des Textes
        article_text = "\n".join(p.strip() for p in paragraphs if p.strip()) # Fügt Absätze mit Zeilenumbruch zusammen

        if title and article_text:
            item = ArticleItem()
            item['url'] = response.url
            item['title'] = title.strip()
            item['text'] = article_text
            item['source'] = self.name
            item['timestamp'] = datetime.datetime.now().isoformat()
            yield item
            self.logger.debug(f"Artikel extrahiert: {item['title']}")
        elif not title:
             self.logger.warning(f"Konnte Titel nicht extrahieren von: {response.url}")
        elif not article_text:
             self.logger.warning(f"Konnte Text nicht extrahieren von: {response.url} (Titel: {title.strip() if title else 'N/A'})")
        else:
             self.logger.warning(f"Konnte Titel oder Text nicht extrahieren von: {response.url}") 