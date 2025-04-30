# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter
import logging
import uuid

logger = logging.getLogger(__name__)

class LearningManagerPipeline:

    def __init__(self):
        # Initialisiere Zähler
        self.items_processed = 0
        self.items_added_to_db = 0
        logger.info("LearningManagerPipeline initialisiert.")

    def close_spider(self, spider):
        """Wird aufgerufen, wenn der Spider beendet wird."""
        logger.info(f"Pipeline beendet. Verarbeitete Items: {self.items_processed}, Zur DB hinzugefügt: {self.items_added_to_db}")
        # Hier könnten noch DB-Verbindungen geschlossen werden, falls nötig
        # Der LearningManager sollte das aber intern handhaben.

    def process_item(self, item, spider):
        """Verarbeitet jedes Item, das vom Spider kommt."""
        self.items_processed += 1
        adapter = ItemAdapter(item)

        # Hole den LearningManager direkt vom Spider
        learning_manager = getattr(spider, 'learning_manager', None)

        if not learning_manager:
            logger.error(f"LearningManager nicht im Spider gefunden ({spider.name}). Überspringe Item: {adapter.get('url')}")
            return item

        try:
            doc_id = f"web_{adapter.get('source')}_{uuid.uuid5(uuid.NAMESPACE_URL, adapter.get('url'))}"

            metadata = {
                "entry_type": "web_content",
                "source": adapter.get('source', spider.name),
                "url": adapter.get('url'),
                "original_title": adapter.get('title'),
                "crawl_timestamp": adapter.get('timestamp')
            }

            content = adapter.get('text', '')

            if content:
                 logger.debug(f"Füge Eintrag zur DB hinzu: ID={doc_id}, URL={adapter.get('url')}")
                 # Verwende die Instanz vom Spider
                 learning_manager.add_entry(
                     doc_id=doc_id,
                     content=content,
                     metadata=metadata
                 )
                 self.items_added_to_db += 1
                 logger.info(f"Eintrag erfolgreich zur DB hinzugefügt: {adapter.get('url')}")
            else:
                 logger.warning(f"Kein Text im Item gefunden, überspringe DB-Eintrag für URL: {adapter.get('url')}")

        except Exception as e:
            logger.error(f"Fehler beim Verarbeiten/Hinzufügen des Items zur DB (URL: {adapter.get('url')}): {e}", exc_info=True)

        return item
