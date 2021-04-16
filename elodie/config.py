"""Load config file as a singleton."""
from configparser import RawConfigParser
from os import path


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
