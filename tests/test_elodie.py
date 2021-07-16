# Project imports
from imp import load_source
import mock
import os
import sys
import shutil

from click.testing import CliRunner
from nose.plugins.skip import SkipTest
from nose.tools import assert_raises
from six import text_type, unichr as six_unichr
from tempfile import gettempdir
from datetime import datetime
import unittest

import helper
elodie = load_source('elodie', os.path.abspath('{}/../elodie.py'.format(os.path.dirname(os.path.realpath(__file__)))))

from elodie.config import load_config
from elodie.localstorage import Db
from elodie.media.audio import Audio
from elodie.media.photo import Photo
from elodie.media.video import Video
from elodie.plugins.plugins import Plugins
from elodie.plugins.googlephotos.googlephotos import GooglePhotos

os.environ['TZ'] = 'GMT'

def test_import_file_audio():
    temporary_folder, folder = helper.create_working_folder()
    temporary_folder_destination, folder_destination = helper.create_working_folder()

    origin = '%s/audio.m4a' % folder
    shutil.copyfile(helper.get_file('audio.m4a'), origin)

    db = Db(folder)
    dest_path = elodie.import_file(origin, folder_destination, db, False,
            'copy', False, False)

    shutil.rmtree(folder)
    shutil.rmtree(folder_destination)

    assert helper.path_tz_fix(os.path.join('2016-01-Jan','Houston','2016-01-03_21-23-39-audio.m4a')) in dest_path, dest_path

def test_import_file_photo():
    temporary_folder, folder = helper.create_working_folder()
    temporary_folder_destination, folder_destination = helper.create_working_folder()

    origin = '%s/plain.jpg' % folder
    shutil.copyfile(helper.get_file('plain.jpg'), origin)

    db = Db(folder)
    dest_path = elodie.import_file(origin, folder_destination, db, False,
            'copy', False, False)

    shutil.rmtree(folder)
    shutil.rmtree(folder_destination)

    assert helper.path_tz_fix(os.path.join('2015-12-Dec','Unknown Location','2015-12-05_00-59-26-plain.jpg')) in dest_path, dest_path

def test_import_file_video():
    temporary_folder, folder = helper.create_working_folder()
    temporary_folder_destination, folder_destination = helper.create_working_folder()

    origin = '%s/video.mov' % folder
    shutil.copyfile(helper.get_file('video.mov'), origin)

    db = Db(folder)
    dest_path = elodie.import_file(origin, folder_destination, db, False,
            'copy', False, False)

    shutil.rmtree(folder)
    shutil.rmtree(folder_destination)

    assert helper.path_tz_fix(os.path.join('2015-01-Jan','California','2015-01-19_12-45-11-video.mov')) in dest_path, dest_path

def test_import_file_path_unicode_checkmark():
    temporary_folder, folder = helper.create_working_folder()
    temporary_folder_destination, folder_destination = helper.create_working_folder()

    origin = text_type(folder)+u'/unicode\u2713filename.png'

    shutil.copyfile(helper.get_file('photo.png'), origin)

    db = Db(folder)
    dest_path = elodie.import_file(origin, folder_destination, db, False,
            'copy', False, False)

    shutil.rmtree(folder)
    shutil.rmtree(folder_destination)

    assert helper.path_tz_fix(os.path.join('2015-01-Jan','Unknown Location',
        u'2015-01-18_12-01-01-unicode\u2713filename.png')) in dest_path, dest_path

def test_import_file_path_unicode_latin_nbsp():
    temporary_folder, folder = helper.create_working_folder()
    temporary_folder_destination, folder_destination = helper.create_working_folder()

    origin = text_type(folder)+u'/unicode'+six_unichr(160)+u'filename.png'

    shutil.copyfile(helper.get_file('photo.png'), origin)

    db = Db(folder)
    dest_path = elodie.import_file(origin, folder_destination, db, False,
            'copy', False, False)

    shutil.rmtree(folder)
    shutil.rmtree(folder_destination)

    assert helper.path_tz_fix(os.path.join('2015-01-Jan','Unknown Location',
        u'2015-01-18_12-01-01-unicode\xa0filename.png')) in dest_path, dest_path

