"""Load config file as a singleton."""
from configparser import RawConfigParser
from os import path
from dozo import constants


def write(conf_file, config):
    with open(conf_file, 'w') as conf_file:
        config.write(conf_file)
        return True

    return False

def load_config(file):
    if not path.exists(file):
        return {}

    config = RawConfigParser()
    config.read(file)
    return config

def get_path_definition(config):
    """Returns a list of folder definitions.

    Each element in the list represents a folder.
    Fallback folders are supported and are nested lists.

    :returns: string
    """

    if 'Path' in config:
        if 'format' in config['Path']:
            return config['Path']['format']
        elif 'dirs_path' and 'name' in config['Path']:
            return config['Path']['dirs_path'] + '/' + config['Path']['name']

    return constants.default_path + '/' + constants.default_name

def get_geocoder():
    config = load_config(constants.CONFIG_FILE)
    if 'Geolocation' in config and 'geocoder' in config['Geolocation']:
        return config['Geolocation']['geocoder']

    return constants.default_geocoder

