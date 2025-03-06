import logging
from logging.handlers import RotatingFileHandler

print("Logging handlers available:", dir(logging.handlers))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler('test.log', maxBytes=1000000, backupCount=3),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logger.info("Test message from isolated logging configuration")