def test_import_file_allow_duplicate_false():
    temporary_folder, folder = helper.create_working_folder()
    temporary_folder_destination, folder_destination = helper.create_working_folder()

    origin = '%s/with-original-name.jpg' % folder
    shutil.copyfile(helper.get_file('with-original-name.jpg'), origin)

    db = Db(folder)
    dest_path1 = elodie.import_file(origin, folder_destination, db, False,
            'copy', False, False)
    dest_path2 = elodie.import_file(origin, folder_destination, db, False,
            'copy', False, False)

    shutil.rmtree(folder)
    shutil.rmtree(folder_destination)

    assert dest_path1 is not None
    assert dest_path2 is None

def test_import_file_allow_duplicate_true():
    temporary_folder, folder = helper.create_working_folder()
    temporary_folder_destination, folder_destination = helper.create_working_folder()

    origin = '%s/with-original-name.jpg' % folder
    shutil.copyfile(helper.get_file('with-original-name.jpg'), origin)

    db = Db(folder)
    dest_path1 = elodie.import_file(origin, folder_destination, db, False,
            'copy', False, True)
    dest_path2 = elodie.import_file(origin, folder_destination, db, False,
            'copy', False, True)

    shutil.rmtree(folder)
    shutil.rmtree(folder_destination)

    assert dest_path1 is not None
    assert dest_path2 is not None
    assert dest_path1 == dest_path2

def test_import_file_send_to_trash_false():
    temporary_folder, folder = helper.create_working_folder()
    temporary_folder_destination, folder_destination = helper.create_working_folder()

    origin = '%s/photo.png' % folder
    shutil.copyfile(helper.get_file('photo.png'), origin)

    db = Db(folder)
    dest_path = elodie.import_file(origin, folder_destination, db, False,
            'copy', False, False)

    assert os.path.isfile(origin), origin

    shutil.rmtree(folder)
    shutil.rmtree(folder_destination)

    assert dest_path is not None

def test_import_file_send_to_trash_true():
    raise SkipTest("Temporarily disable send2trash test gh-230")

    temporary_folder, folder = helper.create_working_folder()
    temporary_folder_destination, folder_destination = helper.create_working_folder()

    origin = '%s/photo.png' % folder
    shutil.copyfile(helper.get_file('photo.png'), origin)

    db = Db(folder)
    dest_path = elodie.import_file(origin, folder_destination, db, False,
            'copy', True, False)

    assert not os.path.isfile(origin), origin

    shutil.rmtree(folder)
    shutil.rmtree(folder_destination)

    assert dest_path is not None

def test_import_destination_in_source():
    temporary_folder, folder = helper.create_working_folder()
    folder_destination = '{}/destination'.format(folder)
    os.mkdir(folder_destination)

    origin = '%s/plain.jpg' % folder
    shutil.copyfile(helper.get_file('plain.jpg'), origin)

    db = Db(folder)
    dest_path = elodie.import_file(origin, folder_destination, db, False,
            'copy', False, False)

    shutil.rmtree(folder)

    assert dest_path is None, dest_path

def test_import_destination_in_source_gh_287():
    temporary_folder, folder = helper.create_working_folder()
    folder_destination = '{}-destination'.format(folder)
    os.mkdir(folder_destination)

    origin = '%s/video.mov' % folder
    shutil.copyfile(helper.get_file('video.mov'), origin)

    db = Db(folder)
    dest_path = elodie.import_file(origin, folder_destination, db, False,
            'copy', False, False)

    shutil.rmtree(folder)

    assert dest_path is not None, dest_path

@unittest.skip("Invalid file disabled")
def test_import_invalid_file_exit_code():
    temporary_folder, folder = helper.create_working_folder()
    temporary_folder_destination, folder_destination = helper.create_working_folder()

    # use a good and bad
    origin_invalid = '%s/invalid.jpg' % folder
    shutil.copyfile(helper.get_file('invalid.jpg'), origin_invalid)

    origin_valid = '%s/photo.png' % folder
    shutil.copyfile(helper.get_file('plain.jpg'), origin_valid)

    runner = CliRunner()
    result = runner.invoke(elodie._import, ['--destination', folder_destination, '--allow-duplicates', origin_invalid, origin_valid])

    shutil.rmtree(folder)
    shutil.rmtree(folder_destination)

    assert result.exit_code == 1, result.exit_code

