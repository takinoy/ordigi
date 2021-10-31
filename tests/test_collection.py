# TODO to be removed later
from datetime import datetime
import shutil
import sqlite3
from pathlib import Path
import re
import pytest
import inquirer

from ordigi import constants
from ordigi.collection import Collection, FPath
from ordigi.exiftool import ExifToolCaching, exiftool_is_running, terminate_exiftool
from ordigi.geolocation import GeoLocation
from ordigi import log
from ordigi.media import Media
from ordigi import utils
from .conftest import randomize_files, randomize_db
from ordigi.summary import Summary


class TestFPath:

    @pytest.fixture(autouse=True)
    def setup_class(cls, sample_files_paths):
        cls.src_path, cls.file_paths = sample_files_paths
        cls.path_format = constants.DEFAULT_PATH + '/' + constants.DEFAULT_NAME
        cls.logger = log.get_logger(level=10)

    def test_get_part(self, tmp_path):
        """
        Test all parts
        """
        fpath = FPath(self.path_format, 4, self.logger)
        # Item to search for:
        items = fpath.get_items()
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
            media = Media(file_path, self.src_path, use_date_filename=True,
                    use_file_dates=True)
            subdirs = file_path.relative_to(self.src_path).parent
            exif_tags = {}
            for key in ('album', 'camera_make', 'camera_model', 'latitude',
                    'longitude', 'original_name', 'title'):
                exif_tags[key] = media.tags_keys[key]

            exif_data = ExifToolCaching(str(file_path)).asdict()
            loc = GeoLocation()
            metadata = media.get_metadata(self.src_path, loc)
            for item, regex in items.items():
                for mask in masks:
                    matched = re.search(regex, mask)
                    if matched:
                        part = fpath.get_part(item, mask[1:-1], metadata)
                        # check if part is correct
                        assert isinstance(part, str), file_path
                        if item == 'basename':
                            assert part == file_path.stem, file_path
                        elif item == 'date':
                            if part == '':
                                media.get_date_media()
                            assert datetime.strptime(part, mask[1:-1])
                        elif item == 'folder':
                            assert part == subdirs.name, file_path
                        elif item == 'folders':
                            assert part in str(subdirs)
                        elif item == 'ext':
                            assert part == file_path.suffix[1:], file_path
                        elif item == 'name':
                            expected_part = file_path.stem
                            for i, rx in utils.get_date_regex(expected_part):
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

    def test_get_early_morning_photos_date(self):
        date = datetime(2021, 10, 16, 2, 20, 40)
        fpath = FPath(self.path_format, 4, self.logger)
        part = fpath.get_early_morning_photos_date(date, '%Y-%m-%d')
        assert part == '2021-10-15'

        part = fpath.get_early_morning_photos_date(date, '%Y%m%d-%H%M%S')
        assert part == '20211016-022040'


