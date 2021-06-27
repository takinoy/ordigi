# -*- coding: utf-8
# Project imports
import os
import sys

import shutil
import tempfile
import time
from datetime import datetime
from dateutil.parser import parse

sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))

import helper
from elodie.media.media import Media
from elodie.media.video import Video

os.environ['TZ'] = 'GMT'

def test_video_extensions():
    video = Video()
    extensions = video.extensions

    assert 'avi' in extensions
    assert 'm4v' in extensions
    assert 'mov' in extensions
    assert 'm4v' in extensions
    assert '3gp' in extensions

    valid_extensions = Video.get_valid_extensions()

    assert extensions == valid_extensions, valid_extensions

def test_empty_album():
    video = Video(helper.get_file('video.mov'))
    assert video.get_album() is None

def test_get_camera_make():
    video = Video(helper.get_file('video.mov'))
    print(video.get_metadata())
    make = video.get_camera_make()

    assert make == 'Apple', make

def test_get_camera_model():
    video = Video(helper.get_file('video.mov'))
    model = video.get_camera_model()

    assert model == 'iPhone 5', model

def test_get_coordinate():
    video = Video(helper.get_file('video.mov'))
    coordinate = video.get_coordinate()

    assert coordinate == 38.1893, coordinate

def test_get_coordinate_latitude():
    video = Video(helper.get_file('video.mov'))
    coordinate = video.get_coordinate('latitude')

    assert coordinate == 38.1893, coordinate

def test_get_coordinate_longitude():
    video = Video(helper.get_file('video.mov'))
    coordinate = video.get_coordinate('longitude')

    assert coordinate == -119.9558, coordinate

def test_get_date_original():
    media = Media(helper.get_file('video.mov'))
    date_original = media.get_date_attribute(['QuickTime:ContentCreateDate'])
    date = parse('2015-01-19 12:45:11-08:00')

    assert date_original == date, date_original

def test_get_exiftool_attributes():
    video = Video(helper.get_file('video.mov'))
    exif = video.get_exiftool_attributes()

    assert exif is not None, exif
    assert exif is not False, exif

def test_is_valid():
    video = Video(helper.get_file('video.mov'))

    assert video.is_valid()

def test_is_not_valid():
    video = Video(helper.get_file('photo.png'))

    assert not video.is_valid()

def test_set_album():
    temporary_folder, folder = helper.create_working_folder()

    origin = '%s/video.mov' % folder
    shutil.copyfile(helper.get_file('video.mov'), origin)

    video = Video(origin)
    metadata = video.get_metadata()

    assert metadata['album'] is None, metadata['album']

    status = video.set_album('Test Album', origin)

    assert status == True, status

    video_new = Video(origin)
    metadata_new = video_new.get_metadata()

    shutil.rmtree(folder)

    assert metadata_new['album'] == 'Test Album', metadata_new['album']

def test_set_date_original():
    temporary_folder, folder = helper.create_working_folder()

    origin = '%s/video.mov' % folder
    shutil.copyfile(helper.get_file('video.mov'), origin)

    media = Media(origin)
    status = media.set_date_original(datetime(2013, 9, 30, 7, 6, 5), origin)

    assert status == True, status

    media_new = Media(origin)
    metadata = media_new.get_metadata()

    date_original = metadata['date_original']

    shutil.rmtree(folder)

    assert date_original == datetime(2013, 9, 30, 7, 6, 5), metadata['date_original']


    temporary_folder, folder = helper.create_working_folder()

    origin = '%s/video.mov' % folder
    shutil.copyfile(helper.get_file('video.mov'), origin)

    video = Video(origin)
    origin_metadata = video.get_metadata()

    # Verify that original video has different location info that what we
    #   will be setting and checking
    assert not helper.isclose(origin_metadata['latitude'], 11.1111111111), origin_metadata['latitude']
    assert not helper.isclose(origin_metadata['longitude'], 99.9999999999), origin_metadata['longitude']

    status = video.set_location(11.1111111111, 99.9999999999, origin)

    assert status == True, status

    video_new = Video(origin)
    metadata = video_new.get_metadata()

    shutil.rmtree(folder)

    assert helper.isclose(metadata['latitude'], 11.1111111111), metadata['latitude']
    assert helper.isclose(metadata['longitude'], 99.9999999999), metadata['longitude']

def test_set_title():
    temporary_folder, folder = helper.create_working_folder()

    origin = '%s/video.mov' % folder
    shutil.copyfile(helper.get_file('video.mov'), origin)

    video = Video(origin)
    origin_metadata = video.get_metadata()

    status = video.set_title('my video title', origin)

    assert status == True, status

    video_new = Video(origin)
    metadata = video_new.get_metadata()

    shutil.rmtree(folder)

    assert metadata['title'] == 'my video title', metadata['title']

def test_set_title_non_ascii():
    temporary_folder, folder = helper.create_working_folder()

    origin = '%s/video.mov' % folder
    shutil.copyfile(helper.get_file('video.mov'), origin)

    video = Video(origin)
    origin_metadata = video.get_metadata()

    unicode_title = u'形声字 / 形聲字' 
    status = video.set_title(unicode_title, origin)

    assert status == True, status

    video_new = Video(origin)
    metadata = video_new.get_metadata()

    shutil.rmtree(folder)

    assert metadata['title'] == unicode_title, metadata['title']
