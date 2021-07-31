# Project imports
import mock
import os
import re
import shutil
import sys
import time
from datetime import datetime
from datetime import timedelta
from dateutil.tz import tzutc
from tempfile import gettempdir

from . import helper
from elodie import constants
from elodie.config import load_config
from elodie.filesystem import FileSystem
from elodie.media.media import Media
from elodie.media.photo import Photo
from elodie.media.video import Video
from nose.plugins.skip import SkipTest
from elodie.external.pyexiftool import ExifTool
from elodie.dependencies import get_exiftool
from elodie.localstorage import Db

os.environ['TZ'] = 'GMT'

PHOTO_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'files')

def setup_module():
    exiftool_addedargs = [
            u'-config',
            u'"{}"'.format(constants.exiftool_config)
        ]
    ExifTool(executable_=get_exiftool(), addedargs=exiftool_addedargs).start()

def teardown_module():
    ExifTool().terminate

def test_create_directory_success():
    filesystem = FileSystem()
    folder = os.path.join(helper.temp_dir(), helper.random_string(10))
    status = filesystem.create_directory(folder)

    # Needs to be a subdirectory
    assert helper.temp_dir() != folder

    assert status == True
    assert os.path.isdir(folder) == True
    assert os.path.exists(folder) == True

    # Clean up
    shutil.rmtree(folder)


def test_create_directory_recursive_success():
    filesystem = FileSystem()
    folder = os.path.join(helper.temp_dir(), helper.random_string(10), helper.random_string(10))
    status = filesystem.create_directory(folder)

    # Needs to be a subdirectory
    assert helper.temp_dir() != folder

    assert status == True
    assert os.path.isdir(folder) == True
    assert os.path.exists(folder) == True

    shutil.rmtree(folder)

@mock.patch('elodie.filesystem.os.makedirs')
def test_create_directory_invalid_permissions(mock_makedirs):
    if os.name == 'nt':
       raise SkipTest("It isn't implemented on Windows")

    # Mock the case where makedirs raises an OSError because the user does
    # not have permission to create the given directory.
    mock_makedirs.side_effect = OSError()

    filesystem = FileSystem()
    status = filesystem.create_directory('/apathwhichdoesnotexist/afolderwhichdoesnotexist')

    assert status == False

def test_delete_directory_if_empty():
    filesystem = FileSystem()
    folder = os.path.join(helper.temp_dir(), helper.random_string(10))
    os.makedirs(folder)

    assert os.path.isdir(folder) == True
    assert os.path.exists(folder) == True

    filesystem.delete_directory_if_empty(folder)

    assert os.path.isdir(folder) == False
    assert os.path.exists(folder) == False

def test_delete_directory_if_empty_when_not_empty():
    filesystem = FileSystem()
    folder = os.path.join(helper.temp_dir(), helper.random_string(10), helper.random_string(10))
    os.makedirs(folder)
    parent_folder = os.path.dirname(folder)

    assert os.path.isdir(folder) == True
    assert os.path.exists(folder) == True
    assert os.path.isdir(parent_folder) == True
    assert os.path.exists(parent_folder) == True

    filesystem.delete_directory_if_empty(parent_folder)

    assert os.path.isdir(folder) == True
    assert os.path.exists(folder) == True
    assert os.path.isdir(parent_folder) == True
    assert os.path.exists(parent_folder) == True

    shutil.rmtree(parent_folder)


def test_walklevel():
    filesystem = FileSystem()
    maxlevel=2
    for root, dirs, files, level in filesystem.walklevel(helper.get_file_path('dir'), maxlevel):
        for paths in root, dirs, files:
            for path in paths:
                assert isinstance(path, str), path
        assert level <= maxlevel, level


def test_get_all_files_success():
    filesystem = FileSystem()
    folder = helper.populate_folder(5)

    files = set()
    files.update(filesystem.get_all_files(folder))
    shutil.rmtree(folder)

    length = len(files)
    assert length == 5, files

def test_get_all_files_by_extension():
    filesystem = FileSystem()
    folder = helper.populate_folder(5)

    files = set()
    files.update(filesystem.get_all_files(folder))
    length = len(files)
    assert length == 5, length

    files = set()
    filesystem = FileSystem(filter_by_ext=('%media',))
    files.update(filesystem.get_all_files(folder))
    length = len(files)
    assert length == 3, length

    files = set()
    files.update(filesystem.get_all_files(folder, 'jpg'))
    length = len(files)
    assert length == 3, length

    files = set()
    files.update(filesystem.get_all_files(folder, 'txt'))
    length = len(files)
    assert length == 2, length

    files = set()
    files.update(filesystem.get_all_files(folder, 'gif'))
    length = len(files)
    assert length == 0, length

    shutil.rmtree(folder)


# @unittest.skip("Get all files including invalid files")
def test_get_all_files_with_only_invalid_file():
    filesystem = FileSystem()
    folder = helper.populate_folder(0, include_invalid=True)

    files = set()
    files.update(filesystem.get_all_files(folder))
    shutil.rmtree(folder)

    length = len(files)
    assert length == 1, length

# @unittest.skip("Get all files including invalid files")
def test_get_all_files_with_invalid_file():
    filesystem = FileSystem()
    folder = helper.populate_folder(5, include_invalid=True)

    files = set()
    files.update(filesystem.get_all_files(folder))
    shutil.rmtree(folder)

    length = len(files)
    assert length == 6, length

def test_get_all_files_for_loop():
    filesystem = FileSystem()
    folder = helper.populate_folder(5)

    files = set()
    files.update()
    counter = 0
    for file in filesystem.get_all_files(folder):
        counter += 1
    shutil.rmtree(folder)

    assert counter == 5, counter

def test_get_current_directory():
    filesystem = FileSystem()
    assert os.getcwd() == filesystem.get_current_directory()

def test_get_file_name_definition_default():
    filesystem = FileSystem()
    name_template, definition = filesystem.get_file_name_definition()

    assert name_template == '%date-%original_name-%title.%extension', name_template
    assert definition == [[('date', '%Y-%m-%d_%H-%M-%S')], [('original_name', '')], [('title', '')], [('extension', '')]], definition #noqa

@mock.patch('elodie.constants.CONFIG_FILE', '%s/config.ini-custom-filename' % gettempdir())
def test_get_file_name_definition_custom():
    with open('%s/config.ini-custom-filename' % gettempdir(), 'w') as f:
        f.write("""
[File]
date=%Y-%m-%b
name=%date-%original_name.%extension
        """)
    if hasattr(load_config, 'config'):
        del load_config.config

    filesystem = FileSystem()
    name_template, definition = filesystem.get_file_name_definition()

    if hasattr(load_config, 'config'):
        del load_config.config

    assert name_template == '%date-%original_name.%extension', name_template
    assert definition == [[('date', '%Y-%m-%b')], [('original_name', '')], [('extension', '')]], definition #noqa

