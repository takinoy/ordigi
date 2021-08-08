
import pytest
from pathlib import Path
import shutil
import tempfile

from .conftest import copy_sample_files
from dozo import constants
from dozo.media.media import Media
from dozo.media.audio import Audio
from dozo.media.photo import Photo
from dozo.media.video import Video
from dozo.exiftool import ExifToolCaching

DOZO_PATH = Path(__file__).parent.parent

class TestMetadata:

    def setup_class(cls):
        cls.src_paths, cls.file_paths = copy_sample_files()

    def test_get_exiftool_attribute(self, tmp_path):
        for file_path in self.file_paths:
            exif_data = ExifToolCaching(str(file_path)).asdict()
            ignore_tags = ('File:FileModifyDate', 'File:FileAccessDate')
            exif_data_filtered = {}
            for key in exif_data:
                if key not in ignore_tags:
                    exif_data_filtered[key] = exif_data[key]
            media = Media(str(file_path), ignore_tags)
            exif = media.get_exiftool_attributes()
            # Ensure returned value is a dictionary
            assert isinstance(exif, dict)
            for tag in ignore_tags:
                assert tag not in exif
            assert exif == exif_data_filtered

