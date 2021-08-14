"""
Methods for interacting with database files
"""
from builtins import map
from builtins import object

import json
import os
import sys

from math import radians, cos, sqrt
from shutil import copyfile
from time import strftime

from ordigi import constants


class Db(object):

    """A class for interacting with the JSON files  database."""

    def __init__(self, target_dir):

        # Create dir for target database
        dirname = os.path.join(target_dir, '.ordigi')

        if not os.path.exists(dirname):
            try:
                os.makedirs(dirname)
            except OSError:
                pass

        # self.hash_db = constants.hash_db
        self.hash_db_file = os.path.join(dirname, constants.hash_db)
        self.check_db(self.hash_db_file)

        self.hash_db = {}

        # We know from above that this file exists so we open it
        #   for reading only.
        with open(self.hash_db_file, 'r') as f:
            try:
                self.hash_db = json.load(f)
            except ValueError:
                pass

        # self.location_db_file = constants.location_db
        self.location_db_file = os.path.join(dirname, constants.location_db)
        self.check_db(self.location_db_file)

        self.location_db = []

        # We know from above that this file exists so we open it
        #   for reading only.
        with open(self.location_db_file, 'r') as f:
            try:
                self.location_db = json.load(f)
            except ValueError:
                pass

    def check_db(self, db_file):
        '''Load db from file'''
        # If the hash db doesn't exist we create it.
        # Otherwise we only open for reading
        if not os.path.isfile(db_file):
            with open(db_file, 'a'):
                os.utime(db_file, None)

    def add_hash(self, key, value, write=False):
        """Add a hash to the hash db.

        :param str key:
        :param str value:
        :param bool write: If true, write the hash db to disk.
        """
        self.hash_db[key] = value
        if(write is True):
            self.update_hash_db()

    # Location database
    # Currently quite simple just a list of long/lat pairs with a name
    # If it gets many entries a lookup might take too long and a better
    # structure might be needed. Some speed up ideas:
    # - Sort it and inter-half method can be used
    # - Use integer part of long or lat as key to get a lower search list
    # - Cache a small number of lookups, images are likely to be taken in
    #   clusters around a spot during import.
    def add_location(self, latitude, longitude, place, write=False):
        """Add a location to the database.

        :param float latitude: Latitude of the location.
        :param float longitude: Longitude of the location.
        :param str place: Name for the location.
        :param bool write: If true, write the location db to disk.
        """
        data = {}
        data['lat'] = latitude
        data['long'] = longitude
        data['name'] = place
        self.location_db.append(data)
        if(write is True):
            self.update_location_db()

    def backup_hash_db(self):
        """Backs up the hash db."""
        # TODO 
        if os.path.isfile(self.hash_db_file):
            mask = strftime('%Y-%m-%d_%H-%M-%S')
            backup_file_name = '%s-%s' % (self.hash_db_file, mask)
            copyfile(self.hash_db_file, backup_file_name)
            return backup_file_name

    def check_hash(self, key):
        """Check whether a hash is present for the given key.

        :param str key:
        :returns: bool
        """
        return key in self.hash_db

    def get_hash(self, key):
        """Get the hash value for a given key.

        :param str key:
        :returns: str or None
        """
        if(self.check_hash(key) is True):
            return self.hash_db[key]
        return None

    def get_location_name(self, latitude, longitude, threshold_m):
        """Find a name for a location in the database.

        :param float latitude: Latitude of the location.
        :param float longitude: Longitude of the location.
        :param int threshold_m: Location in the database must be this close to
            the given latitude and longitude.
        :returns: str, or None if a matching location couldn't be found.
        """
        last_d = sys.maxsize
        name = None
        for data in self.location_db:
            # As threshold is quite small use simple math
            # From http://stackoverflow.com/questions/15736995/how-can-i-quickly-estimate-the-distance-between-two-latitude-longitude-points  # noqa
            # convert decimal degrees to radians

            lon1, lat1, lon2, lat2 = list(map(
                radians,
                [longitude, latitude, data['long'], data['lat']]
            ))

            r = 6371000  # radius of the earth in m
            x = (lon2 - lon1) * cos(0.5 * (lat2 + lat1))
            y = lat2 - lat1
            d = r * sqrt(x * x + y * y)
            # Use if closer then threshold_km reuse lookup
            if(d <= threshold_m and d < last_d):
                name = data['name']
            last_d = d

        return name

    def get_location_coordinates(self, name):
        """Get the latitude and longitude for a location.

        :param str name: Name of the location.
        :returns: tuple(float), or None if the location wasn't in the database.
        """
        for data in self.location_db:
            if data['name'] == name:
                return (data['lat'], data['long'])

        return None

    def all(self):
        """Generator to get all entries from self.hash_db

        :returns tuple(string)
        """
        for checksum, path in self.hash_db.items():
            yield (checksum, path)

    def reset_hash_db(self):
        self.hash_db = {}

    def update_hash_db(self):
        """Write the hash db to disk."""
        with open(self.hash_db_file, 'w') as f:
            json.dump(self.hash_db, f)

    def update_location_db(self):
        """Write the location db to disk."""
        with open(self.location_db_file, 'w') as f:
            json.dump(self.location_db, f)