def test_get_file_name_plain():
    filesystem = FileSystem()
    media = Photo(helper.get_file('plain.jpg'))
    file_name = filesystem.get_file_name(media.get_metadata())

    assert file_name == helper.path_tz_fix('2015-12-05_00-59-26-plain.jpg'), file_name

def test_get_file_name_with_title():
    filesystem = FileSystem()
    media = Photo(helper.get_file('with-title.jpg'))
    file_name = filesystem.get_file_name(media.get_metadata())

    assert file_name == helper.path_tz_fix('2015-12-05_00-59-26-with-title-some-title.jpg'), file_name

def test_get_file_name_with_original_name_exif():
    filesystem = FileSystem()
    media = Photo(helper.get_file('with-filename-in-exif.jpg'))
    file_name = filesystem.get_file_name(media.get_metadata())

    assert file_name == helper.path_tz_fix('2015-12-05_00-59-26-foobar.jpg'), file_name

def test_get_file_name_with_original_name_title_exif():
    filesystem = FileSystem()
    media = Photo(helper.get_file('with-filename-and-title-in-exif.jpg'))
    file_name = filesystem.get_file_name(media.get_metadata())

    assert file_name == helper.path_tz_fix('2015-12-05_00-59-26-foobar-foobar-title.jpg'), file_name

def test_get_file_name_with_uppercase_and_spaces():
    filesystem = FileSystem()
    media = Photo(helper.get_file('Plain With Spaces And Uppercase 123.jpg'))
    file_name = filesystem.get_file_name(media.get_metadata())

    assert file_name == helper.path_tz_fix('2015-12-05_00-59-26-plain-with-spaces-and-uppercase-123.jpg'), file_name

@mock.patch('elodie.constants.CONFIG_FILE', '%s/config.ini-filename-custom' % gettempdir())
def test_get_file_name_custom():
    with open('%s/config.ini-filename-custom' % gettempdir(), 'w') as f:
        f.write("""
[File]
date=%Y-%m-%b
name=%date-%original_name.%extension
        """)
    if hasattr(load_config, 'config'):
        del load_config.config

    filesystem = FileSystem()
    media = Photo(helper.get_file('plain.jpg'))
    file_name = filesystem.get_file_name(media.get_metadata())

    if hasattr(load_config, 'config'):
        del load_config.config

    assert file_name == helper.path_tz_fix('2015-12-dec-plain.jpg'), file_name

@mock.patch('elodie.constants.CONFIG_FILE', '%s/config.ini-filename-custom-with-title' % gettempdir())
def test_get_file_name_custom_with_title():
    with open('%s/config.ini-filename-custom-with-title' % gettempdir(), 'w') as f:
        f.write("""
[File]
date=%Y-%m-%d
name=%date-%original_name-%title.%extension
        """)
    if hasattr(load_config, 'config'):
        del load_config.config

    filesystem = FileSystem()
    media = Photo(helper.get_file('with-title.jpg'))
    file_name = filesystem.get_file_name(media.get_metadata())

    if hasattr(load_config, 'config'):
        del load_config.config

    assert file_name == helper.path_tz_fix('2015-12-05-with-title-some-title.jpg'), file_name

@mock.patch('elodie.constants.CONFIG_FILE', '%s/config.ini-filename-custom-with-empty-value' % gettempdir())
def test_get_file_name_custom_with_empty_value():
    with open('%s/config.ini-filename-custom-with-empty-value' % gettempdir(), 'w') as f:
        f.write("""
[File]
date=%Y-%m-%d
name=%date-%original_name-%title.%extension
        """)
    if hasattr(load_config, 'config'):
        del load_config.config

    filesystem = FileSystem()
    media = Photo(helper.get_file('plain.jpg'))
    file_name = filesystem.get_file_name(media.get_metadata())

    if hasattr(load_config, 'config'):
        del load_config.config

    assert file_name == helper.path_tz_fix('2015-12-05-plain.jpg'), file_name

@mock.patch('elodie.constants.CONFIG_FILE', '%s/config.ini-filename-custom-with-lowercase' % gettempdir())
def test_get_file_name_custom_with_lower_capitalization():
    with open('%s/config.ini-filename-custom-with-lowercase' % gettempdir(), 'w') as f:
        f.write("""
[File]
date=%Y-%m-%d
name=%date-%original_name-%title.%extension
capitalization=lower
        """)
    if hasattr(load_config, 'config'):
        del load_config.config

    filesystem = FileSystem()
    media = Photo(helper.get_file('plain.jpg'))
    file_name = filesystem.get_file_name(media.get_metadata())

    if hasattr(load_config, 'config'):
        del load_config.config

    assert file_name == helper.path_tz_fix('2015-12-05-plain.jpg'), file_name

@mock.patch('elodie.constants.CONFIG_FILE', '%s/config.ini-filename-custom-with-invalidcase' % gettempdir())
def test_get_file_name_custom_with_invalid_capitalization():
    with open('%s/config.ini-filename-custom-with-invalidcase' % gettempdir(), 'w') as f:
        f.write("""
[File]
date=%Y-%m-%d
name=%date-%original_name-%title.%extension
capitalization=garabage
        """)
    if hasattr(load_config, 'config'):
        del load_config.config

    filesystem = FileSystem()
    media = Photo(helper.get_file('plain.jpg'))
    file_name = filesystem.get_file_name(media.get_metadata())

    if hasattr(load_config, 'config'):
        del load_config.config

    assert file_name == helper.path_tz_fix('2015-12-05-plain.jpg'), file_name

@mock.patch('elodie.constants.CONFIG_FILE', '%s/config.ini-filename-custom-with-uppercase' % gettempdir())
def test_get_file_name_custom_with_upper_capitalization():
    with open('%s/config.ini-filename-custom-with-uppercase' % gettempdir(), 'w') as f:
        f.write("""
[File]
date=%Y-%m-%d
name=%date-%original_name-%title.%extension
capitalization=upper
        """)
    if hasattr(load_config, 'config'):
        del load_config.config

    filesystem = FileSystem()
    media = Photo(helper.get_file('plain.jpg'))
    file_name = filesystem.get_file_name(media.get_metadata())

    if hasattr(load_config, 'config'):
        del load_config.config

    assert file_name == helper.path_tz_fix('2015-12-05-PLAIN.JPG'), file_name

