import hashlib
import json
import logging
import sys


def hash_properties(properties: dict) -> str:
    """
    :param properties: GQL type or field properties
    :return: md5 hash

    Hash the properties so we can quickly determine if there are new changes to existing nodes when importing the schema
    """
    hash = hashlib.md5(json.dumps(
        properties, sort_keys=True).encode("utf-8")).hexdigest()

    return hash


def get_logger(path: str = "debug.log") -> logging.Logger:
    """
    :param path: path to log file
    :return: a logger instance that writes to file in path
    """
    logger = logging.getLogger()
    if not len(logger.handlers):
        logger.setLevel(logging.DEBUG)

        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setLevel(logging.WARN)
        stream_handler.setFormatter(logging.Formatter(
            "%(asctime)s:%(levelname)s: %(message)s"))
        logger.addHandler(stream_handler)

        handler = logging.FileHandler(path)
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s:%(levelname)s: %(message)s"))
        logger.addHandler(handler)

    return logger
