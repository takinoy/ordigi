"""
Settings.
"""

from os import environ
from pathlib import Path

#: If True, debug messages will be printed.
debug = False


# Ordigi settings directory.
def get_config_dir(name):
    if 'XDG_CONFIG_HOME' in environ:
        confighome = Path(environ['XDG_CONFIG_HOME'])
    elif 'APPDATA' in environ:
        confighome = Path(environ['APPDATA'])
    else:
        confighome = Path(environ['HOME'], '.config')

    return confighome / name


APPLICATION_DIRECTORY = get_config_dir('ordigi')

DEFAULT_PATH = '{%Y-%m-%b}/{album}|{city}'
DEFAULT_NAME = '{%Y-%m-%d_%H-%M-%S}-{name}-{title}.%l{ext}'
DEFAULT_PATH_FORMAT = DEFAULT_PATH + '/' + DEFAULT_NAME
DEFAULT_GEOCODER = 'Nominatim'

CONFIG_FILE = APPLICATION_DIRECTORY / 'ordigi.conf'
