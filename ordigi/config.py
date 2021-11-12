from configparser import RawConfigParser
from os import path
from ordigi import constants
from geopy.geocoders import options as gopt


class Config:
    """Manage config file"""

    def __init__(self, conf_path=constants.CONFIG_FILE, conf={}):
        self.conf_path = conf_path
        if conf == {}:
            self.conf = self.load_config()
            if self.conf == {}:
                # Fallback to default config
                self.conf_path = constants.CONFIG_FILE
                self.conf = self.load_config()
        else:
            self.conf = conf

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

    def get_option(self, option, section):

        if section in self.conf and option in self.conf[section]:
            return self.conf[section][option]

        return False

    def get_path_definition(self):
        """Returns a list of folder definitions.

        Each element in the list represents a folder.
        Fallback folders are supported and are nested lists.

        :returns: string
        """

        if 'Path' in self.conf:
            if 'format' in self.conf['Path']:
                return self.conf['Path']['format']
            elif 'dirs_path' and 'name' in self.conf['Path']:
                return self.conf['Path']['dirs_path'] + '/' + self.conf['Path']['name']

        return constants.DEFAULT_PATH_FORMAT

    def get_options(self):
        """Get config options
        :returns: dict
        """

        options = {}
        geocoder = self.get_option('geocoder', 'Geolocation')
        if geocoder and geocoder in ('Nominatim',):
            options['geocoder'] = geocoder
        else:
            options['geocoder'] = constants.DEFAULT_GEOCODER

        prefer_english_names = self.get_option('prefer_english_names', 'Geolocation')
        if prefer_english_names:
            options['prefer_english_names'] = bool(prefer_english_names)
        else:
            options['prefer_english_names'] = False

        timeout = self.get_option('timeout', 'Geolocation')
        if timeout:
            options['timeout'] = timeout
        else:
            options['timeout'] = gopt.default_timeout

        options['path_format'] = self.get_path_definition()

        options['day_begins'] = 0
        options['max_deep'] = None
        if 'Path' in self.conf:
            if 'day_begins' in self.conf['Path']:
                options['day_begins'] = int(self.conf['Path']['day_begins'])
            if 'max_deep' in self.conf['Path']:
                options['max_deep'] = int(self.conf['Path']['max_deep'])

        options['exclude'] = []
        if 'Exclusions' in self.conf:
            options['exclude'] = [value for key, value in self.conf.items('Exclusions')]

        return options
