# -*- coding: utf-8 -*-
# Owner: Bulat <bulat.kurbangaliev@cinarra.com>
import logging
from datetime import timedelta
from multiprocessing import Process
from time import time, sleep
import django

django.setup()

from django.conf import settings
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from car_finder_app.models import SpiderRun
from spiders.Drive2 import Drive2Spider

__author__ = 'ilov3'
logger = logging.getLogger(__name__)


def start_crawl():
    spider_run = SpiderRun.objects.create()
    start = time()
    process = CrawlerProcess(get_project_settings())
    process.crawl(Drive2Spider)
    process.start()
    spider_run.duration = timedelta(seconds=time() - start)
    spider_run.save()


if __name__ == '__main__':
    # start_crawl()
    while True:
        p = Process(target=start_crawl)
        p.start()
        p.join()
        sleep(settings.SCRAPY_LAUNCH_INTERVAL)