def test_get_folder_path_plain():
    filesystem = FileSystem()
    media = Photo(helper.get_file('plain.jpg'))
    db = Db(PHOTO_PATH)
    path = filesystem.get_folder_path(media.get_metadata(), db)

    assert path == os.path.join('2015-12-Dec','Unknown Location'), path

def test_get_folder_path_with_title():
    filesystem = FileSystem()
    media = Photo(helper.get_file('with-title.jpg'))
    db = Db(PHOTO_PATH)
    path = filesystem.get_folder_path(media.get_metadata(), db)

    assert path == os.path.join('2015-12-Dec','Unknown Location'), path

def test_get_folder_path_with_location():
    filesystem = FileSystem()
    media = Photo(helper.get_file('with-location.jpg'))
    db = Db(PHOTO_PATH)
    path = filesystem.get_folder_path(media.get_metadata(), db)

    assert path == os.path.join('2015-12-Dec','Sunnyvale'), path

@mock.patch('elodie.constants.CONFIG_FILE', '%s/config.ini-original-with-camera-make-and-model' % gettempdir())
def test_get_folder_path_with_camera_make_and_model():
    with open('%s/config.ini-original-with-camera-make-and-model' % gettempdir(), 'w') as f:
        f.write("""
[Directory]
full_path=%camera_make/%camera_model
        """)
    if hasattr(load_config, 'config'):
        del load_config.config
    filesystem = FileSystem()
    media = Photo(helper.get_file('plain.jpg'))
    db = Db(PHOTO_PATH)
    path = filesystem.get_folder_path(media.get_metadata(), db)
    if hasattr(load_config, 'config'):
        del load_config.config

    assert path == os.path.join('Canon', 'Canon EOS REBEL T2i'), path

@mock.patch('elodie.constants.CONFIG_FILE', '%s/config.ini-original-with-camera-make-and-model-fallback' % gettempdir())
def test_get_folder_path_with_camera_make_and_model_fallback():
    with open('%s/config.ini-original-with-camera-make-and-model-fallback' % gettempdir(), 'w') as f:
        f.write("""
[Directory]
full_path=%camera_make|"nomake"/%camera_model|"nomodel"
        """)
    if hasattr(load_config, 'config'):
        del load_config.config
    filesystem = FileSystem()
    media = Photo(helper.get_file('no-exif.jpg'))
    db = Db(PHOTO_PATH)
    path = filesystem.get_folder_path(media.get_metadata(), db)
    if hasattr(load_config, 'config'):
        del load_config.config

    assert path == os.path.join('nomake', 'nomodel'), path

@mock.patch('elodie.constants.CONFIG_FILE', '%s/config.ini-int-in-component-path' % gettempdir())
def test_get_folder_path_with_int_in_config_component():
    # gh-239
    with open('%s/config.ini-int-in-component-path' % gettempdir(), 'w') as f:
        f.write("""
[Directory]
date=%Y
full_path=%date
        """)
    if hasattr(load_config, 'config'):
        del load_config.config
    filesystem = FileSystem()
    media = Photo(helper.get_file('plain.jpg'))
    db = Db(PHOTO_PATH)
    path = filesystem.get_folder_path(media.get_metadata(), db)
    if hasattr(load_config, 'config'):
        del load_config.config

    assert path == os.path.join('2015'), path

@mock.patch('elodie.constants.CONFIG_FILE', '%s/config.ini-combined-date-and-album' % gettempdir())
def test_get_folder_path_with_combined_date_and_album():
    # gh-239
    with open('%s/config.ini-combined-date-and-album' % gettempdir(), 'w') as f:
        f.write("""
[Directory]
date=%Y-%m-%b
custom=%date %album
full_path=%custom
        """)
    if hasattr(load_config, 'config'):
        del load_config.config
    filesystem = FileSystem()
    media = Photo(helper.get_file('with-album.jpg'))
    db = Db(PHOTO_PATH)
    path = filesystem.get_folder_path(media.get_metadata(), db)
    if hasattr(load_config, 'config'):
        del load_config.config

    assert path == '2015-12-Dec Test Album', path

@mock.patch('elodie.constants.CONFIG_FILE', '%s/config.ini-combined-date-album-location-fallback' % gettempdir())
def test_get_folder_path_with_album_and_location_fallback():
    # gh-279
    with open('%s/config.ini-combined-date-album-location-fallback' % gettempdir(), 'w') as f:
        f.write("""
[Directory]
date=%Y-%m-%b
custom=%album
full_path=%custom|%city
        """)
    if hasattr(load_config, 'config'):
        del load_config.config
    filesystem = FileSystem()

    # Test with no location
    media = Photo(helper.get_file('plain.jpg'))
    db = Db(PHOTO_PATH)
    path_plain = filesystem.get_folder_path(media.get_metadata(), db)

    # Test with City
    media = Photo(helper.get_file('with-location.jpg'))
    path_city = filesystem.get_folder_path(media.get_metadata(), db)
    if hasattr(load_config, 'config'):
        del load_config.config

    assert path_plain == 'Unknown Location', path_plain
    assert path_city == 'Sunnyvale', path_city


def test_get_folder_path_with_int_in_source_path():
    # gh-239
    filesystem = FileSystem()
    temporary_folder, folder = helper.create_working_folder('int')

    origin = os.path.join(folder,'plain.jpg')
    shutil.copyfile(helper.get_file('plain.jpg'), origin)

    media = Photo(origin)
    db = Db(folder)
    path = filesystem.get_folder_path(media.get_metadata(), db)

    assert path == os.path.join('2015-12-Dec','Unknown Location'), path

@mock.patch('elodie.constants.CONFIG_FILE', '%s/config.ini-original-default-unknown-location' % gettempdir())
def test_get_folder_path_with_original_default_unknown_location():
    with open('%s/config.ini-original-default-with-unknown-location' % gettempdir(), 'w') as f:
        f.write('')
    if hasattr(load_config, 'config'):
        del load_config.config
    filesystem = FileSystem()
    media = Photo(helper.get_file('plain.jpg'))
    db = Db(PHOTO_PATH)
    path = filesystem.get_folder_path(media.get_metadata(), db)
    if hasattr(load_config, 'config'):
        del load_config.config

    assert path == os.path.join('2015-12-Dec','Unknown Location'), path

