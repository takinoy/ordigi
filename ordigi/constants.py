"""
Settings.
"""

from os import environ, path
from sys import version_info

#: If True, debug messages will be printed.
debug = False

#Ordigi settings directory.
if 'XDG_CONFIG_HOME' in environ:
    confighome = environ['XDG_CONFIG_HOME']
elif 'APPDATA' in environ:
    confighome = environ['APPDATA']
else:
    confighome = path.join(environ['HOME'], '.config')
application_directory = path.join(confighome, 'ordigi')

default_path = '{%Y-%m-%b}/{album}|{city}|{"Unknown Location"}'
default_name = '{%Y-%m-%d_%H-%M-%S}-{name}-{title}.%l{ext}'
default_geocoder = 'Nominatim'
# Checksum storage file.
hash_db = 'hash.json'
# TODO  will be removed eventualy later
# hash_db = '{}/hash.json'.format(application_directory)

# Geolocation details file.
location_db = 'location.json'
# TODO  will be removed eventualy later
# location_db = '{}/location.json'.format(application_directory)

# Ordigi installation directory.
script_directory = path.dirname(path.dirname(path.abspath(__file__)))

#: Accepted language in responses from MapQuest
accepted_language = 'en'

# check python version, required in filesystem.py to trigger appropriate method
python_version = version_info.major

CONFIG_FILE = f'{application_directory}/ordigi.conf'
