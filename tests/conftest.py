""" pytest test configuration """

from configparser import RawConfigParser
import pytest
from pathlib import Path
import shutil
import tempfile

from dozo import config
from dozo.exiftool import _ExifToolProc

DOZO_PATH = Path(__file__).parent.parent

@pytest.fixture(autouse=True)
def reset_singletons():
    """ Need to clean up any ExifTool singletons between tests """
    _ExifToolProc.instance = None


def copy_sample_files():
    src_path = tempfile.mkdtemp(prefix='dozo-src')
    paths = Path(DOZO_PATH, 'samples/test_exif').glob('*')
    file_paths = [x for x in paths if x.is_file()]
    for file_path in file_paths:
        source_path = Path(src_path, file_path.name)
        shutil.copyfile(file_path, source_path)

    return src_path, file_paths


@pytest.fixture(scope="module")
def conf_path():
    tmp_path = tempfile.mkdtemp(prefix='dozo-')
    conf = RawConfigParser() 
    conf['Path'] = {
            'day_begins': '4',
            'dirs_path':'%u{%Y-%m}/{city}|{city}-{%Y}/{folders[:1]}/{folder}',
            'name':'{%Y-%m-%b-%H-%M-%S}-{basename}.%l{ext}'
            }
    conf['Geolocation'] = {
            'geocoder': 'Nominatium'
            }
    conf_path = Path(tmp_path, "dozo.conf")
    config.write(conf_path, conf)

    yield conf_path

    shutil.rmtree(tmp_path)

