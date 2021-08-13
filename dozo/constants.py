"""
Settings.
"""

from os import environ, path
from sys import version_info

#: If True, debug messages will be printed.
debug = False

#: Directory in which to store Dozo settings.
application_directory = '{}/.dozo'.format(path.expanduser('~'))
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

# Dozo installation directory.
script_directory = path.dirname(path.dirname(path.abspath(__file__)))

#: Accepted language in responses from MapQuest
accepted_language = 'en'

# check python version, required in filesystem.py to trigger appropriate method
python_version = version_info.major

CONFIG_FILE = '%s/config.ini' % application_directory
