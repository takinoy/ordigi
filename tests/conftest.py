""" pytest test configuration """

from configparser import RawConfigParser
import os
import pytest
from pathlib import Path, PurePath
import random
import shutil
import string
import tempfile

from ordigi.config import Config
from ordigi.exiftool import _ExifToolProc

ORDIGI_PATH = Path(__file__).parent.parent

@pytest.fixture(autouse=True)
def reset_singletons():
    """ Need to clean up any ExifTool singletons between tests """
    _ExifToolProc.instance = None


@pytest.fixture(scope="session")
def sample_files_paths(tmpdir_factory):
    tmp_path = Path(tmpdir_factory.mktemp("ordigi-src-"))
    path = Path(ORDIGI_PATH, 'samples/test_exif')
    shutil.copytree(path, tmp_path / path.name)
    paths = Path(tmp_path).glob('**/*')
    file_paths = [x for x in paths if x.is_file()]

    return tmp_path, file_paths


def randomize_files(dest_dir):
    # Get files randomly
    paths = Path(dest_dir).glob('*')
    for path, subdirs, files in os.walk(dest_dir):
        if '.ordigi' in path:
            continue

        for name in files:
            file_path = PurePath(path, name)
            if bool(random.getrandbits(1)):
                with open(file_path, 'wb') as fout:
                    fout.write(os.urandom(random.randrange(128, 2048)))
            if bool(random.getrandbits(1)):
                dest_path = PurePath(path, file_path.stem + '_1'+ file_path.suffix)
                shutil.copyfile(file_path, dest_path)


def randomize_db(dest_dir):
    # alterate database
    file_path = Path(str(dest_dir), '.ordigi', str(dest_dir.name) + '.db')
    with open(file_path, 'wb') as fout:
        fout.write(os.urandom(random.randrange(128, 2048)))


@pytest.fixture(scope="module")
def conf_path():
    conf_dir = tempfile.mkdtemp(prefix='ordigi-')
    conf = RawConfigParser() 
    conf['Path'] = {
            'day_begins': '4',
            'dirs_path':'%u{%Y-%m}/{city}|{city}-{%Y}/{folders[:1]}/{folder}',
            'name':'{%Y-%m-%b-%H-%M-%S}-{basename}.%l{ext}'
            }
    conf['Geolocation'] = {
            'geocoder': 'Nominatium'
            }
    conf_path = Path(conf_dir, "ordigi.conf")
    config = Config(conf_path)
    config.write(conf)

    yield conf_path

    shutil.rmtree(conf_dir)

