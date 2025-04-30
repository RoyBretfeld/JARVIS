import scrapy
import datetime
from ..items import ArticleItem
# Importiere signals, um sie zu verwenden
from scrapy import signals
import logging
# Importiere urllib.parse
from urllib.parse import urlparse, parse_qs

# Logger spezifisch für den Spider
spider_logger = logging.getLogger("GolemSpider")

class GolemSpider(scrapy.Spider):
    name = "golem_spider"
    allowed_domains = ["golem.de"]
    # Entferne start_urls, da wir start_requests überschreiben
    # start_urls = ["https://www.golem.de/"]

    # Platzhalter für das Consent Cookie
    # BITTE ERSETZEN mit dem echten Namen und Wert! -> Ersetzt!
    GOLEM_CONSENT_COOKIE = {
        'name': 'golem_consent20',
        'value': 'cmp|250101'
    }

    # Angepasster __init__ (identisch zu HeiseSpider)
    def __init__(self, learning_manager=None, thread_instance=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.learning_manager = learning_manager
        self.thread_instance = thread_instance # Speichere die Thread-Instanz
        self.logger.info(f"GolemSpider initialisiert {'mit' if learning_manager else 'ohne'} LearningManager und {'mit' if thread_instance else 'ohne'} Thread-Instanz.")

    # Implementiere from_crawler (identisch zu HeiseSpider)
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

    # Implementiere closed (identisch zu HeiseSpider)
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
        self.logger.info(f"GolemSpider ({self.name}) geschlossen. Grund: {reason}")

    def start_requests(self):
        """Generiert die erste(n) Anfrage(n) mit dem Consent Cookie."""
        start_url = "https://www.golem.de/"
        self.logger.info(f"Sende Startanfrage an {start_url} mit Consent Cookie...")

        # Korrigierte Überprüfung: Prüfe auf Gleichheit mit den Platzhaltern
        if self.GOLEM_CONSENT_COOKIE['name'] == 'HIER_COOKIE_NAMEN_EINFUEGEN' or \
           self.GOLEM_CONSENT_COOKIE['value'] == 'HIER_COOKIE_WERT_EINFUEGEN':
            self.logger.warning("Golem Consent Cookie wurde nicht konfiguriert (Platzhalter gefunden)! Der Crawl wird wahrscheinlich fehlschlagen.")
            # Optional: Hier abbrechen oder ohne Cookie weitermachen?
            # Wir machen erstmal ohne weiter, aber loggen die Warnung.
            yield scrapy.Request(url=start_url, callback=self.parse)
        else:
            self.logger.info("Sende Anfrage mit konfiguriertem Consent Cookie.")
            yield scrapy.Request(
                url=start_url,
                cookies=[self.GOLEM_CONSENT_COOKIE], # Setze das Cookie
                callback=self.parse
            )

    def parse(self, response):
        """Parse die Startseite oder Übersichtsseiten, um Artikellinks zu finden."""
        # Entferne die Logik zur Behandlung der Zustimmungsseite, da wir hoffen, sie mit dem Cookie zu umgehen
        # if "/zustimmung/auswahl.html" in response.url:
        #    ...

        self.logger.info(f"Parsing Übersichtsseite: {response.url}")

        # === Aktualisierte Annahmen für Golem.de Links ===
        # Versuche verschiedene gängige Selektoren
        # Passe diese Selektoren bei Bedarf an!
        selectors = [
            'article header a::attr(href)',        # Link in Artikel-Überschrift
            'article a.link-cover::attr(href)',    # Links, die oft ganze Teaser abdecken
            'ul.list--articles a.list-articles__link::attr(href)', # Vorheriger Versuch
            'a.teaser__link[href*="/news/"]::attr(href)', # Spezifischer Teaser-Link
            'h2 > a[href*="/news/"]::attr(href)',        # Link innerhalb einer H2, der nach /news/ aussieht
            'h3 > a[href*="/news/"]::attr(href)',        # Link innerhalb einer H3, der nach /news/ aussieht
            'article a[href*="/news/"]::attr(href)'      # Link innerhalb von article, der nach /news/ aussieht
        ]
        article_links = set() # Verwende ein Set, um Duplikate zu vermeiden
        for selector in selectors:
            found_links = response.css(selector).getall()
            if found_links:
                self.logger.debug(f"Selector '{selector}' fand {len(found_links)} Links.")
                for link in found_links:
                     article_links.add(link) # Füge zum Set hinzu
            else:
                 self.logger.debug(f"Selector '{selector}' fand keine Links.")

        self.logger.info(f"Gefundene potenzielle Artikel-Links (gesamt, unique): {len(article_links)}")

        if not article_links:
             self.logger.warning(f"Keine Artikel-Links auf {response.url} mit den aktuellen Selektoren gefunden.")

        for article_url in article_links:
            if article_url:
                absolute_url = response.urljoin(article_url)
                # Filtert externe Links oder Links, die unwahrscheinlich Artikel sind
                if self.allowed_domains[0] in absolute_url and '/news/' in absolute_url: # Typische URL-Struktur? Anpassen!
                    self.logger.debug(f"Folge Artikel-Link: {absolute_url}")
                    yield scrapy.Request(absolute_url, callback=self.parse_article)
                else:
                    self.logger.debug(f"Überspringe Link (kein Artikel?): {absolute_url}")

    def parse_article(self, response):
        """Parse eine einzelne Artikelseite."""
        self.logger.info(f"Parsing Artikelseite: {response.url}")

        # === Annahmen für Golem.de Artikelinhalte ===
        # Passe diese Selektoren bei Bedarf an!
        # Neuer, spezifischer Selektor vom User als erste Priorität
        title = response.css('#screen > div:nth-child(2) > article > header > hgroup > h1 > span:nth-child(3)::text').get() or \
                response.css('header.head--article h1::text').get() or \
                response.css('h1::text').get()

        # Versuche, Absätze im Hauptinhalt zu extrahieren
        paragraphs = response.css('div.formatted p::text').getall() or \
                     response.css('article p::text').getall()
        # === Ende Annahmen ===

        article_text = '\n'.join(p.strip() for p in paragraphs if p.strip())

        if title and article_text:
            item = ArticleItem()
            item['url'] = response.url
            # Stelle sicher, dass der Titel sauber ist (keine überflüssigen Leerzeichen)
            item['title'] = title.strip()
            item['text'] = article_text
            item['source'] = self.name # Name des Spiders
            item['timestamp'] = datetime.datetime.now().isoformat()
            yield item
            self.logger.debug(f"Artikel extrahiert: {item['title']}")
        elif not title:
             self.logger.warning(f"Konnte Titel nicht extrahieren von: {response.url} mit Selektoren.")
        elif not article_text:
             self.logger.warning(f"Konnte Text nicht extrahieren von: {response.url} (Titel: {title.strip() if title else 'N/A'})")
        else: # Sollte nicht passieren, aber zur Sicherheit
            self.logger.warning(f"Konnte Titel oder Text nicht extrahieren von: {response.url}") 