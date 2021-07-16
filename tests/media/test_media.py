# Project imports
import os
import sys

import hashlib
import random
import re
import shutil
import string
import tempfile
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))

import helper
from elodie.media.media import Media, get_all_subclasses
from elodie.media.audio import Audio
from elodie.media.photo import Photo
from elodie.media.video import Video

os.environ['TZ'] = 'GMT'

setup_module = helper.setup_module
teardown_module = helper.teardown_module

def test_get_all_subclasses():
    subclasses = get_all_subclasses(Media)
    expected = {Media, Photo, Video, Audio}
    assert subclasses == expected, subclasses


# def test_get_media_class(_file):
#     pass

def test_get_class_by_file_without_extension():
    base_file = helper.get_file('withoutextension')

    cls = Media.get_class_by_file(base_file, [Audio, Photo, Video])

    assert cls is not None, cls

def test_get_original_name():
    temporary_folder, folder = helper.create_working_folder()

    origin = '%s/%s' % (folder, 'with-original-name.jpg')
    file = helper.get_file('with-original-name.jpg')

    shutil.copyfile(file, origin)

    media = Media.get_class_by_file(origin, [Photo])
    original_name = media.get_original_name()

    assert original_name == 'originalfilename.jpg', original_name

def test_get_original_name_invalid_file():
    temporary_folder, folder = helper.create_working_folder()

    origin = '%s/%s' % (folder, 'invalid.jpg')
    file = helper.get_file('invalid.jpg')

    shutil.copyfile(file, origin)

    media = Media.get_class_by_file(origin, [Photo])
    original_name = media.get_original_name()

    assert original_name is None, original_name

def test_set_album_from_folder_invalid_file():
    temporary_folder, folder = helper.create_working_folder()

    base_file = helper.get_file('invalid.jpg')
    origin = '%s/invalid.jpg' % folder

    shutil.copyfile(base_file, origin)

    media = Media(origin)
    status = media.set_album_from_folder(origin)

    assert status == False, status

def test_set_album_from_folder():
    temporary_folder, folder = helper.create_working_folder()

    origin = '%s/photo.jpg' % folder
    shutil.copyfile(helper.get_file('plain.jpg'), origin)

    media = Media(origin)
    metadata = media.get_metadata()

    assert metadata['album'] is None, metadata['album']

    new_album_name = os.path.split(folder)[1]
    status = media.set_album_from_folder(origin)

    assert status == True, status

    media_new = Media(origin)
    metadata_new = media_new.get_metadata(update_cache=True)

    shutil.rmtree(folder)

    assert metadata_new['album'] == new_album_name, metadata_new['album']

def test_set_metadata():
    temporary_folder, folder = helper.create_working_folder()

    origin = '%s/photo.jpg' % folder
    shutil.copyfile(helper.get_file('plain.jpg'), origin)

    media = Media(origin)

    metadata = media.get_metadata()

    assert metadata['title'] == None, metadata['title']

    new_title = 'Some Title'
    media.set_metadata(title = new_title)

    new_metadata = media.get_metadata()

    assert new_metadata['title'] == new_title, new_metadata['title']

def test_set_metadata_basename():
    temporary_folder, folder = helper.create_working_folder()

    origin = '%s/photo.jpg' % folder
    shutil.copyfile(helper.get_file('plain.jpg'), origin)

    media = Media(origin)

    metadata = media.get_metadata()

    assert metadata['base_name'] == 'photo', metadata['base_name']

    new_basename = 'Some Base Name'
    media.set_metadata_basename(new_basename)

    new_metadata = media.get_metadata()

    assert new_metadata['base_name'] == new_basename, new_metadata['base_name']


def test_get_file_path():
    media = Media(helper.get_file('plain.jpg'))
    path = media.get_file_path()

    assert 'plain.jpg' in path, path

def test_get_class_by_file_photo():
    media = Media.get_class_by_file(helper.get_file('plain.jpg'), [Photo, Video])

    assert media.__name__ == 'Photo'

def test_get_class_by_file_video():
    media = Media.get_class_by_file(helper.get_file('video.mov'), [Photo, Video])

    assert media.__name__ == 'Video'

def test_get_class_by_file_unsupported():
    media = Media.get_class_by_file(helper.get_file('text.txt'), [Photo, Video])

    assert media is not None, media

def test_get_class_by_file_ds_store():
    media = Media.get_class_by_file(helper.get_file('.DS_Store'),
                                    [Photo, Video, Audio])
    assert media is None, media

def test_get_class_by_file_invalid_type():
    media = Media.get_class_by_file(None,
                                    [Photo, Video, Audio])
    assert media is None

    media = Media.get_class_by_file(False,
                                    [Photo, Video, Audio])
    assert media is None

    media = Media.get_class_by_file(True,
                                    [Photo, Video, Audio])
    assert media is None

def test_set_original_name_when_exists():
    temporary_folder, folder = helper.create_working_folder()

    origin = '%s/%s' % (folder, 'with-original-name.jpg')
    file = helper.get_file('with-original-name.jpg')

    shutil.copyfile(file, origin)

    media = Media.get_class_by_file(origin, [Photo])
    result = media.set_original_name(origin)

    assert result is None, result

def test_set_original_name_when_does_not_exist():
    temporary_folder, folder = helper.create_working_folder()

    origin = '%s/%s' % (folder, 'plain.jpg')
    file = helper.get_file('plain.jpg')

    shutil.copyfile(file, origin)

    media = Media.get_class_by_file(origin, [Photo])
    metadata_before = media.get_metadata()
    result = media.set_original_name(origin)
    metadata_after = media.get_metadata(update_cache=True)

    assert metadata_before['original_name'] is None, metadata_before
    assert metadata_after['original_name'] == 'plain.jpg', metadata_after
    assert result is True, result

def test_set_original_name_with_arg():
    temporary_folder, folder = helper.create_working_folder()

    origin = '%s/%s' % (folder, 'plain.jpg')
    file = helper.get_file('plain.jpg')

    shutil.copyfile(file, origin)

    new_name = helper.random_string(15)

    media = Media.get_class_by_file(origin, [Photo])
    metadata_before = media.get_metadata()
    result = media.set_original_name(origin, name=new_name)
    metadata_after = media.get_metadata(update_cache=True)

    assert metadata_before['original_name'] is None, metadata_before
    assert metadata_after['original_name'] == new_name, metadata_after
    assert result is True, result

def test_set_original_name():
    files = ['plain.jpg', 'audio.m4a', 'photo.nef', 'video.mov']

    for file in files:
        ext = os.path.splitext(file)[1]

        temporary_folder, folder = helper.create_working_folder()

        random_file_name = '%s%s' % (helper.random_string(10), ext)
        origin = '%s/%s' % (folder, random_file_name)
        file_path = helper.get_file(file)
        if file_path is False:
            file_path = helper.download_file(file, folder)

        shutil.copyfile(file_path, origin)

        media = Media.get_class_by_file(origin, [Audio, Photo, Video])
        metadata = media.get_metadata()
        media.set_original_name(origin)
        metadata_updated = media.get_metadata(update_cache=True)

        shutil.rmtree(folder)

        assert metadata['original_name'] is None, metadata['original_name']
        assert metadata_updated['original_name'] == random_file_name, metadata_updated['original_name']

def is_valid():
    media = Media()

    assert not media.is_valid()
