
import pytest
from pathlib import Path
import shutil
import tempfile

from dozo import constants
from dozo.media.media import Media
from dozo.media.audio import Audio
from dozo.media.photo import Photo
from dozo.media.video import Video
from dozo.exiftool import ExifToolCaching

DOZO_PATH = Path(__file__).parent.parent

class TestMetadata:

    def setup_class(cls):
        cls.SRCPATH = tempfile.mkdtemp(prefix='dozo-src')
        filenames = ['invalid.jpg', 'photo.png', 'plain.jpg', 'text.txt', 'withoutextension']
        cls.file_paths = set()
        for filename in filenames:
            source_path = Path(cls.SRCPATH, filename)
            file_path = Path(DOZO_PATH, 'samples', filename)
            shutil.copyfile(file_path, source_path)
            cls.file_paths.add(source_path)
        cls.path_format = constants.default_path + '/' + constants.default_name

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

