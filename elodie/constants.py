"""
Settings used by Elodie.
"""

from os import environ, path
from sys import version_info

#: If True, debug messages will be printed.
debug = False

#: Directory in which to store Elodie settings.
application_directory = '{}/.elodie'.format(path.expanduser('~'))
if (
        'ELODIE_APPLICATION_DIRECTORY' in environ and
        path.isdir(environ['ELODIE_APPLICATION_DIRECTORY'])
   ):
    application_directory = environ['ELODIE_APPLICATION_DIRECTORY']

default_path = '{%Y-%m-%b}/{album}|{city}|{"Unknown Location"}'
default_name = '{%Y-%m-%d_%H-%M-%S}-{original_name}-{title}.{ext}'

#: File in which to store details about media Elodie has seen.
hash_db = 'hash.json'
# TODO  will be removed eventualy later
# hash_db = '{}/hash.json'.format(application_directory)

#: File in which to store geolocation details about media Elodie has seen.
location_db = 'location.json'
# TODO  will be removed eventualy later
# location_db = '{}/location.json'.format(application_directory)

#: Elodie installation directory.
script_directory = path.dirname(path.dirname(path.abspath(__file__)))

#: Path to Elodie's ExifTool config file.
exiftool_config = path.join(script_directory, 'configs', 'ExifTool_config')

#: Path to MapQuest base URL
mapquest_base_url = 'https://open.mapquestapi.com'
if (
        'ELODIE_MAPQUEST_BASE_URL' in environ and
        environ['ELODIE_MAPQUEST_BASE_URL'] != ''
    ):
    mapquest_base_url = environ['ELODIE_MAPQUEST_BASE_URL']

#: MapQuest key from environment
mapquest_key = None
if (
        'ELODIE_MAPQUEST_KEY' in environ and
        environ['ELODIE_MAPQUEST_KEY'] != ''
   ):
    mapquest_key = environ['ELODIE_MAPQUEST_KEY']

#: Accepted language in responses from MapQuest
accepted_language = 'en'

# check python version, required in filesystem.py to trigger appropriate method
python_version = version_info.major

CONFIG_FILE = '%s/config.ini' % application_directory
