from datetime import datetime
import pytest
from pathlib import Path
import re
import shutil
import tempfile

from .conftest import copy_sample_files
from dozo import constants
from dozo.media.media import Media
from dozo.media.audio import Audio
from dozo.media.photo import Photo
from dozo.media.video import Video
from dozo.exiftool import ExifTool, ExifToolCaching

DOZO_PATH = Path(__file__).parent.parent
CACHING = True

class TestMetadata:

    def setup_class(cls):
        cls.src_paths, cls.file_paths = copy_sample_files()
        cls.ignore_tags = ('EXIF:CreateDate', 'File:FileModifyDate',
                'File:FileAccessDate', 'EXIF:Make', 'Composite:LightValue')

    def get_media(self):
        for file_path in self.file_paths:
            self.exif_data = ExifTool(str(file_path)).asdict()
            yield Media(str(file_path), self.ignore_tags)

    def test_get_metadata(self):
        for media in self.get_media():
            result = media.get_metadata()
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

        # Will be changed to get_metadata
        # check if metatadata type are correct

        # if(isinstance(self.metadata, dict) and update_cache is False):
            # return self.metadata
        # Album for folder implemented other place
