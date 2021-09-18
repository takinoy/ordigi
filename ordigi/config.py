from configparser import RawConfigParser
from os import path
from ordigi import constants
from geopy.geocoders import options as gopt


class Config:
    """Manage config file"""

    def __init__(self, conf_path=None, conf={}):
        self.conf_path = conf_path
        if conf_path == None:
            self.conf = conf
        else:
            self.conf = self.load_config()

    def write(self, conf):
        with open(self.conf_path, 'w') as conf_path:
            conf.write(conf_path)
            return True

        return False

    def load_config(self):
        if not path.exists(self.conf_path):
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

        return constants.default_path + '/' + constants.default_name

    def get_options(self):
        """Get config options
        :returns: dict
        """

        options = {}
        geocoder = self.get_option('geocoder', 'Geolocation')
        if geocoder and geocoder in ('Nominatim', ):
            options['geocoder'] = geocoder
        else:
            options['geocoder'] = constants.default_geocoder

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

        if 'Path' in self.conf and 'day_begins' in self.conf['Path']:
            config_directory = self.conf['Path']
            options['day_begins'] = int(config_directory['day_begins'])
        else:
            options['day_begins'] = 0

        if 'Exclusions' in self.conf:
            options['exclude'] = [value for key, value in self.conf.items('Exclusions')]

        return options

