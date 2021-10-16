from datetime import datetime
import os
import pytest
from pathlib import Path
import re
import shutil
import tempfile

from ordigi import constants
from ordigi.media import Media
from ordigi.exiftool import ExifTool, ExifToolCaching
from ordigi.utils import get_date_from_string

ORDIGI_PATH = Path(__file__).parent.parent
CACHING = True

class TestMetadata:

    @pytest.fixture(autouse=True)
    def setup_class(cls, sample_files_paths):
        cls.src_path, cls.file_paths = sample_files_paths
        cls.ignore_tags = ('EXIF:CreateDate', 'File:FileModifyDate',
                'File:FileAccessDate', 'EXIF:Make', 'Composite:LightValue')

    def get_media(self):
        for file_path in self.file_paths:
            self.exif_data = ExifTool(file_path).asdict()
            yield file_path, Media(file_path, self.src_path, album_from_folder=True, ignore_tags=self.ignore_tags)

    def test_get_metadata(self, tmp_path):
        for file_path, media in self.get_media():
            # test get metadata from cache or exif
            for root in self.src_path, tmp_path:
                result = media.get_metadata(root)
                assert result
                assert isinstance(media.metadata, dict), media.metadata
                #check if all tags key are present
                for tags_key, tags in media.tags_keys.items():
                    assert tags_key in media.metadata
                    for tag in tags:
                        for tag_regex in self.ignore_tags:
                            assert not re.match(tag_regex, tag)
                # Check for valid type
                for key, value in media.metadata.items():
                    if value or value == '':
                        if 'date' in key:
                            assert isinstance(value, datetime)
                        elif key in ('latitude', 'longitude'):
                            assert isinstance(value, float)
                        else:
                            assert isinstance(value, str)
                    else:
                        assert value is None

                    if key == 'album':
                        for album in  media._get_key_values('album'):
                            if album is not None and album != '':
                                assert value == album
                                break
                        else:
                            assert value == file_path.parent.name

                # Check if has_exif_data() is True if 'date_original' key is
                # present, else check if it's false
                has_exif_data = False
                for tag in media.tags_keys['date_original']:
                    if tag in media.exif_metadata:
                        if media.get_date_format(media.exif_metadata[tag]):
                            has_exif_data = True
                            assert media.has_exif_data()
                            break
                if has_exif_data == False:
                    assert not media.has_exif_data()

    def test_get_date_media(self):
        for file_path in self.file_paths:
            exif_data = ExifToolCaching(str(file_path)).asdict()
            media = Media(file_path, self.src_path, use_date_filename=True,
                    use_file_dates=True)
            metadata = media.get_metadata(self.src_path)
            date_media = media.get_date_media()

            date_filename = None
            for tag in media.tags_keys['original_name']:
                if tag in exif_data:
                    date_filename = get_date_from_string(exif_data[tag])
                break
            if not date_filename:
                date_filename = get_date_from_string(file_path.name)

            if media.metadata['date_original']:
                assert date_media == media.metadata['date_original']
            elif date_filename:
                assert date_media == date_filename
            elif media.metadata['date_created']:
                assert date_media == media.metadata['date_created']
            elif media.metadata['date_modified']:
                assert date_media == media.metadata['date_modified']

        # Will be changed to get_metadata
        # check if metatadata type are correct

        # if(isinstance(self.metadata, dict) and update_cache is False):
            # return self.metadata
        # Album for folder implemented other place
