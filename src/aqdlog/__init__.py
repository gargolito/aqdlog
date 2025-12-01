# async_logging.py
import queue
import logging
from logging.handlers import QueueHandler, QueueListener


class DuplicateFilter(logging.Filter):
    def __init__(self):
        super().__init__()
        self.logged_messages = set()

    def filter(self, record):
        log_entry = (
            record.levelno,
            record.getMessage(),
        )  # Only consider level and message
        if log_entry in self.logged_messages:
            return False
        self.logged_messages.add(log_entry)
        return True


def log(name: str, level="INFO", log_file=None) -> logging.Logger:
    """
    Create an asynchronous logger using a QueueHandler and a QueueListener.

    Args:
        name (str): The name of the logger.
        level (int): The logging level, e.g., logging.INFO, logging.DEBUG, etc.

    Returns:
        logging.Logger: The configured asynchronous logger.
    """
    logger = logging.getLogger(name)
    if logger.hasHandlers():
        # If the logger has handlers, it means it's already set up.
        return logger

    duplicate_filter = DuplicateFilter()
    # Set up logging with a QueueHandler
    log_queue = queue.Queue(-1)  # Use a queue with no size limit
    queue_handler = QueueHandler(log_queue)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(funcName)s:%(lineno)s - %(message)s"
    )
    queue_handler.setFormatter(formatter)

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.addHandler(queue_handler)

    logger.addFilter(duplicate_filter)
    # If a log_file is specified, add a FileHandler to the logger
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    else:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # Set up a QueueListener to handle log records from the QueueHandler
    queue_listener = QueueListener(log_queue, *logger.handlers)

    # Start the QueueListener
    queue_listener.start()

    # Add a shutdown method to the logger to stop the QueueListener
    def shutdown():
        """
        Stop the QueueListener to ensure that all log messages are properly
        written and to close the logging handlers.
        """
        queue_listener.stop()

    logger.shutdown = shutdown()

    return logger

__all__ = ["log"]

