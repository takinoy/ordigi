# TODO to be removed later
from datetime import datetime
import os
import pytest
from pathlib import Path
import re
import shutil
from sys import platform
import tempfile
from time import sleep

from dozo import constants
from dozo.database import Db
from dozo.filesystem import FileSystem
from dozo.media.media import Media
from dozo.exiftool import ExifToolCaching, exiftool_is_running, terminate_exiftool


DOZO_PATH = Path(__file__).parent.parent


@pytest.mark.skip()
class TestDb:
    pass

class TestFilesystem:
    def setup_class(cls):
        cls.SRCPATH = tempfile.mkdtemp(prefix='dozo-src')
        filenames = ['photo.png', 'plain.jpg', 'text.txt', 'withoutextension',
                'no-exif.jpg']
        cls.FILE_PATHS = set()
        for filename in filenames:
            source_path = Path(cls.SRCPATH, filename)
            file_path = Path(DOZO_PATH, 'samples', filename)
            shutil.copyfile(file_path, source_path)
            cls.FILE_PATHS.add(source_path)
        cls.path_format = constants.default_path + '/' + constants.default_name

    def teardown_class(self):
        terminate_exiftool()
        assert not exiftool_is_running()

    def test_get_part(self):
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

        media = Media()
        exif_tags = {
                'album': media.album_keys,
                'camera_make': media.camera_make_keys,
                'camera_model': media.camera_model_keys,
                # 'date_original': media.date_original,
                # 'date_created': media.date_created,
                # 'date_modified': media.date_modified,
                'latitude': media.latitude_keys,
                'longitude': media.longitude_keys,
                'original_name': [media.original_name_key],
                'title': media.title_keys
                }

        subdirs = Path('a', 'b', 'c', 'd')

        for file_path in self.FILE_PATHS:
            media = Media(str(file_path))
            exif_data = ExifToolCaching(str(file_path)).asdict()
            metadata = media.get_metadata()

            for item, regex in items.items():
                for mask in masks:
                    matched = re.search(regex, mask)
                    if matched:
                        part = filesystem.get_part(item, mask[1:-1], metadata,
                                {}, subdirs)
                        # check if part is correct
                        assert isinstance(part, str)
                        expected_part = ''
                        if item == 'basename':
                            expected_part = file_path.stem
                        elif item == 'date':
                            assert datetime.strptime(part, mask[1:-1])
                            expected_part = part
                        elif item == 'folder':
                            expected_part = subdirs.name
                        elif item == 'folders':
                            if platform == "win32":
                                assert '\\' in part
                            else:
                                assert '/' in part
                            expected_part = part
                        elif item == 'ext':
                            expected_part = file_path.suffix[1:]
                        if item == 'name':
                            expected_part = file_path.stem
                            for i, rx in filesystem.match_date_from_string(expected_part):
                                expected_part = re.sub(rx, '', expected_part)
                        elif item == 'custom':
                            expected_part = mask[2:-2]
                        elif item in ('city', 'country', 'location', 'state'):
                            expected_part = part
                        elif item in exif_tags.keys():
                            f = False
                            for key in exif_tags[item]:
                                if key in exif_data:
                                    f = True
                                    expected_part = exif_data[key]
                                    break
                            if f == False:
                                expected_part = ''

                        assert part == expected_part


    def test_get_date_taken(self):
        filesystem = FileSystem()
        for file_path in self.FILE_PATHS:
            exif_data = ExifToolCaching(str(file_path)).asdict()
            media = Media(str(file_path))
            metadata = media.get_metadata()
            date_taken = filesystem.get_date_taken(metadata)

            dates = {}
            for key, date in ('original', media.date_original), ('created',
                    media.date_created), ('modified', media.date_modified):
                dates[key] = media.get_date_attribute(date)

            if media.original_name_key in exif_data:
                date_filename = filesystem.get_date_from_string(
                        exif_data[media.original_name_key])
            else:
                date_filename = filesystem.get_date_from_string(file_path.name)

            if dates['original']:
                assert date_taken == dates['original']
            elif date_filename:
                assert date_taken == date_filename
            elif dates['created']:
                assert date_taken == dates['created']
            elif dates['modified']:
                assert date_taken == dates['modified']

    def test_sort_files(self, tmp_path):
        db = Db(tmp_path)
        filesystem = FileSystem(path_format=self.path_format)

        summary, has_errors = filesystem.sort_files([self.SRCPATH], tmp_path, db)

        # Summary is created and there is no errors
        assert summary, summary
        assert not has_errors, has_errors

        # TODO check if path follow path_format

    # TODO make another class?
    def test_sort_file(self, tmp_path):

        for mode in 'copy', 'move':
            filesystem = FileSystem(path_format=self.path_format, mode=mode)
            # copy mode
            src_path = Path(self.SRCPATH, 'photo.png')
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
