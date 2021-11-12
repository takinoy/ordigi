"""Logging module"""

import logging


def get_level(verbose):
    """Return int logging level from string"""
    if verbose.isnumeric():
        return int(verbose)

    return int(logging.getLevelName(verbose))


def get_logger(name='ordigi', level=30):
    """Get configured logger"""
    if level > 10:
        log_format='%(levelname)s:%(message)s'
    else:
        log_format='%(levelname)s:%(name)s:%(message)s'

    logging.basicConfig(format=log_format, level=level)
    logging.getLogger('asyncio').setLevel(level)
    logger = logging.getLogger(name)
    logger.setLevel(level)

    return logger
