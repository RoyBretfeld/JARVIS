import scrapy
import datetime
from ..items import ArticleItem
from scrapy import signals
import logging
from urllib.parse import urlparse, parse_qs

# Logger spezifisch für den Spider
spider_logger = logging.getLogger("T3nSpider")

class T3nSpider(scrapy.Spider):
    name = "t3n_spider"
    allowed_domains = ["t3n.de"]
    start_urls = ["https://t3n.de/"]

    # Hinweis: t3n verwendet ebenfalls ein Consent-Management.
    # Eventuell müssen wir hier später analog zu Golem Cookies setzen.
    # Wir versuchen es aber erstmal ohne.

    # Angepasster __init__
    def __init__(self, learning_manager=None, thread_instance=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.learning_manager = learning_manager
        self.thread_instance = thread_instance
        self.logger.info(f"T3nSpider initialisiert {'mit' if learning_manager else 'ohne'} LearningManager und {'mit' if thread_instance else 'ohne'} Thread-Instanz.")

    # Implementiere from_crawler
    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = cls(*args, **kwargs)
        spider._set_crawler(crawler)
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

    # Implementiere closed
    def closed(self, reason):
        if self.thread_instance and hasattr(self, 'crawler') and hasattr(self.crawler, 'signals'):
            try:
                self.logger.info("Trenne Signale vom Spider zur Thread-Instanz...")
                self.crawler.signals.disconnect(self.thread_instance._item_scraped_handler, signal=signals.item_scraped)
                self.crawler.signals.disconnect(self.thread_instance._spider_closed_handler, signal=signals.spider_closed)
                self.crawler.signals.disconnect(self.thread_instance._spider_error_handler, signal=signals.spider_error)
                self.logger.info("Signale erfolgreich getrennt.")
            except Exception as e:
                self.logger.error(f"Fehler beim Trennen der Signale im Spider: {e}", exc_info=True)
        self.logger.info(f"T3nSpider ({self.name}) geschlossen. Grund: {reason}")

    # Keine Überschreibung von start_requests erstmal, versuchen es ohne Cookie

    def parse(self, response):
        """Parse die Startseite oder Übersichtsseiten, um Artikellinks zu finden."""
        self.logger.info(f"Parsing Übersichtsseite: {response.url}")

        # === Annahmen für t3n.de Links ===
        # Versuche verschiedene gängige Selektoren
        # Passe diese Selektoren bei Bedarf an!
        selectors = [
            'article a[href*="/news/"]::attr(href)',     # Generischer Artikel-Link mit /news/
            'a.c-card__link[href*="/news/"]::attr(href)', # Spezifischer Link in Karten-Layout?
            'h2 > a[href*="/news/"]::attr(href)',        # Link innerhalb einer H2
            'h3 > a[href*="/news/"]::attr(href)'        # Link innerhalb einer H3
        ]
        article_links = set()
        for selector in selectors:
            found_links = response.css(selector).getall()
            if found_links:
                self.logger.debug(f"Selector '{selector}' fand {len(found_links)} Links.")
                for link in found_links:
                     # Entferne mögliche Query-Parameter von den Links
                     article_links.add(response.urljoin(link.split('?')[0]))
            else:
                 self.logger.debug(f"Selector '{selector}' fand keine Links.")

        self.logger.info(f"Gefundene potenzielle Artikel-Links (gesamt, unique): {len(article_links)}")

        if not article_links:
             self.logger.warning(f"Keine Artikel-Links auf {response.url} mit den aktuellen Selektoren gefunden.")

        for article_url in article_links:
            if article_url:
                # Keine explizite URL-Prüfung hier, da schon in Selektoren [href*="/news/"]
                if self.allowed_domains[0] in article_url:
                     self.logger.debug(f"Folge Artikel-Link: {article_url}")
                     yield scrapy.Request(article_url, callback=self.parse_article)
                else:
                     self.logger.debug(f"Überspringe Link (falsche Domain?): {article_url}")
            else:
                 self.logger.debug(f"Überspringe leeren Link.")

    def parse_article(self, response):
        """Parse eine einzelne Artikelseite."""
        self.logger.info(f"Parsing Artikelseite: {response.url}")

        # === Annahmen für t3n.de Artikelinhalte ===
        # Passe diese Selektoren bei Bedarf an!
        title = response.css('h1.c-article__headline::text').get() or \
                response.css('h1::text').get()

        # Versuche, Absätze im Hauptinhalt zu extrahieren
        # Oft in einem div mit Klasse wie "article-content" oder "entry-content"
        paragraphs = response.css('div.c-article__content p::text').getall() or \
                     response.css('article p::text').getall()
        # === Ende Annahmen ===

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