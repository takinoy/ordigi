from pathlib import Path
import pytest
import shutil
import tempfile
from unittest import mock

from ordigi import config

# Helpers
import random
import string

def random_char(y):
    return ''.join(random.choice(string.printable) for x in range(y))

def write_random_file(file_path):
    with open(file_path, 'w') as conf_file:
        conf_file.write(random_char(20))

class TestConfig:

    @pytest.fixture(scope="module")
    def conf(self, conf_path):
        return config.load_config(conf_path)

    def test_write(self, conf_path):
        assert conf_path.is_file()

    def test_load_config(self, conf):
        """
        Read files from config and return variables
        """
        # test valid config file
        assert conf['Path']['dirs_path'] == '%u{%Y-%m}/{city}|{city}-{%Y}/{folders[:1]}/{folder}'
        assert conf['Path']['name'] == '{%Y-%m-%b-%H-%M-%S}-{basename}.%l{ext}'
        assert conf['Path']['day_begins'] == '4'
        assert conf['Geolocation']['geocoder'] == 'Nominatium'

    def test_load_config_no_exist(self):
        # test file not exist
        conf = config.load_config('filename')
        assert conf == {}

    def test_load_config_invalid(self, conf_path):
        # test invalid config
        write_random_file(conf_path)
        with pytest.raises(Exception) as e:
            config.load_config(conf_path)
        assert e.typename == 'MissingSectionHeaderError'

    def test_get_path_definition(self, conf):
        """
        Get path definition from config
        """
        path = config.get_path_definition(conf)
        assert path == '%u{%Y-%m}/{city}|{city}-{%Y}/{folders[:1]}/{folder}/{%Y-%m-%b-%H-%M-%S}-{basename}.%l{ext}'