@mock.patch('elodie.constants.CONFIG_FILE', '%s/config.ini-custom-path' % gettempdir())
def test_get_folder_path_with_custom_path():
    with open('%s/config.ini-custom-path' % gettempdir(), 'w') as f:
        f.write("""
[Geolocation]
geocoder=Nominatim

[Directory]
date=%Y-%m-%d
location=%country-%state-%city
full_path=%date/%location
        """)
    if hasattr(load_config, 'config'):
        del load_config.config
    filesystem = FileSystem()
    media = Photo(helper.get_file('with-location.jpg'))
    db = Db(PHOTO_PATH)
    path = filesystem.get_folder_path(media.get_metadata(), db)
    if hasattr(load_config, 'config'):
        del load_config.config

    assert path == os.path.join('2015-12-05','United States-California-Sunnyvale'), path

@mock.patch('elodie.constants.CONFIG_FILE', '%s/config.ini-fallback' % gettempdir())
def test_get_folder_path_with_fallback_folder():
    with open('%s/config.ini-fallback' % gettempdir(), 'w') as f:
        f.write("""
[Directory]
year=%Y
month=%m
full_path=%year/%month/%album|%"No Album Fool"/%month
        """)
#full_path=%year/%album|"No Album"
    if hasattr(load_config, 'config'):
        del load_config.config
    filesystem = FileSystem()
    media = Photo(helper.get_file('plain.jpg'))
    db = Db(PHOTO_PATH)
    path = filesystem.get_folder_path(media.get_metadata(), db)
    if hasattr(load_config, 'config'):
        del load_config.config

    assert path == os.path.join('2015','12','No Album Fool','12'), path

@mock.patch('elodie.constants.CONFIG_FILE', '%s/config.ini-location-date' % gettempdir())
def test_get_folder_path_with_with_more_than_two_levels():
    with open('%s/config.ini-location-date' % gettempdir(), 'w') as f:
        f.write("""
[Geolocation]
mapquest_key=czjNKTtFjLydLteUBwdgKAIC8OAbGLUx

[Directory]
year=%Y
month=%m
location=%city, %state
full_path=%year/%month/%location
        """)

    if hasattr(load_config, 'config'):
        del load_config.config

    filesystem = FileSystem()
    media = Photo(helper.get_file('with-location.jpg'))
    db = Db(PHOTO_PATH)
    path = filesystem.get_folder_path(media.get_metadata(), db)
    if hasattr(load_config, 'config'):
        del load_config.config

    assert path == os.path.join('2015','12','Sunnyvale, California'), path

@mock.patch('elodie.constants.CONFIG_FILE', '%s/config.ini-location-date' % gettempdir())
def test_get_folder_path_with_with_only_one_level():
    with open('%s/config.ini-location-date' % gettempdir(), 'w') as f:
        f.write("""
[Directory]
year=%Y
full_path=%year
        """)

    if hasattr(load_config, 'config'):
        del load_config.config

    filesystem = FileSystem()
    media = Photo(helper.get_file('plain.jpg'))
    db = Db(PHOTO_PATH)
    path = filesystem.get_folder_path(media.get_metadata(), db)
    if hasattr(load_config, 'config'):
        del load_config.config

    assert path == os.path.join('2015'), path

def test_get_folder_path_with_location_and_title():
    filesystem = FileSystem()
    media = Photo(helper.get_file('with-location-and-title.jpg'))
    db = Db(PHOTO_PATH)
    path = filesystem.get_folder_path(media.get_metadata(), db)

    assert path == os.path.join('2015-12-Dec','Sunnyvale'), path

def test_parse_folder_name_default():
    if hasattr(load_config, 'config'):
        del load_config.config
    filesystem = FileSystem()
    place_name = {'default': u'California', 'country': u'United States of America', 'state': u'California', 'city': u'Sunnyvale'}
    mask = '%city'
    location_parts = re.findall('(%[^%]+)', mask)
    path = filesystem.parse_mask_for_location(mask, location_parts, place_name)
    if hasattr(load_config, 'config'):
        del load_config.config

    assert path == 'Sunnyvale', path

def test_parse_folder_name_multiple():
    if hasattr(load_config, 'config'):
        del load_config.config
    filesystem = FileSystem()
    place_name = {'default': u'California', 'country': u'United States of America', 'state': u'California', 'city': u'Sunnyvale'}
    mask = '%city-%state-%country'
    location_parts = re.findall('(%[^%]+)', mask)
    path = filesystem.parse_mask_for_location(mask, location_parts, place_name)
    if hasattr(load_config, 'config'):
        del load_config.config

    assert path == 'Sunnyvale-California-United States of America', path

def test_parse_folder_name_static_chars():
    if hasattr(load_config, 'config'):
        del load_config.config
    filesystem = FileSystem()
    place_name = {'default': u'California', 'country': u'United States of America', 'state': u'California', 'city': u'Sunnyvale'}
    mask = '%city-is-the-city'
    location_parts = re.findall('(%[^%]+)', mask)
    path = filesystem.parse_mask_for_location(mask, location_parts, place_name)
    if hasattr(load_config, 'config'):
        del load_config.config

    assert path == 'Sunnyvale-is-the-city', path

def test_parse_folder_name_key_not_found():
    if hasattr(load_config, 'config'):
        del load_config.config
    filesystem = FileSystem()
    place_name = {'default': u'California', 'country': u'United States of America', 'state': u'California'}
    mask = '%city'
    location_parts = re.findall('(%[^%]+)', mask)
    path = filesystem.parse_mask_for_location(mask, location_parts, place_name)
    if hasattr(load_config, 'config'):
        del load_config.config

    assert path == 'California', path

def test_parse_folder_name_key_not_found_with_static_chars():
    if hasattr(load_config, 'config'):
        del load_config.config
    filesystem = FileSystem()
    place_name = {'default': u'California', 'country': u'United States of America', 'state': u'California'}
    mask = '%city-is-not-found'
    location_parts = re.findall('(%[^%]+)', mask)
    path = filesystem.parse_mask_for_location(mask, location_parts, place_name)
    if hasattr(load_config, 'config'):
        del load_config.config

    assert path == 'California', path

def test_parse_folder_name_multiple_keys_not_found():
    if hasattr(load_config, 'config'):
        del load_config.config
    filesystem = FileSystem()
    place_name = {'default': u'United States of America', 'country': u'United States of America'}
    mask = '%city-%state'
    location_parts = re.findall('(%[^%]+)', mask)
    path = filesystem.parse_mask_for_location(mask, location_parts, place_name)
    if hasattr(load_config, 'config'):
        del load_config.config

    assert path == 'United States of America', path

