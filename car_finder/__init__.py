import logging
import os

LOG_FORMAT = '%(asctime)s::%(levelname)s::%(name)s::%(funcName)s::%(lineno)d:  %(message)s'
LOG_LEVEL = os.environ.get('LOG_LEVEL', logging.INFO)


def setup_logging():
    logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
    logging.getLogger('scrapy').setLevel(LOG_LEVEL)
    logging.getLogger('parso').setLevel(LOG_LEVEL)


setup_logging()
