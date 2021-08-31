
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
        cls.sqlite.add_file_data('filename', 'ksinslsdosic', 'original_name', 'date_original', 'album', 1)
        cls.sqlite.add_location(24.2, 7.3, 'city', 'state', 'country', 'default')

        yield

        shutil.rmtree(tmp_path)

    def test_init(self):
        assert isinstance(self.sqlite.filename, Path)
        assert isinstance(self.sqlite.con, sqlite3.Connection)
        assert isinstance(self.sqlite.cur, sqlite3.Cursor)

    def test_create_file_table(self):
        assert self.sqlite.is_table('file')

    def test_add_file_data(self):
        result = tuple(self.sqlite.cur.execute("""select * from file where
            rowid=1""").fetchone())
        assert result == ('filename', 'ksinslsdosic', 'original_name', 'date_original', 'album', 1)

    def test_get_checksum(self):
        assert not self.sqlite.get_checksum('checksum')
        assert self.sqlite.get_checksum('filename') == 'ksinslsdosic'

    def test_get_file_data(self):
        assert not self.sqlite.get_file_data('invalid', 'DateOriginal')
        assert self.sqlite.get_file_data('filename', 'Album') == 'album'

    def test_create_location_table(self):
        assert self.sqlite.is_table('location')

    def test_add_location(self):
        result = tuple(self.sqlite.cur.execute("""select * from location where
            rowid=1""").fetchone())
        assert result == (24.2, 7.3, 'city', 'state', 'country', 'default')

    @pytest.mark.skip('TODO')
    def test_get_location_data(self, LocationId, data):
        pass

    @pytest.mark.skip('TODO')
    def test_get_location(self, Latitude, Longitude, column):
        pass

    def test_get_location_nearby(self):
        value = self.sqlite.get_location_nearby(24.2005, 7.3004, 'Default')
        assert value == 'default'

    @pytest.mark.skip('TODO')
    def test_delete_row(self, table, id):
        pass

    @pytest.mark.skip('TODO')
    def test_delete_all_rows(self, table):
        pass