def test_import_file_with_single_exclude():
    temporary_folder, folder = helper.create_working_folder()
    temporary_folder_destination, folder_destination = helper.create_working_folder()

    origin_valid = '%s/photo.png' % folder
    shutil.copyfile(helper.get_file('plain.jpg'), origin_valid)

    runner = CliRunner()
    result = runner.invoke(elodie._import, ['--destination', folder_destination, '--exclude-regex', origin_valid[0:5], '--allow-duplicates', origin_valid])

    assert 'Success         0' in result.output, result.output
    assert 'Error           0' in result.output, result.output

def test_import_file_with_multiple_exclude():
    temporary_folder, folder = helper.create_working_folder()
    temporary_folder_destination, folder_destination = helper.create_working_folder()

    origin_valid = '%s/photo.png' % folder
    shutil.copyfile(helper.get_file('plain.jpg'), origin_valid)

    runner = CliRunner()
    result = runner.invoke(elodie._import, ['--destination', folder_destination, '--exclude-regex', 'does not exist in path', '--exclude-regex', origin_valid[0:5], '--allow-duplicates', origin_valid])

    assert 'Success         0' in result.output, result.output
    assert 'Error           0' in result.output, result.output

def test_import_file_with_non_matching_exclude():
    temporary_folder, folder = helper.create_working_folder()
    temporary_folder_destination, folder_destination = helper.create_working_folder()

    origin_valid = '%s/photo.png' % folder
    shutil.copyfile(helper.get_file('plain.jpg'), origin_valid)

    runner = CliRunner()
    result = runner.invoke(elodie._import, ['--destination', folder_destination, '--exclude-regex', 'does not exist in path', '--allow-duplicates', origin_valid])

    assert 'Success         1' in result.output, result.output
    assert 'Error           0' in result.output, result.output

@unittest.skip('to fix')
def test_import_directory_with_matching_exclude():
    temporary_folder, folder = helper.create_working_folder()
    temporary_folder_destination, folder_destination = helper.create_working_folder()

    origin_valid = '%s/photo.png' % folder
    shutil.copyfile(helper.get_file('plain.jpg'), origin_valid)
    exclude_regex_list = (os.path.basename(os.path.dirname(folder)))
    exclude_regex_list = (os.path.dirname(folder))

    runner = CliRunner()
    result = runner.invoke(elodie._import, ['--destination',
        folder_destination, '--source', folder, '--exclude-regex',
        exclude_regex_list, '--allow-duplicates'])

    assert 'Success         0' in result.output, result.output
    assert 'Error           0' in result.output, result.output

def test_import_directory_with_non_matching_exclude():
    temporary_folder, folder = helper.create_working_folder()
    temporary_folder_destination, folder_destination = helper.create_working_folder()

    origin_valid = '%s/photo.png' % folder
    shutil.copyfile(helper.get_file('plain.jpg'), origin_valid)

    runner = CliRunner()
    result = runner.invoke(elodie._import, ['--destination', folder_destination, '--source', folder, '--exclude-regex', 'non-matching', '--allow-duplicates'])

    assert 'Success         1' in result.output, result.output
    assert 'Error           0' in result.output, result.output

@mock.patch('elodie.constants.CONFIG_FILE', '%s/config.ini-import-file-with-single-config-exclude' % gettempdir())
def test_import_file_with_single_config_exclude():
    config_string = """
    [Exclusions]
    name1=photo
            """
    with open('%s/config.ini-import-file-with-single-config-exclude' % gettempdir(), 'w') as f:
        f.write(config_string)

    if hasattr(load_config, 'config'):
        del load_config.config

    temporary_folder, folder = helper.create_working_folder()
    temporary_folder_destination, folder_destination = helper.create_working_folder()

    origin_valid = '%s/photo.png' % folder
    shutil.copyfile(helper.get_file('plain.jpg'), origin_valid)

    runner = CliRunner()
    result = runner.invoke(elodie._import, ['--destination', folder_destination, '--allow-duplicates', origin_valid, '--debug'])

    if hasattr(load_config, 'config'):
        del load_config.config

    assert 'Success         0' in result.output, result.output
    assert 'Error           0' in result.output, result.output

