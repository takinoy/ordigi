import logging

def get_logger(verbose, debug):
    if debug:
        level = logging.DEBUG
    elif verbose:
        level = logging.INFO
    else:
        level = logging.WARNING

    logging.basicConfig(format='%(levelname)s:%(message)s', level=level)
    logging.getLogger('asyncio').setLevel(level)
    logger = logging.getLogger('ordigi')
    logger.level = level
    return logger

