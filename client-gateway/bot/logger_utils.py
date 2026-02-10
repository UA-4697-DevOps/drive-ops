"""
Centralized logging utility for the Telegram taxi bot.
Provides structured JSON logging with correlation IDs for CloudWatch.
"""

import logging
import os
import uuid
from logging.handlers import RotatingFileHandler
from pythonjsonlogger import jsonlogger

LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, 'bot.log')

# Environment variable to control log format (json for production/CloudWatch, text for local dev)
LOG_FORMAT = os.getenv('LOG_FORMAT', 'json').lower()


class CloudWatchJsonFormatter(jsonlogger.JsonFormatter):
    """
    Custom JSON formatter that adds service metadata and ensures 
    all fields are properly formatted for CloudWatch Logs.
    """
    def add_fields(self, log_record, record, message_dict):
        super(CloudWatchJsonFormatter, self).add_fields(log_record, record, message_dict)
        
        # Add service identifier
        log_record['service'] = 'client-gateway'
        
        # Ensure timestamp is present with proper ISO 8601 format
        if not log_record.get('timestamp'):
            import datetime
            dt = datetime.datetime.fromtimestamp(record.created, tz=datetime.timezone.utc)
            log_record['timestamp'] = dt.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        
        # Add level name
        log_record['level'] = record.levelname
        
        # Ensure correlationId is always present
        if not log_record.get('correlationId'):
            log_record['correlationId'] = 'NONE'
        
        # Add logger name for traceability
        log_record['logger'] = record.name
        
        # Include source location for debugging
        log_record['source'] = f"{record.filename}:{record.lineno}"


class CorrelationIdFilter(logging.Filter):
    """
    Filter to ensure correlationId field is always present in log records.
    """
    def filter(self, record):
        if not hasattr(record, 'correlationId'):
            record.correlationId = 'NONE'
        return True


def setup_logger(name='drive_ops', log_file=LOG_FILE):
    """
    Setup logger with JSON structured logging for CloudWatch or text format for local dev.
    
    Args:
        name: Logger name
        log_file: Path to log file
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.INFO)
    
    # Choose formatter based on LOG_FORMAT environment variable
    if LOG_FORMAT == 'json':
        # JSON formatter for CloudWatch
        formatter = CloudWatchJsonFormatter(
            '%(timestamp)s %(level)s %(message)s %(correlationId)s %(service)s',
            datefmt='%Y-%m-%dT%H:%M:%S.%fZ'
        )
    else:
        # Text formatter for local development
        formatter = logging.Formatter(
            "[%(asctime)s] | [%(levelname)s] | [%(correlationId)s] | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    
    # Add correlation ID filter
    correlation_filter = CorrelationIdFilter()
    
    # File handler with rotation
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(correlation_filter)
    logger.addHandler(file_handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(correlation_filter)
    logger.addHandler(console_handler)
    
    return logger


def generate_correlation_id():
    """
    Generate a short correlation ID for tracking requests.
    
    Returns:
        8-character UUID prefix
    """
    return str(uuid.uuid4())[:8]


def create_trip_request_logger():
    """
    Create a logger instance for trip request tracking.
    
    Returns:
        Configured logger instance
    """
    logger = setup_logger()
    return logger