@mock.patch('elodie.constants.CONFIG_FILE', '%s/config.ini-import-file-with-multiple-config-exclude' % gettempdir())
def test_import_file_with_multiple_config_exclude():
    config_string = """
    [Exclusions]
    name1=notvalidatall
    name2=photo
            """
    with open('%s/config.ini-import-file-with-multiple-config-exclude' % gettempdir(), 'w') as f:
        f.write(config_string)

    if hasattr(load_config, 'config'):
        del load_config.config

    temporary_folder, folder = helper.create_working_folder()
    temporary_folder_destination, folder_destination = helper.create_working_folder()

    origin_valid = '%s/photo.png' % folder
    shutil.copyfile(helper.get_file('plain.jpg'), origin_valid)

    runner = CliRunner()
    result = runner.invoke(elodie._import, ['--destination', folder_destination, '--allow-duplicates', origin_valid, '--debug'])

    if hasattr(load_config, 'config'):
        del load_config.config

    assert 'Success         0' in result.output, result.output
    assert 'Error           0' in result.output, result.output


def test_get_all_files_in_paths():
    pass


def test_update_location_on_audio():
    temporary_folder, folder = helper.create_working_folder()
    temporary_folder_destination, folder_destination = helper.create_working_folder()

    origin = '%s/audio.m4a' % folder
    shutil.copyfile(helper.get_file('audio.m4a'), origin)

    audio = Audio(origin)
    metadata = audio.get_metadata()

    db = Db(folder)
    status = elodie.update_location(audio, origin, 'Sunnyvale, CA', db)

    audio_processed = Audio(origin)
    metadata_processed = audio_processed.get_metadata()

    shutil.rmtree(folder)
    shutil.rmtree(folder_destination)

    assert status == True, status
    assert metadata['latitude'] != metadata_processed['latitude'], metadata_processed['latitude']
    assert helper.isclose(metadata_processed['latitude'], 37.36883), metadata_processed['latitude']
    assert helper.isclose(metadata_processed['longitude'], -122.03635), metadata_processed['longitude']

def test_update_location_on_photo():
    temporary_folder, folder = helper.create_working_folder()
    temporary_folder_destination, folder_destination = helper.create_working_folder()

    origin = '%s/plain.jpg' % folder
    shutil.copyfile(helper.get_file('plain.jpg'), origin)

    photo = Photo(origin)
    metadata = photo.get_metadata()

    db = Db(folder)
    status = elodie.update_location(photo, origin, 'Sunnyvale, CA', db)

    photo_processed = Photo(origin)
    metadata_processed = photo_processed.get_metadata()

    shutil.rmtree(folder)
    shutil.rmtree(folder_destination)

    assert status == True, status
    assert metadata['latitude'] != metadata_processed['latitude']
    assert helper.isclose(metadata_processed['latitude'], 37.36883), metadata_processed['latitude']
    assert helper.isclose(metadata_processed['longitude'], -122.03635), metadata_processed['longitude']

def test_update_location_on_video():
    temporary_folder, folder = helper.create_working_folder()
    temporary_folder_destination, folder_destination = helper.create_working_folder()

    origin = '%s/video.mov' % folder
    shutil.copyfile(helper.get_file('video.mov'), origin)

    video = Video(origin)
    metadata = video.get_metadata()

    db = Db(folder)
    status = elodie.update_location(video, origin, 'Sunnyvale, CA', db)

    video_processed = Video(origin)
    metadata_processed = video_processed.get_metadata()

    shutil.rmtree(folder)
    shutil.rmtree(folder_destination)

    assert status == True, status
    assert metadata['latitude'] != metadata_processed['latitude']
    assert helper.isclose(metadata_processed['latitude'], 37.36883), metadata_processed['latitude']
    assert helper.isclose(metadata_processed['longitude'], -122.03635), metadata_processed['longitude']

def test_update_time_on_audio():
    temporary_folder, folder = helper.create_working_folder()
    temporary_folder_destination, folder_destination = helper.create_working_folder()

    origin = '%s/audio.m4a' % folder
    shutil.copyfile(helper.get_file('audio.m4a'), origin)

    audio = Audio(origin)
    metadata = audio.get_metadata()

    status = elodie.update_time(audio, origin, '2000-01-01 12:00:00')

    audio_processed = Audio(origin)
    metadata_processed = audio_processed.get_metadata()

    shutil.rmtree(folder)
    shutil.rmtree(folder_destination)

    assert status == True, status
    assert metadata['date_original'] != metadata_processed['date_original']
    assert metadata_processed['date_original'] == datetime(2000, 1, 1, 12, 0)

