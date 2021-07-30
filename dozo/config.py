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

def load_plugin_config(file):
    config = load_config(file)

    # If plugins are defined in the config we return them as a list
    # Else we return an empty list
    if 'Plugins' in config and 'plugins' in config['Plugins']:
        return config['Plugins']['plugins'].split(',')

    return []

def load_config_for_plugin(name, file):
    # Plugins store data using Plugin%PluginName% format.
    key = 'Plugin{}'.format(name)
    config = load_config(file)

    if key in config:
        return config[key]

    return {}


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
            return path.join(config['Path']['dirs_path'],
                   config['Path']['name'])

    return path.join(constants.default_path, constants.default_name)


