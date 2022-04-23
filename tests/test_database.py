
from datetime import datetime
from pathlib import Path
import pytest
import shutil
import sqlite3

from ordigi.database import Sqlite

class TestSqlite:

    @pytest.fixture(autouse=True)
    def setup_class(cls, tmp_path):
        cls.test='abs'
        cls.sqlite = Sqlite(tmp_path)

        row_data = {
            'FilePath': 'file_path',
            'Checksum': 'checksum',
            'Album': 'album',
            'Title': 'title',
            'LocationId': 2,
            'DateMedia': datetime(2012, 3, 27),
            'DateOriginal': datetime(2013, 3, 27),
            'DateCreated': 'date_created',
            'DateModified': 'date_modified',
            'FileModifyDate': 'file_modify_date',
            'CameraMake': 'camera_make',
            'CameraModel': 'camera_model',
            'OriginalName':'original_name',
            'SrcPath': 'src_path',
            'Subdirs': 'subdirs',
            'Filename': 'filename'
        }

        location_data = {
            'Latitude': 24.2,
            'Longitude': 7.3,
            'LatitudeRef': 'latitude_ref',
            'LongitudeRef': 'longitude_ref',
            'City': 'city',
            'State': 'state',
            'Country': 'country',
            'Location': 'location'
        }

        cls.sqlite.add_row('metadata', row_data)
        cls.sqlite.add_row('location', location_data)
        # cls.sqlite.add_metadata_data('filename', 'ksinslsdosic', 'original_name', 'date_original', 'album', 1)
        # cls.sqlite.add_location(24.2, 7.3, 'city', 'state', 'country', 'location')

        yield

        shutil.rmtree(tmp_path)

    def test_init(self):
        assert isinstance(self.sqlite.filename, Path)
        assert isinstance(self.sqlite.con, sqlite3.Connection)
        assert isinstance(self.sqlite.cur, sqlite3.Cursor)

    def test_create_table(self):
        assert self.sqlite.is_table('metadata')
        assert self.sqlite.is_table('location')

    def test_add_metadata_data(self):
        result = tuple(self.sqlite.cur.execute("""select * from metadata where
            rowid=1""").fetchone())
        assert result == (
            'file_path',
            'checksum',
            'album',
            'title',
            2,
            '2012-03-27 00:00:00',
            '2013-03-27 00:00:00',
            'date_created',
            'date_modified',
            'file_modify_date',
            'camera_make',
            'camera_model',
            'original_name',
            'src_path',
            'subdirs',
            'filename'
        )

    def test_get_checksum(self):
        assert not self.sqlite.get_checksum('invalid')
        assert self.sqlite.get_checksum('file_path') == 'checksum'

    def test_get_metadata(self):
        assert not self.sqlite.get_metadata('invalid', 'DateOriginal')
        assert self.sqlite.get_metadata('file_path', 'Album') == 'album'

    def test_add_location(self):
        result = tuple(self.sqlite.cur.execute("""select * from location where
            rowid=1""").fetchone())
        assert result == (
            24.2, 7.3,
            'latitude_ref',
            'longitude_ref',
            'city',
            'state',
            'country',
            'location',
        )

    @pytest.mark.skip('TODO')
    def test_get_location_data(self, LocationId, data):
        pass

    @pytest.mark.skip('TODO')
    def test_get_location(self, Latitude, Longitude, column):
        pass

    def test_get_location_nearby(self):
        value = self.sqlite.get_location_nearby(24.2005, 7.3004, 'Location')
        assert value == 'location'

    @pytest.mark.skip('TODO')
    def test_delete_row(self, table, id):
        pass

    @pytest.mark.skip('TODO')
    def test_delete_all_rows(self, table):
        pass