class TestCollection:

    @pytest.fixture(autouse=True)
    def setup_class(cls, sample_files_paths):
        cls.src_path, cls.file_paths = sample_files_paths
        cls.path_format = constants.DEFAULT_PATH + '/' + constants.DEFAULT_NAME
        cls.logger = log.get_logger(level=10)

    def teardown_class(self):
        terminate_exiftool()
        assert not exiftool_is_running()

    def assert_import(self, summary, nb):
        # Summary is created and there is no errors
        assert summary.errors == 0
        assert summary.result['import'] == nb

    def assert_sort(self, summary, nb):
        # Summary is created and there is no errors
        assert summary.errors == 0
        assert summary.result['sort'] == nb

    def test_sort_files(self, tmp_path):
        collection = Collection(tmp_path, album_from_folder=True,
                logger=self.logger)
        loc = GeoLocation()
        summary = collection.sort_files([self.src_path],
                self.path_format, loc, import_mode='copy')

        self.assert_import(summary, 30)

        summary = collection.check_files()
        assert summary.result['check'] == 30
        assert not summary.errors

        # check if album value are set
        for file_path in tmp_path.glob('**/*'):
            if '.db' not in str(file_path):
                media = Media(file_path, tmp_path, album_from_folder=True)
                media.get_exif_metadata()
                for value in media._get_key_values('album'):
                    assert value != '' or None

        collection = Collection(tmp_path, album_from_folder=True)
        # Try to change path format and sort files again
        path = '{city}/{%Y}-{name}.%l{ext}'
        summary = collection.sort_files([tmp_path],
                self.path_format, loc)

        self.assert_sort(summary, 24)

        shutil.copytree(tmp_path / 'test_exif', tmp_path / 'test_exif_copy')
        collection.summary = Summary(tmp_path)
        assert sum(collection.summary.result.values()) == 0
        summary = collection.update(loc)
        assert summary.result['update'] == 2
        assert not summary.errors
        collection.summary = Summary(tmp_path)
        summary = collection.update(loc)
        assert not summary.result['update']
        assert not summary.errors

        # test with populated dest dir
        randomize_files(tmp_path)
        summary = collection.check_files()
        assert summary.errors

        # test summary update
        collection.summary = Summary(tmp_path)
        summary = collection.update(loc)
        assert summary.result['update']
        assert not summary.errors

    def test_sort_files_invalid_db(self, tmp_path):
        collection = Collection(tmp_path)
        loc = GeoLocation()
        randomize_db(tmp_path)
        with pytest.raises(sqlite3.DatabaseError) as e:
            summary = collection.sort_files([self.src_path],
                    self.path_format, loc, import_mode='copy')

    def test_sort_file(self, tmp_path):
        for import_mode in 'copy', 'move', False:
            collection = Collection(tmp_path)
            # copy mode
            src_path = Path(self.src_path, 'test_exif', 'photo.png')
            media = Media(src_path, self.src_path)
            metadata = media.get_metadata(tmp_path)
            name = 'photo_' + str(import_mode) + '.png'
            dest_path = Path(tmp_path, name)
            src_checksum = utils.checksum(src_path)
            summary = collection.sort_file(src_path, dest_path, media,
                    import_mode=import_mode)
            assert not summary.errors
            # Ensure files remain the same
            assert collection._checkcomp(dest_path, src_checksum)

            if import_mode == 'copy':
                assert src_path.exists()
            else:
                assert not src_path.exists()
                shutil.copyfile(dest_path, src_path)

    def test__get_files_in_path(self, tmp_path):
        collection = Collection(tmp_path, exclude={'**/*.dng',}, max_deep=1,
                use_date_filename=True, use_file_dates=True)
        paths = [x for x in collection._get_files_in_path(self.src_path,
            glob='**/photo*')]
        assert len(paths) == 6
        for path in paths:
            assert isinstance(path, Path)

    def test_sort_similar_images(self, tmp_path):
        path = tmp_path / 'collection'
        shutil.copytree(self.src_path, path)
        collection = Collection(path, logger=self.logger)
        loc = GeoLocation()
        summary = collection.init(loc)
        summary = collection.sort_similar_images(path, similarity=60)

        # Summary is created and there is no errors
        assert not summary.errors

    @pytest.mark.skip()
    def test_fill_data(self, tmp_path, monkeypatch):
        path = tmp_path / 'collection'
        shutil.copytree(self.src_path, path)
        collection = Collection(path, logger=self.logger)
        # loc = GeoLocation()
        import ipdb; ipdb.set_trace()

#         def mockreturn(prompt, theme):
#             return {'value': '03-12-2021 08:12:35'}

#         monkeypatch.setattr(inquirer, 'prompt', mockreturn)
#         collection.fill_data(path, 'date_original')
#         # check if db value is set
#         import ipdb; ipdb.set_trace()
#         date = collection.db.get_metadata_data('test_exif/invalid.invalid',
#                 'DateOriginal')
#         assert date == '2021-03-12 08:12:35'
        # Check if exif value is set


        collection.fill_data(path, 'date_original', edit=True)