def test_update_time_on_photo():
    temporary_folder, folder = helper.create_working_folder()
    temporary_folder_destination, folder_destination = helper.create_working_folder()

    origin = '%s/plain.jpg' % folder
    shutil.copyfile(helper.get_file('plain.jpg'), origin)

    photo = Photo(origin)
    metadata = photo.get_metadata()

    status = elodie.update_time(photo, origin, '2000-01-01 12:00:00')

    photo_processed = Photo(origin)
    metadata_processed = photo_processed.get_metadata()

    shutil.rmtree(folder)
    shutil.rmtree(folder_destination)

    assert status == True, status
    assert metadata['date_original'] != metadata_processed['date_original']
    assert metadata_processed['date_original'] == datetime(2000, 1, 1, 12, 0)

def test_update_time_on_video():
    temporary_folder, folder = helper.create_working_folder()
    temporary_folder_destination, folder_destination = helper.create_working_folder()

    origin = '%s/video.mov' % folder
    shutil.copyfile(helper.get_file('video.mov'), origin)

    video = Video(origin)
    metadata = video.get_metadata()

    status = elodie.update_time(video, origin, '2000-01-01 12:00:00')

    video_processed = Video(origin)
    metadata_processed = video_processed.get_metadata()

    shutil.rmtree(folder)
    shutil.rmtree(folder_destination)

    assert status == True, status
    assert metadata['date_original'] != metadata_processed['date_original']
    assert metadata_processed['date_original'] == datetime(2000, 1, 1, 12, 0)

def test_update_with_directory_passed_in():
    temporary_folder, folder = helper.create_working_folder()
    temporary_folder_destination, folder_destination = helper.create_working_folder()

    origin = '%s/photo.png' % folder
    shutil.copyfile(helper.get_file('photo.png'), origin)

    runner = CliRunner()
    result = runner.invoke(elodie._import, ['--destination', folder_destination, folder])
    runner2 = CliRunner()
    result = runner2.invoke(elodie._update, ['--album', 'test', folder_destination])

    updated_file_path = "{}/2015-01-Jan/test/2015-01-18_12-01-01-photo.png".format(folder_destination)
    updated_file_exists = os.path.isfile(updated_file_path)

    shutil.rmtree(folder)
    shutil.rmtree(folder_destination)

    assert updated_file_exists, updated_file_path

@unittest.skip("Invalid file disabled")
def test_update_invalid_file_exit_code():
    temporary_folder, folder = helper.create_working_folder()
    temporary_folder_destination, folder_destination = helper.create_working_folder()

    # use a good and bad
    origin_invalid = '%s/invalid.jpg' % folder
    shutil.copyfile(helper.get_file('invalid.jpg'), origin_invalid)

    origin_valid = '%s/photo.png' % folder
    shutil.copyfile(helper.get_file('plain.jpg'), origin_valid)

    runner = CliRunner()
    result = runner.invoke(elodie._update, ['--album', 'test', origin_invalid, origin_valid])

    # bugfix deleted by elodie._update....
    # shutil.rmtree(folder)
    shutil.rmtree(folder_destination)

    assert result.exit_code == 1, result.exit_code

def test_regenerate_db_invalid_source():
    runner = CliRunner()
    result = runner.invoke(elodie._generate_db, ['--path', '/invalid/path'])
    assert result.exit_code == 1, result.exit_code

def test_regenerate_valid_source():
    temporary_folder, folder = helper.create_working_folder()

    origin = '%s/photo.png' % folder
    shutil.copyfile(helper.get_file('photo.png'), origin)

    runner = CliRunner()
    result = runner.invoke(elodie._generate_db, ['--path', folder])
    db = Db(folder)

    shutil.rmtree(folder)

    assert result.exit_code == 0, result.exit_code
    assert '66ca09b5533aba8b4ccdc7243435f2c4638c1a6762940ab9dbe66da185b3513e' in db.hash_db, db.hash_db

