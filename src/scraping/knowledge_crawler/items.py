# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class KnowledgeCrawlerItem(scrapy.Item):
    # define the fields for your item here like:
    # name = scrapy.Field()
    pass

class ArticleItem(scrapy.Item):
    # Definiere die Felder für die Artikeldaten
    url = scrapy.Field()
    title = scrapy.Field()
    text = scrapy.Field()
    source = scrapy.Field()
    timestamp = scrapy.Field()