def test_checkcomp():
    filesystem = FileSystem()
    temporary_folder, folder = helper.create_working_folder()
    orig = helper.get_file('photo.png')
    src_path1 = os.path.join(folder,'photo.png')
    src_path2 = os.path.join(folder,'plain.jpg')
    shutil.copyfile(helper.get_file('photo.png'), src_path1)
    shutil.copyfile(helper.get_file('plain.jpg'), src_path2)
    dest_path = os.path.join(folder,'photo_copy.jpg')
    shutil.copyfile(src_path1, dest_path)
    checksum1 = filesystem.checksum(src_path1)
    checksum2 = filesystem.checksum(src_path2)
    valid_checksum = filesystem.checkcomp(dest_path, checksum1)
    invalid_checksum = filesystem.checkcomp(dest_path, checksum2)
    assert valid_checksum
    assert not invalid_checksum


def test_check_for_early_morning_photos():
    date_origin = datetime(1985, 1, 1, 3, 5)
    filesystem = FileSystem(day_begins=4)
    date = filesystem.check_for_early_morning_photos(date_origin)
    assert date.date() == datetime(1984, 12, 31).date()


def test_sort_file():
    filesystem = FileSystem()
    temporary_folder, folder = helper.create_working_folder()
    src_path = os.path.join(folder,'photo.png')
    shutil.copyfile(helper.get_file('photo.png'), src_path)
    dest_path1 = os.path.join(folder,'photo_copy.jpg')
    checksum1 = filesystem.checksum(src_path)
    result_copy = filesystem.sort_file(src_path, dest_path1)
    assert result_copy
    assert filesystem.checkcomp(dest_path1, checksum1)

    dest_path2 = os.path.join(folder,'photo_move.jpg')
    checksum2 = filesystem.checksum(src_path)
    result_move = filesystem.sort_file(src_path, dest_path2)
    assert result_move
    assert filesystem.checkcomp(dest_path2, checksum2)


def test_sort_files():
    temporary_folder, folder = helper.create_working_folder()
    temporary_folder_destination, folder_destination = helper.create_working_folder()

    db = Db(folder)
    path_format = os.path.join(constants.default_path, constants.default_name)
    filesystem = FileSystem(path_format=path_format)

    filenames = ['photo.png', 'plain.jpg', 'text.txt', 'withoutextension']
    for src_file in filenames:
        origin = os.path.join(folder, src_file)
        shutil.copyfile(helper.get_file(src_file), origin)

    summary, has_errors = filesystem.sort_files([folder], folder_destination, db)

    shutil.rmtree(folder)
    shutil.rmtree(folder_destination)

    assert summary, summary
    assert not has_errors, has_errors


def test_process_file_invalid():
    filesystem = FileSystem()
    temporary_folder, folder = helper.create_working_folder()

    origin = os.path.join(folder,'photo.jpg')
    shutil.copyfile(helper.get_file('invalid.jpg'), origin)

    media = Photo(origin)
    db = Db(folder)
    destination = filesystem.process_file(origin, folder, db, media,
            False, 'copy', allowDuplicate=True)

    assert destination is None

def test_process_file_plain():
    filesystem = FileSystem()
    temporary_folder, folder = helper.create_working_folder()

    origin = os.path.join(folder,'photo.jpg')
    shutil.copyfile(helper.get_file('plain.jpg'), origin)

    db = Db(folder)
    origin_checksum_preprocess = db.checksum(origin)
    media = Photo(origin)
    destination = filesystem.process_file(origin, folder, db, media,
            False, 'copy', allowDuplicate=True)

    origin_checksum = db.checksum(origin)
    destination_checksum = db.checksum(destination)

    shutil.rmtree(folder)

    assert origin_checksum_preprocess is not None
    assert origin_checksum is not None
    assert destination_checksum is not None
    assert origin_checksum_preprocess == origin_checksum
    assert helper.path_tz_fix(os.path.join('2015-12-Dec','Unknown Location','2015-12-05_00-59-26-photo.jpg')) in destination, destination

def test_process_file_with_title():
    filesystem = FileSystem()
    temporary_folder, folder = helper.create_working_folder()

    origin = '%s/photo.jpg' % folder
    shutil.copyfile(helper.get_file('with-title.jpg'), origin)

    db = Db(folder)
    origin_checksum_preprocess = db.checksum(origin)
    media = Photo(origin)
    destination = filesystem.process_file(origin, folder, db, media,
            False, 'copy', allowDuplicate=True)

    origin_checksum = db.checksum(origin)
    destination_checksum = db.checksum(destination)

    shutil.rmtree(folder)

    assert origin_checksum_preprocess is not None
    assert origin_checksum is not None
    assert destination_checksum is not None
    assert origin_checksum_preprocess == origin_checksum
    assert helper.path_tz_fix(os.path.join('2015-12-Dec','Unknown Location','2015-12-05_00-59-26-photo-some-title.jpg')) in destination, destination

def test_process_file_with_location():
    filesystem = FileSystem()
    temporary_folder, folder = helper.create_working_folder()

    origin = os.path.join(folder,'photo.jpg')
    shutil.copyfile(helper.get_file('with-location.jpg'), origin)

    db = Db(folder)
    origin_checksum_preprocess = db.checksum(origin)
    media = Photo(origin)
    destination = filesystem.process_file(origin, folder, db, media,
            False, 'copy', allowDuplicate=True)

    origin_checksum = db.checksum(origin)
    destination_checksum = db.checksum(destination)

    shutil.rmtree(folder)

    assert origin_checksum_preprocess is not None
    assert origin_checksum is not None
    assert destination_checksum is not None
    assert origin_checksum_preprocess == origin_checksum
    assert helper.path_tz_fix(os.path.join('2015-12-Dec','Sunnyvale','2015-12-05_00-59-26-photo.jpg')) in destination, destination

def test_process_file_validate_original_checksum():
    filesystem = FileSystem()
    temporary_folder, folder = helper.create_working_folder()

    origin = os.path.join(folder,'photo.jpg')
    shutil.copyfile(helper.get_file('plain.jpg'), origin)

    db = Db(folder)
    origin_checksum_preprocess = db.checksum(origin)
    media = Photo(origin)
    destination = filesystem.process_file(origin, folder, db, media,
            False, 'copy', allowDuplicate=True)

    origin_checksum = db.checksum(origin)
    destination_checksum = db.checksum(destination)

    shutil.rmtree(folder)

    assert origin_checksum_preprocess is not None, origin_checksum_preprocess
    assert origin_checksum is not None, origin_checksum
    assert destination_checksum is not None, destination_checksum
    assert origin_checksum_preprocess == origin_checksum, (origin_checksum_preprocess, origin_checksum)