@unittest.skip("Invalid file disabled")
def test_regenerate_valid_source_with_invalid_files():
    temporary_folder, folder = helper.create_working_folder()

    origin_valid = '%s/photo.png' % folder
    shutil.copyfile(helper.get_file('photo.png'), origin_valid)
    origin_invalid = '%s/invalid.invalid' % folder
    shutil.copyfile(helper.get_file('invalid.invalid'), origin_invalid)

    runner = CliRunner()
    result = runner.invoke(elodie._generate_db, ['--path', folder])
    db = Db(folder)

    shutil.rmtree(folder)

    assert result.exit_code == 0, result.exit_code
    assert '3c19a5d751cf19e093b7447297731124d9cc987d3f91a9d1872c3b1c1b15639a' in db.hash_db, db.hash_db
    assert 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855' not in db.hash_db, db.hash_db

def test_verify_ok():
    temporary_folder, folder = helper.create_working_folder()

    origin = '%s/photo.png' % folder
    shutil.copyfile(helper.get_file('photo.png'), origin)

    runner = CliRunner()
    runner.invoke(elodie._generate_db, ['--path', folder])
    result = runner.invoke(elodie._verify, ['--path', folder])

    shutil.rmtree(folder)

    assert 'Success         1' in result.output, result.output
    assert 'Error           0' in result.output, result.output

def test_verify_error():
    temporary_folder, folder = helper.create_working_folder()

    origin = '%s/photo.png' % folder
    shutil.copyfile(helper.get_file('photo.png'), origin)

    runner = CliRunner()
    runner.invoke(elodie._generate_db, ['--path', folder])
    with open(origin, 'w') as f:
        f.write('changed text')
    result = runner.invoke(elodie._verify, ['--path', folder])

    shutil.rmtree(folder)

    assert origin in result.output, result.output
    assert 'Error           1' in result.output, result.output

@unittest.skip('depreciated')
@mock.patch('elodie.constants.CONFIG_FILE', '%s/config.ini-cli-batch-plugin-googlephotos' % gettempdir())
def test_cli_batch_plugin_googlephotos():
    auth_file = helper.get_file('plugins/googlephotos/auth_file.json')
    secrets_file = helper.get_file('plugins/googlephotos/secrets_file.json')
    config_string = """
    [Plugins]
    plugins=GooglePhotos

    [PluginGooglePhotos]
    auth_file={}
    secrets_file={}
            """
    config_string_fmt = config_string.format(
        auth_file,
        secrets_file
    )
    with open('%s/config.ini-cli-batch-plugin-googlephotos' % gettempdir(), 'w') as f:
        f.write(config_string_fmt)

    if hasattr(load_config, 'config'):
        del load_config.config

    final_file_path_1 = helper.get_file('plain.jpg')
    final_file_path_2 = helper.get_file('no-exif.jpg')
    sample_metadata_1 = Photo(final_file_path_1).get_metadata()
    sample_metadata_2 = Photo(final_file_path_2).get_metadata()
    gp = GooglePhotos()
    gp.after('', '', final_file_path_1, sample_metadata_1)
    gp.after('', '', final_file_path_2, sample_metadata_1)

    runner = CliRunner()
    result = runner.invoke(elodie._batch)

    if hasattr(load_config, 'config'):
        del load_config.config

    assert "elodie/elodie/tests/files/plain.jpg uploaded successfully.\"}\n" in result.output, result.output
    assert "elodie/elodie/tests/files/no-exif.jpg uploaded successfully.\"}\n" in result.output, result.output

@unittest.skip('to fix')
def test_cli_debug_import():
    runner = CliRunner()
    # import
    result = runner.invoke(elodie._import, ['--destination', '/does/not/exist', '/does/not/exist'])
    assert "Could not find /does/not/exist\n" not in result.output, result.output
    result = runner.invoke(elodie._import, ['--destination', '/does/not/exist', '--debug', '/does/not/exist'])
    assert "Could not find /does/not/exist\n" in result.output, result.output

@unittest.skip('to fix')
def test_cli_debug_update():
    runner = CliRunner()
    # update
    result = runner.invoke(elodie._update, ['--location', 'foobar', '/does/not/exist'])
    assert "Could not find /does/not/exist\n" not in result.output, result.output
    result = runner.invoke(elodie._update, ['--location', 'foobar', '--debug', '/does/not/exist'])
    assert "Could not find /does/not/exist\n" in result.output, result.output
