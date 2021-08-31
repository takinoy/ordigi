
import json
import os
from pathlib import Path
import sqlite3
import sys

from shutil import copyfile
from time import strftime

from ordigi import constants
from ordigi.utils import distance_between_two_points


class Sqlite:

    """Methods for interacting with Sqlite database"""

    def __init__(self, target_dir):

        # Create dir for target database
        db_dir = Path(target_dir, '.ordigi')

        if not db_dir.exists():
            try:
                db_dir.mkdir()
            except OSError:
                pass

        self.db_type = 'SQLite format 3'
        self.filename = Path(db_dir, target_dir.name + '.db')
        self.con = sqlite3.connect(self.filename)
        # Allow selecting column by name
        self.con.row_factory = sqlite3.Row
        self.cur = self.con.cursor()

        # Create tables
        if not self.is_table('file'):
            self.create_file_table()
        if not self.is_table('location'):
            self.create_location_table()

    def is_Sqlite3(self, filename):
        import ipdb; ipdb.set_trace()
        if not os.path.isfile(filename):
            return False
        if os.path.getsize(filename) < 100: # SQLite database file header is 100 bytes
            return False

        with open(filename, 'rb') as fd:
            header = fd.read(100)

        return header[:16] == self.db_type + '\x00'

    def is_table(self, table):
        """Check if table exist"""

        try:
            # get the count of tables with the name
            self.cur.execute(f"SELECT count(name) FROM sqlite_master WHERE type='table' AND name='{table}'")
        except sqlite3.DatabaseError as e:
            # raise type(e)(e.message + ' :{self.filename} %s' % arg1)
            raise sqlite3.DatabaseError(f"{self.filename} is not valid database")

        # if the count is 1, then table exists
        if self.cur.fetchone()[0] == 1:
            return True

        return False

    def _run(self, query, n=0):
        result = None
        result = self.cur.execute(query).fetchone()

        if result:
            return result[n]
        else:
            return None

    def _run_many(self, query):
        self.cur.executemany(query, table_list)
        if self.cur.fetchone()[0] != 1:
            return False
        self.con.commit()
        return True

    def create_file_table(self):
        query = """create table file (
            FilePath text not null primary key,
            Checksum text,
            OriginalName text,
            DateOriginal text,
            Album text,
            LocationId integer)
        """
        self.cur.execute(query)

    def add_file_data(self, FilePath, Checksum, OriginalName, DateOriginal,
            Album, LocationId):
        query =f"""insert into file values
            ('{FilePath}', '{Checksum}', '{OriginalName}',
            '{DateOriginal}', '{Album}', '{LocationId}')"""

        self.cur.execute(query)
        self.con.commit()

    def add_file_values(self, table_list):
        query = f"insert into file values (?, ?, ?, ?, ?, ?)"
        return self._run_many(query)

    def get_checksum(self, FilePath):
        query = f"select Checksum from file where FilePath='{FilePath}'"
        return self._run(query)

    def get_file_data(self, FilePath, data):
        query = f"select {data} from file where FilePath='{FilePath}'"
        return self._run(query)

    def create_location_table(self):
        query = """create table location (
            Latitude real not null,
            Longitude real not null,
            City text,
            State text,
            Country text,
            'Default' text)
        """
        self.cur.execute(query)

    def match_location(self, Latitude, Longitude):
        query = f"""select 1 from location where Latitude='{Latitude}'
                and Longitude='{Longitude}'"""
        return self._run(query)

    def add_location(self, Latitude, Longitude, City, State, Country, Default):
        # Check if row with same latitude and longitude have not been already
        # added
        location_id = self.get_location(Latitude, Longitude, 'ROWID')

        if not location_id:
            query = f"""insert into location values
                ('{Latitude}', '{Longitude}', '{City}', '{State}',
                '{Country}', '{Default}')
            """
            self.cur.execute(query)
            self.con.commit()

            return self._run('select last_insert_rowid()')

        return location_id

    def add_location_values(self, table_list):
        query = f"insert into location values (?, ?, ?, ?, ?, ?)"
        return _insert_many_query(query)

    def get_location_data(self, LocationId, data):
        query = f"select {data} from file where ROWID='{LocationId}'"
        return self._run(query)

    def get_location(self, Latitude, Longitude, column):
        query = f"""select {column} from location where Latitude='{Latitude}'
        and Longitude='{Longitude}'"""
        return self._run(query)

    def _get_table(self, table):
        self.cur.execute(f'SELECT * FROM {table}').fetchall()

    def get_location_nearby(self, latitude, longitude, Column,
            threshold_m=3000):
        """Find a name for a location in the database.

        :param float latitude: Latitude of the location.
        :param float longitude: Longitude of the location.
        :param int threshold_m: Location in the database must be this close to
            the given latitude and longitude.
        :returns: str, or None if a matching location couldn't be found.
        """
        shorter_distance = sys.maxsize
        value = None
        self.cur.execute('SELECT * FROM location')
        for row in self.cur:
            distance = distance_between_two_points(latitude, longitude,
                    row[0], row[1])
            # Use if closer then threshold_km reuse lookup
            if(distance < shorter_distance and distance <= threshold_m):
                shorter_distance = distance
                value = row[Column]

        return value

    def delete_row(self, table, id):
        """
        Delete a row by row id in table
        :param table: database table
        :param id: id of the row
        :return:
        """
        sql = f'delete from {table} where id=?'
        self.cur.execute(sql, (id,))
        self.con.commit()

    def delete_all_rows(self, table):
        """
        Delete all row in table
        :param table: database table
        :return:
        """
        sql = f'delete from {table}'
        self.cur.execute(sql)
        self.con.commit()