# See https://github.com/jmathai/elodie/issues/330
def test_process_file_no_exif_date_is_correct_gh_330():
    filesystem = FileSystem()
    temporary_folder, folder = helper.create_working_folder()

    origin = os.path.join(folder,'photo.jpg')
    shutil.copyfile(helper.get_file('no-exif.jpg'), origin)

    atime = 1330712100
    utime = 1330712900
    os.utime(origin, (atime, utime))

    media = Photo(origin)
    metadata = media.get_metadata()

    db = Db(folder)
    destination = filesystem.process_file(origin, folder, db, media,
            False, 'copy', allowDuplicate=True)

    shutil.rmtree(folder)

    assert '/2012-03-Mar/' in destination, destination
    assert '/2012-03-02_18-28-20' in destination, destination

def test_process_file_with_location_and_title():
    filesystem = FileSystem()
    temporary_folder, folder = helper.create_working_folder()

    origin = os.path.join(folder,'photo.jpg')
    shutil.copyfile(helper.get_file('with-location-and-title.jpg'), origin)

    db = Db(folder)
    origin_checksum_preprocess = db.checksum(origin)
    media = Photo(origin)
    destination = filesystem.process_file(origin, folder, db, media,
            False, 'copy', allowDuplicate=True)

    origin_checksum = db.checksum(origin)
    destination_checksum = db.checksum(destination)

    shutil.rmtree(folder)

    assert origin_checksum_preprocess is not None
    assert origin_checksum is not None
    assert destination_checksum is not None
    assert origin_checksum_preprocess == origin_checksum
    assert helper.path_tz_fix(os.path.join('2015-12-Dec','Sunnyvale','2015-12-05_00-59-26-photo-some-title.jpg')) in destination, destination

def test_process_file_with_album():
    filesystem = FileSystem()
    temporary_folder, folder = helper.create_working_folder()

    origin = os.path.join(folder,'photo.jpg')
    shutil.copyfile(helper.get_file('with-album.jpg'), origin)

    db = Db(folder)
    origin_checksum_preprocess = db.checksum(origin)
    media = Photo(origin)
    destination = filesystem.process_file(origin, folder, db, media,
            False, 'copy', allowDuplicate=True)

    origin_checksum = db.checksum(origin)
    destination_checksum = db.checksum(destination)

    shutil.rmtree(folder)

    assert origin_checksum_preprocess is not None
    assert origin_checksum is not None
    assert destination_checksum is not None
    assert origin_checksum_preprocess == origin_checksum
    assert helper.path_tz_fix(os.path.join('2015-12-Dec','Test Album','2015-12-05_00-59-26-photo.jpg')) in destination, destination

def test_process_file_with_album_and_title():
    filesystem = FileSystem()
    temporary_folder, folder = helper.create_working_folder()

    origin = os.path.join(folder,'photo.jpg')
    shutil.copyfile(helper.get_file('with-album-and-title.jpg'), origin)

    db = Db(folder)
    origin_checksum_preprocess = db.checksum(origin)
    media = Photo(origin)
    destination = filesystem.process_file(origin, folder, db, media,
            False, 'copy', allowDuplicate=True)

    origin_checksum = db.checksum(origin)
    destination_checksum = db.checksum(destination)

    shutil.rmtree(folder)

    assert origin_checksum_preprocess is not None
    assert origin_checksum is not None
    assert destination_checksum is not None
    assert origin_checksum_preprocess == origin_checksum
    assert helper.path_tz_fix(os.path.join('2015-12-Dec','Test Album','2015-12-05_00-59-26-photo-some-title.jpg')) in destination, destination

def test_process_file_with_album_and_title_and_location():
    filesystem = FileSystem()
    temporary_folder, folder = helper.create_working_folder()

    origin = os.path.join(folder,'photo.jpg')
    shutil.copyfile(helper.get_file('with-album-and-title-and-location.jpg'), origin)

    db = Db(folder)
    origin_checksum_preprocess = db.checksum(origin)
    media = Photo(origin)
    destination = filesystem.process_file(origin, folder, db, media,
            False, 'copy', allowDuplicate=True)

    origin_checksum = db.checksum(origin)
    destination_checksum = db.checksum(destination)

    shutil.rmtree(folder)

    assert origin_checksum_preprocess is not None
    assert origin_checksum is not None
    assert destination_checksum is not None
    assert origin_checksum_preprocess == origin_checksum
    assert helper.path_tz_fix(os.path.join('2015-12-Dec','Test Album','2015-12-05_00-59-26-photo-some-title.jpg')) in destination, destination

# gh-89 (setting album then title reverts album)
def test_process_video_with_album_then_title():
    filesystem = FileSystem()
    temporary_folder, folder = helper.create_working_folder()

    origin = os.path.join(folder,'movie.mov')
    shutil.copyfile(helper.get_file('video.mov'), origin)

    db = Db(folder)
    origin_checksum = db.checksum(origin)

    origin_checksum_preprocess = db.checksum(origin)
    media = Video(origin)
    media.set_album('test_album', origin)
    media.set_title('test_title', origin)
    destination = filesystem.process_file(origin, folder, db, media,
            False, 'copy', allowDuplicate=True)

    destination_checksum = db.checksum(destination)

    shutil.rmtree(folder)

    assert origin_checksum_preprocess is not None
    assert origin_checksum is not None
    assert destination_checksum is not None
    assert origin_checksum_preprocess == origin_checksum
    assert helper.path_tz_fix(os.path.join('2015-01-Jan','test_album','2015-01-19_12-45-11-movie-test_title.mov')) in destination, destination

@mock.patch('elodie.constants.CONFIG_FILE', '%s/config.ini-fallback-folder' % gettempdir())
def test_process_file_fallback_folder():
    with open('%s/config.ini-fallback-folder' % gettempdir(), 'w') as f:
        f.write("""
[Directory]
date=%Y-%m
full_path=%date/%album|"fallback"
        """)

    if hasattr(load_config, 'config'):
        del load_config.config
    filesystem = FileSystem()
    temporary_folder, folder = helper.create_working_folder()

    origin = os.path.join(folder,'plain.jpg')
    shutil.copyfile(helper.get_file('plain.jpg'), origin)

    media = Photo(origin)
    db = Db(folder)
    destination = filesystem.process_file(origin, folder, db, media,
            False, 'copy', allowDuplicate=True)

    if hasattr(load_config, 'config'):
        del load_config.config

    assert helper.path_tz_fix(os.path.join('2015-12', 'fallback', '2015-12-05_00-59-26-plain.jpg')) in destination, destination

    shutil.rmtree(folder)

