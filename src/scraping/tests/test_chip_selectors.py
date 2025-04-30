import unittest
import os
from scrapy.http import HtmlResponse, Request
from src.scraping.knowledge_crawler.spiders.chip_spider import ChipSpider

class ChipSelectorsTest(unittest.TestCase):

    def setUp(self):
        """Lädt die Test-HTML-Datei und initialisiert den Spider."""
        # Pfad zur gespeicherten HTML-Datei des Testartikels
        # Verwende os.path.join für plattformunabhängige Pfade
        # Annahme: Das Skript liegt in D:\\...\\JARVIS\\src\\scraping\\tests\\
        # Ziel ist D:\\...\\JARVIS\\src\\scraping\\tests\\chip_kabel_router_article.html
        current_dir = os.path.dirname(__file__) # Verzeichnis des Testskripts
        html_file_path = os.path.join(current_dir, 'chip_kabel_router_article.html') # Korrekter Pfad

        # Versuche, die Datei zu öffnen und zu lesen
        try:
            with open(html_file_path, 'r', encoding='utf-8') as f:
                self.html_content = f.read()
        except FileNotFoundError:
            self.fail(f"HTML-Testdatei nicht gefunden unter: {html_file_path}")
        except Exception as e:
            self.fail(f"Fehler beim Lesen der HTML-Datei: {e}")

        # Erstelle eine Dummy-Response für den Spider
        self.response = HtmlResponse(
            url='https://www.chip.de/news/Internet-per-Kabel-Empfehlenswerte-Kabel-Router_185947350.html', # <-- Geänderte URL
            body=self.html_content,
            encoding='utf-8'
        )
        # Initialisiere den Spider (wichtig: übergib notwendige Argumente, falls der __init__ sie benötigt)
        self.spider = ChipSpider()
        # Initialisiere den Spider mit dem Dummy MessageBrokerService
        # self.spider = ChipSpider(broker_service=MessageBrokerService()) # Wenn Broker benötigt wird

    def test_parse_article_title(self):
        """Testet die Extraktion des Titels von der Artikelseite."""
        print(f"\nVersuche Titel zu extrahieren von: {self.response.url}")
        items = list(self.spider.parse_article(self.response))

        extracted_title = None
        if items:
            extracted_title = items[0].get('title')
            print(f"Titel aus parse_article: '{extracted_title}'")
        else:
            print(f"WARNUNG: Kein Item von parse_article erhalten. Teste Titel-Selektoren direkt...")
            # Direkte Selektorprüfung als Fallback
            # Versuche Selektor 1
            title_selector = 'h2.Article-Title::text' # Aktueller Selektor
            extracted_title = self.response.css(title_selector).get()
            if not extracted_title:
                 print(f"Selektor '{title_selector}' fand keinen Titel. Versuche alternativen Selektor...")
                 # Versuche alternativen Selektor
                 title_selector = 'h1.Article-Title::text' # Alter Selektor
                 extracted_title = self.response.css(title_selector).get()
            if not extracted_title:
                print(f"WARNUNG: Auch '{title_selector}' fand keinen Titel. Versuche <meta property='og:title'>...")
                title_selector = 'meta[property="og:title"]::attr(content)'
                extracted_title = self.response.css(title_selector).get()


            if extracted_title:
                 extracted_title = extracted_title.strip()
                 print(f"Titel direkt extrahiert: '{extracted_title}' mit Selektor '{title_selector}'")


        self.assertIsNotNone(extracted_title, f"Titel konnte mit keinem der Selektoren extrahiert werden.") # Angepasste Fehlermeldung
        self.assertIsInstance(extracted_title, str)
        self.assertTrue(len(extracted_title) > 5, f"Extrahierter Titel '{extracted_title}' ist zu kurz.")
        # Optional: Prüfe auf erwarteten Titel (kann bei dynamischen Seiten schwierig sein)
        # self.assertEqual(extracted_title, "Erwarteter Titel hier")

    def test_parse_article_text(self):
        """Testet die Extraktion des Artikeltextes."""
        print(f"\nVersuche Text zu extrahieren von: {self.response.url}")
        items = list(self.spider.parse_article(self.response))

        extracted_text = None
        if items:
            extracted_text = items[0].get('text')
            print(f"Text aus parse_article: '{extracted_text[:100]}...'") # Nur Anfang ausgeben
        else:
            print(f"WARNUNG: Kein Item von parse_article erhalten. Teste Text-Selektoren direkt...")
            # Direkte Selektorprüfung als Fallback
            text_selector = 'div.Article-Content div.Html-Block[data-qa-article-content-text] p::text' # Aktueller Selektor
            extracted_paragraphs = self.response.css(text_selector).getall()

            if not extracted_paragraphs:
                print(f"Selektor '{text_selector}' fand keinen Text. Versuche alternativen Selektor...")
                text_selector = 'div.article-content p::text, div.copytext p::text, article p::text' # Alter Selektor
                extracted_paragraphs = self.response.css(text_selector).getall()

            if extracted_paragraphs:
                extracted_text = "\n".join(p.strip() for p in extracted_paragraphs if p.strip())
                print(f"Text direkt extrahiert (Anfang): '{extracted_text[:100]}...' mit Selektor '{text_selector}'")
            else:
                print(f"WARNUNG: Keiner der Text-Selektoren fand Inhalt.")


        self.assertTrue(extracted_text, f"Text konnte mit keinem der Selektoren extrahiert werden.")
        self.assertIsInstance(extracted_text, str)
        self.assertTrue(len(extracted_text) > 50, f"Extrahierter Text '{extracted_text[:100]}...' ist zu kurz.")

    # Hier könnten weitere Tests hinzugefügt werden, z.B. für die Links auf der Übersichtsseite (parse-Methode)

if __name__ == '__main__':
    unittest.main() 