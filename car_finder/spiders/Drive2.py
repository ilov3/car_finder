# -*- coding: utf-8 -*-
import logging
from urllib import parse

import requests
import scrapy
import json
from lxml import html
from scrapy import signals
from scrapy.loader import ItemLoader
from scrapy.utils.request import request_fingerprint

from car_finder.items import CarItem, Country
from car_finder.settings import REST_API_HOST, REST_API_PORT

logger = logging.getLogger(__name__)

car_brands_map = {
    'alfaromeo': 'b_17',
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
    'seat': 'b_14',
    'skoda': 'b_15',
    'subaru': 'b_62',
    'suzuki': 'b_63',
    'toyota': 'b_64',
    'volvo': 'b_16',
    'volkswagen': 'b_65',
    'hyundai': 'b_6',
}
inverted_map = {a: b for b, a in car_brands_map.items()}
url_template = 'https://www.drive2.com/ajax/carsearch.cshtml?context={brand_id}&start={start}&sort=Selling'
base_url = 'https://www.drive2.com{}'


class Drive2Spider(scrapy.Spider):
    name = 'Drive2'
    handle_httpstatus_list = [429]
    allowed_domains = ['www.drive2.com', 'drive2.com', 'www.drive2.ru', 'drive2.ru']
    start_urls = [url_template.format(brand_id=brand_id, start=0) for _, brand_id in car_brands_map.items()]
    counter = {brand: 0 for brand in car_brands_map.keys()}

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        crawler.signals.connect(spider.spider_closed, signal=signals.spider_closed)
        return spider

    def spider_closed(self, spider):
        spider.logger.info('Spider closed: %s', spider.name)
        url = f'http://{REST_API_HOST}:{REST_API_PORT}/spider-finished'
        requests.post(url)

    def parse(self, response, **kwargs):
        d = json.loads(response.body.strip())
        next_start = d.get('start', None)
        brand_id = self.get_brand_id(response.url)
        brand = inverted_map[brand_id]
        for item in self.parse_list_of_sales(d['html'], brand_id):
            yield item
        if next_start and brand_id:
            yield scrapy.Request(url_template.format(brand_id=brand_id, start=next_start), meta=dict(download_slot=self.name))
        else:
            logger.info(f'Finished to parse brand: {brand}. Found {self.counter[inverted_map[brand_id]]} cars.')

    def parse_list_of_sales(self, s, brand_id):
        try:
            tree = html.fromstring(s)
            for el in tree.xpath('//body/div/div[contains(@class, "c-car-card-sa")]'):
                price = self.get_price(el)
                title = self.get_title(el)
                url = self.get_url(el)
                image_url = self.get_img_url(el)
                geo = self.get_geo(el)
                if title:
                    self.counter[inverted_map[brand_id]] += 1
                    country_loader = ItemLoader(item=Country())
                    country_loader.add_value('country', geo)
                    loader = ItemLoader(item=CarItem())
                    loader.add_value('price', price)
                    loader.add_value('title', title)
                    loader.add_value('url', url)
                    loader.add_value('city', geo)
                    loader.add_value('country', geo)
                    loader.add_value('image_urls', image_url)
                    yield scrapy.Request(url, meta={'loader': loader, 'download_slot': self.name}, callback=self.parse_car_sale_info)
        except Exception as e:
            logger.error(f'Failed to parse body. Error: {e}')

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
            logger.error(f'Can not parse car info: {e}')

    def get_img_url(self, el):
        try:
            return el.xpath('div/div/img')[0].attrib['src']
        except Exception as e:
            logger.error(f'Can not parse image url: {e}')

    def get_years(self, response):
        try:
            years_pattern = "//div[@class='c-car-forsale']/ul/li[contains(text(), 'Manufactured') or contains(text(), 'Purchased')]"
            return response.xpath(years_pattern)[0].extract()
        except (IndexError, AttributeError):
            logger.debug('Can not parse years')

    def get_brand(self, response):
        try:
            return response.xpath('//a[@data-ym-target="car2brand"]/text()')[0].extract()
        except (IndexError, AttributeError):
            logger.debug('Can not parse brand')

    def get_model(self, response):
        try:
            return response.xpath('//a[@data-ym-target="car2model"]/text()')[0].extract()
        except (IndexError, AttributeError):
            logger.debug('Can not parse model')

    def get_generation(self, response):
        try:
            return response.xpath('//a[@data-ym-target="car2gen"]/text()')[0].extract()
        except (IndexError, AttributeError):
            logger.debug('Can not parse generation')

    def get_price(self, el):
        try:
            return el.xpath('div//span[@class="c-car-card-sa__price"]')[0].text
        except (IndexError, AttributeError):
            logger.debug(f'Can not parse price from elem: {el}')

    def get_title(self, el):
        try:
            return el.xpath('div//span[@class="c-car-title  c-link"]')[0].text
        except (IndexError, AttributeError):
            logger.debug(f'Can not parse title from elem: {el}')

    def get_url(self, el):
        try:
            url = el.xpath('a[@class="u-link-area"]')[0].attrib['href']
            return base_url.format(url)
        except (IndexError, AttributeError):
            logger.debug(f'Can not parse url from elem: {el}')

    def get_geo(self, el):
        try:
            return el.xpath('div/div[@class="c-car-card-sa__location"]/span')[0].text
        except (IndexError, AttributeError):
            logger.debug(f'Can not parse geo from elem: {el}')

    def get_brand_id(self, url):
        try:
            parsed = parse.urlparse(url)
            qs = parse.parse_qs(parsed.query)
            return qs['context'][0]
        except IndexError:
            logger.debug(f'Can\'t get brand id from url: f{url}.')

    def get_car_attr(self, el, filter_str):
        try:
            return el.xpath(f"//div[@class='c-car-forsale']/ul/li[contains(text(), {filter_str})]")[0].extract()
        except IndexError:
            logger.debug(f'Could not get attribute by filter {filter_str}')

    def get_mileage(self, el):
        return self.get_car_attr(el, 'Mileage')

    def get_engine_info(self, el):
        return self.get_car_attr(el, 'Engine')

    def get_gearbox_type(self, el):
        try:
            return el.xpath("//div[@class='c-car-forsale']/ul/li[contains(text(), 'Manual') or contains(text(), 'Automatic')]")[0].extract()
        except IndexError:
            logger.debug(f'Could not get gearbox type')
