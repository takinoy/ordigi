# TODO to be removed later
from datetime import datetime
import os
import pytest
import sqlite3
from pathlib import Path
import re
from sys import platform
from time import sleep

from .conftest import randomize_files, randomize_db
from ordigi import constants
from ordigi.database import Sqlite
from ordigi.exiftool import ExifToolCaching, exiftool_is_running, terminate_exiftool
from ordigi.collection import Collection
from ordigi.geolocation import GeoLocation
from ordigi.media import Media
from ordigi.utils import get_date_from_string, get_date_regex


class TestCollection:

    @pytest.fixture(autouse=True)
    def setup_class(cls, sample_files_paths):
        cls.src_path, cls.file_paths = sample_files_paths
        cls.path_format = constants.default_path + '/' + constants.default_name

    def teardown_class(self):
        terminate_exiftool()
        assert not exiftool_is_running()

    def test_get_part(self, tmp_path):
        """
        Test all parts
        """
        # Item to search for:
        collection = Collection(tmp_path, self.path_format)
        items = collection.get_items()
        masks = [
                '{album}',
                '{basename}',
                '{camera_make}',
                '{camera_model}',
                '{city}',
                '{"custom"}',
                '{country}',
                '{ext}',
                '{folder}',
                '{folders[1:3]}',
                '{location}',
                '{name}',
                '{original_name}',
                '{state}',
                '{title}',
                '{%Y-%m-%d}',
                '{%Y-%m-%d_%H-%M-%S}',
                '{%Y-%m-%b}'
                ]

        for file_path in self.file_paths:
            media = Media(file_path, self.src_path)
            subdirs = file_path.relative_to(self.src_path).parent
            exif_tags = {}
            for key in ('album', 'camera_make', 'camera_model', 'latitude',
                    'longitude', 'original_name', 'title'):
                exif_tags[key] = media.tags_keys[key]

            exif_data = ExifToolCaching(str(file_path)).asdict()
            loc = GeoLocation()
            metadata = media.get_metadata(loc)
            for item, regex in items.items():
                for mask in masks:
                    matched = re.search(regex, mask)
                    if matched:
                        part = collection.get_part(item, mask[1:-1],
                                metadata, subdirs)
                        # check if part is correct
                        assert isinstance(part, str), file_path
                        if item == 'basename':
                            assert part == file_path.stem, file_path
                        elif item == 'date':
                            assert datetime.strptime(part, mask[1:-1])
                        elif item == 'folder':
                            assert part == subdirs.name, file_path
                        elif item == 'folders':
                            assert part in str(subdirs)
                        elif item == 'ext':
                            assert part == file_path.suffix[1:], file_path
                        elif item == 'name':
                            expected_part = file_path.stem
                            for i, rx in get_date_regex(expected_part):
                                part = re.sub(rx, '', expected_part)
                            assert part == expected_part, file_path
                        elif item == 'custom':
                            assert part == mask[2:-2], file_path
                        elif item in ('city', 'country', 'location', 'state'):
                            pass
                        elif item in exif_tags.keys():
                            f = False
                            for key in exif_tags[item]:
                                if key in exif_data:
                                    f = True
                                    assert part == exif_data[key], file_path
                                    break
                            if f == False:
                                assert part == '', file_path
                        else:
                            assert part == '', file_path


    def test_get_date_taken(self, tmp_path):
        collection = Collection(tmp_path, self.path_format)
        for file_path in self.file_paths:
            exif_data = ExifToolCaching(str(file_path)).asdict()
            media = Media(file_path, self.src_path)
            metadata = media.get_metadata()
            date_taken = media.get_date_taken()

            date_filename = None
            for tag in media.tags_keys['original_name']:
                if tag in exif_data:
                    date_filename = get_date_from_string(exif_data[tag])
                break
            if not date_filename:
                date_filename = get_date_from_string(file_path.name)

            if media.metadata['date_original']:
                assert date_taken == media.metadata['date_original']
            elif date_filename:
                assert date_taken == date_filename
            elif media.metadata['date_created']:
                assert date_taken == media.metadata['date_created']
            elif media.metadata['date_modified']:
                assert date_taken == media.metadata['date_modified']

    def test_sort_files(self, tmp_path):
        collection = Collection(tmp_path, self.path_format, album_from_folder=True)
        loc = GeoLocation()
        summary, has_errors = collection.sort_files([self.src_path], loc)

        # Summary is created and there is no errors
        assert summary, summary
        assert not has_errors, has_errors

        for file_path in tmp_path.glob('**/*'):
            if '.db' not in str(file_path):
                media = Media(file_path, tmp_path, album_from_folder=True)
                media.get_exif_metadata()
                for value in media._get_key_values('album'):
                    assert value != '' or None

        # test with populated dest dir
        randomize_files(tmp_path)
        summary, has_errors = collection.sort_files([self.src_path], loc)

        assert summary, summary
        assert not has_errors, has_errors
        # TODO check if path follow path_format

    def test_sort_files_invalid_db(self, tmp_path):
        collection = Collection(tmp_path, self.path_format)
        loc = GeoLocation()
        randomize_db(tmp_path)
        with pytest.raises(sqlite3.DatabaseError) as e:
            summary, has_errors = collection.sort_files([self.src_path], loc)

    def test_sort_file(self, tmp_path):

        for mode in 'copy', 'move':
            collection = Collection(tmp_path, self.path_format, mode=mode)
            # copy mode
            src_path = Path(self.src_path, 'test_exif', 'photo.png')
            name = 'photo_' + mode + '.png'
            dest_path = Path(tmp_path, name)
            src_checksum = collection.checksum(src_path)
            result_copy = collection.sort_file(src_path, dest_path)
            assert result_copy
            # Ensure files remain the same
            assert collection.checkcomp(dest_path, src_checksum)

            if mode == 'copy':
                assert src_path.exists()
            else:
                assert not src_path.exists()

        # TODO check for conflicts


        # TODO check date

    def test__get_files_in_path(self, tmp_path):
        collection = Collection(tmp_path, self.path_format, exclude='**/*.dng')
        paths = [x for x in collection._get_files_in_path(self.src_path,
            maxlevel=1, glob='**/photo*')]
        assert len(paths) == 6
        for path in paths:
            assert isinstance(path, Path)


# TODO Sort similar images into a directory
#    collection.sort_similar

