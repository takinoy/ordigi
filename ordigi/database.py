
from datetime import datetime
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
        self.types = {
            'text': (str, datetime),
            'integer': (int,),
            'real': (float,)
            }

        self.filename = Path(db_dir, target_dir.name + '.db')
        self.con = sqlite3.connect(self.filename)
        # Allow selecting column by name
        self.con.row_factory = sqlite3.Row
        self.cur = self.con.cursor()

        metadata_header = {
            'FilePath': 'text not null',
            'Checksum': 'text',
            'Album': 'text',
            'LocationId': 'integer',
            'DateTaken': 'text',
            'DateOriginal': 'text',
            'DateCreated': 'text',
            'DateModified': 'text',
            'CameraMake': 'text',
            'CameraModel': 'text',
            'SrcPath': 'text',
            'Subdirs': 'text',
            'Filename': 'text'
        }

        location_header = {
            'Latitude': 'real not null',
            'Longitude': 'real not null',
            'LatitudeRef': 'text',
            'LongitudeRef': 'text',
            'City': 'text',
            'State': 'text',
            'Country': 'text',
            'Default': 'text'
        }

        self.tables = {
            'metadata': {
                'header': metadata_header,
                'primary_keys': ('FilePath',)
            },
            'location': {
                'header': location_header,
                'primary_keys': ('Latitude', 'Longitude')
            }
        }

        self.primary_metadata_keys = self.tables['metadata']['primary_keys']
        self.primary_location_keys = self.tables['location']['primary_keys']
        # Create tables
        for table, d in self.tables.items():
            if not self.is_table(table):
                self.create_table(table, d['header'], d['primary_keys'])

    def is_Sqlite3(self, filename):
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
            self.cur.execute(f"select count(name) from sqlite_master where type='table' and name='{table}'")
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

    def create_table(self, table, header, primary_keys):
        """
        :params: row data (dict), primary_key (tuple)
        :returns: bool
        """
        fieldset = []
        for col, definition in header.items():
            fieldset.append(f"'{col}' {definition}")
        items = ', '.join(primary_keys)
        fieldset.append(f"primary key ({items})")

        if len(fieldset) > 0:
            query = "create table {0} ({1})".format(table, ", ".join(fieldset))
            self.cur.execute(query)
            self.tables[table]['header'] = header
            return True

        return False

    def add_row(self, table, row_data):
        """
        :returns: lastrowid (int)
        """
        header = self.tables[table]['header']
        if len(row_data) != len(header):
            raise ValueError(f'''Table {table} length mismatch: row_data
            {row_data}, header {header}''')

        columns = ', '.join(row_data.keys())
        placeholders = ', '.join('?' * len(row_data))
        # If duplicate primary keys, row is replaced(updated) with new value
        query = f'replace into {table} values ({placeholders})'
        values = []
        for key, value in row_data.items():
            if key in self.tables[table]['primary_keys'] and value is None:
                # Ignore entry is primary key is None
                return None

            if isinstance(value, bool):
                values.append(int(value))
            else:
                values.append(value)

        self.cur.execute(query, values)
        self.con.commit()

        return self.cur.lastrowid

    def get_header(self, row_data):
        """
        :params: row data (dict)
        :returns: header
        """

        sql_table = {}
        for key, value in row_data.items():
            for sql_type, t in self.types.items():
                # Find corresponding sql_type from python type
                if type(value) in t:
                    sql_table[key] = sql_type

        return sql_table

    def build_table(self, table, row_data, primary_keys):
        header = self.get_header(row_data)
        create_table(table, row_data, primary_keys)

    def build_row(self, table, row_data):
        """
        :params: row data (dict), primary_key (tuple)
        :returns: bool
        """
        if not self.tables[table]['header']:
            result = self.build_table(table, row_data,
                    self.tables[table]['primary_keys'])
            if not result:
                return False

        return self.add_row(table, row_data)

    def get_checksum(self, FilePath):
        query = f"select Checksum from metadata where FilePath='{FilePath}'"
        return self._run(query)

    def get_metadata_data(self, FilePath, data):
        query = f"select {data} from metadata where FilePath='{FilePath}'"
        return self._run(query)

    def match_location(self, Latitude, Longitude):
        query = f"""select 1 from location where Latitude='{Latitude}'
                and Longitude='{Longitude}'"""
        return self._run(query)

    def get_location_data(self, LocationId, data):
        query = f"select {data} from location where ROWID='{LocationId}'"
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
