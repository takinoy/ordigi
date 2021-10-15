"""
Settings.
"""

from os import environ, path

#: If True, debug messages will be printed.
debug = False

# Ordigi settings directory.
if 'XDG_CONFIG_HOME' in environ:
    confighome = environ['XDG_CONFIG_HOME']
elif 'APPDATA' in environ:
    confighome = environ['APPDATA']
else:
    confighome = path.join(environ['HOME'], '.config')
application_directory = path.join(confighome, 'ordigi')

default_path = '{%Y-%m-%b}/{album}|{city}'
default_name = '{%Y-%m-%d_%H-%M-%S}-{name}-{title}.%l{ext}'
default_geocoder = 'Nominatim'

CONFIG_FILE = f'{application_directory}/ordigi.conf'
