import json
import re

from configparser import RawConfigParser
from ordigi import constants
from geopy.geocoders import options as gopt


def check_option(getoption):
    """Check option type int or boolean"""
    try:
        getoption
    except ValueError as e:
        # TODO
        return None
    else:
        return getoption


def check_json(getoption):
    """Check if json string is valid"""
    try:
        getoption
    except json.JSONDecodeError as e:
        # TODO
        return None
    else:
        return getoption


def check_re(getoption):
    """Check if regex string is valid"""
    try:
        getoption
    except re.error as e:
        # TODO
        return None
    else:
        return getoption


class Config:
    """Manage config file"""

    def __init__(self, conf_path=constants.CONFIG_FILE, conf=None):
        self.conf_path = conf_path
        if conf is None:
            self.conf = self.load_config()
            if self.conf == {}:
                # Fallback to default config
                self.conf_path = constants.CONFIG_FILE
                self.conf = self.load_config()
        else:
            self.conf = conf

        self.options = self.set_default_options()

    def set_default_options(self) -> dict:
        # Initialize with default options
        return {
            'Exif': {
                'album_from_folder': False,
                'cache': False,
                'ignore_tags': None,
                'use_date_filename': False,
                'use_file_dates': False,
            },
            'Filters': {
                'exclude': None,
                'extensions': None,
                'glob': '**/*',
                'max_deep': None,
            },
            'Geolocation': {
                'geocoder': constants.DEFAULT_GEOCODER,
                'prefer_english_names': False,
                'timeout': gopt.default_timeout,
            },
            'Path': {
                'day_begins': 0,
                'path_format': constants.DEFAULT_PATH_FORMAT,
            },
            'Terminal': {
                'dry_run': False,
                'interactive': False,
            },
        }

    def write(self, conf):
        with open(self.conf_path, 'w') as conf_file:
            conf.write(conf_file)
            return True

        return False

    def load_config(self):
        if not self.conf_path.exists():
            return {}

        conf = RawConfigParser()
        conf.read(self.conf_path)
        return conf

    def is_option(self, section, option):
        """Get ConfigParser options"""
        if section in self.conf and option in self.conf[section]:
            return True

        return False

    @check_option
    def _getboolean(self, section, option):
        return self.conf.getboolean(section, option)
    getboolean = check_option(_getboolean)

    @check_option
    def _getint(self, section, option):
        return self.conf.getint(section, option)
    getint = check_option(_getint)

    @check_json
    def _getjson(self, section, option):
        return json.loads(self.conf.get(section, option))
    getjson = check_json(_getjson)

    @check_re
    def _getre(self, section, option):
        return re.compile(self.conf.get(section, option))
    getre = check_re(_getre)

    def get_config_option(self, section, option):
        bool_options = {
            'cache',
            'dry_run',
            'prefer_english_names',
            'album_from_folder',
            'interactive',
            'use_date_filename',
            'use_file_dates',
        }

        int_options = {
            'day_begins',
            'max_deep',
            'timeout',
        }

        string_options = {
            'glob',
            'geocoder',
        }

        multi_options = {
            'exclude',
            'extensions',
            'ignore_tags',
        }

        value = self.options[section][option]
        if self.is_option(section, option):
            if option in bool_options:
                return self.getboolean(section, option)
            if option in int_options:
                return self.getint(section, option)
            if option == 'geocoder' and value in ('Nominatim',):
                return self.conf[section][option]
            if option == 'glob':
                return self.getre(section, option)
            if option == 'path_format':
                return self.conf[section][option]
            if option in multi_options:
                return set(self.getjson(section, option))

            return value

        if self.is_option('Path', 'name') and self.is_option('dirs_path', option):
            # Path format is split in two parts
            value = self.conf['Path']['dirs_path'] + '/' + self.conf['Path']['name']

        return value

    def get_config_options(self) -> dict:
        """Get config options"""

        for section in self.options:
            for option in self.options[section]:
                # Option is in section
                value = self.get_config_option(section, option)
                self.options[section][option] = value

        return self.options
