# -*- coding: utf-8 -*-

# Define here the models for your spider middleware
#
# See documentation in:
# https://doc.scrapy.org/en/latest/topics/spider-middleware.html
import time
import logging

import requests
from lxml import html
from stem import Signal
from stem.control import Controller

from scrapy.crawler import Crawler
from scrapy.downloadermiddlewares.retry import RetryMiddleware
from scrapy.utils.response import response_status_message

from car_finder.settings import TOR_PROXY

logger = logging.getLogger(__name__)


class TooManyRequestsRetryMiddleware(RetryMiddleware):
    TRACK_LAST_ERRORS = 10
    WITHOUT_ERR_THRESHOLD = 30

    def __init__(self, settings):
        super(TooManyRequestsRetryMiddleware, self).__init__(settings)
        self.errors = []
        self.last_err_rate = 0
        self.delay = 0
        self.delay_inc = 0.05
        self.last_decrease_time = 0

    @classmethod
    def from_crawler(cls, crawler: Crawler):
        cls.crawler = crawler
        return cls(crawler.settings)

    def get_error_rate(self):
        if len(self.errors) < self.TRACK_LAST_ERRORS:
            return 0
        timedelta = self.errors[-1] - self.errors[-self.TRACK_LAST_ERRORS]
        return self.TRACK_LAST_ERRORS / timedelta

    def track_error(self):
        if len(self.errors) > self.TRACK_LAST_ERRORS:
            self.errors = self.errors[-self.TRACK_LAST_ERRORS:]
        self.errors.append(time.time())

    def compute_delay(self):
        rate = self.get_error_rate()
        base_delay_inc = self.delay_inc
        rate_diff = rate - self.last_err_rate
        delay_inc = min(base_delay_inc * max(abs(rate_diff), 0.1), base_delay_inc)
        if rate_diff <= 0 and rate < 0.05 and self.delay > delay_inc:
            self.delay -= delay_inc
            # logger.info(f'Decreasing delay: {self.delay:.2f} (-{delay_inc})')
        else:
            self.delay += delay_inc
            # logger.info(f'Increasing delay: {self.delay:.2f} (+{delay_inc})')
        self.last_err_rate = rate
        return self.delay

    def _get_slot(self, request):
        key = request.meta.get('download_slot')
        return key, self.crawler.engine.downloader.slots.get(key)

    def _decrease_delay(self, slot):
        now = time.time()
        if self.errors and (now - self.errors[-1]) > self.WITHOUT_ERR_THRESHOLD and (now - self.last_decrease_time) > self.WITHOUT_ERR_THRESHOLD:
            # logger.info(f'Decreasing delay: {self.delay}')
            slot.delay = self.compute_delay()
            self.last_decrease_time = now

    def process_request(self, request, spider):
        if TOR_PROXY:
            request.meta["proxy"] = TOR_PROXY

    def process_response(self, request, response, spider):
        # key, slot = self._get_slot(request)
        if request.meta.get('dont_retry', False):
            return response
        elif response.status == 429:
            logger.info(f'Got 429, rate: {self.get_error_rate()}')
            self.track_error()
            # slot.delay = self.compute_delay()
            request.meta['max_retry_times'] = 1000
            reason = response_status_message(response.status)
            return self._retry(request, reason, spider) or response
        elif response.status in self.retry_http_codes:
            reason = response_status_message(response.status)
            return self._retry(request, reason, spider) or response
        elif response.status == 403:
            logger.info('Got 403')
            request.meta['max_retry_times'] = 1000
        # self._decrease_delay(slot)

        return response


class ConnectionManager:
    def __init__(self, tor_passw):
        self.current_identity = None
        self.passw = tor_passw
        self.controller = Controller.from_port(port=9900)
        self.controller.authenticate(password='JlzLCVylvNsa1LsvCU')

    def _get_connection(self):
        """
        TOR new connection
        """
        self.controller.signal(Signal.NEWNYM)

    def __del__(self):
        logger.info('Closing TOR connection manager')
        self.controller.close()

    @staticmethod
    def request(url):
        """
        TOR communication through local proxy
        :param url: web page to parser
        :return: request
        """
        try:
            return requests.get(url, proxies={
                'http': TOR_PROXY,
                'https': TOR_PROXY,
            }, timeout=5)
        except (requests.Timeout, requests.ConnectionError):
            pass

    def get_current_identity(self):
        resp = self.request("https://check.torproject.org/")
        if resp and resp.status_code == 200:
            try:
                tree = html.fromstring(resp.text)
                return tree.xpath('//strong')[0].text
            except Exception as e:
                logger.error(f'Could not parse ip addr from response: {e}')

    def new_identity(self):
        logger.info(f'Requesting new identity')
        start = time.time()
        old_id = self.current_identity
        counter = 0
        while True:
            counter += 1
            self._get_connection()
            new_id = self.get_current_identity()
            if new_id and new_id != old_id:
                break
            time.sleep(0.1)
        self.current_identity = new_id
        logger.info(f'Got new identity: {new_id}, {counter} iterations, {time.time() - start:.2f}sec')


class TorProxyDownloader:
    def __init__(self, settings):
        self.settings = settings
        self.tor_mgr = ConnectionManager(settings.get('TOR_PASSWORD'))
        self.tor_mgr.new_identity()

    @classmethod
    def from_crawler(cls, crawler: Crawler):
        cls.crawler = crawler
        return cls(crawler.settings)

    def process_request(self, request, spider):
        request.meta["proxy"] = TOR_PROXY

    def process_response(self, request, response, spider):
        if response.status == 403:
            logger.info('GOT 403')
            self.crawler.engine.pause()
            request.meta['max_retry_times'] = 30
            self.tor_mgr.new_identity()
            self.crawler.engine.unpause()
        return response
