"""Logging module"""

import logging


def get_logger(name, level=30):
    """Get logger"""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    return logger


def log_format(level):
    if level > 10:
        return '%(levelname)s:%(message)s'

    return '%(levelname)s:%(name)s:%(message)s'


def set_formatter(handler, level):
    """create formatter and add it to the handlers"""
    formatter = logging.Formatter(log_format(level))
    handler.setFormatter(formatter)


def console(logger, level=30):
    """create console handler with a higher log level"""
    logger.setLevel(level)
    handler = logging.StreamHandler()
    handler.setLevel(level)
    set_formatter(handler, level)

    # add the handlers to logger
    logger.addHandler(handler)


def file_logger(logger, file, level=30):
    """create file handler that logs debug and higher level messages"""
    logger.setLevel(level)
    handler = logging.FileHandler(file)
    handler.setLevel(level)
    set_formatter(handler, log_format(level))

    # add the handlers to logger
    logger.addHandler(handler)


def get_level(verbose):
    """Return int logging level from string"""
    if verbose.isnumeric():
        return int(verbose)

    return int(logging.getLevelName(verbose))
