""" pytest test configuration """

from configparser import RawConfigParser
import os
from pathlib import Path, PurePath
import random
import shutil
import tempfile

import pytest

from ordigi.exiftool import _ExifToolProc

ORDIGI_PATH = Path(__file__).parent.parent


@pytest.fixture(autouse=True)
def reset_singletons():
    """ Need to clean up any ExifTool singletons between tests """
    _ExifToolProc.instance = None


def copy_sample_path(tmpdir_factory, path_name):
    tmp_path = Path(tmpdir_factory.mktemp(path_name))
    path = Path(ORDIGI_PATH, 'samples/test_exif')
    shutil.copytree(path, tmp_path / path.name)

    return tmp_path


@pytest.fixture(scope="module")
def sample_files_paths(tmpdir_factory):
    tmp_path = copy_sample_path(tmpdir_factory, "ordigi-src-")
    paths = Path(tmp_path).glob('**/*')
    file_paths = [x for x in paths if x.is_file()]

    return tmp_path, file_paths


@pytest.fixture(scope="module")
def sample_collection_paths(tmpdir_factory):
    return copy_sample_path(tmpdir_factory, "ordigi-collection-")


def randomize_files(dest_dir):
    # Get files randomly
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
    file_path = Path(str(dest_dir), '.ordigi', 'collection.db')
    with open(file_path, 'wb') as fout:
        fout.write(os.urandom(random.randrange(128, 2048)))


@pytest.fixture(scope="module")
def conf_path():
    conf_dir = tempfile.mkdtemp(prefix='ordigi-')
    conf = RawConfigParser() 
    conf['Path'] = {
            'day_begins': '4',
            'dirs_path':'%u<%Y-%m>/<city>|<city>-<%Y>/<folders[:1]>/<folder>',
            'name':'<%Y-%m-%b-%H-%M-%S>-<basename>.%l<ext>'
            }
    conf['Geolocation'] = {
            'geocoder': 'Nominatium'
            }
    conf_path = Path(conf_dir, "ordigi.conf")
    with open(conf_path, 'w') as conf_file:
        conf.write(conf_file)

    yield conf_path

    shutil.rmtree(conf_dir)

