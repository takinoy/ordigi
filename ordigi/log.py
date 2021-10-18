import logging


def level(verbose, debug):
    if debug:
        return logging.DEBUG
    elif verbose:
        return logging.INFO

    return logging.WARNING


def get_logger(name='ordigi', level=30):
    if level > 10:
        format='%(levelname)s:%(message)s'
    else:
        format='%(levelname)s:%(name)s:%(message)s'

    logging.basicConfig(format=format, level=level)
    logging.getLogger('asyncio').setLevel(level)
    logger = logging.getLogger(name)
    return logger