@mock.patch('elodie.constants.CONFIG_FILE', '%s/config.ini-multiple-directories' % gettempdir())
def test_process_twice_more_than_two_levels_of_directories():
    with open('%s/config.ini-multiple-directories' % gettempdir(), 'w') as f:
        f.write("""
[Directory]
year=%Y
month=%m
day=%d
full_path=%year/%month/%day
        """)

    if hasattr(load_config, 'config'):
        del load_config.config

    filesystem = FileSystem()
    temporary_folder, folder = helper.create_working_folder()

    origin = os.path.join(folder,'plain.jpg')
    shutil.copyfile(helper.get_file('plain.jpg'), origin)

    media = Photo(origin)
    db = Db(folder)
    destination = filesystem.process_file(origin, folder, db, media,
            False, 'copy', allowDuplicate=True)

    if hasattr(load_config, 'config'):
        del load_config.config

    assert helper.path_tz_fix(os.path.join('2015','12','05', '2015-12-05_00-59-26-plain.jpg')) in destination, destination

    if hasattr(load_config, 'config'):
        del load_config.config

    media_second = Photo(destination)
    media_second.set_title('foo', destination)
    destination_second = filesystem.process_file(origin, folder, db,
            media_second, False, 'copy', allowDuplicate=True)

    if hasattr(load_config, 'config'):
        del load_config.config

    assert destination.replace('.jpg', '-foo.jpg') == destination_second, destination_second

    shutil.rmtree(folder)

def test_process_existing_file_without_changes():
    # gh-210
    filesystem = FileSystem()
    temporary_folder, folder = helper.create_working_folder()

    origin = os.path.join(folder,'with-original-name.jpg')
    shutil.copyfile(helper.get_file('with-original-name.jpg'), origin)

    media = Photo(origin)
    db = Db(folder)
    destination = filesystem.process_file(origin, folder, db, media,
            False, 'copy', allowDuplicate=False)

    assert helper.path_tz_fix(os.path.join('2015-12-Dec', 'Unknown Location',
        '2015-12-05_00-59-26-originalfilename.jpg')) in destination, destination

    media_second = Photo(destination)
    destination_second = filesystem.process_file(origin, folder, db,
            media_second, False, 'copy', allowDuplicate=False)

    assert destination_second is None, destination_second

    shutil.rmtree(folder)

@mock.patch('elodie.constants.CONFIG_FILE', '%s/config.ini-plugin-throw-error' % gettempdir())
def test_process_file_with_plugin_throw_error():
    with open('%s/config.ini-plugin-throw-error' % gettempdir(), 'w') as f:
        f.write("""
[Plugins]
plugins=ThrowError
        """)

    if hasattr(load_config, 'config'):
        del load_config.config

    filesystem = FileSystem()
    temporary_folder, folder = helper.create_working_folder()

    origin = os.path.join(folder,'plain.jpg')
    shutil.copyfile(helper.get_file('plain.jpg'), origin)

    media = Photo(origin)
    db = Db(folder)
    destination = filesystem.process_file(origin, folder, db,
            media, False, 'copy', allowDuplicate=True)

    if hasattr(load_config, 'config'):
        del load_config.config

    assert destination is None, destination

@mock.patch('elodie.constants.CONFIG_FILE', '%s/config.ini-plugin-runtime-error' % gettempdir())
def test_process_file_with_plugin_runtime_error():
    with open('%s/config.ini-plugin-runtime-error' % gettempdir(), 'w') as f:
        f.write("""
[Plugins]
plugins=RuntimeError
        """)
    if hasattr(load_config, 'config'):
        del load_config.config

    filesystem = FileSystem()
    temporary_folder, folder = helper.create_working_folder()

    origin = os.path.join(folder,'plain.jpg')
    shutil.copyfile(helper.get_file('plain.jpg'), origin)

    media = Photo(origin)
    db = Db(folder)
    destination = filesystem.process_file(origin, folder, db,
            media, False, 'copy', allowDuplicate=True)

    if hasattr(load_config, 'config'):
        del load_config.config

    assert '2015-12-Dec/Unknown Location/2015-12-05_00-59-26-plain.jpg' in destination, destination

def test_set_utime_with_exif_date():
    filesystem = FileSystem()
    temporary_folder, folder = helper.create_working_folder()

    origin = os.path.join(folder,'photo.jpg')
    shutil.copyfile(helper.get_file('plain.jpg'), origin)

    media_initial = Photo(origin)
    metadata_initial = media_initial.get_metadata()

    initial_stat = os.stat(origin)
    initial_time = int(min(initial_stat.st_mtime, initial_stat.st_ctime))
    initial_time = datetime.fromtimestamp(initial_time)
    db = Db(folder)
    initial_checksum = db.checksum(origin)

    assert initial_time != metadata_initial['date_original']

    filesystem.set_utime_from_metadata(metadata_initial['date_original'], media_initial.get_file_path())
    final_stat = os.stat(origin)
    final_time = datetime.fromtimestamp(final_stat.st_mtime)
    final_checksum = db.checksum(origin)

    media_final = Photo(origin)
    metadata_final = media_final.get_metadata()

    shutil.rmtree(folder)

    assert initial_stat.st_mtime != final_stat.st_mtime
    assert final_time == metadata_final['date_original']
    assert initial_checksum == final_checksum

def test_set_utime_without_exif_date():
    filesystem = FileSystem()
    temporary_folder, folder = helper.create_working_folder()

    origin = os.path.join(folder,'photo.jpg')
    shutil.copyfile(helper.get_file('no-exif.jpg'), origin)

    media_initial = Photo(origin)
    metadata_initial = media_initial.get_metadata()

    initial_stat = os.stat(origin)
    mtime = datetime.fromtimestamp(initial_stat.st_mtime).replace(microsecond=0)
    mtime = mtime.replace(tzinfo=tzutc())
    db = Db(folder)
    initial_checksum = db.checksum(origin)
    date_modified = metadata_initial['date_modified']

    assert mtime == date_modified

    filesystem.set_utime_from_metadata(mtime, media_initial.get_file_path())
    final_stat = os.stat(origin)
    final_time = datetime.fromtimestamp(final_stat.st_mtime).replace(microsecond=0)
    final_time = final_time.replace(tzinfo=tzutc())
    final_checksum = db.checksum(origin)

    media_final = Photo(origin)
    metadata_final = media_final.get_metadata()
    date_modified = metadata_final['date_modified']

    shutil.rmtree(folder)

    assert mtime == final_time
    assert final_time == date_modified, (final_time,
            metadata_final['date_modified'])
    assert initial_checksum == final_checksum

def test_should_exclude_with_no_exclude_arg():
    filesystem = FileSystem()
    result = filesystem.should_exclude('/some/path')
    assert result == False, result

