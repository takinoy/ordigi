from datetime import datetime
import os
from pathlib import Path
import sqlite3
import sys

from ordigi import LOG
from ordigi.utils import check_dir, distance_between_two_points


class Sqlite:
    """Methods for interacting with Sqlite database"""

    def __init__(self, db_dir):

        self.db_type = 'SQLite format 3'
        self.log = LOG.getChild(self.__class__.__name__)
        self.types = {'text': (str, datetime), 'integer': (int,), 'real': (float,)}

        self.filename = Path(db_dir, 'collection.db')
        self.con = sqlite3.connect(self.filename)
        # Allow selecting column by name
        self.con.row_factory = sqlite3.Row
        self.cur = self.con.cursor()

        metadata_header = {
            'FilePath': 'text not null',
            'Checksum': 'text',
            'Album': 'text',
            'Title': 'text',
            'LocationId': 'integer',
            'DateMedia': 'text',
            'DateOriginal': 'text',
            'DateCreated': 'text',
            'DateModified': 'text',
            'FileModifyDate': 'text',
            'CameraMake': 'text',
            'CameraModel': 'text',
            'OriginalName': 'text',
            'SrcDir': 'text',
            'Subdirs': 'text',
            'Filename': 'text',
        }

        location_header = {
            'Latitude': 'real not null',
            'Longitude': 'real not null',
            'LatitudeRef': 'text',
            'LongitudeRef': 'text',
            'City': 'text',
            'State': 'text',
            'Country': 'text',
            'Location': 'text',
        }

        self.tables = {
            'metadata': {'header': metadata_header},
            'location': {'header': location_header},
        }

        # Create tables
        for table, d in self.tables.items():
            if not self.is_table(table):
                if table == 'metadata':
                    # https://www.quackit.com/sqlite/tutorial/create_a_relationship.cfm
                    self.create_table(
                        table, d['header'],
                        (
                            "unique('FilePath')",
                            "foreign key(LocationId) references location(Id)",
                        ),
                    )
                elif table == 'location':
                    self.create_table(
                        table, d['header'],
                        ("unique('Latitude', 'Longitude')",),
                    )

    def is_Sqlite3(self, filename):
        if not os.path.isfile(filename):
            return False
        if os.path.getsize(filename) < 100:  # SQLite database file header is 100 bytes
            return False

        with open(filename, 'rb') as fd:
            header = fd.read(100)

        return header[:16] == self.db_type + '\x00'

    def is_table(self, table):
        """Check if table exist"""

        try:
            # get the count of tables with the name
            self.cur.execute(
                f"select count(name) from sqlite_master where type='table' and name='{table}'"
            )
        except sqlite3.DatabaseError as e:
            # raise type(e)(e.message + ' :{self.filename} %s' % arg1)
            raise sqlite3.DatabaseError(f"{self.filename} is not valid database")

        # if the count is 1, then table exists
        if self.cur.fetchone()[0] == 1:
            return True

        return False

    def get_rows(self, table):
        """Cycle through rows in table
        :params: str
        :return: iter
        """
        self.cur.execute(f'select * from {table}')
        for row in self.cur:
            yield row

    def is_empty(self, table):
        if [x for x in self.get_rows(table)] == []:
            return True

        return False

    def _run(self, query, n=0):
        self.log.debug(f"Sqlite run '{query}'")

        try:
            result = self.cur.execute(query).fetchone()
        except sqlite3.DatabaseError as e:
            self.log.error(e)
            result = False

        if result:
            if n < 0:
                return result
            else:
                return result[n]
        else:
            return False

    def _run_many(self, query, table_list):
        self.cur.executemany(query, table_list)
        if self.cur.fetchone()[0] != 1:
            return False
        self.con.commit()
        return True

    def create_table(self, table, header, statements=None):
        """
        :params: row data (dict), primary_key (tuple)
        :returns: bool
        """
        fieldset = []
        fieldset.append("Id integer primary key autoincrement")
        for col, definition in header.items():
            fieldset.append(f"{col} {definition}")
        # https://stackoverflow.com/questions/11719073/sqlite-insert-or-update-without-changing-rowid-value
        if statements:
            for statement in statements:
                fieldset.append(statement)

        if len(fieldset) > 0:
            query = "create table {0} ({1})".format(table, ", ".join(fieldset))
            self.cur.execute(query)
            self.tables[table]['header'] = header
            return True

        return False

    def check_row(self, table, row_data):
        header = self.tables[table]['header']
        if len(row_data) != len(header):
            raise ValueError(
                f"""Table {table} length mismatch: row_data
            {row_data}, header {header}"""
            )

        columns = ', '.join(row_data.keys())
        placeholders = ', '.join('?' * len(row_data))

        return columns, placeholders

    def update_query(self, table, row_id, columns, placeholders):
        """
        :returns: query (str)
        """
        return f"""replace into {table} (Id, {columns})
        values ((select id from {table} where id={row_id}), {placeholders})"""

    def insert_query(self, table, columns, placeholders):
        """
        :returns: query (str)
        """
        return f"insert into {table} ({columns}) values ({placeholders})"

    def upsert_row(self, table, row_data, columns, placeholders, row_id=None):
        """
        :returns: lastrowid (int)
        https://www.sqlitetutorial.net/sqlite-replace-statement/
        https://www.sqlite.org/lang_UPSERT.html
        """
        if row_id:
            query = self.update_query(table, row_id, columns, placeholders)
        else:
            query = self.insert_query(table, columns, placeholders)

        values = []
        for key, value in row_data.items():
            if isinstance(value, bool):
                values.append(int(value))
            else:
                values.append(value)

        self.cur.execute(query, values)
        self.con.commit()

        return self.cur.lastrowid

    def upsert_location(self, row_data):
        # Check if row already exist
        row_id = self.get_location(row_data['Latitude'], row_data['Longitude'], 'Id')
        columns, placeholders = self.check_row('location', row_data)

        return self.upsert_row('location', row_data, columns, placeholders, row_id)

    def upsert_metadata(self, row_data):
        # Check if row already exist
        row_id = self.get_metadata(row_data['FilePath'], 'Id')
        columns, placeholders = self.check_row('metadata', row_data)

        return self.upsert_row('metadata', row_data, columns, placeholders, row_id)

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

    def build_table(self, table, row_data, statements=None):
        header = self.get_header(row_data)
        return self.create_table(table, header, statements=None)

    def check_table(self, table, row_data):
        """
        :params: row data (dict), primary_key (tuple)
        :returns: bool
        """
        if not self.tables[table]['header']:
            self.log.error(f"Table {table} do not exist")
            return False

        return True

    def escape_quote(self, string):
        return string.translate(str.maketrans({"'":  r"''"}))

    def get_checksum(self, file_path):
        file_path_e = self.escape_quote(str(file_path))
        query = f"select Checksum from metadata where FilePath='{file_path_e}'"
        return self._run(query)

    def get_metadata(self, file_path, column):
        file_path_e = self.escape_quote(str(file_path))
        query = f"select {column} from metadata where FilePath='{file_path_e}'"
        return self._run(query)

    def get_filepath(self, column, value, n=0):
        query = f"select FilePath from metadata where {column}='{value}'"
        return self._run(query, n)

    def match_location(self, latitude, longitude):
        query = f"""select 1 from location where Latitude='{latitude}'
                and Longitude='{longitude}'"""
        return self._run(query)

    def get_location_data(self, location_id, data):
        query = f"select {data} from location where Id='{location_id}'"
        return self._run(query)

    def get_location(self, latitude, longitude, column):
        query = f"""select {column} from location where Latitude='{latitude}'
        and Longitude='{longitude}'"""
        return self._run(query)

    def _get_table(self, table):
        self.cur.execute(f'SELECT * FROM {table}').fetchall()

    def get_location_nearby(self, latitude, longitude, Column, threshold_m=3000):
        """
        Find a name for a location in the database.
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
            distance = distance_between_two_points(
                latitude, longitude, row['Latitude'], row['Longitude']
            )
            # Use if closer then threshold_km reuse lookup
            if distance < shorter_distance and distance <= threshold_m:
                shorter_distance = distance
                value = row[Column]

        return value

    def delete_row(self, table, column, value):
        """
        Delete a row by row id in table
        :param table: database table
        :param id: id of the row
        :return:
        """
        sql = f'delete from {table} where {column}=?'
        self.cur.execute(sql, (value,))
        self.con.commit()

    def delete_filepath(self, value):
        self.delete_row('metadata', 'FilePath', value)

    def delete_all_rows(self, table):
        """
        Delete all row in table
        :param table: database table
        :return:
        """
        sql = f'delete from {table}'
        self.cur.execute(sql)
        self.con.commit()

    def len(self, table):
        sql = f'select count() from {table}'
        return self._run(sql)

