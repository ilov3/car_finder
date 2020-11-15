# -*- coding: utf-8 -*-

# Define here the models for your scraped items
#
# See documentation in:
# https://doc.scrapy.org/en/latest/topics/items.html
import re
import scrapy
from scrapy.loader.processors import MapCompose, TakeFirst

from car_finder import settings


def extract_price(value):
    if '$' in value:
        return int(''.join([char for char in value if char.isdigit()])) * settings.RUB_IN_USD
    elif '₽' in value:
        return int(''.join([char for char in value if char.isdigit()]))


def get_city(value):
    try:
        return value.split(',')[0].strip()
    except IndexError:
        pass


def get_country(value):
    try:
        return value.split(',')[1].strip()
    except IndexError:
        pass


def extract_manufactured(value):
    try:
        return int(re.template('manufactured in (\d\d\d\d)', flags=re.IGNORECASE).findall(value)[0])
    except IndexError:
        pass


def extract_purchased(value):
    try:
        return int(re.template('purchased in (\d\d\d\d)', flags=re.IGNORECASE).findall(value)[0])
    except IndexError:
        pass


class CarItem(scrapy.Item):
    url_fingerprint = scrapy.Field(output_processor=TakeFirst())
    model = scrapy.Field(output_processor=TakeFirst())
    generation = scrapy.Field(output_processor=TakeFirst())
    brand = scrapy.Field(output_processor=TakeFirst())
    price = scrapy.Field(input_processor=MapCompose(extract_price), output_processor=TakeFirst(), )
    manufactured = scrapy.Field(input_processor=MapCompose(extract_manufactured), output_processor=TakeFirst(), )
    purchased = scrapy.Field(input_processor=MapCompose(extract_purchased), output_processor=TakeFirst(), )
    title = scrapy.Field(output_processor=TakeFirst())
    city = scrapy.Field(input_processor=MapCompose(get_city), output_processor=TakeFirst())
    country = scrapy.Field(input_processor=MapCompose(get_country), output_processor=TakeFirst())
    url = scrapy.Field(output_processor=TakeFirst())


class BaseNameableItem(scrapy.Item):
    name = scrapy.Field()


class Country(BaseNameableItem):
    pass


class City(BaseNameableItem):
    country = scrapy.Field()


class CarBrand(BaseNameableItem):
    pass


class CarModel(BaseNameableItem):
    brand = scrapy.Field()


class Generation(BaseNameableItem):
    model = scrapy.Field()


class Car(scrapy.Item):
    model = scrapy.Field()
    generation = scrapy.Field()
    manufactured = scrapy.Field()
    purchased = scrapy.Field()
    name = scrapy.Field()
    city = scrapy.Field()
    country = scrapy.Field()
    capacity = scrapy.Field()
    horse_power = scrapy.Field()
    engine_type = scrapy.Field()
    gear_type = scrapy.Field()
    transmission = scrapy.Field()
    url_fingerprint = scrapy.Field()
    url = scrapy.Field()


class CarSaleItem(scrapy.Item):
    price = scrapy.Field()
    url_fingerprint = scrapy.Field()
    url = scrapy.Field()
