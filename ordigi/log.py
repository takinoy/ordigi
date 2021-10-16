import logging


def level(verbose, debug):
    if debug:
        return logging.DEBUG
    elif verbose:
        return logging.INFO

    return logging.WARNING


def get_logger(name='ordigi', level=30):
    logging.basicConfig(format='%(levelname)s:%(message)s', level=level)
    logging.getLogger('asyncio').setLevel(level)
    logger = logging.getLogger(name)
    return logger
