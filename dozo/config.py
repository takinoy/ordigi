"""Load config file as a singleton."""
from configparser import RawConfigParser
from os import path
from dozo import constants


def load_config(file):
    if hasattr(load_config, "config"):
        return load_config.config

    if not path.exists(file):
        return {}

    load_config.config = RawConfigParser()
    load_config.config.read(file)
    return load_config.config


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

