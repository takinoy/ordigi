from datetime import datetime
import shutil
import sqlite3
from pathlib import Path
import re
import pytest
import inquirer

from ordigi import LOG
from ordigi import constants
from ordigi.collection import Collection, FPath, Paths
from ordigi.exiftool import ExifTool, ExifToolCaching, exiftool_is_running, terminate_exiftool
from ordigi.geolocation import GeoLocation
from ordigi.media import Media, ReadExif
from ordigi import utils
from .conftest import randomize_files, randomize_db
from ordigi.summary import Summary

LOG.setLevel(10)

class TestFPath:

    @pytest.fixture(autouse=True)
    def setup_class(cls, sample_files_paths):
        cls.src_path, cls.file_paths = sample_files_paths
        cls.path_format = constants.DEFAULT_PATH + '/' + constants.DEFAULT_NAME

    def test_get_part(self, tmp_path):
        """
        Test all parts
        """
        fpath = FPath(self.path_format, 4)
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
            media.get_metadata(self.src_path, loc)
            for item, regex in items.items():
                for mask in masks:
                    matched = re.search(regex, mask)
                    if matched:
                        part = fpath.get_part(item, mask[1:-1], media.metadata)
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
                            for rx in utils.get_date_regex().values():
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
        fpath = FPath(self.path_format, 4)
        part = fpath.get_early_morning_photos_date(date, '%Y-%m-%d')
        assert part == '2021-10-15'

        part = fpath.get_early_morning_photos_date(date, '%Y%m%d-%H%M%S')
        assert part == '20211016-022040'


class TestCollection:

    @pytest.fixture(autouse=True)
    def setup_class(cls, sample_files_paths):
        cls.src_path, cls.file_paths = sample_files_paths
        cls.path_format = constants.DEFAULT_PATH + '/' + constants.DEFAULT_NAME

    def teardown_class(self):
        terminate_exiftool()
        assert not exiftool_is_running()

    def assert_import(self, summary, nb):
        # Summary is created and there is no errors
        assert summary.errors == 0
        assert summary.success_table.sum('import') == nb

    def assert_sort(self, summary, nb):
        # Summary is created and there is no errors
        assert summary.errors == 0
        assert summary.success_table.sum('sort') == nb

    def test_sort_files(self, tmp_path):
        cli_options = {'album_from_folder': True, 'cache': False}
        collection = Collection(tmp_path, cli_options=cli_options)
        loc = GeoLocation()
        summary = collection.sort_files([self.src_path],
                self.path_format, loc, imp='copy')

        self.assert_import(summary, 29)

        summary = collection.check_files()
        assert summary.success_table.sum('import') == 29
        assert summary.success_table.sum('update') == 0
        assert not summary.errors

        # check if album value are set
        filters = {
            'exclude': None,
            'extensions': None,
            'glob': '**/*',
            'max_deep': None,
        }
        paths = Paths(filters).get_files(tmp_path)
        for file_path in paths:
            if '.db' not in str(file_path):
                for value in ReadExif(file_path).get_key_values('album'):
                    assert value != '' or None

        collection = Collection(tmp_path, cli_options=cli_options)
        # Try to change path format and sort files again
        path_format = 'test_exif/{city}/{%Y}-{name}.%l{ext}'
        summary = collection.sort_files([tmp_path], path_format, loc)

        self.assert_sort(summary, 27)

        shutil.copytree(tmp_path / 'test_exif', tmp_path / 'test_exif_copy')
        collection.summary = Summary(tmp_path)
        assert collection.summary.success_table.sum() == 0
        summary = collection.update(loc)
        assert summary.success_table.sum('update') == 29
        assert summary.success_table.sum() == 29
        assert not summary.errors
        collection.summary = Summary(tmp_path)
        summary = collection.update(loc)
        assert summary.success_table.sum() == 0
        assert not summary.errors

        # test with populated dest dir
        randomize_files(tmp_path)
        summary = collection.check_files()
        assert summary.errors

        # test summary update
        collection.summary = Summary(tmp_path)
        summary = collection.update(loc)
        assert summary.success_table.sum('sort') == 0
        assert summary.success_table.sum('update')
        assert not summary.errors

    def test_sort_files_invalid_db(self, tmp_path):
        collection = Collection(tmp_path)
        loc = GeoLocation()
        randomize_db(tmp_path)
        with pytest.raises(sqlite3.DatabaseError) as e:
            summary = collection.sort_files([self.src_path],
                    self.path_format, loc, imp='copy')

    def test_sort_file(self, tmp_path):
        for imp in ('copy', 'move', False):
            collection = Collection(tmp_path)
            # copy mode
            src_path = Path(self.src_path, 'test_exif', 'photo.png')
            media = Media(src_path, self.src_path)
            media.get_metadata(tmp_path)
            name = 'photo_' + str(imp) + '.png'
            media.metadata['file_path'] = name
            dest_path = Path(tmp_path, name)
            src_checksum = utils.checksum(src_path)
            summary = collection.sort_file(
                src_path, dest_path, media.metadata, imp=imp
            )
            assert not summary.errors
            # Ensure files remain the same
            assert collection._checkcomp(dest_path, src_checksum)

            if imp == 'copy':
                assert src_path.exists()
            else:
                assert not src_path.exists()
                shutil.copyfile(dest_path, src_path)

    def test_get_files(self):
        filters = {
            'exclude': {'**/*.dng',},
            'extensions': None,
            'glob': '**/*',
            'max_deep': 1,
        }
        paths = Paths(filters)
        paths = list(paths.get_files(self.src_path))
        assert len(paths) == 9
        assert Path(self.src_path, 'test_exif/photo.dng') not in paths
        for path in paths:
            assert isinstance(path, Path)

    def test_sort_similar_images(self, tmp_path):
        path = tmp_path / 'collection'
        shutil.copytree(self.src_path, path)
        collection = Collection(path)
        loc = GeoLocation()
        summary = collection.init(loc)
        summary = collection.sort_similar_images(path, similarity=60)

        # Summary is created and there is no errors
        assert not summary.errors

    def test_edit_metadata(self, tmp_path, monkeypatch):
        path = tmp_path / 'collection'
        shutil.copytree(self.src_path, path)
        collection = Collection(path, {'cache': False})
        # loc = GeoLocation()

        def mockreturn(prompt, theme):
            return {'value': '03-12-2021 08:12:35'}

        monkeypatch.setattr(inquirer, 'prompt', mockreturn)

        collection.edit_metadata({path}, {'date_original'}, overwrite=True)
        # check if db value is set
        date = collection.db.sqlite.get_metadata_data('test_exif/photo.rw2',
            'DateOriginal')
        assert date == '2021-03-12 08:12:35'
        # Check if exif value is set
        file_path = path.joinpath('test_exif/photo.rw2')
        date = ExifTool(file_path).asdict()['EXIF:DateTimeOriginal']
        assert date == '2021-03-12 08:12:35'