def test_should_exclude_with_non_matching_regex():
    filesystem = FileSystem()
    result = filesystem.should_exclude('/some/path', {re.compile('foobar')})
    assert result == False, result

def test_should_exclude_with_matching_regex():
    filesystem = FileSystem()
    result = filesystem.should_exclude('/some/path', {re.compile('some')})
    assert result == True, result

def test_should_not_exclude_with_multiple_with_non_matching_regex():
    filesystem = FileSystem()
    result = filesystem.should_exclude('/some/path', {re.compile('foobar'), re.compile('dne')})
    assert result == False, result

def test_should_exclude_with_multiple_with_one_matching_regex():
    filesystem = FileSystem()
    result = filesystem.should_exclude('/some/path', {re.compile('foobar'), re.compile('some')})
    assert result == True, result

def test_should_exclude_with_complex_matching_regex():
    filesystem = FileSystem()
    result = filesystem.should_exclude('/var/folders/j9/h192v5v95gd_fhpv63qzyd1400d9ct/T/T497XPQH2R/UATR2GZZTX/2016-04-Apr/London/2016-04-07_11-15-26-valid-sample-title.txt', {re.compile('London.*\.txt$')})
    assert result == True, result

@mock.patch('elodie.constants.CONFIG_FILE', '%s/config.ini-does-not-exist' % gettempdir())
def test_get_folder_path_definition_default():
    if hasattr(load_config, 'config'):
        del load_config.config
    filesystem = FileSystem()
    path_definition = filesystem.get_folder_path_definition()
    if hasattr(load_config, 'config'):
        del load_config.config

    assert path_definition == [[('date', '%Y-%m-%b')], [('album', ''), ('location', '%city'), ('"Unknown Location"', '')]], path_definition

@mock.patch('elodie.constants.CONFIG_FILE', '%s/config.ini-date-location' % gettempdir())
def test_get_folder_path_definition_date_location():
    with open('%s/config.ini-date-location' % gettempdir(), 'w') as f:
        f.write("""
[Directory]
date=%Y-%m-%d
location=%country
full_path=%date/%location
        """)

    if hasattr(load_config, 'config'):
        del load_config.config
    filesystem = FileSystem()
    path_definition = filesystem.get_folder_path_definition()
    expected = [
        [('date', '%Y-%m-%d')], [('location', '%country')]
    ]
    if hasattr(load_config, 'config'):
        del load_config.config

    assert path_definition == expected, path_definition

@mock.patch('elodie.constants.CONFIG_FILE', '%s/config.ini-location-date' % gettempdir())
def test_get_folder_path_definition_location_date():
    with open('%s/config.ini-location-date' % gettempdir(), 'w') as f:
        f.write("""
[Directory]
date=%Y-%m-%d
location=%country
full_path=%location/%date
        """)

    if hasattr(load_config, 'config'):
        del load_config.config
    filesystem = FileSystem()
    path_definition = filesystem.get_folder_path_definition()
    expected = [
        [('location', '%country')], [('date', '%Y-%m-%d')]
    ]
    if hasattr(load_config, 'config'):
        del load_config.config

    assert path_definition == expected, path_definition

@mock.patch('elodie.constants.CONFIG_FILE', '%s/config.ini-cached' % gettempdir())
def test_get_folder_path_definition_cached():
    with open('%s/config.ini-cached' % gettempdir(), 'w') as f:
        f.write("""
[Directory]
date=%Y-%m-%d
location=%country
full_path=%date/%location
        """)

    if hasattr(load_config, 'config'):
        del load_config.config
    filesystem = FileSystem()
    path_definition = filesystem.get_folder_path_definition()
    expected = [
        [('date', '%Y-%m-%d')], [('location', '%country')]
    ]

    assert path_definition == expected, path_definition

    with open('%s/config.ini-cached' % gettempdir(), 'w') as f:
        f.write("""
[Directory]
date=%uncached
location=%uncached
full_path=%date/%location
        """)
    if hasattr(load_config, 'config'):
        del load_config.config
    filesystem = FileSystem()
    path_definition = filesystem.get_folder_path_definition()
    expected = [
        [('date', '%Y-%m-%d')], [('location', '%country')]
    ]
    if hasattr(load_config, 'config'):
        del load_config.config

@mock.patch('elodie.constants.CONFIG_FILE', '%s/config.ini-location-date' % gettempdir())
def test_get_folder_path_definition_with_more_than_two_levels():
    with open('%s/config.ini-location-date' % gettempdir(), 'w') as f:
        f.write("""
[Directory]
year=%Y
month=%m
day=%d
full_path=%year/%month/%day
        """)

    if hasattr(load_config, 'config'):
        del load_config.config
    filesystem = FileSystem()
    path_definition = filesystem.get_folder_path_definition()
    expected = [
        [('year', '%Y')], [('month', '%m')], [('day', '%d')]
    ]
    if hasattr(load_config, 'config'):
        del load_config.config

    assert path_definition == expected, path_definition

@mock.patch('elodie.constants.CONFIG_FILE', '%s/config.ini-location-date' % gettempdir())
def test_get_folder_path_definition_with_only_one_level():
    with open('%s/config.ini-location-date' % gettempdir(), 'w') as f:
        f.write("""
[Directory]
year=%Y
full_path=%year
        """)

    if hasattr(load_config, 'config'):
        del load_config.config
    filesystem = FileSystem()
    path_definition = filesystem.get_folder_path_definition()
    expected = [
        [('year', '%Y')]
    ]
    if hasattr(load_config, 'config'):
        del load_config.config

    assert path_definition == expected, path_definition

@mock.patch('elodie.constants.CONFIG_FILE', '%s/config.ini-multi-level-custom' % gettempdir())
def test_get_folder_path_definition_multi_level_custom():
    with open('%s/config.ini-multi-level-custom' % gettempdir(), 'w') as f:
        f.write("""
[Directory]
year=%Y
month=%M
full_path=%year/%album|%month|%"foo"/%month
        """)

    if hasattr(load_config, 'config'):
        del load_config.config
    filesystem = FileSystem()
    path_definition = filesystem.get_folder_path_definition()

    expected = [[('year', '%Y')], [('album', ''), ('month', '%M'), ('"foo"', '')], [('month', '%M')]]
    if hasattr(load_config, 'config'):
        del load_config.config

    assert path_definition == expected, path_definition

def test_get_date_taken_without_exif():
    filesystem = FileSystem()
    source = helper.get_file('no-exif.jpg')
    photo = Photo(source)
    date_taken = filesystem.get_date_taken(photo.get_metadata())

    date_modified = photo.get_metadata()['date_modified']

    assert date_taken == date_modified, date_taken
