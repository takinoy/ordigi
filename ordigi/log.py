"""Logging module"""

import logging
from pathlib import Path

from ordigi.utils import check_dir, date_now


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


def file_logger(logger, root, level=30):
    """create file handler that logs debug and higher level messages"""
    ordigi_dir = Path(root, '.ordigi')
    check_dir(ordigi_dir)
    file = Path(ordigi_dir, 'ordigi_' + date_now("%y%m%d-%H%M%S") + '.log')
    open(file, 'a').close()
    logger.setLevel(level)
    handler = logging.FileHandler(file)
    handler.setLevel(level)
    set_formatter(handler, level)

    # add the handlers to logger
    logger.addHandler(handler)


def get_level(quiet=False, verbose=False, debug=False, num=None):
    """Return int logging level from command line args"""
    if num and num.isnumeric():
        return int(num)

    if debug:
        return int(logging.getLevelName('DEBUG'))
    if verbose:
        return int(logging.getLevelName('INFO'))
    if quiet:
        return int(logging.getLevelName('ERROR'))

    return int(logging.getLevelName('WARNING'))


def init_logger(logger, root, log_level, dry_run=False, log_option=False):
    if not dry_run and log_option:
        file_logger(logger, root, level=log_level)
    else:
        console(logger, level=log_level)
