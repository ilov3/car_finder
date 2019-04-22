# -*- coding: utf-8 -*-
from urllib import parse

import scrapy
import json
from lxml import html
from scrapy.loader import ItemLoader
from scrapy.utils.request import request_fingerprint

from car_finder.items import CarItem

car_brands_map = {'alfaromeo': 'b_17',
                  'audi': 'b_2',
                  'bmw': 'b_3',
                  'chevrolet': 'b_20',
                  'citroen': 'b_4',
                  'ford': 'b_40',
                  'honda': 'b_43',
                  'infiniti': 'b_7',
                  'kia': 'b_25',
                  'lexus': 'b_9',
                  'mazda': 'b_29',
                  'mercedes': 'b_47',
                  'mitsubishi': 'b_51',
                  'nissan': 'b_52',
                  'opel': 'b_54',
                  'saab': 'b_30',
                  'skoda': 'b_15',
                  'subaru': 'b_62',
                  'suzuki': 'b_63',
                  'toyota': 'b_64',
                  'volvo': 'b_16',
                  'volkswagen': 'b_65', }
inverted_map = {a: b for b, a in car_brands_map.items()}
url_template = 'https://www.drive2.com/ajax/carsearch.cshtml?context={brand_id}&start={start}&sort=Selling'
base_url = 'https://www.drive2.com{}'


class Drive2Spider(scrapy.Spider):
    name = 'Drive2'
    allowed_domains = ['www.drive2.com', 'drive2.com', 'www.drive2.ru', 'drive2.ru']
    start_urls = [f'https://www.drive2.com/ajax/carsearch.cshtml?context={brand_id}&start=0&sort=Selling' for _, brand_id in car_brands_map.items()]
    counter = {brand: 0 for brand in car_brands_map.keys()}

    def parse(self, response):
        d = json.loads(response.body.strip())
        next_start = d.get('start', None)
        brand_id = self.get_brand_id(response.url)
        brand = inverted_map[brand_id]
        for item in self.parse_body(d['html'], brand_id):
            yield item
        if next_start and brand_id:
            yield scrapy.Request(url_template.format(brand_id=brand_id, start=next_start))
        else:
            print(f'Finished to parse brand: {brand}. Found {self.counter[inverted_map[brand_id]]} cars.')

    def parse_body(self, s, brand_id):
        try:
            tree = html.fromstring(s)
            for el in tree.xpath('//body/div/div'):
                price = self.get_price(el)
                title = self.get_title(el)
                url = self.get_url(el)
                geo = self.get_geo(el)
                if title:
                    self.counter[inverted_map[brand_id]] += 1
                    loader = ItemLoader(item=CarItem())
                    loader.add_value('price', price)
                    loader.add_value('title', title)
                    loader.add_value('url', url)
                    loader.add_value('city', geo)
                    loader.add_value('country', geo)
                    yield scrapy.Request(url, meta={'loader': loader}, callback=self.parse_car_sale_info)
        except Exception as e:
            print(f'Failed to parse body. Error: {e}')

    def parse_car_sale_info(self, response):
        loader = response.meta['loader']
        try:
            loader.add_value('url_fingerprint', request_fingerprint(response.request))
            loader.add_value('manufactured', self.get_years(response))
            loader.add_value('purchased', self.get_years(response))
            loader.add_value('brand', self.get_brand(response))
            loader.add_value('model', self.get_model(response))
            loader.add_value('generation', self.get_generation(response))
            yield loader.load_item()
        except Exception as e:
            self.logger.debug(f'Can not parse car info: {e}')
            yield loader.load_item()

    def get_years(self, response):
        try:
            years_pattern = "//div[@class='c-car-forsale']/ul/li[contains(text(), 'Manufactured') or contains(text(), 'Purchased')]"
            return response.xpath(years_pattern)[0].extract()
        except (IndexError, AttributeError):
            pass

    def get_brand(self, response):
        try:
            return response.xpath('//a[@data-ym-target="car2brand"]/text()')[0].extract()
        except (IndexError, AttributeError):
            pass

    def get_model(self, response):
        try:
            return response.xpath('//a[@data-ym-target="car2model"]/text()')[0].extract()
        except (IndexError, AttributeError):
            pass

    def get_generation(self, response):
        try:
            return response.xpath('//a[@data-ym-target="car2gen"]/text()')[0].extract()
        except (IndexError, AttributeError):
            pass

    def get_price(self, el):
        try:
            return el.xpath('div//span[@class="c-car-card__price"]')[0].text
        except (IndexError, AttributeError):
            self.logger.debug('Can not parse price')

    def get_title(self, el):
        try:
            return el.xpath('div//a[@class="c-car-title c-link c-link--text"]')[0].text
        except (IndexError, AttributeError):
            self.logger.debug('Can not parse title')

    def get_url(self, el):
        try:
            url = el.xpath('div//a[@class="c-car-title c-link c-link--text"]')[0].attrib['href']
            return base_url.format(url)
        except (IndexError, AttributeError):
            self.logger.debug('Can not parse url')

    def get_geo(self, el):
        try:
            return el.xpath('div//div[@class="c-car-card__info "]/span')[0].text
        except (IndexError, AttributeError):
            self.logger.debug('Can not parse geo')

    def get_brand_id(self, url):
        try:
            parsed = parse.urlparse(url)
            qs = parse.parse_qs(parsed.query)
            return qs['context'][0]
        except IndexError:
            self.logger.debug(f'Can\'t get brand id from url: f{url}.')
