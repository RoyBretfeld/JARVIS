import scrapy
import datetime
from ..items import ArticleItem
from scrapy import signals
import logging
from urllib.parse import urlparse, parse_qs
import queue # Sicherstellen, dass queue importiert ist

# Logger spezifisch für den Spider
spider_logger = logging.getLogger("ComputerBaseSpider")

class ComputerBaseSpider(scrapy.Spider):
    name = "computerbase_spider"
    allowed_domains = ["computerbase.de"]
    start_urls = ["https://www.computerbase.de/"]

    # Hinweis: Consent-Management beachten.

    # Angepasster __init__ - Erwartet jetzt result_queue
    def __init__(self, learning_manager=None, result_queue=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.learning_manager = learning_manager
        self.result_queue = result_queue # *** Queue speichern ***
        self.logger.info(f"ComputerBaseSpider initialisiert {'mit' if learning_manager else 'ohne'} LearningManager und {'mit' if result_queue else 'ohne'} Result Queue.")

    # Implementiere from_crawler - Verbindet jetzt lokale Handler
    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        # Rufe die Eltern-Implementierung auf, die __init__ mit *args/**kwargs aufrufen sollte
        spider = super().from_crawler(crawler, *args, **kwargs)

        # Verbinde Signale NACHDEM der Spider initialisiert wurde
        # self.result_queue sollte jetzt durch __init__ gesetzt sein.
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
            # Detaillierteres Logging, warum die Verbindung fehlschlägt
            reason = []
            if not spider.result_queue: reason.append("result_queue nicht verfügbar")
            if not hasattr(spider.crawler, 'signals'): reason.append("crawler.signals nicht verfügbar")
            spider.logger.warning(f"Konnte lokale Signal-Handler nicht verbinden: {', '.join(reason)}.")

        return spider

    # --- NEUE Lokale Signal-Handler (analog zu CtSpider) --- 
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
        # Logge das Schließen auch ohne Queue
        self.logger.info(f"ComputerBaseSpider ({self.name}) geschlossen (lokaler Handler). Grund: {reason}")

    def _handle_spider_error(self, failure, response, spider):
        if self.result_queue:
            try:
                error_msg = f"Spider Error in {spider.name}: {failure.getErrorMessage()}"
                self.logger.error(f"Spider-Fehler (lokaler Handler): {error_msg}", exc_info=failure.value)
                self.result_queue.put(('error', spider.name, error_msg)) # Nachricht in Queue
            except Exception as e:
                self.logger.error(f"Fehler im _handle_spider_error: {e}", exc_info=True)

    # --- Ende NEUE Handler ---

    # Ggf. start_requests für Cookies überschreiben

    def parse(self, response):
        """Parse die Startseite oder Übersichtsseiten, um Artikellinks zu finden."""
        self.logger.info(f"Parsing Übersichtsseite: {response.url}")

        # === PLATZHALTER für ComputerBase Links ===
        # Passe diese Selektoren an die Struktur von computerbase.de an!
        selectors = [
            'article a[href*="/artikel/"]::attr(href)', # Mögliche Artikel-URL-Struktur?
            'a.news__link::attr(href)', # Möglicher News-Link?
            'h2 > a::attr(href)',
            'h3 > a::attr(href)'
        ]
        article_links = set()
        for selector in selectors:
            found_links = response.css(selector).getall()
            if found_links:
                self.logger.debug(f"Selector '{selector}' fand {len(found_links)} Links.")
                for link in found_links:
                    parsed_link = urlparse(link)
                    if parsed_link.path and (parsed_link.scheme == '' or parsed_link.netloc == self.allowed_domains[0]):
                        article_links.add(response.urljoin(link.split('?')[0]))
            else:
                self.logger.debug(f"Selector '{selector}' fand keine Links.")

        self.logger.info(f"Gefundene potenzielle Artikel-Links (gesamt, unique): {len(article_links)}")

        if not article_links:
             self.logger.warning(f"Keine Artikel-Links auf {response.url} mit den aktuellen Selektoren gefunden.")

        for article_url in article_links:
            if article_url and self.allowed_domains[0] in article_url:
                self.logger.debug(f"Folge Artikel-Link: {article_url}")
                yield scrapy.Request(article_url, callback=self.parse_article)
            else:
                 self.logger.debug(f"Überspringe Link (leer oder externe Domain): {article_url}")

    def parse_article(self, response):
        """Parse eine einzelne Artikelseite."""
        self.logger.info(f"Parsing Artikelseite: {response.url}")

        # === Korrekte Selektoren für ComputerBase Artikelinhalte (basierend auf test_cb_article_parser.py) ===
        title = response.css('h1.article-view__h1::text').get()

        paragraphs = response.css('div.article-view__content p.text-p::text').getall()
        # === Ende korrekte Selektoren ===

        article_text = '\n'.join(p.strip() for p in paragraphs if p.strip())

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