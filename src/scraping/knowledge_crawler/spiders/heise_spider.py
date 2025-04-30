import scrapy
import datetime
from ..items import ArticleItem
# Importiere signals, um sie zu verwenden
from scrapy import signals
import logging

# Logger spezifisch für den Spider
spider_logger = logging.getLogger("HeiseSpider")

class HeiseSpider(scrapy.Spider):
    name = "heise_spider"
    allowed_domains = ["heise.de"]
    start_urls = ["https://www.heise.de/"]

    # Angepasster __init__
    def __init__(self, learning_manager=None, thread_instance=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.learning_manager = learning_manager
        self.thread_instance = thread_instance # Speichere die Thread-Instanz
        # Logger wird automatisch von Scrapy bereitgestellt (self.logger)
        self.logger.info(f"HeiseSpider initialisiert {'mit' if learning_manager else 'ohne'} LearningManager und {'mit' if thread_instance else 'ohne'} Thread-Instanz.")
        # KEINE Signalverbindung hier, da self.crawler noch nicht existiert

    # Implementiere from_crawler, um Signale zu verbinden
    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        # kwargs enthält die Argumente, die an process.crawl übergeben wurden (learning_manager, thread_instance)
        spider = cls(*args, **kwargs)
        spider._set_crawler(crawler) # Wichtig: Setzt self.crawler

        # Verbinde Signale hier, da self.crawler verfügbar ist
        if spider.thread_instance and hasattr(spider.crawler, 'signals'):
            try:
                spider.logger.info("Verbinde Signale vom Spider zur Thread-Instanz...")
                spider.crawler.signals.connect(spider.thread_instance._item_scraped_handler, signal=signals.item_scraped)
                spider.crawler.signals.connect(spider.thread_instance._spider_closed_handler, signal=signals.spider_closed)
                spider.crawler.signals.connect(spider.thread_instance._spider_error_handler, signal=signals.spider_error)
                spider.logger.info("Signale erfolgreich verbunden.")
            except Exception as e:
                spider.logger.error(f"Fehler beim Verbinden der Signale im Spider: {e}", exc_info=True)
        else:
            spider.logger.warning("Konnte Signale nicht verbinden: thread_instance oder crawler.signals nicht verfügbar.")

        return spider

    # Implementiere closed, um Signale zu trennen
    def closed(self, reason):
        """Wird aufgerufen, wenn der Spider geschlossen wird."""
        # Trenne Signale, um Duplikate bei erneutem Lauf zu vermeiden
        if self.thread_instance and hasattr(self, 'crawler') and hasattr(self.crawler, 'signals'):
            try:
                self.logger.info("Trenne Signale vom Spider zur Thread-Instanz...")
                self.crawler.signals.disconnect(self.thread_instance._item_scraped_handler, signal=signals.item_scraped)
                self.crawler.signals.disconnect(self.thread_instance._spider_closed_handler, signal=signals.spider_closed)
                self.crawler.signals.disconnect(self.thread_instance._spider_error_handler, signal=signals.spider_error)
                self.logger.info("Signale erfolgreich getrennt.")
            except Exception as e:
                self.logger.error(f"Fehler beim Trennen der Signale im Spider: {e}", exc_info=True)
        self.logger.info(f"HeiseSpider ({self.name}) geschlossen. Grund: {reason}")

    def parse(self, response):
        """Diese Methode wird aufgerufen, um die Startseite zu parsen."""
        
        # Finde Links innerhalb von <article>-Elementen (breiterer Ansatz)
        # Wir nehmen an, dass dies die Hauptartikel-Links sind.
        self.logger.info(f"Parsing Startseite: {response.url}")
        article_links = response.css('article a::attr(href)').getall()
        self.logger.info(f"Gefundene potenzielle Artikel-Links: {len(article_links)}")
        
        for article_url in article_links:
            # Extrahiere den Link (bereits durch getall() geschehen)
            if article_url:
                # Wandle relative URLs (z.B. /news/artikel.html) in absolute um
                absolute_url = response.urljoin(article_url)
                
                # Filtert externe Links oder Links, die unwahrscheinlich Artikel sind (optional, kann angepasst werden)
                if self.allowed_domains[0] in absolute_url and ('/news/' in absolute_url or '/tp/' in absolute_url or '/select/' in absolute_url):
                    self.logger.debug(f"Folge Artikel-Link: {absolute_url}")
                    # Folge dem Link zur Artikelseite und rufe parse_article auf
                    yield scrapy.Request(absolute_url, callback=self.parse_article)
                else:
                    self.logger.debug(f"Überspringe Link (kein Artikel?): {absolute_url}")

    def parse_article(self, response):
        """Diese Methode wird aufgerufen, um eine einzelne Artikelseite zu parsen."""
        
        # Extrahiere Titel (verschiedene Möglichkeiten, Heise ändert Struktur manchmal)
        title = response.css('h1::text').get() or \
                response.css('header h1::text').get() or \
                response.css('article h1::text').get() or \
                response.css('.article-header h1::text').get()
                
        # Extrahiere den Artikeltext (oft in einem <article> oder spezifischen divs)
        # Wir nehmen Absätze innerhalb des Haupt-Artikel-Containers
        paragraphs = response.css('article p::text').getall() or \
                     response.css('div.article-content p::text').getall()
                     
        # Kombiniere die Absätze zu einem einzigen Text
        article_text = '\n'.join(p.strip() for p in paragraphs if p.strip())

        if title and article_text:
            # Erzeuge ein ArticleItem statt eines Dictionaries
            item = ArticleItem()
            item['url'] = response.url
            item['title'] = title.strip()
            item['text'] = article_text
            item['source'] = self.name
            item['timestamp'] = datetime.datetime.now().isoformat()
            yield item # Gib das Item zurück
        else:
            self.logger.warning(f"Konnte Titel oder Text nicht extrahieren von: {response.url}")
