# TODO to be removed later
from datetime import datetime
import os
import pytest
from pathlib import Path
import re
from sys import platform
from time import sleep

from .conftest import copy_sample_files
from ordigi import constants
from ordigi.database import Db
from ordigi.filesystem import FileSystem
from ordigi.media import Media
from ordigi.exiftool import ExifToolCaching, exiftool_is_running, terminate_exiftool


@pytest.mark.skip()
class TestDb:
    pass

class TestFilesystem:
    def setup_class(cls):
        cls.src_paths, cls.file_paths = copy_sample_files()
        cls.path_format = constants.default_path + '/' + constants.default_name

    def teardown_class(self):
        terminate_exiftool()
        assert not exiftool_is_running()

    def test_get_part(self, tmp_path):
        """
        Test all parts
        """
        # Item to search for:
        filesystem = FileSystem()
        items = filesystem.get_items()
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

        subdirs = Path('a', 'b', 'c', 'd')

        for file_path in self.file_paths:
            media = Media(str(file_path))
            exif_tags = {}
            for key in ('album', 'camera_make', 'camera_model', 'latitude',
                    'longitude', 'original_name', 'title'):
                exif_tags[key] = media.tags_keys[key]

            exif_data = ExifToolCaching(str(file_path)).asdict()
            metadata = media.get_metadata()
            for item, regex in items.items():
                for mask in masks:
                    matched = re.search(regex, mask)
                    if matched:
                        part = filesystem.get_part(item, mask[1:-1],
                                metadata, Db(tmp_path), subdirs)
                        # check if part is correct
                        assert isinstance(part, str), file_path
                        if item == 'basename':
                            assert part == file_path.stem, file_path
                        elif item == 'date':
                            assert datetime.strptime(part, mask[1:-1])
                        elif item == 'folder':
                            assert part == subdirs.name, file_path
                        elif item == 'folders':
                            if platform == "win32":
                                assert '\\' in part, file_path
                            else:
                                assert '/' in part, file_path
                        elif item == 'ext':
                            assert part == file_path.suffix[1:], file_path
                        elif item == 'name':
                            expected_part = file_path.stem
                            for i, rx in filesystem.match_date_from_string(expected_part):
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


    def test_get_date_taken(self):
        filesystem = FileSystem()
        for file_path in self.file_paths:
            exif_data = ExifToolCaching(str(file_path)).asdict()
            media = Media(str(file_path))
            metadata = media.get_metadata()
            date_taken = filesystem.get_date_taken(metadata)

            date_filename = None
            for tag in media.tags_keys['original_name']:
                if tag in exif_data:
                    date_filename = filesystem.get_date_from_string(exif_data[tag])
                break
            if not date_filename:
                date_filename = filesystem.get_date_from_string(file_path.name)

            if media.metadata['date_original']:
                assert date_taken == media.metadata['date_original']
            elif date_filename:
                assert date_taken == date_filename
            elif media.metadata['date_created']:
                assert date_taken == media.metadata['date_created']
            elif media.metadata['date_modified']:
                assert date_taken == media.metadata['date_modified']

    def test_sort_files(self, tmp_path):
        db = Db(tmp_path)
        filesystem = FileSystem(path_format=self.path_format)

        summary, has_errors = filesystem.sort_files([self.src_paths], tmp_path, db)

        # Summary is created and there is no errors
        assert summary, summary
        assert not has_errors, has_errors

        # TODO check if path follow path_format

    # TODO make another class?
    def test_sort_file(self, tmp_path):

        for mode in 'copy', 'move':
            filesystem = FileSystem(path_format=self.path_format, mode=mode)
            # copy mode
            src_path = Path(self.src_paths, 'photo.png')
            dest_path = Path(tmp_path,'photo_copy.png')
            src_checksum = filesystem.checksum(src_path)
            result_copy = filesystem.sort_file(src_path, dest_path)
            assert result_copy
            # Ensure files remain the same
            assert filesystem.checkcomp(dest_path, src_checksum)

            if mode == 'copy':
                assert src_path.exists()
            else:
                assert not src_path.exists()

        # TODO check for conflicts


        # TODO check date

#    filesystem.sort_files
#- Sort similar images into a directory
#    filesystem.sort_similar

