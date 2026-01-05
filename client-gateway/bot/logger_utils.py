"""
Centralized logging utility for the Telegram taxi bot.
Provides structured logging with correlation IDs for tracking request lifecycle.
"""

import logging
import os
import uuid
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, 'bot.log')


class CorrelationIdFilter(logging.Filter):
    def filter(self, record):
        # Get correlation ID from extra dict if provided
        if not hasattr(record, 'correlationId'):
            record.correlationId = 'NONE'
        return True


def setup_logger(name='drive_ops', log_file=LOG_FILE):
    logger = logging.getLogger(name)
    
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.INFO)
    
    log_format = logging.Formatter(
        "[%(asctime)s] | [%(levelname)s] | [%(correlationId)s] | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Add filter to all handlers
    correlation_filter = CorrelationIdFilter()
    
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding='utf-8'
    )
    file_handler.setFormatter(log_format)
    file_handler.addFilter(correlation_filter)
    logger.addHandler(file_handler)
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_format)
    console_handler.addFilter(correlation_filter)
    logger.addHandler(console_handler)
    
    return logger


def generate_correlation_id():
    return str(uuid.uuid4())[:8]


def create_trip_request_logger():
    logger = setup_logger()
    return logger
